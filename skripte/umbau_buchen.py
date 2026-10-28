#!/usr/bin/env python3
"""Trägt den Sammel-Titel-Umbau in die Manifeste nach.

Die Manifeste sind die Aufzeichnung dessen, was im Server liegt — nach dem Umbau
(neu anlegen, dann altes löschen) dürfen sie nicht weiter auf gelöschte Threads
zeigen, sonst ist jede spätere Prüfung wertlos.

Quellen: _pruefen/umbau_result.csv (neue Thread-IDs/URLs) und das LOESCHEN-Register
aus sammeltitel_umbau.py (alter Titel -> Ersatz). Kein zweites Register, keine
zweite Wahrheit.

Aufruf:  python3 umbau_buchen.py [--schreiben]
"""
from __future__ import annotations

import argparse
import csv
import pathlib
import sys
import unicodedata

S = pathlib.Path(__file__).resolve().parent
PROJECT = S.parent
sys.path.insert(0, str(S))
from sammeltitel_umbau import LOESCHEN, N              # noqa: E402

MANIFESTE = ["manifest_neu.result.csv", "manifest_biologie.result.csv",
             "manifest_chemie.result.csv"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--schreiben", action="store_true")
    args = ap.parse_args()

    # Ersatz-Register: (forum, alter Titel) -> [Ersatz-Titel ...]
    register = {(f, N(t)): [N(e) for e, _ in ersatz] for f, t, ersatz in LOESCHEN}

    # Neue Thread-IDs/URLs aus dem Umbau-Ergebnis (der erste Eintrag eines Titels
    # ist der Thread selbst, spätere sind Antworten darin).
    neu = {}
    for r in csv.DictReader((PROJECT / "_pruefen" / "umbau_result.csv").open(
            newline="", encoding="utf-8"), delimiter=";"):
        key = (r["ziel_kanal"], N(r["titel"]))
        if key not in neu or r["aktion"] == "created":
            neu.setdefault(key, r)

    geaendert, gesamt = 0, 0
    for name in MANIFESTE:
        p = PROJECT / name
        if not p.exists():
            continue
        rows = list(csv.DictReader(p.open(newline="", encoding="utf-8"), delimiter=";"))
        felder = list(rows[0].keys())
        for r in rows:
            gesamt += 1
            key = (r.get("ziel_kanal", ""), N(r.get("titel", "")))
            if key not in register:
                continue
            ersatz = register[key]
            ziel = neu.get((key[0], ersatz[0]))
            alt = r["titel"]
            hinweis = (f"Sammel-Titel '{alt}' ersetzt"
                       + (f" durch {ersatz[0]}" if len(ersatz) == 1
                          else f" — Inhalt aufgeteilt auf: {', '.join(ersatz)}"))
            r["titel"] = ersatz[0]
            if ziel:
                r["thread_id"] = ziel["thread_id"]
                r["url"] = ziel["url"]
            # Nur Spalten füllen, die es in DIESEM Manifest gibt: das Ergebnis-Manifest
            # von post_neu hat weder status noch notiz. Ein Schreibversuch mit fremden
            # Spalten hat die Datei beim ersten Lauf geleert — deshalb hier bedingt.
            if "status" in felder:
                r["status"] = "ersetzt"
            if "notiz" in felder:
                r["notiz"] = r.get("notiz", "") + f" | {hinweis}"
            geaendert += 1
            print(f"  {name}: [{key[0]}] '{alt}' -> '{ersatz[0]}' {ziel['thread_id'] if ziel else ''}")
        if args.schreiben:
            # Atomar schreiben: erst daneben, dann ersetzen. Ein Abbruch darf die
            # Aufzeichnung nicht halbfertig oder leer hinterlassen.
            tmp = p.with_suffix(".tmp")
            with tmp.open("w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=felder, delimiter=";")
                w.writeheader()
                w.writerows(rows)
            tmp.replace(p)

    # Gegenprobe: keine Zeile darf noch auf einen gelöschten Thread zeigen.
    weg = {"1564940191477665885", "1564940617229008927", "1564940874083733578",
           "1564943548703445013", "1564942189622984705", "1564942213341778003",
           "1564941773741101067", "1564945339008553042", "1558818205936386071",
           "1558818213897310270", "1558816991928914117"}
    rest = []
    for name in MANIFESTE:
        p = PROJECT / name
        if not p.exists():
            continue
        for r in csv.DictReader(p.open(newline="", encoding="utf-8"), delimiter=";"):
            if r.get("thread_id") in weg:
                rest.append(f"{name}: {r['datei'][:50]} -> {r['thread_id']}")
    print(f"\n  {geaendert} von {gesamt} Zeilen angepasst"
          + ("" if args.schreiben else "  (Probelauf — nichts geschrieben)"))
    print(f"  Zeilen, die noch auf gelöschte Threads zeigen: {len(rest)}")
    for r in rest:
        print(f"     {r}")
    return 0 if not rest else 1


if __name__ == "__main__":
    raise SystemExit(main())
