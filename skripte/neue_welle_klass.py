#!/usr/bin/env python3
"""Zuordnung (`_klass_neu.json`) für eine neue Material-Welle aus der Ordnerstruktur.

Entscheidungen von Domenic (28.10.):
  - Stufe: alles E-Phase (die Grundforen) — die Ordner tragen EP-Marker, die Themen
    sind E-Phase-Lehrplan. Das Werkzeug schlug bei einem Teil GK vor; das steht als
    Hinweis in der Notiz, entschieden ist E-Phase.
  - Titel: Ordnername WÖRTLICH, "LB 3" bleibt dran.
  - Vier große Filme (>10 MB) werden nicht gepostet.
  - Nichts doppelt: Dateien, deren Inhalt schon im Server liegt, fallen aus dem
    Bündel; ist ein Thema komplett vorhanden, entsteht kein Post. Titelgleiche
    Themen behandelt post_neu selbst (Antwort im bestehenden Thread).

Aufruf:  python3 neue_welle_klass.py [--zeigen]
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import pathlib
import re
import sys

S = pathlib.Path(__file__).resolve().parent
PROJECT = S.parent
sys.path.insert(0, str(S))
import classify                                     # noqa: E402
from add_material import foren, resolve             # noqa: E402
from agy_discord import ATTACH_EXT, IMG_EXT, ist_sammeltitel   # noqa: E402
from neue_welle_plan import art_von                 # noqa: E402

BUNDLEBAR = {".pdf"} | IMG_EXT          # alles andere: Original als eigener Post
GRENZE = 9_400_000                      # Discord-Limit mit Reserve


def thash(t: str) -> str:
    return hashlib.sha256(re.sub(r"\W+", " ", (t or "").lower()).encode()).hexdigest()[:16]


def archiv_inhalte() -> set[str]:
    """Text-Hashes des Bestands (das ist, was im Server liegt)."""
    aus = set()
    for p in PROJECT.glob("_text_*.json"):
        if p.name == "_text_neu.json":
            continue
        for r in json.load(p.open()):
            if len(r.get("text") or "") >= 40:
                aus.add(thash(r["text"]))
    return aus


def titel_von(thema_pfad: list[str]) -> str:
    """Ordnername wörtlich, Ebenen mit ' – ' verbunden (`LB 3` bleibt stehen)."""
    t = " – ".join(x.strip() for x in thema_pfad)
    t = re.sub(r"\s*[-–]\s*", " - ", t)          # Bindestrich-Abstand vereinheitlichen
    t = re.sub(r"\s+", " ", t).strip(" -")
    return t[:100]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zeigen", action="store_true")
    args = ap.parse_args()

    kept = classify.load_kept("neu")
    gueltig = foren()
    vorhanden = archiv_inhalte()
    print(f"  {len(kept)} Dateien im Index (nach Inhalts-Dedup) | "
          f"{len(vorhanden)} verschiedene Inhalte im Server")

    gruppen: dict[tuple[str, list[str]], dict] = collections.defaultdict(
        lambda: {"buendel": [], "einzeln": [], "schon_da": [], "zu_gross": [],
                 "stufen_hinweis": collections.Counter()})
    for i, r in enumerate(kept):
        teile = pathlib.PurePath(r["rel"]).parts
        fach, *rest = teile[1:]                  # teile[0] = "neu"
        thema_pfad = rest[:-1] or ["(ohne Unterordner)"]
        g = gruppen[(fach, tuple(thema_pfad))]
        name, groesse = r["datei"], r.get("bytes", 0)
        endung = pathlib.Path(name).suffix.lower()
        if len(r.get("text") or "") >= 40 and thash(r["text"]) in vorhanden:
            g["schon_da"].append(name)
            continue
        if endung not in BUNDLEBAR and groesse > GRENZE:
            g["zu_gross"].append(name)           # Medien über 10 MB: nicht postbar
            continue
        (g["buendel"] if endung in BUNDLEBAR else g["einzeln"]).append((i, name))

    posts, uebersicht = [], []
    for (fach, thema_pfad), g in sorted(gruppen.items()):
        if not (g["buendel"] or g["einzeln"]):
            continue                              # Thema komplett vorhanden
        ziel, hinweis, _eindeutig = resolve(fach, gueltig)
        basis = ziel.split("-")[0]
        if ziel != basis:
            g["stufen_hinweis"][ziel] += 1
        ziel = basis                              # Entscheidung: alles E-Phase
        titel = titel_von(list(thema_pfad))
        # Zwei Fälle, in denen der Ordnername den Thread nicht benennen darf:
        #   (a) Dateien direkt im Fach-Ordner -> "(ohne Unterordner)" wäre Unsinn,
        #   (b) Behälter-Name wie "Mitschriften" / "Online - Aufgaben" / "Common
        #       mistakes" sagt nichts über den Inhalt (Domenics Auftrag; die erste
        #       Welle wurde dafür nachträglich aufgeräumt, siehe sammeltitel_umbau.py).
        # In beiden Fällen benennen die Dateien den Thread.
        if ist_sammeltitel(titel) or list(thema_pfad) == ["(ohne Unterordner)"]:
            alle = [n for _, n in g["buendel"]] + [n for _, n in g["einzeln"]]
            stamm = pathlib.Path(alle[0]).stem if alle else fach
            titel = stamm if len(alle) == 1 else f"{stamm} (+{len(alle) - 1} weitere)"
            titel = titel[:100]
        namen = [n for _, n in g["buendel"]] + [n for _, n in g["einzeln"]]
        art = art_von(namen, titel)
        notiz = f"aus {fach}/{ '/'.join(thema_pfad) }"
        if g["stufen_hinweis"]:
            notiz += f" | Werkzeug schlug {', '.join(g['stufen_hinweis'])} vor, gesetzt: E-Phase"
        if g["schon_da"]:
            notiz += f" | {len(g['schon_da'])} Datei(en) schon im Server, weggelassen"
        if g["zu_gross"]:
            notiz += f" | {len(g['zu_gross'])} Medium über 10 MB nicht gepostet"
        if g["buendel"]:
            posts.append({"ids": [i for i, _ in g["buendel"]], "ziel": ziel,
                          "kurs": "E-Phase", "thema": titel, "art": art,
                          "titel": titel, "notiz": notiz})
        for i, n in g["einzeln"]:
            posts.append({"ids": [i], "ziel": ziel, "kurs": "E-Phase",
                          "thema": titel, "art": art, "titel": f"{titel} - {n}"[:100],
                          "notiz": notiz + " | Original angehängt (nicht in PDF wandelbar)"})
        uebersicht.append({"fach": fach, "thema": titel, "ziel": ziel, "art": art,
                           "buendel": len(g["buendel"]), "einzeln": len(g["einzeln"]),
                           "schon_da": len(g["schon_da"]), "zu_gross": len(g["zu_gross"]),
                           "notiz": notiz})

    weg = {n for (f, t), g in gruppen.items() for n in g["schon_da"]}
    gross = {n for (f, t), g in gruppen.items() for n in g["zu_gross"]}
    print(f"\n  {len(posts)} Posts aus {len(uebersicht)} Themen")
    print(f"  Dateien: {sum(z['buendel'] + z['einzeln'] for z in uebersicht)} im Post | "
          f"{len(weg)} schon im Server (weggelassen) | {len(gross)} zu groß (weggelassen)")
    arten = collections.Counter(p["art"] for p in posts)
    ziele = collections.Counter(p["ziel"] for p in posts)
    print(f"  Art:    " + ", ".join(f"{k} {v}" for k, v in arten.most_common()))
    print(f"  Foren:  " + ", ".join(f"{k} {v}" for k, v in ziele.most_common()))
    themen_weg = [f"{f}/{t}" for (f, t), g in gruppen.items()
                  if not (g["buendel"] or g["einzeln"])]
    if themen_weg:
        print(f"  Themen komplett schon vorhanden (kein Post): {len(themen_weg)}")
        for t in themen_weg:
            print(f"     {t}")

    out = PROJECT / "_klass_neu.json"
    if not args.zeigen:
        out.write_text(json.dumps(posts, ensure_ascii=False, indent=1), encoding="utf-8")
        with (PROJECT / "_pruefen" / "welle_posts.csv").open("w", newline="",
                                                             encoding="utf-8") as fh:
            import csv as _csv
            w = _csv.DictWriter(fh, fieldnames=list(uebersicht[0].keys()), delimiter=";")
            w.writeheader()
            w.writerows(uebersicht)
        print(f"\n-> {out.name}  +  _pruefen/welle_posts.csv")
    if args.zeigen:
        for p in posts:
            print(f"  {p['ziel']:<12} {p['art']:<16} {len(p['ids'])}D  {p['titel'][:60]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
