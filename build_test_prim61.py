#!/usr/bin/env python3
"""Petit diagnostic réel PRIM pour l'iPhone, sans stocker le jeton dans GitHub.
Il teste /places, /lines?filter=line.code=61, puis /lines/{id}/stop_areas.
"""
from pathlib import Path
import sys
from shortcutkit import Shortcut, ref, variable, text

BASE = "https://prim.iledefrance-mobilites.fr/marketplace/v2/navitia"
s=Shortcut("Test PRIM 61",color="Blue")
def a(name,**params):
    return s.action("is.workflow.actions."+name,**params)
def value(*pieces):
    return a("gettext",WFTextActionText=text(*pieces))
def dct(input,key):
    return a("getvalueforkey",WFInput=input,WFGetDictionaryValueType="Value",WFDictionaryKey=key)
def fetch(url):
    headers={
        "WFSerializationType":"WFDictionaryFieldValue",
        "Value":{"WFDictionaryFieldValueItems":[
            {"WFItemType":0,"WFKey":"apikey","WFValue":text(variable("PRIMTestKey"))},
            {"WFItemType":0,"WFKey":"Accept","WFValue":"application/json"}
        ]}
    }
    return a("downloadurl",WFURL=url,WFHTTPMethod="GET",WFHTTPHeaders=headers)
key=a("ask",WFInputType="Text",WFAskActionPrompt="Colle ta clé API PRIM ici (elle ne sera PAS publiée).")
a("setvariable",WFVariableName="PRIMTestKey",WFInput=ref(key))

check=fetch(BASE+"/places?q=Gare%20de%20Lyon&count=1")
places=dct(ref(check),"places")
placecount=a("count",Input=ref(places),WFCountType="Items")
a("showresult",Text=text("Test 1 : PRIM /places -> ",ref(placecount)," résultat(s). Si zéro, la clé ou la recherche est à examiner."))

lines=fetch(BASE+"/lines?filter=line.code%3D61&count=30")
list_lines=dct(ref(lines),"lines")
nlines=a("count",Input=ref(list_lines),WFCountType="Items")
a("showresult",Text=text("Test 2 : PRIM /lines?filter=line.code=61 -> ",ref(nlines)," ligne(s) trouvée(s)."))

first=a("getitemfromlist",WFInput=ref(list_lines),WFItemSpecifier="First Item")
lineid=dct(ref(first),"id")
linename=dct(ref(first),"name")
encoded=a("urlencode",WFEncodeMode="Encode",WFInput=ref(lineid))
a("showresult",Text=text("Ligne 61 de l'API : ",ref(linename),"\nIdentifiant : ",ref(lineid)))

stopurl=text(BASE,"/lines/",ref(encoded),"/stop_areas?count=100")
stops_response=fetch(stopurl)
stops=dct(ref(stops_response),"stop_areas")
stopcount=a("count",Input=ref(stops),WFCountType="Items")
a("showresult",Text=text("Test 3 : arrêts de cette ligne -> ",ref(stopcount)," arrêt(s)."))

# Échantillon de vrai nom d'arrêt renvoyé par l'API.
first_stop=a("getitemfromlist",WFInput=ref(stops),WFItemSpecifier="First Item")
stop_name=dct(ref(first_stop),"name")
a("showresult",Text=text("Premier arrêt reçu : ",ref(stop_name),
  "\nLe raccourci a réellement interrogé Île-de-France Mobilités. "
  "Ne m'envoie pas ta clé, seulement le résultat de ces tests."))

if __name__=="__main__":
    p=Path(sys.argv[1] if len(sys.argv)>1 else "Test-PRIM-61.unsigned.shortcut")
    p.parent.mkdir(parents=True,exist_ok=True)
    s.write(p)
    print("Test PRIM 61",len(s.actions),"actions ->",p)
