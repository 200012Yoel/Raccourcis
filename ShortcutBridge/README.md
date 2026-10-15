# Shortcut Bridge (iPhone, open source)

**Objectif :** récupérer un fichier `.shortcut` généré automatiquement sur GitHub, puis **copier tous ses blocs dans le presse-papiers de l'iPhone** pour les coller en une fois dans l'application **Raccourcis**.

## La bonne différence

Le fichier `.shortcut` complet exige normalement une signature Apple avant importation directe sur iOS récent. **Le collage d'actions dans l'éditeur est une opération différente.** Le code de `ShortcutClipboardBridge.swift` décode un workflow non signé, puis fournit **un élément du presse-papiers par action** avec le type `com.apple.shortcuts.action`. C'est un format utilisé par Raccourcis pour copier/coller ses propres blocs.

Cette fonction est expérimentale car il s'agit d'un format de presse-papiers **non documenté par Apple**. Elle a été décrite par la communauté, mais **pas encore testée sur un iPhone sous iOS 27** ni sur les 131 blocs du raccourci Transport.

## Test sur l'iPhone (une fois notre app installée)

1. Télécharger le fichier `Transport.unsigned.shortcut` sur l'iPhone (Fichiers).
2. Ouvrir Shortcut Bridge puis toucher **Choisir le fichier .shortcut**.
3. Sélectionner `Transport.unsigned.shortcut`. L'application copie les 131 actions dans le presse-papiers.
4. Toucher **Ouvrir un nouveau raccourci**.
5. Dans l'éditeur Raccourcis, ajouter une action simple **Commentaire**.
6. Toucher l'icône de cette action, choisir **Coller en dessous** (ou option de collage équivalente).
7. Vérifier que toutes les actions sont présentes, les conditions, menus et références fonctionnent. Supprimer le Commentaire de départ si inutile.

Ce n'est pas un import automatique ni un jailbreak. Il faut encore effectuer **une opération Coller** dans Raccourcis.

## Compiler

Le dépôt contient un projet XcodeGen `ShortcutBridge/project.yml` et un workflow GitHub [Build Shortcut Bridge iOS](../../actions/workflows/build-shortcut-bridge.yml). Celui-ci compile une application iOS puis archive le résultat en IPA **non signé** à des fins de test/développement.

**L'IPA non signé ne peut pas être installé directement sur un iPhone standard.** Il faut une signature d'application autorisée par iOS (ce n'est pas la même chose que la signature d'un raccourci). Le build de GitHub n'est donc pas une solution complète d'installation sur un iPhone seul.

## Solution existante accessible directement sur iPhone

La technique existe aussi dans **Shortcut Source Tool** (par gluebyte), avec l'application gratuite **Actions** :

- https://routinehub.co/shortcut/5256/
- https://apps.apple.com/app/id1586435171

Le menu *Copy Actions* accepte des sources de raccourcis, y compris des fichiers non signés; il copie les blocs en une fois, sans signer le raccourci. Cette solution n'a pas été vérifiée ici sur iOS 27. Elle est distincte du partage natif d'un fichier complet.

## Sécurité et confidentialité

La fonction de presse-papiers ne transmet pas ton fichier à un serveur. Le code source est disponible dans ce dossier. Examine toujours le contenu d'un raccourci créé par quelqu'un d'autre avant de lancer ses actions, notamment s'il demande localisation, contacts ou accès à Internet.
