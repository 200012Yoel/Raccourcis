#!/usr/bin/env python3
"""Transport V3 : Siri natif, lignes exactes et recherche souple des arrêts.

Ne dépend d'aucune action "Énoncer le texte". Les questions sont des actions
Demander une entrée / Choisir dans le menu et la réponse finale est Afficher résultat.
La voix éventuelle est celle de Siri lorsque le raccourci est lancé par Siri.

Clé PRIM : demandée par le raccourci sur l'iPhone, jamais dans le code.
"""
from pathlib import Path
import sys
from shortcutkit import Shortcut, ref, variable, text, current_date, repeat_item

ROOT = "https://prim.iledefrance-mobilites.fr/marketplace/v2/navitia"
s = Shortcut("Transport", color="Blue")

def act(name, **kw):
    return s.action("is.workflow.actions." + name, **kw)

def ask(question):
    return act("ask", WFInputType="Text", WFAskActionPrompt=question)

def result(*parts):
    return act("showresult", Text=text(*parts))

def value(*parts):
    return act("gettext", WFTextActionText=text(*parts))

def setvar(name, output):
    return act("setvariable", WFVariableName=name, WFInput=ref(output))

def dct(obj, key):
    return act("getvalueforkey", WFInput=obj,
               WFGetDictionaryValueType="Value", WFDictionaryKey=key)

def regexp_replace(obj, pattern, replacement, ignore_case=False):
    return act("text.replace", WFInput=obj, WFReplaceTextFind=pattern,
               WFReplaceTextReplace=replacement,
               WFReplaceTextRegularExpression=True,
               WFReplaceTextCaseSensitive=not ignore_case)

def encoded(obj):
    return act("urlencode", WFEncodeMode="Encode", WFInput=obj)

def empty_dict():
    return act("detect.dictionary", WFInput=ref(value("{}")))

def set_dictionary_item(dictionary, key, val):
    return act("setvalueforkey", WFDictionary=variable(dictionary),
               WFDictionaryKey=key, WFDictionaryValue=val)

def stop(*parts):
    result(*parts)
    act("exit")

def request(url):
    headers = {
        "WFSerializationType": "WFDictionaryFieldValue",
        "Value": {"WFDictionaryFieldValueItems": [
            {"WFItemType": 0, "WFKey": "apikey", "WFValue": text(variable("IDFMKey"))},
            {"WFItemType": 0, "WFKey": "Accept", "WFValue": "application/json"}
        ]}
    }
    return act("downloadurl", WFURL=url, WFHTTPMethod="GET",
               WFHTTPHeaders=headers)

def match_stops(query, stops):
    """Appliquer une recherche souple sur les SEULS arrêts de la ligne."""
    # Ex. "Mairie Gambetta" -> Gambetta
    # "mairie du 20e" -> 20e ; "gare de Lyon" -> Lyon
    cleaned = regexp_replace(query,
        r"(?i)\b(?:mairie|gare|station|arret|arrêt|bus|de|du|des|la|le|les|d|l|à|au|aux)\b",
        " ")
    trimmed = regexp_replace(ref(cleaned), r"^\s+|\s+$", "")
    gap_regex = regexp_replace(ref(trimmed), r"\s+", ".*")
    pattern = value("(?i)", ref(gap_regex))
    mapping = empty_dict()
    setvar("FoundStopMap", mapping)
    each = s.repeat_each(stops)
    name = dct(repeat_item(), "name")
    identifier = dct(repeat_item(), "id")
    hit = act("text.match", WFMatchTextPattern=ref(pattern), WFInput=ref(name))
    cond = s.if_(ref(hit), "has_any_value")
    new_map = set_dictionary_item("FoundStopMap", ref(name), ref(identifier))
    setvar("FoundStopMap", new_map)
    s.end_if(cond)
    s.end_repeat_each(each)
    return act("getvalueforkey", WFInput=variable("FoundStopMap"),
               WFGetDictionaryValueType="All Keys")

