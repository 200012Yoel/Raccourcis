import Foundation
import AppIntents

struct NextTransportIntent: AppIntent {
    static var title: LocalizedStringResource = "Horaires Île-de-France"
    static var description = IntentDescription("Cherche les prochains passages de transport via PRIM.")
    static var openAppWhenRun: Bool = false

    @Parameter(title: "Ligne", description: "Exemple : 20, 11, A, H")
    var line: String

    @Parameter(title: "Arrêt", description: "Exemple : Place des Fêtes")
    var stopName: String

    static var parameterSummary: some ParameterSummary {
        Summary("Prochains passages de la ligne \(\.$line) à \(\.$stopName)")
    }

    func perform() async throws -> some IntentResult & ReturnsValue<String> {
        guard let key = APIKeyStore.read() else { throw IDFMError.missingKey }
        let output = try await IDFMService.searchLine(line, stopName: stopName, key: key)
        return .result(value: output)
    }
}

struct BridgeAppShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: NextTransportIntent(),
            phrases: ["Consulter les transports avec \(.applicationName)",
                      "Prochains transports avec \(.applicationName)"],
            shortTitle: "Transport IDFM",
            systemImageName: "tram.fill"
        )
    }
    static var shortcutTileColor: ShortcutTileColor = .blue
}
