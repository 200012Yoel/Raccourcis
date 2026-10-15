import SwiftUI
import CoreLocation
import UniformTypeIdentifiers

@MainActor
final class PhoneLocation: NSObject, ObservableObject, CLLocationManagerDelegate {
    @Published var coordinate: CLLocationCoordinate2D?
    @Published var errorMessage = ""
    private let manager = CLLocationManager()

    override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyHundredMeters
    }

    func request() {
        errorMessage = ""
        manager.requestWhenInUseAuthorization()
        manager.requestLocation()
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        coordinate = locations.last?.coordinate
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        errorMessage = "Localisation indisponible : \(error.localizedDescription)"
    }
}

struct HomeView: View {
    @StateObject private var location = PhoneLocation()

    @State private var apiKey = APIKeyStore.read() ?? ""
    @State private var apiMessage = APIKeyStore.read() == nil ? "Aucune clé configurée." : "Une clé est enregistrée sur cet iPhone."
    @State private var line = "20"
    @State private var stopName = "Place des Fêtes"
    @State private var mode = "Bus"
    @State private var isBusy = false
    @State private var status = ""
    @State private var stops: [IDFMStop] = []
    @State private var selectedStopID = ""
    @State private var passages: [IDFMDeparture] = []
    @State private var importFile = false
    @State private var importedFileName = ""
    @State private var importedActions: [String] = []
    @State private var importMessage = ""
    @State private var readyToPaste = false

