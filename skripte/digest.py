#!/usr/bin/env python3
"""Gruppen-Digest für die Klassifikation: pro Nachricht (= 1 Post) eine Übersicht
mit Text-Vorschau, Content-Hash und Ziel-Forum."""
import collections
import hashlib
import json
import pathlib
import re
import sys

PROJECT = pathlib.Path(__file__).resolve().parent.parent
src = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else PROJECT / "_text_geschichte.json"
data = json.loads(src.read_text(encoding="utf-8"))

NOISE = {"memes-agy", "chat-1-💌", "chat-2-💌", "allgemeines", "herzlich-willkommen",
         "diskussionen", "interessantes"}


def ziel(kanal: str, server: str) -> str:
    if kanal in NOISE:
        return ""
    fach = {"mathe": "mathematik"}.get(kanal, kanal)
    if fach.startswith(("gk-", "lk-")):
        kurs, rest = fach.split("-", 1)
        return f"{rest}-{kurs}"
    return fach if server.startswith("E-Phase") else f"{fach}-gk"


def clean(t: str) -> str:
    t = re.sub(r"\s+", " ", t or "")
    return t.strip()


for r in data:
    p = pathlib.Path(r["pfad"])
    r["hash"] = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else "?"
    r["ziel"] = ziel(r["kanal"], r["server"])

# Dedup: gleicher Inhalt -> nur die erste Zeile behalten, aber pro Ziel-Forum getrennt
seen: dict[tuple, dict] = {}
dupes = []
for r in sorted(data, key=lambda x: (x["zeit"], x["msg_id"])):
    key = (r["hash"], r["ziel"])
    if key in seen:
        dupes.append(r)
        continue
    seen[key] = r
keep = list(seen.values())

print(f"Dateien: {len(data)}  |  nach Dedup: {len(keep)}  |  entfernt: {len(dupes)}")
print(f"Ziel-Foren: {dict(collections.Counter(r['ziel'] for r in keep))}\n")

groups = collections.OrderedDict()
for r in sorted(keep, key=lambda x: (x["ziel"], x["zeit"])):
    groups.setdefault((r["ziel"], r["msg_id"]), []).append(r)

print(f"POST-GRUPPEN: {len(groups)}\n")
for i, ((zl, mid), items) in enumerate(groups.items(), 1):
    head = items[0]
    print(f"[{i:>3}] {zl or 'VERWERFEN':<16} {head['autor']:<12} {head['zeit'][:10]}  "
          f"{len(items)} Datei(en)  msg={mid}")
    if clean(head["msg_text"]):
        print(f"      MSG: {clean(head['msg_text'])[:180]}")
    for it in items:
        prev = clean(it["text"])[:150]
        print(f"      - {it['datei'][:52]:<52} {it['bytes']/1e6:6.1f}MB {it['typ']:<5} «{prev}»")
