import Foundation
import Security

enum IDFMError: LocalizedError {
    case missingKey
    case rejectedKey
    case unavailable(String)
    case badData

    var errorDescription: String? {
        switch self {
        case .missingKey: return "Enregistre d'abord ta clé API PRIM dans Shortcut Bridge."
        case .rejectedKey: return "Clé API refusée par Île-de-France Mobilités."
        case .unavailable(let message): return message
        case .badData: return "Réponse inattendue de l'API PRIM."
        }
    }
}

enum APIKeyStore {
    private static let service = "com.nathandave.shortcutbridge.prim"
    private static let account = "api-key"

    static func read() -> String? {
        let q: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        var result: CFTypeRef?
        guard SecItemCopyMatching(q as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    static func save(_ value: String) throws {
        let value = value.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !value.isEmpty else { throw IDFMError.missingKey }
        let q: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account
        ]
        SecItemDelete(q as CFDictionary)
        var a = q
        a[kSecValueData as String] = Data(value.utf8)
        a[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        let status = SecItemAdd(a as CFDictionary, nil)
        guard status == errSecSuccess else {
            throw IDFMError.unavailable("Impossible de stocker la clé dans le trousseau iOS (code \(status)).")
        }
    }
}

struct IDFMStop: Identifiable, Hashable {
    let id: String
    let name: String
}

struct IDFMDeparture: Identifiable {
    let id: UUID = UUID()
    let line: String
    let destination: String
    let clock: String
    let minutes: Int?
    let isRealtime: Bool

    var display: String {
        let waiting = minutes.map { "\($0) min" } ?? clock
        return "\(line) → \(destination) : \(waiting) (\(isRealtime ? "temps réel" : "horaire théorique"))"
    }
}

enum IDFMService {
    static let root = "https://prim.iledefrance-mobilites.fr/marketplace/v2/navitia"

    private static func query(_ path: String, _ parameters: [URLQueryItem], key: String) async throws -> [String: Any] {
        guard !key.isEmpty else { throw IDFMError.missingKey }
        var components = URLComponents(string: root + "/" + path)!
        components.queryItems = parameters
        guard let url = components.url else { throw IDFMError.badData }
        var request = URLRequest(url: url, timeoutInterval: 20)
        request.setValue(key, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        let (data, response) = try await URLSession.shared.data(for: request)
        if let http = response as? HTTPURLResponse {
            if http.statusCode == 401 || http.statusCode == 403 { throw IDFMError.rejectedKey }
            guard (200...299).contains(http.statusCode) else {
                throw IDFMError.unavailable("Erreur PRIM : HTTP \(http.statusCode).")
            }
        }
        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw IDFMError.badData
        }
        return json
    }

    static func testKey(_ key: String) async throws {
        let result = try await query("places", [
            URLQueryItem(name: "q", value: "Gare de Lyon"),
            URLQueryItem(name: "count", value: "1")
        ], key: key)
        guard result["places"] is [Any] else {
            throw IDFMError.unavailable("La clé n'a pas pu être confirmée par PRIM.")
        }
    }

    private static func parseStops(_ values: [[String: Any]]) -> [IDFMStop] {
        var ids = Set<String>()
        return values.compactMap { entry in
            let area = entry["stop_area"] as? [String: Any] ?? entry
            guard let id = area["id"] as? String,
                  let name = area["name"] as? String,
                  !id.isEmpty, ids.insert(id).inserted else { return nil }
            return IDFMStop(id: id, name: name)
        }
    }

    static func findStops(named term: String, key: String) async throws -> [IDFMStop] {
        let json = try await query("places", [
            URLQueryItem(name: "q", value: term),
            URLQueryItem(name: "count", value: "30"),
            URLQueryItem(name: "type[]", value: "stop_area")
        ], key: key)
        return parseStops(json["places"] as? [[String: Any]] ?? [])
    }

    static func nearbyStops(latitude: Double, longitude: Double, key: String) async throws -> [IDFMStop] {
        let path = "coords/\(longitude);\(latitude)/places_nearby"
        let json = try await query(path, [
            URLQueryItem(name: "distance", value: "900"),
            URLQueryItem(name: "count", value: "35"),
            URLQueryItem(name: "type[]", value: "stop_area")
        ], key: key)
        return parseStops(json["places_nearby"] as? [[String: Any]] ?? [])
    }

    static func departures(stop: IDFMStop, line: String, key: String) async throws -> [IDFMDeparture] {
        guard let safeID = stop.id.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) else {
            throw IDFMError.badData
        }
        let json = try await query("stop_areas/\(safeID)/departures", [
            URLQueryItem(name: "count", value: "100")
        ], key: key)
        let records = json["departures"] as? [[String: Any]] ?? []
        let fmt = DateFormatter()
        fmt.locale = Locale(identifier: "en_US_POSIX")
        fmt.timeZone = TimeZone(identifier: "Europe/Paris")
        fmt.dateFormat = "yyyyMMdd'T'HHmmss"
        let clock = DateFormatter()
        clock.timeZone = TimeZone(identifier: "Europe/Paris")
        clock.dateFormat = "HH:mm"

        return records.compactMap { item in
            let display = item["display_informations"] as? [String: Any] ?? [:]
            let code = display["code"] as? String ?? ""
            if !line.trimmingCharacters(in: .whitespaces).isEmpty,
               code.localizedCaseInsensitiveCompare(line.trimmingCharacters(in: .whitespaces)) != .orderedSame {
                return nil
            }
            let stopDateTime = item["stop_date_time"] as? [String: Any] ?? [:]
            let raw = stopDateTime["departure_date_time"] as? String ?? ""
            guard let date = fmt.date(from: raw), date > Date().addingTimeInterval(-60) else { return nil }
            let minutes = max(0, Int(ceil(date.timeIntervalSinceNow / 60)))
            let freshness = stopDateTime["data_freshness"] as? String
            return IDFMDeparture(line: code, destination: display["direction"] as? String ?? "Destination inconnue",
                                 clock: clock.string(from: date), minutes: minutes,
                                 isRealtime: freshness == "realtime")
        }.sorted { ($0.minutes ?? 999999) < ($1.minutes ?? 999999) }
    }

    static func searchLine(_ line: String, stopName: String, key: String) async throws -> String {
        let options = try await findStops(named: stopName, key: key)
        guard !options.isEmpty else {
            return "Aucun arrêt trouvé pour « \(stopName) »."
        }
        // Plusieurs arrêts peuvent avoir le même nom. Chercher le premier avec cette ligne.
        for stop in options.prefix(12) {
            let departures = try await departures(stop: stop, line: line, key: key)
            if !departures.isEmpty {
                return (["🚏 \(stop.name)"] + departures.prefix(5).map(\.display)).joined(separator: "\n")
            }
        }
        return "Aucun passage disponible pour la ligne \(line) dans les arrêts trouvés à « \(stopName) »."
    }
}
