#!/usr/bin/env python3
"""Transport V2 : Siri vocal + recherche de ligne précise Navitia.

Génère un .shortcut non signé (à copier/coller avec Shortcut Bridge).
La clé PRIM reste locale à l'iPhone et n'est jamais incluse dans ce programme.
"""
from pathlib import Path
import sys

from shortcutkit import Shortcut, ref, variable, text, repeat_item, current_date

ROOT = "https://prim.iledefrance-mobilites.fr/marketplace/v2/navitia"
s = Shortcut("Transport", color="Blue")

def action(name, **params):
    return s.action("is.workflow.actions." + name, **params)

def speak(*parts):
    return action("speaktext", WFText=text(*parts),
                  WFSpeakTextWait=True, WFSpeakTextRate=0.52,
                  WFSpeakTextPitch=1.0, WFSpeakTextLanguage="fr-FR")

def show(*parts):
    return action("showresult", Text=text(*parts))

def ask_input(question):
    # Le dialogue Siri peut récupérer la réponse à la voix.
    return action("ask", WFInputType="Text", WFAskActionPrompt=question)

def store(name, result):
    action("setvariable", WFInput=ref(result), WFVariableName=name)

def datum(value, key):
    return action("getvalueforkey", WFInput=value,
                  WFGetDictionaryValueType="Value", WFDictionaryKey=key)

def raw(*parts):
    return action("gettext", WFTextActionText=text(*parts))

def encode(value):
    return action("urlencode", WFEncodeMode="Encode", WFInput=value)

def replace(value, find, to):
    return action("text.replace", WFInput=value,
                  WFReplaceTextFind=find, WFReplaceTextReplace=to,
                  WFReplaceTextRegularExpression=True)

def fetch(url):
    # La connexion PRIM est directe depuis l'iPhone.
    api_headers = {
        "WFSerializationType": "WFDictionaryFieldValue",
        "Value": {"WFDictionaryFieldValueItems": [
            {"WFItemType": 0, "WFKey": "apikey", "WFValue": text(variable("IDFMKey"))},
            {"WFItemType": 0, "WFKey": "Accept", "WFValue": "application/json"}
        ]}
    }
    return action("downloadurl", WFURL=url, WFHTTPMethod="GET",
                  WFHTTPHeaders=api_headers)

def stop(message):
    speak(message)
    action("exit")

# 1. Accueil et authentification locale
speak("Bonjour ! Bienvenue dans Transport. Je vais rechercher tes prochains passages.")
key = action("getstoredcontent", WFStoredContentKey="IDFM_PRIM_KEY",
             WFStoredContentGlobalValue=False)
missing = s.if_(ref(key), "has_no_value")
speak("Pour commencer, colle ta clé API Île-de-France Mobilités. Elle restera sur ton iPhone.")
entered = ask_input("Clé API PRIM")
store("IDFMKey", entered)
probe = fetch(ROOT + "/places?q=Gare%20de%20Lyon&count=1")
places = datum(ref(probe), "places")
validated = s.if_(ref(places), "has_no_value")
stop("La clé API n'a pas été validée. Vérifie-la puis relance le raccourci.")
s.end_if(validated)
action("setstoredcontent", WFStoredContentKey="IDFM_PRIM_KEY",
       WFInput=variable("IDFMKey"), WFStoredContentGlobalValue=False)
speak("Clé enregistrée. Merci !")
s.otherwise(missing)
store("IDFMKey", key)
s.end_if(missing)

# 2. Mode de transport précis
speak("Quel transport veux-tu ? Métro, tramway, bus, bus de banlieue, RER ou Transilien ?")
modes = [
    ("Métro", "Metro"),
    ("Tramway", "Tramway"),
    ("Bus de Paris", "Bus"),
    ("Bus de banlieue", "Bus"),
    ("RER", "RapidTransit"),
    ("Transilien", "LocalTrain"),
]
mode_menu = s.choose_from_menu("Choisis le transport", [title for title, _ in modes])
for title, physical_mode in modes:
    s.menu_item(mode_menu, title)
    mode_name = raw(title)
    mode_key = raw(physical_mode)
    store("ModeName", mode_name)
    store("ModeKey", mode_key)
s.end_menu(mode_menu)

speak("Quelle ligne veux-tu rechercher ? Tu peux dire A pour le RER A, ou 20 pour le bus 20.")
code = ask_input("Numéro ou lettre de ligne : A, B, 20, H...")
store("LineCode", code)
code_url = encode(ref(code))

# 3. Chercher la véritable ligne par code ET par mode physique :
#    interdire de confondre un bus 20 avec un autre bus portant le code 20.
lines_url = text(ROOT, "/physical_modes/physical_mode%3A", variable("ModeKey"),
                 "/lines?filter=line.code%3D", ref(code_url), "&count=40")
response = fetch(lines_url)
lines = datum(ref(response), "lines")
missing_lines = s.if_(ref(lines), "has_no_value")
stop("Aucune ligne correspondante trouvée. Vérifie le type de transport et le numéro de ligne.")
s.end_if(missing_lines)

