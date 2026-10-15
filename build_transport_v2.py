#!/usr/bin/env python3
"""Transport V2 - assistant vocal Siri pour les passages IDFM.
Génère un .shortcut non signé, à coller via Shortcut Bridge.
Ne contient AUCUNE clé API personnelle.
"""
from pathlib import Path
import sys
from shortcutkit import Shortcut, ref, variable, text, repeat_item, current_date

ROOT = "https://prim.iledefrance-mobilites.fr/marketplace/v2/navitia"
s = Shortcut("Transport", color="Blue")

def a(name, **kw):
    return s.action("is.workflow.actions." + name, **kw)

def speak(*parts):
    return a("speaktext", WFText=text(*parts), WFSpeakTextWait=True,
             WFSpeakTextRate=0.50, WFSpeakTextPitch=1.0,
             WFSpeakTextLanguage="fr-FR")

def ask(question):
    return a("ask", WFInputType="Text", WFAskActionPrompt=question)

def t(*parts):
    return a("gettext", WFTextActionText=text(*parts))

def setvar(name, result):
    a("setvariable", WFVariableName=name, WFInput=ref(result))

def dct(obj, key):
    return a("getvalueforkey", WFInput=obj,
             WFGetDictionaryValueType="Value", WFDictionaryKey=key)

def encoded(inp):
    return a("urlencode", WFEncodeMode="Encode", WFInput=inp)

def substitution(inp, find, repl):
    return a("text.replace", WFInput=inp,
             WFReplaceTextFind=find, WFReplaceTextReplace=repl,
             WFReplaceTextRegularExpression=True)

def fetch(url):
    headers = {
        "WFSerializationType": "WFDictionaryFieldValue",
        "Value": {"WFDictionaryFieldValueItems": [
            {"WFItemType": 0, "WFKey": "apikey", "WFValue": text(variable("IDFMKey"))},
            {"WFItemType": 0, "WFKey": "Accept", "WFValue": "application/json"},
        ]},
    }
    return a("downloadurl", WFURL=url, WFHTTPMethod="GET", WFHTTPHeaders=headers)

def die(*message):
    speak(*message)
    a("exit")

# A. Clé PRIM : saisie au premier démarrage, test avant mémorisation.
key = a("getstoredcontent", WFStoredContentKey="IDFM_PRIM_KEY", WFStoredContentGlobalValue=False)
setup = s.if_(ref(key), "has_no_value")
speak("Bienvenue dans Transport. Entre ta clé API PRIM pour la première utilisation.")
newkey = ask("Colle ta clé API Île-de-France Mobilités")
setvar("IDFMKey", newkey)
health = fetch(ROOT + "/places?q=Gare%20de%20Lyon&count=1")
health_places = dct(ref(health), "places")
invalid = s.if_(ref(health_places), "has_no_value")
die("Je ne peux pas valider cette clé. Vérifie la connexion et réessaie.")
s.end_if(invalid)
a("setstoredcontent", WFStoredContentKey="IDFM_PRIM_KEY",
  WFInput=variable("IDFMKey"), WFStoredContentGlobalValue=False)
speak("Clé enregistrée. Tu n'auras plus à la saisir.")
s.otherwise(setup)
setvar("IDFMKey", key)
s.end_if(setup)

# B. Type de transport + question adaptée, exemples réellement spécifiques.
speak("Quel transport veux-tu prendre ? Métro, tramway, bus, bus de banlieue, RER ou Transilien ?")
modes = [
    ("Métro", "Metro", "Quelle ligne de métro ? Par exemple 1, 6 ou 11."),
    ("Tramway", "Tramway", "Quelle ligne de tramway ? Par exemple T 1, T 2 ou T 3 b."),
    ("Bus de Paris", "Bus", "Quelle ligne de bus ? Par exemple 20, 26, 48 ou 60."),
    ("Bus de banlieue", "Bus", "Quelle ligne de bus de banlieue ? Donne son numéro ou son nom."),
    ("RER", "RapidTransit", "Quelle ligne de RER ? Par exemple A, B, C, D ou E."),
    ("Transilien", "LocalTrain", "Quelle ligne de Transilien ? Par exemple H, J, L, N, P ou R."),
]
menu = s.choose_from_menu("Quel moyen de transport ?", [m[0] for m in modes])
for title, physical, question in modes:
    s.menu_item(menu, title)
    spoken_mode = t(title)
    code_mode = t(physical)
    setvar("ModeName", spoken_mode)
    setvar("ModeKey", code_mode)
    speak(question)
    answer = ask(question)
    setvar("LineCode", answer)
s.end_menu(menu)

# C. Rechercher la vraie ligne par mode et code. Choisir en cas d'homonymie.
safe_code = encoded(variable("LineCode"))
line_url = text(ROOT, "/physical_modes/physical_mode%3A", variable("ModeKey"),
                "/lines?filter=line.code%3D", ref(safe_code), "&count=40")