    private let modes = ["Métro", "Tram", "Bus", "Bus de banlieue", "RER", "Transilien"]

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Label("Shortcut Bridge", systemImage: "arrow.triangle.branch")
                        .font(.headline)
                    Text("Actions natives dans Raccourcis, sans jailbreak.")
                        .foregroundStyle(.secondary)
                }

                Section("1. Ma clé Île-de-France Mobilités") {
                    SecureField("Clé API PRIM", text: $apiKey)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    Button(isBusy ? "Vérification..." : "Tester et enregistrer") {
                        Task { await saveKey() }
                    }
                    .disabled(isBusy || apiKey.isEmpty)
                    Text(apiMessage).font(.footnote).foregroundStyle(.secondary)
                }

                Section("2. Trouver un transport") {
                    Picker("Transport", selection: $mode) {
                        ForEach(modes, id: \.self) { Text($0) }
                    }
                    TextField("Ligne", text: $line)
                        .textInputAutocapitalization(.characters)
                    TextField("Arrêt (ex : Place des Fêtes)", text: $stopName)
                    HStack {
                        Button("Chercher un arrêt") {
                            Task { await lookupStops() }
                        }
                        .disabled(isBusy)
                        Spacer()
                        Button {
                            location.request()
                        } label: {
                            Label("Autour de moi", systemImage: "location")
                        }
                        .disabled(isBusy)
                    }

                    if !stops.isEmpty {
                        Picker("Arrêt trouvé", selection: $selectedStopID) {
                            ForEach(stops) { stop in
                                Text(stop.name).tag(stop.id)
                            }
                        }
                        Button(isBusy ? "Recherche..." : "Afficher les passages") {
                            Task { await showPassages() }
                        }
                        .disabled(isBusy || selectedStopID.isEmpty)
                    }
                    if !status.isEmpty {
                        Text(status).foregroundStyle(.secondary)
                    }
                    ForEach(passages) { passage in
                        VStack(alignment: .leading, spacing: 3) {
                            Text("\(passage.line) → \(passage.destination)")
                                .font(.headline)
                            Text("\(passage.minutes ?? 0) min · \(passage.clock) · \(passage.isRealtime ? "Temps réel" : "Horaire théorique")")
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                        }
                    }
                }

                Section("3. Ajouter l'action à Raccourcis") {
                    Text("Après installation, cherche « Horaires Île-de-France » dans les actions de Raccourcis. Renseigne la ligne et l'arrêt, puis lance l'action.")
                    Button("Ouvrir l'application Raccourcis") {
                        if let link = URL(string: "shortcuts://") {
                            UIApplication.shared.open(link)
                        }
                    }
                }

                Section("4. Coller tous les blocs dans Raccourcis") {
                    Text("Importe ton .shortcut NON SIGNÉ : l’application va copier tous ses blocs dans le presse-papiers Apple, sans signer ni installer le fichier.")
                        .font(.footnote)
                    Button {
                        importFile = true
                    } label: {
                        Label("Choisir le fichier .shortcut", systemImage: "doc.badge.plus")
                    }
                    if !importedFileName.isEmpty {
                        Text(importedFileName).font(.headline)
                        Text("\(importedActions.count) blocs détectés")
                            .foregroundStyle(.secondary)
                    }
                    if readyToPaste {
                        Label("\(importedActions.count) blocs copiés dans le presse-papiers !", systemImage: "checkmark.circle.fill")
                            .foregroundStyle(.green)
                        Button {
                            guard let url = URL(string: "shortcuts://create-shortcut") else { return }
                            UIApplication.shared.open(url)
                        } label: {
                            Label("Ouvrir un nouveau raccourci", systemImage: "arrow.up.right.square")
                        }
                        Text("Dans Raccourcis : ajoute d'abord une action « Commentaire », touche son icône, puis choisis « Coller en dessous ». Les blocs copiés doivent apparaître d'un coup. Si Coller n'apparaît pas, iOS a peut-être changé son format de presse-papiers.")
                            .font(.footnote)
                    }
                    if !importMessage.isEmpty {
                        Text(importMessage).font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                }

                Section {
                    Link("Code source libre sur GitHub",
                         destination: URL(string: "https://github.com/200012Yoel/Raccourcis/tree/main/ShortcutBridge")!)
                }
            }
            .navigationTitle("Shortcut Bridge")
            .fileImporter(isPresented: $importFile,
                          allowedContentTypes: [UTType(filenameExtension: "shortcut") ?? .data]) { result in
                do {
                    let url = try result.get()
                    let security = url.startAccessingSecurityScopedResource()
                    defer { if security { url.stopAccessingSecurityScopedResource() } }
                    let bytes = try Data(contentsOf: url)
                    let actions = try ShortcutClipboardBridge.actions(from: bytes)
                    let count = try ShortcutClipboardBridge.copyAllActions(from: bytes)
                    importedFileName = url.lastPathComponent
                    importedActions = actions.map {
                        ($0["WFWorkflowActionIdentifier"] as? String ?? "Action inconnue")
                            .replacingOccurrences(of: "is.workflow.actions.", with: "")
                    }
                    readyToPaste = true
                    importMessage = "\(count) blocs copiés. Aucun serveur, aucune signature nécessaire pour cette opération."
                } catch {
                    readyToPaste = false
                    importedFileName = ""
                    importedActions = []
                    importMessage = "La copie a échoué : \(error.localizedDescription)"
                }
            }
            .onReceive(location.$coordinate) { coordinate in
                guard let coordinate else { return }
                Task { await lookupNearby(coordinate) }
            }
        }
    }

    private func saveKey() async {
        isBusy = true
        defer { isBusy = false }
        do {
            try await IDFMService.testKey(apiKey)
            try APIKeyStore.save(apiKey)
            apiMessage = "✅ Clé acceptée et stockée localement dans le trousseau iOS."
        } catch {
            apiMessage = "❌ \(error.localizedDescription). La clé n'a pas été enregistrée."
        }
    }

    private func key() throws -> String {
        guard let current = APIKeyStore.read() else { throw IDFMError.missingKey }
        return current
    }

    private func lookupStops() async {
        isBusy = true
        defer { isBusy = false }
        do {
            let items = try await IDFMService.findStops(named: stopName, key: key())
            stops = items
            selectedStopID = items.first?.id ?? ""
            passages = []
            status = items.isEmpty ? "Aucun arrêt trouvé." : "Choisis ton arrêt puis affiche les prochains passages."
        } catch {
            status = error.localizedDescription
        }
    }

    private func lookupNearby(_ coordinate: CLLocationCoordinate2D) async {
        isBusy = true
        defer { isBusy = false }
        do {
            let items = try await IDFMService.nearbyStops(latitude: coordinate.latitude,
                                                         longitude: coordinate.longitude,
                                                         key: key())
            stops = items
            selectedStopID = items.first?.id ?? ""
            passages = []
            status = items.isEmpty ? "Aucun arrêt à proximité." : "Arrêts proches détectés. Sélectionne ton arrêt."
        } catch {
            status = error.localizedDescription
        }
    }

    private func showPassages() async {
        guard let selection = stops.first(where: { $0.id == selectedStopID }) else { return }
        isBusy = true
        defer { isBusy = false }
        do {
            passages = try await IDFMService.departures(stop: selection, line: line, key: key())
            status = passages.isEmpty ? "Aucun passage trouvé pour cette ligne à cet arrêt." :
                "Horaires disponibles, vérifie la mention temps réel ou théorique."
        } catch {
            status = error.localizedDescription
        }
    }
}