# Chaque ligne candidate est identifiée par son véritable URI Navitia,
# sélectionnée sans aucune condition Si 'est [variable]' qui casse à l'import.
each = s.repeat_each(ref(lines))
line_name = datum(repeat_item(), "name")
line_code = datum(repeat_item(), "code")
line_id = datum(repeat_item(), "id")
label = raw(ref(line_code), " | ", ref(line_name), "  •  ", ref(line_id))
action("appendvariable", WFVariableName="LineOptions", WFInput=ref(label))
s.end_repeat_each(each)

speak("J'ai trouvé la ligne. S'il y a plusieurs résultats, choisis celui qui correspond à ton trajet.")
picked_line = action("choosefromlist", WFInput=variable("LineOptions"),
                     WFChooseFromListActionPrompt="Choisis la bonne ligne")
# Exemple du choix : A | RER A • line:IDFM:Cxxxxx
id_only = replace(ref(picked_line), "^.*  •  ", "")
store("LineID", id_only)
encoded_line_id = encode(ref(id_only))

# 4. Sélection d'un arrêt, soit localisé, soit dicté à Siri.
stop_menu = s.choose_from_menu("Comment chercher l'arrêt ?", ["Près de moi", "Dire le nom de l'arrêt"])

s.menu_item(stop_menu, "Près de moi")
speak("Je cherche les arrêts à proximité de ta position.")
position = action("getcurrentlocation")
lat = action("properties.locations", WFContentItemPropertyName="Latitude")
action("getvariable", WFVariable=ref(position))
lon = action("properties.locations", WFContentItemPropertyName="Longitude")
near_url = text(ROOT, "/coords/", ref(lon), ";", ref(lat),
                "/places_nearby?distance=950&count=30&type%5B%5D=stop_area")
near_data = fetch(near_url)
near_places = datum(ref(near_data), "places_nearby")
store("Stops", near_places)

s.menu_item(stop_menu, "Dire le nom de l'arrêt")
speak("Comment s'appelle ton arrêt ou ta gare ?")
stop_input = ask_input("Nom exact de l'arrêt ou de la gare")
safe_name = encode(ref(stop_input))
search_url = text(ROOT, "/places?q=", ref(safe_name), "&count=30&type%5B%5D=stop_area")
search = fetch(search_url)
search_places = datum(ref(search), "places")
store("Stops", search_places)
s.end_menu(stop_menu)

none_found = s.if_(variable("Stops"), "has_no_value")
stop("Je n'ai trouvé aucun arrêt. Essaie avec un nom plus précis.")
s.end_if(none_found)

each = s.repeat_each(variable("Stops"))
# Objet places avec stop_area imbriqué; même forme pour places_nearby.
area = datum(repeat_item(), "stop_area")
area_name = datum(ref(area), "name")
area_id = datum(ref(area), "id")
stop_label = raw(ref(area_name), "  •  ", ref(area_id))
action("appendvariable", WFVariableName="StopOptions", WFInput=ref(stop_label))
s.end_repeat_each(each)

speak("J'ai trouvé plusieurs arrêts possibles. Choisis celui que tu souhaites.")
choice = action("choosefromlist", WFInput=variable("StopOptions"),
                WFChooseFromListActionPrompt="Choisis l'arrêt")
stop_id = replace(ref(choice), "^.*  •  ", "")
encoded_stop_id = encode(ref(stop_id))

# 5. Intersection serveur ligne + arrêt : aucun filtrage client fragile.
depart_url = text(ROOT, "/stop_areas/", ref(encoded_stop_id),
                  "/lines/", ref(encoded_line_id), "/departures?count=5")
response = fetch(depart_url)
departures = datum(ref(response), "departures")
no_dep = s.if_(ref(departures), "has_no_value")
stop("Aucun passage annoncé pour cette ligne à cet arrêt. Essaie un autre arrêt ou une autre direction.")
s.end_if(no_dep)

speak("Voici les prochains passages de la ligne ", variable("LineCode"), ".")
each = s.repeat_each(ref(departures))
direction = datum(repeat_item(), "display_informations.direction")
departure = datum(repeat_item(), "stop_date_time.departure_date_time")
formatted = replace(ref(departure),
                    r"^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})$",
                    "$4 heures $5")
human_date = replace(ref(departure),
                     r"^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})$",
                     "$1-$2-$3 $4:$5:$6")
as_date = action("detect.date", WFInput=ref(human_date))
have_date = s.if_(ref(as_date), "has_any_value")
mins = action("gettimebetweendates", WFTimeUntilFromDate=current_date(),
              WFInput=ref(as_date), WFTimeUntilUnit="Minutes")
rounded = action("round", WFInput=ref(mins), WFRoundTo="Ones Place", WFRoundMode="Always Round Up")
speak("Direction ", ref(direction), ", dans environ ", ref(rounded),
      " minutes. Départ à ", ref(formatted), ".")
s.otherwise(have_date)
speak("Direction ", ref(direction), ", départ prévu à ", ref(formatted), ".")
s.end_if(have_date)
s.end_repeat_each(each)

speak("Attention, les horaires peuvent être théoriques. Bonne route !")

if __name__ == "__main__":
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "Transport-V2.unsigned.shortcut")
    output.parent.mkdir(parents=True, exist_ok=True)
    s.write(output)
    print(f"Transport V2 : {len(s.actions)} actions dans {output}")