# 1. Valider et stocker la clé API sur le téléphone uniquement.
key = act("getstoredcontent", WFStoredContentKey="IDFM_PRIM_KEY",
          WFStoredContentGlobalValue=False)
first_run = s.if_(ref(key), "has_no_value")
key_input = ask("Première utilisation. Colle ici ta clé API PRIM.")
setvar("IDFMKey", key_input)
probe = request(ROOT + "/places?q=Gare%20de%20Lyon&count=1")
probe_places = dct(ref(probe), "places")
bad_key = s.if_(ref(probe_places), "has_no_value")
stop("La clé API n'a pas été acceptée. Vérifie ta connexion et ta clé.")
s.end_if(bad_key)
act("setstoredcontent", WFStoredContentKey="IDFM_PRIM_KEY",
    WFStoredContentGlobalValue=False, WFInput=variable("IDFMKey"))
s.otherwise(first_run)
setvar("IDFMKey", key)
s.end_if(first_run)

# 2. Menu natif Siri / Shortcuts. Aucune synthèse vocale ajoutée.
modes = [
    ("Métro", "Metro", "Quelle ligne de métro ? Exemples : 1, 6, 11."),
    ("Tramway", "Tramway", "Quelle ligne de tram ? Exemples : T1, T2, T3b."),
    ("Bus de Paris", "Bus", "Quelle ligne de bus parisien ? Exemples : 20, 26, 48, 60, 61."),
    ("Bus de banlieue", "Bus", "Quelle ligne de bus de banlieue ? Donne son numéro."),
    ("RER", "RapidTransit", "Quelle ligne de RER ? A, B, C, D ou E."),
    ("Transilien", "LocalTrain", "Quelle ligne de Transilien ? H, J, L, N, P, R, U ou V."),
]
transport_menu = s.choose_from_menu(
    "Quel transport ? Métro, tramway, bus Paris, bus banlieue, RER ou Transilien ?",
    [m[0] for m in modes])
for title, physical, prompt in modes:
    s.menu_item(transport_menu, title)
    setvar("Mode", value(physical))
    setvar("ModeName", value(title))
    line = ask(prompt)
    # Autorise "bus 61", "ligne 61", "RER A", et "61".
    clean_line = regexp_replace(ref(line),
       r"(?i)\b(?:ligne|bus|rer|métro|metro|tramway|tram|transilien)\b", " ")
    trim_line = regexp_replace(ref(clean_line), r"^\s+|\s+$", "")
    setvar("Line", trim_line)
s.end_menu(transport_menu)

# 3. Recherche de ligne précise dans le mode exact.
line_code = encoded(variable("Line"))
line_url = text(ROOT, "/physical_modes/physical_mode%3A", variable("Mode"),
                "/lines?filter=line.code%3D", ref(line_code), "&count=80")
answer = request(line_url)
lines = dct(ref(answer), "lines")
none_lines = s.if_(ref(lines), "has_no_value")
stop("Je ne trouve pas la ligne ", variable("Line"), " en ", variable("ModeName"), ".")
s.end_if(none_lines)

line_map = empty_dict()
setvar("LineMap", line_map)
loop = s.repeat_each(ref(lines))
name = dct(repeat_item(), "name")
identifier = dct(repeat_item(), "id")
label = value(variable("Line"), " — ", ref(name))
mapped = set_dictionary_item("LineMap", ref(label), ref(identifier))
setvar("LineMap", mapped)
s.end_repeat_each(loop)
line_keys = act("getvalueforkey", WFInput=variable("LineMap"),
                WFGetDictionaryValueType="All Keys")
number_lines = act("count", Input=ref(line_keys), WFCountType="Items")
multiple = s.if_(ref(number_lines), "greater_than", 1)
selected = act("choosefromlist", WFInput=ref(line_keys),
               WFChooseFromListActionPrompt="Choisis ta ligne")
