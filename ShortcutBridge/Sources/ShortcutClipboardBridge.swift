import Foundation
import UIKit

/// Copie tous les blocs d'un workflow .shortcut non signé vers le presse-papiers
/// que l'éditeur Apple Raccourcis utilise pour ses propres actions.
/// Aucune signature du fichier complet n'est requise : ce n'est PAS une importation de .shortcut.
enum ShortcutClipboardBridge {
    static let pasteboardType = "com.apple.shortcuts.action"

    enum BridgeError: LocalizedError {
        case signedArchive
        case invalidWorkflow
        case emptyWorkflow
        case failedToWrite

        var errorDescription: String? {
            switch self {
            case .signedArchive:
                return "Ce fichier possède une enveloppe Apple AEA1. Cette version attend un fichier .shortcut non signé."
            case .invalidWorkflow:
                return "Le fichier ne contient pas un workflow Apple Raccourcis lisible."
            case .emptyWorkflow:
                return "Le workflow ne contient aucune action."
            case .failedToWrite:
                return "Le presse-papiers iOS n'a pas conservé toutes les actions."
            }
        }
    }

    static func actions(from data: Data) throws -> [[String: Any]] {
        if data.starts(with: Data("AEA1".utf8)) {
            throw BridgeError.signedArchive
        }
        let decoded = try PropertyListSerialization.propertyList(
            from: data, options: [], format: nil
        )
        let result: [[String: Any]]
        if let actionList = decoded as? [[String: Any]] {
            result = actionList
        } else if let workflow = decoded as? [String: Any],
                  let actionList = workflow["WFWorkflowActions"] as? [[String: Any]] {
            result = actionList
        } else {
            throw BridgeError.invalidWorkflow
        }
        guard !result.isEmpty else { throw BridgeError.emptyWorkflow }
        return result
    }

    /// Les sorties produites par certains générateurs possèdent des valeurs nulles
    /// qui ne sont pas sérialisables par PropertyListSerialization iOS.
    private static func cleaned(_ value: Any) -> Any? {
        if value is NSNull { return nil }
        if let dictionary = value as? [String: Any] {
            var result: [String: Any] = [:]
            for (key, object) in dictionary {
                if let valid = cleaned(object) { result[key] = valid }
            }
            return result
        }
        if let array = value as? [Any] {
            return array.compactMap { cleaned($0) }
        }
        return value
    }

    /// Une action = un élément UIPasteboard sous le type privé mais documenté
    /// publiquement par la communauté « com.apple.shortcuts.action ».
    /// Copier les dictionnaires complets permet de conserver les UUID,
    /// les références à d'autres actions et les structures Menu/If/Répéter.
    @discardableResult
    static func copyAllActions(from data: Data) throws -> Int {
        let actions = try actions(from: data)
        let items: [[String: Any]] = try actions.map { action in
            let bytes = try PropertyListSerialization.data(
                fromPropertyList: cleaned(action) ?? [:], format: .binary, options: 0
            )
            return [pasteboardType: bytes]
        }

        let board = UIPasteboard.general
        board.setItems(items, options: [.localOnly: true])
        guard board.numberOfItems == actions.count,
              board.items.count == actions.count,
              board.items.allSatisfy({ $0[pasteboardType] is Data })
        else {
            throw BridgeError.failedToWrite
        }
        return actions.count
    }
}
