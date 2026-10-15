#!/usr/bin/env python3
"""Fabrique le raccourci iPhone Transport IDFM (prototype non signé).

Dépendance de génération : pip install shortcutkit
Aucune clé API réelle n'est incluse, collectée ou transmise à GitHub.
"""
import pathlib
import sys
from shortcutkit import Shortcut, ref, variable, current_date, ask, text, repeat_item

BASE = "https://prim.iledefrance-mobilites.fr/marketplace/v2/navitia"
s = Shortcut("Transport", color="Blue")


def act(identifier, **params):
    return s.action("is.workflow.actions." + identifier, **params)


def say(*pieces):
    return act("showresult", Text=text(*pieces))


def plain(value):
    return act("gettext", WFTextActionText=value)


def ask_text(prompt):
    # Le jeton Ask Each Time affiche un champ lors de l'exécution.
    return plain(ask(prompt))


def store_variable(name, output):
    act("setvariable", WFVariableName=name, WFInput=ref(output))


def dictval(data, key):
    return act("getvalueforkey", WFInput=data,
               WFGetDictionaryValueType="Value", WFDictionaryKey=key)


def stop_with(message):
    say(message)
    act("exit")


def headers(api_key):
    # Encodage officiel du paramètre WFHTTPHeaders de Shortcuts.
    return {
        "WFSerializationType": "WFDictionaryFieldValue",
        "Value": {
            "WFDictionaryFieldValueItems": [
                {"WFItemType": 0, "WFKey": "apikey", "WFValue": text(api_key)},
                {"WFItemType": 0, "WFKey": "Accept", "WFValue": "application/json"}
            ]
        }
    }


def request(url, key):
    # Requête HTTPS directe iPhone -> PRIM : aucun serveur intermédiaire.
    return act("downloadurl", WFURL=url, WFHTTPMethod="GET",
               WFHTTPHeaders=headers(key))


# --- Premier lancement : saisie et validation de la clé ---
key_stored = act("getstoredcontent", WFStoredContentKey="IDFM_PRIM_KEY",
                 WFStoredContentGlobalValue=False)
needs_setup = s.if_(ref(key_stored), "has_no_value")
say("Bienvenue dans Transport IDFM ! Saisis ta clé API PRIM. "
    "Elle sera enregistrée uniquement sur cet iPhone.")
new_key = ask_text("Colle ta clé API PRIM Île-de-France Mobilités")
probe = request(BASE + "/places?q=Gare%20de%20Lyon&count=1", ref(new_key))
probe_places = dictval(ref(probe), "places")
valid = s.if_(ref(probe_places), "has_any_value")
act("setstoredcontent", WFInput=ref(new_key),
    WFStoredContentKey="IDFM_PRIM_KEY", WFStoredContentGlobalValue=False)
say("Clé API validée et enregistrée. Tu peux utiliser Transport !")
s.otherwise(valid)
stop_with("La clé n'a pas pu être validée. Rien n'a été enregistré.")
s.end_if(valid)
s.end_if(needs_setup)

key = act("getstoredcontent", WFStoredContentKey="IDFM_PRIM_KEY",
          WFStoredContentGlobalValue=False)

# --- Choix du type de transport ---
modes = [
    ("Métro", "Metro"),
    ("Tram", "Tramway"),
    ("Bus Paris", "Bus"),
    ("Bus de banlieue", "Bus"),
    ("RER", "RapidTransit"),
    ("Transilien", "LocalTrain"),
]
menu = s.choose_from_menu("🚇 Quel transport cherches-tu ?", [x[0] for x in modes])
for label, physical_mode in modes:
    s.menu_item(menu, label)
    mode_obj = plain(physical_mode)
    store_variable("ModeTechnique", mode_obj)
    mode_label = plain(label)
    store_variable("ModeAffiche", mode_label)
s.end_menu(menu)

line_number = ask_text("Numéro/lettre de ligne (ex : 20, 26, 11, A, H)")
store_variable("LigneVoulue", line_number)

# --- Arrêt proche GPS ou recherche manuelle ---
where_menu = s.choose_from_menu("🚏 Quel arrêt ?", ["Autour de moi (GPS)", "Rechercher un arrêt"])
s.menu_item(where_menu, "Autour de moi (GPS)")
loc = act("getcurrentlocation")
latitude = act("properties.locations", WFContentItemPropertyName="Latitude")
act("getvariable", WFVariable=ref(loc))
longitude = act("properties.locations", WFContentItemPropertyName="Longitude")
nearby_url = text(BASE, "/coords/", ref(longitude), ";", ref(latitude),
                  "/places_nearby?distance=900&count=35&type%5B%5D=stop_area")
nearby_result = request(nearby_url, ref(key))
nearby_stops = dictval(ref(nearby_result), "places_nearby")
store_variable("Candidates", nearby_stops)

s.menu_item(where_menu, "Rechercher un arrêt")
name_input = ask_text("Nom de la gare ou de l'arrêt (ex : Place des Fêtes)")
name_encoded = act("urlencode", WFEncodeMode="Encode", WFInput=ref(name_input))
places_url = text(BASE, "/places?q=", ref(name_encoded),
                  "&count=35&type%5B%5D=stop_area")