line_reply = fetch(line_url)
lines = dct(ref(line_reply), "lines")
no_lines = s.if_(ref(lines), "has_no_value")
die("Aucune ligne ne correspond au transport et au numéro indiqués. Essaie un autre numéro.")
s.end_if(no_lines)

each_line = s.repeat_each(ref(lines))
name = dct(repeat_item(), "name")
code = dct(repeat_item(), "code")
identifier = dct(repeat_item(), "id")
item = t(ref(code), " — ", ref(name), "  •  ", ref(identifier))
a("appendvariable", WFVariableName="LineChoices", WFInput=ref(item))
s.end_repeat_each(each_line)

selected_line = a("choosefromlist", WFInput=variable("LineChoices"),
                  WFChooseFromListActionPrompt="Confirme ta ligne")
line_id = substitution(ref(selected_line), "^.*  •  ", "")
safe_line = encoded(ref(line_id))

# D. Demander l'arrêt APRÈS la ligne.
speak("Quel arrêt ou quelle station de la ligne ", variable("LineCode"),
      " veux-tu consulter ?")
stop_choice = s.choose_from_menu("Comment trouver l'arrêt ?", ["Dire le nom de l'arrêt", "Près de moi"])
s.menu_item(stop_choice, "Dire le nom de l'arrêt")
name_response = ask("Quel arrêt ou quelle station de cette ligne ?")
safe_station = encoded(ref(name_response))
# Recherche LIMITÉE AUX ARRÊTS DE LA LIGNE, pas à tous les arrêts d'Île-de-France.
search_url = text(ROOT, "/lines/", ref(safe_line),
                  "/pt_objects?q=", ref(safe_station),
                  "&type%5B%5D=stop_area")
places = fetch(search_url)
found_places = dct(ref(places), "pt_objects")
setvar("CandidateStops", found_places)

s.menu_item(stop_choice, "Près de moi")
speak("Je recherche les arrêts proches de toi.")
position = a("getcurrentlocation")
setvar("DeviceLocation", position)
a("getvariable", WFVariable=variable("DeviceLocation"))
latitude = a("properties.locations", WFContentItemPropertyName="Latitude")
a("getvariable", WFVariable=variable("DeviceLocation"))
longitude = a("properties.locations", WFContentItemPropertyName="Longitude")
near_url = text(ROOT, "/coords/", ref(longitude), ";", ref(latitude),
                "/places_nearby?distance=1000&count=30&type%5B%5D=stop_area")
near_reply = fetch(near_url)
close_stops = dct(ref(near_reply), "places_nearby")
setvar("CandidateStops", close_stops)
s.end_menu(stop_choice)

not_found = s.if_(variable("CandidateStops"), "has_no_value")
die("Je ne trouve pas cet arrêt. Essaie de prononcer son nom autrement.")
s.end_if(not_found)

# Les choix de stations sont présentés SANS identifiants techniques.
# Un dictionnaire {nom affiché: URI Navitia} masque les codes IDFM.
blank_stops = t("{}")
stop_dictionary = a("detect.dictionary", WFInput=ref(blank_stops))
setvar("StopMap", stop_dictionary)

each_stop = s.repeat_each(variable("CandidateStops"))
stop_area = dct(repeat_item(), "stop_area")
stopname = dct(ref(stop_area), "name")
stopid = dct(ref(stop_area), "id")
updated_stops = a("setvalueforkey", WFDictionaryKey=ref(stopname),
                  WFDictionaryValue=ref(stopid),
                  WFDictionary=variable("StopMap"))
setvar("StopMap", updated_stops)
s.end_repeat_each(each_stop)

stop_names = a("getvalueforkey", WFGetDictionaryValueType="All Keys",
               WFInput=variable("StopMap"))
missing_choices = s.if_(ref(stop_names), "has_no_value")
die("Je ne trouve pas de station qui correspond à la ligne demandée.")
s.end_if(missing_choices)

count_stops = a("count", Input=ref(stop_names), WFCountType="Items")
multiple_stops = s.if_(ref(count_stops), "greater_than", 1)
speak("Voici les arrêts possibles pour cette ligne. Choisis celui que tu veux.")
stop_selected = a("choosefromlist", WFInput=ref(stop_names),
                  WFChooseFromListActionPrompt="Choisis ton arrêt")
setvar("SelectedStopName", stop_selected)
s.otherwise(multiple_stops)
single_stop = a("getitemfromlist", WFInput=ref(stop_names), WFItemSpecifier="First Item")
setvar("SelectedStopName", single_stop)
s.end_if(multiple_stops)
station_id = dct(variable("StopMap"), variable("SelectedStopName"))
safe_stop = encoded(ref(station_id))

