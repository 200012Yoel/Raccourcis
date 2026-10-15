# Transport Île-de-France, raccourci Apple (prototype)

Ce dépôt fabrique un raccourci iPhone **Transport** sans jailbreak ni Apple Intelligence.

## Fonctionnalités prévues

- Premier lancement : demander la clé API PRIM d'Île-de-France Mobilités puis la vérifier via une requête officielle.
- En cas de validation, sauvegarde **locale dans les données persistantes du raccourci** : aucune clé n'est stockée dans GitHub.
- Menu : Métro, Tram, Bus Paris, Bus de banlieue, RER, Transilien.
- Saisie de la ligne, puis choix entre **Arrêts autour de moi (GPS)** et **Rechercher un arrêt par son nom**.
- Sélection de l'arrêt et affichage des prochains passages, de leur direction et de l'heure/minutes avant départ quand calculables.

## Génération GitHub Actions

Ouvrir **Actions > Build Transport Shortcut > Run workflow** puis récupérer l'artefact **Transport-unsigned**. Le fichier généré est **non signé**, car le service Apple de signature de raccourcis nécessite une session iCloud, absente des Mac temporaires de GitHub Actions. Nous ne prétendons pas que ce fichier est installable directement.

Sur un Mac personnel connecté à iCloud, la commande officielle est :

    shortcuts sign --mode anyone --input "Transport.unsigned.shortcut" --output "Transport.shortcut"

Ouvrir ensuite le fichier signé sur l'iPhone et confirmer l'ajout dans Raccourcis.

Ce projet utilise ShortcutKit (MIT) : https://github.com/frontboat/shortcutkit

## À connaître avant d'utiliser

**Prototype non encore essayé sur un iPhone réel.** Les horaires de l'API Navitia v2 peuvent être **théoriques**, pas des prévisions temps réel. Cette version n'interroge pas encore l'API SIRI-Lite, et n'affiche aucune arrivée inventée. Le bus parisien et le bus de banlieue sont tous deux du mode Bus dans les données; les autres modes dépendent du libellé de la réponse. La recherche GPS propose des arrêts à proximité mais ne garantit pas que la ligne demandée y passe. Les exemples « Bus 20 / Place des Fêtes » et « Bus 26 / Vigneux » ne sont pas des arrêts validés.

N'ajoutez **jamais** votre clé API aux fichiers GitHub, issues ou journaux. Une clé enregistrée par Raccourcis est locale mais n'est pas un secret stocké dans un coffre-fort spécialisé.

Documentation : https://prim.iledefrance-mobilites.fr/apis/idfm-navitia-general-v2 et https://doc.navitia.io/