setvar("LineChosen", selected)
s.otherwise(multiple)
single = act("getitemfromlist", WFInput=ref(line_keys), WFItemSpecifier="First Item")
setvar("LineChosen", single)
s.end_if(multiple)
line_id = dct(variable("LineMap"), variable("LineChosen"))
line_encoded = encoded(ref(line_id))

# 4. Récupérer tous les arrêts DESSERVIS par cette ligne.
# Évite les 30 "Place des Fêtes" de la recherche globale.
stops_url = text(ROOT, "/lines/", ref(line_encoded), "/stop_areas?count=500")
stops_response = request(stops_url)
line_stops = dct(ref(stops_response), "stop_areas")
no_stop_data = s.if_(ref(line_stops), "has_no_value")
stop("Impossible de récupérer les arrêts de cette ligne.")
s.end_if(no_stop_data)

how = s.choose_from_menu("Quel arrêt veux-tu consulter ?", [
    "Dire ou saisir un arrêt", "Arrêt proche de ma position"])
s.menu_item(how, "Dire ou saisir un arrêt")
station = ask("À quel arrêt ? Exemples : Mairie du 20e, Gambetta, Gare de Lyon.")
setvar("StopQuery", station)
s.menu_item(how, "Arrêt proche de ma position")
# Ne devine pas le nom de l'arrêt à partir d'une rue :
# la saisie courte est plus fiable en version vocale.
near = ask("Dis le nom de l'arrêt proche de toi.")
setvar("StopQuery", near)
s.end_menu(how)

keys = match_stops(variable("StopQuery"), ref(line_stops))
none_match = s.if_(ref(keys), "has_no_value")
again = ask("Aucun arrêt correspondant sur cette ligne. Réessaie avec un mot important du nom.")
setvar("StopQuery", again)
keys = match_stops(variable("StopQuery"), ref(line_stops))
s.end_if(none_match)

no_match = s.if_(ref(keys), "has_no_value")
stop("Aucun arrêt de la ligne ", variable("Line"),
     " ne correspond à ce nom. Essaie un autre arrêt.")
s.end_if(no_match)

count_stop = act("count", Input=ref(keys), WFCountType="Items")
many_stops = s.if_(ref(count_stop), "greater_than", 1)
chosen_stop = act("choosefromlist", WFInput=ref(keys),
                  WFChooseFromListActionPrompt="Choisis le bon arrêt")
setvar("StopName", chosen_stop)
s.otherwise(many_stops)
only_stop = act("getitemfromlist", WFInput=ref(keys), WFItemSpecifier="First Item")
setvar("StopName", only_stop)
s.end_if(many_stops)
stop_id = dct(variable("FoundStopMap"), variable("StopName"))
safe_stop_id = encoded(ref(stop_id))

# 5. Identifier les directions réellement disponibles à cet arrêt.
stop_url = text(ROOT, "/lines/", ref(line_encoded), "/stop_areas/",
                ref(safe_stop_id),
                "/stop_schedules?count=100&items_per_schedule=3&depth=2")
schedules_result = request(stop_url)
schedules = dct(ref(schedules_result), "stop_schedules")
no_schedules = s.if_(ref(schedules), "has_no_value")
stop("Aucun passage annoncé pour la ligne ", variable("Line"),
     " à ", variable("StopName"), ".")
s.end_if(no_schedules)

direction_map = empty_dict()
setvar("DirectionMap", direction_map)
for_each = s.repeat_each(ref(schedules))
display = dct(repeat_item(), "display_informations")
direction_name = dct(ref(display), "direction")
route_id = dct(repeat_item(), "route.id")
# Plusieurs quais d'un même terminus : une seule entrée de menu par direction.
new_direction_map = set_dictionary_item("DirectionMap", ref(direction_name), ref(route_id))
setvar("DirectionMap", new_direction_map)
s.end_repeat_each(for_each)

