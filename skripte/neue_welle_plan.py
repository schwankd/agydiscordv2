#!/usr/bin/env python3
"""Plan für eine neue Material-Welle auf THEMEN-Ebene (`_pruefen/welle_plan.csv`).

Hintergrund: Beim Archiv-Material kam die Themengruppierung aus einer Klassifikation,
die ich aus dem Inhalt gebaut habe. Bei Domenics neuem Material liefert die
**Ordnerstruktur** die Gruppe schon (`<Fach>/<Thema>/…`) — sie ist von Hand gepflegt
und damit verlässlicher als jede Inhaltsclusterung. Ein Themen-Ordner = ein Post.

Das Skript entscheidet NICHTS endgültig, es legt den Vorschlag offen: Fach aus dem
Ordner, Stufe aus dem Archiv-Beleg (zuordnung_vorschlag.csv) bzw. aus den
E-Phase-Markern der Ordnernamen (`EP LB1`, `GEO-E-LB1`), Art aus den Dateinamen.
Gepostet wird erst nach der Vorschau.

Aufruf:  python3 neue_welle_plan.py [--zeigen]
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import pathlib
import re

PROJECT = pathlib.Path(__file__).resolve().parent.parent
NEU = PROJECT / "eingang" / "neu"
TEXT = PROJECT / "_text_neu.json"
VORSCHLAG = PROJECT / "zuordnung_vorschlag.csv"
AUS = PROJECT / "_pruefen" / "welle_plan.csv"

# Art aus Dateinamen. Reihenfolge zählt: erst das Spezifische.
ART_REGELN = [
    ("Klausur/Test", r"\btest\b|klausur|klassenarbeit|lernkontrolle|schulaufgabe|\bEB\b|\bKA\b"),
    ("Hausaufgabe", r"aufgab|übung|uebung|exercis|worksheet|arbeitsblatt|\bAbl\b|\bUE\b|homework|\bHA\b|worksheet"),
    ("Zusammenfassung", r"zusammenfassung|übersicht|uebersicht|hefter|mitschrift|lernkartei|"
                        r"lernkarte|\bPPT\b|merkblatt|leitfaden|skript|protokoll|summary"),
]


def art_von(namen: list[str], thema: str) -> str:
    """Art aus den Dateinamen des Themen-Ordners, sonst Sonstiges."""
    for art, muster in ART_REGELN:
        treffer = sum(1 for n in namen if re.search(muster, n, re.IGNORECASE))
        if treffer >= max(1, len(namen) // 2):        # Mehrheit entscheidet
            return art
    for art, muster in ART_REGELN:                     # sonst: irgendein Treffer
        if re.search(muster, thema, re.IGNORECASE):
            return art
    return "Sonstiges"


def thema_saeubern(thema: str) -> str:
    """`LB 3 - Ökologie` -> `Ökologie`; der Fachname steht schon im Forum."""
    t = re.sub(r"^(LB|Lernbereich)\s*\d+(\.\d+)?\s*[-–]\s*", "", thema, flags=re.IGNORECASE)
    t = re.sub(r"^(GEO|CH|BIO|PH|MA|DE|EN|FR)-E-?", "", t, flags=re.IGNORECASE)
    t = re.sub(r"^\d+(\.\d+)?\s*[-–.]?\s*", "", t)      # führende Numerierung
    return (t or thema).strip() or thema


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zeigen", action="store_true")
    args = ap.parse_args()

    belege = {}
    if VORSCHLAG.exists():
        for r in csv.DictReader(VORSCHLAG.open(newline="", encoding="utf-8"), delimiter=";"):
            z = (r["vorschlag"] or "").split(" + ")
            stufen = [x.split("-")[1].upper() if "-" in x else "E-PHASE" for x in z if x and x != "OFFEN"]
            belege[r["datei"]] = stufen

    gruppen: dict[tuple[str, str], dict] = collections.defaultdict(
        lambda: {"dateien": [], "belegt": 0, "offen": 0, "stufen": collections.Counter()})
    for r in json.load(TEXT.open()):
        rel = pathlib.Path(r["pfad"]).resolve().relative_to(NEU.resolve())
        fach, *rest = rel.parts
        thema = "/".join(rest[:-1]) or "(ohne Unterordner)"
        g = gruppen[(fach, thema)]
        g["dateien"].append((r["datei"], r.get("bytes", 0)))
        st = belege.get(r["datei"], [])
        if st:
            g["belegt"] += 1
            g["stufen"].update(st)
        else:
            g["offen"] += 1

    zeilen = []
    for (fach, thema), g in sorted(gruppen.items()):
        namen = [n for n, _ in g["dateien"]]
        mb = sum(b for _, b in g["dateien"]) / 1e6
        ep_marker = bool(re.search(r"\bEP\b|GEO-E|-E-LB|E-PHASE", fach + " " + thema, re.IGNORECASE))
        if g["stufen"]:
            vorschlag, quelle = g["stufen"].most_common(1)[0][0], "Archiv-Beleg"
        elif ep_marker:
            vorschlag, quelle = "E-PHASE", "E-Marker im Ordnernamen"
        else:
            vorschlag, quelle = "?", "kein Beleg — Entscheidung nötig"
        zeilen.append({
            "fach": fach, "thema": thema, "thema_klar": thema_saeubern(thema),
            "dateien": len(namen), "mb": round(mb, 1),
            "art": art_von(namen, thema), "stufe_vorschlag": vorschlag,
            "beleg": quelle, "belegt": g["belegt"], "offen": g["offen"],
            "belege_detail": ", ".join(f"{k}:{v}" for k, v in g["stufen"].most_common()),
            "groesste": max((b for _, b in g["dateien"]), default=0),
            # Nicht in eine Sammel-PDF gehören: Büro-/Medien-Originale
            "originale": " | ".join(n for n in namen
                                    if n.lower().endswith((".doc", ".docx", ".xls", ".xlsx",
                                                          ".xlsm", ".ppt", ".pptx", ".txt",
                                                          ".html", ".mp4", ".avi", ".wmv",
                                                          ".mp3", ".mov"))),
        })

    AUS.parent.mkdir(parents=True, exist_ok=True)
    with AUS.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(zeilen[0].keys()), delimiter=";")
        w.writeheader()
        w.writerows(zeilen)

    st = collections.Counter(z["stufe_vorschlag"] for z in zeilen)
    arten = collections.Counter(z["art"] for z in zeilen)
    print(f"  {len(zeilen)} Themen-Posts geplant "
          f"({sum(z['dateien'] for z in zeilen)} Dateien, "
          f"{sum(z['mb'] for z in zeilen):.0f} MB)")
    print(f"  Stufe: " + ", ".join(f"{k} {v}" for k, v in st.most_common()))
    print(f"  Art:   " + ", ".join(f"{k} {v}" for k, v in arten.most_common()))
    ohne = [z for z in zeilen if z["stufe_vorschlag"] == "?"]
    print(f"  ohne Stufen-Beleg: {len(ohne)} Themen")
    orig = [z for z in zeilen if z["originale"]]
    print(f"  Themen mit Original-Dateien (Büro/Medium, nicht in die Sammel-PDF): {len(orig)}")
    print(f"\n-> {AUS.relative_to(PROJECT)}")
    if args.zeigen:
        for z in zeilen:
            print(f"  {z['stufe_vorschlag']:<8} {z['art']:<17} "
                  f"{z['fach'] + '/' + z['thema']:<54.54} {z['dateien']:>3} Dateien {z['mb']:>7.1f}M")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
