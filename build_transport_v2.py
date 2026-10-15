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

def die(message):
    speak(message)
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
name_response = ask("Nom de la station ou de l'arrêt. Par exemple Botzaris.")
safe_station = encoded(ref(name_response))
search_url = text(ROOT, "/places?q=", ref(safe_station),
                  "&count=30&type%5B%5D=stop_area")
places = fetch(search_url)
found_places = dct(ref(places), "places")
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

# Le même nom peut exister pour plusieurs arrêts. Proposer de vrais identifiants.
each_stop = s.repeat_each(variable("CandidateStops"))
stop_area = dct(repeat_item(), "stop_area")
stopname = dct(ref(stop_area), "name")
stopid = dct(ref(stop_area), "id")
label = t(ref(stopname), "  •  ", ref(stopid))
a("appendvariable", WFVariableName="StopChoices", WFInput=ref(label))
s.end_repeat_each(each_stop)

stop_selected = a("choosefromlist", WFInput=variable("StopChoices"),
                  WFChooseFromListActionPrompt="Choisis ton arrêt sur cette ligne")
station_id = substitution(ref(stop_selected), "^.*  •  ", "")
safe_stop = encoded(ref(station_id))

# E. Navitia /stop_schedules regroupe les horaires PAR DIRECTION (route).
# Filtrage serveur par vraie ligne + arrêt => pas de mélanges d'autres lignes.
schedule_url = text(ROOT, "/lines/", ref(safe_line), "/stop_areas/",
                    ref(safe_stop), "/stop_schedules?count=2&data_freshness=realtime")
sched_reply = fetch(schedule_url)
schedules = dct(ref(sched_reply), "stop_schedules")
not_available = s.if_(ref(schedules), "has_no_value")
die("Aucun horaire n'est disponible pour cette ligne à cet arrêt. "
    "Essaie un autre arrêt de la ligne.")
s.end_if(not_available)

speak("Voici les prochains passages de la ligne ", variable("LineCode"),
      " à ton arrêt, dans chaque direction disponible.")
each_direction = s.repeat_each(ref(schedules))
display = dct(repeat_item(), "display_informations")
direction_name = dct(ref(display), "direction")
dates = dct(repeat_item(), "date_times")
has_dates = s.if_(ref(dates), "has_any_value")
speak("Direction ", ref(direction_name), ".")
each_time = s.repeat_each(ref(dates))
raw_time = dct(repeat_item(), "date_time")
freshness = dct(repeat_item(), "data_freshness")
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
spoken = t("Passage dans environ ", ref(rounded), " minutes, à ", ref(spoken_hour))
s.otherwise(can_count)
spoken = t("Passage annoncé à ", ref(spoken_hour))
s.end_if(can_count)
speak(ref(spoken))
s.end_repeat_each(each_time)
s.end_if(has_dates)
s.end_repeat_each(each_direction)
speak("Voilà les horaires disponibles. Selon la ligne, ils peuvent être théoriques, "
      "et non une position en direct. Bonne route !")

if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "Transport-V2.unsigned.shortcut")
    out.parent.mkdir(parents=True, exist_ok=True)
    s.write(out)
    print("Transport V2", len(s.actions), "actions ->", out)
