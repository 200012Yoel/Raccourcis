#!/usr/bin/env python3
"""Signer un raccourci sans compte iCloud GitHub, via des services tiers.

Aucune clé IDFM ni donnée utilisateur n'est incluse dans les .shortcut construits.
Les fichiers non signés sont transmis à un service externe de signature.
Ne pas utiliser ce script pour des raccourcis contenant des identifiants privés.
"""
import json
import mimetypes
import pathlib
import plistlib
import sys
import time
import urllib.error
import urllib.request
import uuid


def request(url, content, headers):
    req = urllib.request.Request(url, data=content, method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=35) as res:
        data = res.read()
    if not data.startswith(b"AEA1"):
        raise RuntimeError(f"Réponse non signée : {data[:160]!r}")
    return data


def shortcuty(source):
    boundary = "----TransportIDFM" + uuid.uuid4().hex
    original = source.read_bytes()
    head = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="Transport.shortcut"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode()
    multipart = head + original + f"\r\n--{boundary}--\r\n".encode()
    return request(
        "https://sign.shortcuty.app/api/v1/sign",
        multipart,
        {"Content-Type": f"multipart/form-data; boundary={boundary}",
         "User-Agent": "TransportIDFM-github-actions/1.0"}
    )


def scrub_nones(value):
    # Binary plist handles None, XML plist does not. Remove unsupported plist nulls.
    if isinstance(value, dict):
        return {k: scrub_nones(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [scrub_nones(v) for v in value if v is not None]
    return value


def hubsign(source):
    workflow = scrub_nones(plistlib.loads(source.read_bytes()))
    xml = plistlib.dumps(workflow, fmt=plistlib.FMT_XML).decode("utf-8")
    payload = json.dumps({"shortcutName": "Transport", "shortcut": xml}).encode()
    return request(
        "https://hubsign.routinehub.services/sign",
        payload,
        {"Content-Type": "application/json",
         "Origin": "https://routinehub.co",
         "Referer": "https://routinehub.co/",
         "User-Agent": "TransportIDFM-github-actions/1.0"}
    )


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Utilisation : python sign_remote.py INPUT.unsigned.shortcut OUTPUT.shortcut")
    source = pathlib.Path(sys.argv[1])
    target = pathlib.Path(sys.argv[2])
    # Vérifier qu'il s'agit bien d'un workflow Apple Shortcuts valide.
    workflow = plistlib.loads(source.read_bytes())
    if not workflow.get("WFWorkflowActions"):
        raise ValueError("Fichier sans actions de raccourci")
    failures = []
    attempts = [
        ("Shortcuty #1", shortcuty, 0),
        ("Shortcuty #2", shortcuty, 5),
        ("Shortcuty #3", shortcuty, 10),
        ("HubSign", hubsign, 0),
    ]
    for label, signer, pause in attempts:
        try:
            if pause:
                time.sleep(pause)
            signed = signer(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(signed)
            assert target.read_bytes().startswith(b"AEA1")
            print(f"Signature distante OK ({label}) : {target} ({len(signed)} octets)")
            return
        except Exception as exc:
            failures.append(f"{label}: {type(exc).__name__}: {exc}")
            print(f"Échec signature via {label}: {type(exc).__name__}: {exc}",
                  file=sys.stderr)
    raise RuntimeError("Aucun service distant n'a signé le fichier : " + "; ".join(failures))


if __name__ == "__main__":
    main()