dir_keys = act("getvalueforkey", WFInput=variable("DirectionMap"),
               WFGetDictionaryValueType="All Keys")
no_dirs = s.if_(ref(dir_keys), "has_no_value")
stop("Je n'ai pas trouvé de direction disponible.")
s.end_if(no_dirs)
dir_count = act("count", Input=ref(dir_keys), WFCountType="Items")
multiple_dirs = s.if_(ref(dir_count), "greater_than", 1)
dir_selected = act("choosefromlist", WFInput=ref(dir_keys),
                   WFChooseFromListActionPrompt="Vers quel terminus ?")
setvar("DirectionName", dir_selected)
s.otherwise(multiple_dirs)
only_dir = act("getitemfromlist", WFInput=ref(dir_keys), WFItemSpecifier="First Item")
setvar("DirectionName", only_dir)
s.end_if(multiple_dirs)

route_id = dct(variable("DirectionMap"), variable("DirectionName"))
safe_route = encoded(ref(route_id))
route_url = text(ROOT, "/routes/", ref(safe_route), "/stop_areas/",
                 ref(safe_stop_id),
                 "/stop_schedules?count=12&items_per_schedule=3")
route_result = request(route_url)
route_schedules = dct(ref(route_result), "stop_schedules")
no_passage = s.if_(ref(route_schedules), "has_no_value")
stop("Aucun passage dans cette direction pour le moment.")
s.end_if(no_passage)

# 6. Ne préparer qu'UNE seule réponse finale, lue naturellement par Siri
# quand le raccourci a été lancé avec Siri.
heading = value("Ligne ", variable("Line"), " à ", variable("StopName"),
                ". Direction ", variable("DirectionName"), ".")
setvar("TextResult", heading)
each_schedule = s.repeat_each(ref(route_schedules))
times = dct(repeat_item(), "date_times")
available = s.if_(ref(times), "has_any_value")
each_date = s.repeat_each(ref(times))
date_text = dct(repeat_item(), "date_time")
time_clean = regexp_replace(ref(date_text),
        r"^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})$",
        "$4:$5")
human_date = regexp_replace(ref(date_text),
        r"^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})$",
        "$1-$2-$3 $4:$5:$6")
parsed = act("detect.date", WFInput=ref(human_date))
valid_date = s.if_(ref(parsed), "has_any_value")
minutes = act("gettimebetweendates", WFTimeUntilFromDate=current_date(),
              WFInput=ref(parsed), WFTimeUntilUnit="Minutes")
rounded = act("round", WFInput=ref(minutes), WFRoundTo="Ones Place",
              WFRoundMode="Always Round Up")
item = value("Passage dans environ ", ref(rounded), " minutes, à ", ref(time_clean), ".")
setvar("LineOfResult", item)
s.otherwise(valid_date)
item = value("Passage prévu à ", ref(time_clean), ".")
setvar("LineOfResult", item)
s.end_if(valid_date)
act("appendvariable", WFVariableName="Results", WFInput=variable("LineOfResult"))
s.end_repeat_each(each_date)
s.end_if(available)
s.end_repeat_each(each_schedule)

have_passages = s.if_(variable("Results"), "has_any_value")
joined = act("text.combine", WFInput=variable("Results"),
             WFTextSeparator="New Lines")
result(variable("TextResult"), "\n", ref(joined),
       "\nLes horaires peuvent être théoriques et non en temps réel.")
s.otherwise(have_passages)
stop("Aucun prochain horaire n'est disponible pour cette direction.")
s.end_if(have_passages)

if __name__ == "__main__":
    path = Path(sys.argv[1] if len(sys.argv)>1 else "Transport-V3.unsigned.shortcut")
    path.parent.mkdir(parents=True, exist_ok=True)
    s.write(path)
    print(f"Transport V3 {len(s.actions)} actions -> {path}")
