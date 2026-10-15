# Transport Île-de-France, raccourci Apple (prototype)

Ce dépôt fabrique un raccourci iPhone **Transport** sans jailbreak ni Apple Intelligence.

## Fonctionnalités prévues

- Premier lancement : demander la clé API PRIM d'Île-de-France Mobilités puis la vérifier via une requête officielle.
- En cas de validation, sauvegarde **locale dans les données persistantes du raccourci** : aucune clé n'est stockée dans GitHub.
- Menu : Métro, Tram, Bus Paris, Bus de banlieue, RER, Transilien.
- Saisie de la ligne, puis choix entre **Arrêts autour de moi (GPS)** et **Rechercher un arrêt par son nom**.
- Sélection de l'arrêt et affichage des prochains passages, de leur direction et de l'heure/minutes avant départ quand calculables.

## Génération automatique + signature distante

Le workflow GitHub **Build Transport Shortcut** crée le fichier avec `shortcutkit`, le valide, puis essaie de le signer via les services tiers Shortcuty Signing API (principal) et HubSign de RoutineHub (secours). Le Mac de GitHub **n'est pas connecté à un compte Apple**, donc cette signature ne passe pas par la commande Apple native.

Quand l'exécution a **réussi**, elle publie `dist/Transport.shortcut` dans la branche main. Depuis Safari sur l'iPhone, le lien direct est :

**[Transport.shortcut (uniquement après réussite du workflow)](https://raw.githubusercontent.com/200012Yoel/Raccourcis/main/dist/Transport.shortcut)**

En fonction de Safari, le fichier peut d'abord se télécharger dans Fichiers ; ouvrir ensuite ce fichier pour voir l'écran d'importation Raccourcis. La confirmation d'ajout reste nécessaire.

Si le lien renvoie **404**, cela signifie que le fichier signé n'a pas été publié : ouvrir [le workflow](https://github.com/200012Yoel/Raccourcis/actions/workflows/build-transport.yml), le lancer, examiner le résultat et, si nécessaire, activer GitHub Actions / les autorisations d'écriture du jeton. Une compilation ou un envoi à un service de signature réussi **ne garantit pas à lui seul** que toutes les actions fonctionnent sur iPhone.

La clé API PRIM n'est jamais mise dans GitHub ni transmise au service de signature : elle est demandée **à l'exécution**, sur l'iPhone. Le service de signature tiers voit le contenu du raccourci public, pas la clé que tu ajouteras sur ton téléphone.

## À connaître avant d'utiliser

**Prototype non encore essayé sur un iPhone réel.** Les horaires de l'API Navitia v2 peuvent être **théoriques**, pas des prévisions temps réel. Cette version n'interroge pas encore l'API SIRI-Lite, et n'affiche aucune arrivée inventée. Le bus parisien et le bus de banlieue sont tous deux du mode Bus dans les données; les autres modes dépendent du libellé de la réponse. La recherche GPS propose des arrêts à proximité mais ne garantit pas que la ligne demandée y passe. Les exemples « Bus 20 / Place des Fêtes » et « Bus 26 / Vigneux » ne sont pas des arrêts validés.

N'ajoutez **jamais** votre clé API aux fichiers GitHub, issues ou journaux. Une clé enregistrée par Raccourcis est locale mais n'est pas un secret stocké dans un coffre-fort spécialisé.

Documentation : https://prim.iledefrance-mobilites.fr/apis/idfm-navitia-general-v2 et https://doc.navitia.io/