places_result = request(places_url, ref(key))
found_stops = dictval(ref(places_result), "places")
store_variable("Candidates", found_stops)
s.end_menu(where_menu)

have_stops = s.if_(variable("Candidates"), "has_no_value")
stop_with("Aucun arrêt trouvé. Essaie un autre nom ou augmente la proximité.")
s.end_if(have_stops)

# --- Présenter les noms, choisir un arrêt puis retrouver son identifiant ---
iterator = s.repeat_each(variable("Candidates"))
stop_name = dictval(repeat_item(), "name")
act("appendvariable", WFVariableName="ChoixArrets", WFInput=ref(stop_name))
s.end_repeat_each(iterator)

choice = act("choosefromlist", WFInput=variable("ChoixArrets"),
             WFChooseFromListActionPrompt="Choisis l'arrêt qui correspond à ta ligne",
             WFChooseFromListActionSelectMultiple=False)

iterator = s.repeat_each(variable("Candidates"))
stop_name = dictval(repeat_item(), "name")
matches = s.if_(ref(stop_name), "is", ref(choice))
stop_id = dictval(repeat_item(), "id")
store_variable("IdentifiantArret", stop_id)
s.end_if(matches)
s.end_repeat_each(iterator)

has_selected = s.if_(variable("IdentifiantArret"), "has_no_value")
stop_with("Impossible de retrouver cet arrêt dans les résultats. Réessaie.")
s.end_if(has_selected)

# --- Prochains départs Navitia ---
url = text(BASE, "/stop_areas/", variable("IdentifiantArret"),
           "/departures?count=100")
departures_result = request(url, ref(key))
departures = dictval(ref(departures_result), "departures")
has_departures = s.if_(ref(departures), "has_no_value")
stop_with("Aucun départ actuellement disponible pour cet arrêt.")
s.end_if(has_departures)

loop = s.repeat_each(ref(departures))
code = dictval(repeat_item(), "display_informations.code")
line_matches = s.if_(ref(code), "is", variable("LigneVoulue"))
physical = dictval(repeat_item(), "display_informations.physical_mode")
mode_matches = s.if_(ref(physical), "is", variable("ModeTechnique"))
direction = dictval(repeat_item(), "display_informations.direction")
raw_time = dictval(repeat_item(), "stop_date_time.departure_date_time")
freshness = dictval(repeat_item(), "stop_date_time.data_freshness")

# Exemple Navitia : 20261015T161200 -> 16:12
hhmm = act("text.replace", WFInput=ref(raw_time),
           WFReplaceTextFind=r"^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})$",
           WFReplaceTextReplace="$4:$5", WFReplaceTextRegularExpression=True)
# Conversion pour le calcul des minutes sur le fuseau horaire local de l'iPhone.
readable_time = act("text.replace", WFInput=ref(raw_time),
                    WFReplaceTextFind=r"^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})$",
                    WFReplaceTextReplace="$1-$2-$3T$4:$5:$6",
                    WFReplaceTextRegularExpression=True)
date = act("detect.date", WFInput=ref(readable_time))

real = s.if_(ref(freshness), "is", "realtime")
fresh_word = plain("temps réel")
store_variable("Fraicheur", fresh_word)
s.otherwise(real)
base_word = plain("horaire théorique")
store_variable("Fraicheur", base_word)
s.end_if(real)

can_compute = s.if_(ref(date), "has_any_value")
mins = act("gettimebetweendates", WFTimeUntilFromDate=current_date(),
           WFInput=ref(date), WFTimeUntilUnit="Minutes")
rounded = act("round", WFInput=ref(mins), WFRoundTo="Ones Place",
              WFRoundMode="Always Round Up")
not_past = s.if_(ref(rounded), "greater_or_equal", 0)
display = plain(text("🚆 ", ref(code), " vers ", ref(direction), " : ",
                     ref(rounded), " min (", ref(hhmm), ") · ",
                     variable("Fraicheur")))
act("appendvariable", WFVariableName="Passages", WFInput=ref(display))
s.end_if(not_past)
s.otherwise(can_compute)
display = plain(text("🚆 ", ref(code), " vers ", ref(direction), " : ",
                     ref(hhmm), " · ", variable("Fraicheur")))
act("appendvariable", WFVariableName="Passages", WFInput=ref(display))
s.end_if(can_compute)

s.end_if(mode_matches)
s.end_if(line_matches)
s.end_repeat_each(loop)

found = s.if_(variable("Passages"), "has_any_value")
act("getvariable", WFVariable=variable("Passages"))
combined = act("text.combine", WFTextSeparator="New Lines")
say("🚏 ", ref(choice), "\n", ref(combined),
    "\n\nLes horaires théoriques peuvent différer du passage réel.")
s.otherwise(found)
say("Aucun passage correspondant à la ligne ", variable("LigneVoulue"),
    " et au mode ", variable("ModeAffiche"),
    " à cet arrêt. Essaie un autre arrêt ou une direction.")
s.end_if(found)

if __name__ == "__main__":
    destination = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "Transport.unsigned.shortcut")
    destination.parent.mkdir(parents=True, exist_ok=True)
    s.write(destination)
    print(f"Fichier non signé : {destination} ({len(s.actions)} actions)")