# Récupérer les départs de CETTE LIGNE à CET ARRÊT.
# Navitia renvoie un stop_schedule par point d'arrêt et par route/direction.
schedule_url = text(ROOT, "/lines/", ref(safe_line), "/stop_areas/",
                    ref(safe_stop), "/stop_schedules?count=50&items_per_schedule=2")
sched_reply = fetch(schedule_url)
schedules = dct(ref(sched_reply), "stop_schedules")
not_available = s.if_(ref(schedules), "has_no_value")
die("Pas d'horaire disponible pour la ligne ", variable("LineCode"),
    " à l'arrêt choisi. Vérifie le nom ou essaie une autre station.")
s.end_if(not_available)

# Préparer le dictionnaire des directions réelles : {Direction affichée: route.id}.
# Les clés d'un dictionnaire sont uniques, donc pas de doublons dans le menu.
blank_directions = t("{}")
directions_dictionary = a("detect.dictionary", WFInput=ref(blank_directions))
setvar("DirectionMap", directions_dictionary)
each_route = s.repeat_each(ref(schedules))
infos = dct(repeat_item(), "display_informations")
direction = dct(ref(infos), "direction")
route = dct(repeat_item(), "route")
route_id = dct(ref(route), "id")
updated_map = a("setvalueforkey", WFDictionaryKey=ref(direction),
                WFDictionaryValue=ref(route_id), WFDictionary=variable("DirectionMap"))
setvar("DirectionMap", updated_map)
s.end_repeat_each(each_route)

direction_names = a("getvalueforkey", WFInput=variable("DirectionMap"),
                    WFGetDictionaryValueType="All Keys")
no_directions = s.if_(ref(direction_names), "has_no_value")
die("Aucune direction n'est annoncée pour cet arrêt.")
s.end_if(no_directions)

n_directions = a("count", Input=ref(direction_names), WFCountType="Items")
multiple_directions = s.if_(ref(n_directions), "greater_than", 1)
speak("Dans quelle direction veux-tu voyager ? Choisis le terminus dans le menu.")
choice = a("choosefromlist", WFInput=ref(direction_names),
           WFChooseFromListActionPrompt="Choisis la direction du trajet")
setvar("SelectedDirection", choice)
s.otherwise(multiple_directions)
only_direction = a("getitemfromlist", WFInput=ref(direction_names),
                   WFItemSpecifier="First Item")
setvar("SelectedDirection", only_direction)
s.end_if(multiple_directions)

selected_route_id = dct(variable("DirectionMap"), variable("SelectedDirection"))
route_url_id = encoded(ref(selected_route_id))
# Un nouvel appel contraint cette fois par route, station et donc direction.
specific_url = text(ROOT, "/routes/", ref(route_url_id), "/stop_areas/",
                    ref(safe_stop), "/stop_schedules?count=10&items_per_schedule=2")
direction_response = fetch(specific_url)
filtered = dct(ref(direction_response), "stop_schedules")
no_selected = s.if_(ref(filtered), "has_no_value")
die("Je ne trouve pas de passage pour cette direction à cet arrêt.")
s.end_if(no_selected)

speak("Pour la ligne ", variable("LineCode"),
      ", à l'arrêt ", variable("SelectedStopName"),
      ", direction ", variable("SelectedDirection"), ", voici les prochains passages.")
each_selected = s.repeat_each(ref(filtered))
times = dct(repeat_item(), "date_times")
with_times = s.if_(ref(times), "has_any_value")
each_time = s.repeat_each(ref(times))
raw_time = dct(repeat_item(), "date_time")
spoken_hour = substitution(ref(raw_time),
                           r"^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})$",
                           "$4 heures $5")
human = substitution(ref(raw_time),
                     r"^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})$",
                     "$1-$2-$3 $4:$5:$6")
parsed = a("detect.date", WFInput=ref(human))
can_count = s.if_(ref(parsed), "has_any_value")
minutes = a("gettimebetweendates", WFTimeUntilFromDate=current_date(),
            WFInput=ref(parsed), WFTimeUntilUnit="Minutes")
rounded = a("round", WFInput=ref(minutes), WFRoundTo="Ones Place",
            WFRoundMode="Always Round Up")
future = s.if_(ref(rounded), "greater_or_equal", 0)
speak("Le prochain passage est dans ", ref(rounded),
      " minutes, à ", ref(spoken_hour), ".")
s.end_if(future)
s.otherwise(can_count)
speak("Un passage est annoncé à ", ref(spoken_hour), ".")
s.end_if(can_count)
s.end_repeat_each(each_time)
s.end_if(with_times)
s.end_repeat_each(each_selected)
speak("Voilà les horaires disponibles. Selon la ligne, ils peuvent être théoriques, "
      "et non une position en direct. Bonne route !")

if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "Transport-V2.unsigned.shortcut")
    out.parent.mkdir(parents=True, exist_ok=True)
    s.write(out)
    print("Transport V2", len(s.actions), "actions ->", out)
