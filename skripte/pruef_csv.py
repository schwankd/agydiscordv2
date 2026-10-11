#!/usr/bin/env python3
"""Prüf-Liste: alle auffälligen Dateien einer Fach-Welle als CSV + Dateikopien.

Kategorisiert nach `notiz` aus manifest_<match>.csv:
  1 Rechte/§4        – §4, OFFIZIELL, Fremd
  2 kein Lerninhalt  – Screenshots, Termine, unbrauchbar
  3 OCR unklar       – Handschrift/Bild nicht lesbar
  4 Hinweis          – Mengen-/Struktur-Notizen (unkritisch)

Schreibt problematisch_<match>.csv und aktualisiert die Gesamtliste problematisch.csv.
Kopien liegen in _pruefen/ (Dateiname trägt das Fach als Präfix).

Aufruf:
    python3 pruef_csv.py --match englisch
    python3 pruef_csv.py --match mathe
"""
from __future__ import annotations

import argparse
import collections
import csv
import pathlib
import shutil

PROJECT = pathlib.Path(__file__).resolve().parent.parent
PRUEF = PROJECT / "_pruefen"
COLS = ["kategorie", "fach", "kurs", "art", "titel", "notiz", "datei",
        "aktion", "thread_url", "lokal"]


def kategorie(notiz: str) -> str:
    n = notiz.lower()
    if "§4" in notiz or "offiziell" in n or "fremd" in n:
        return "1 Rechte/§4"
    if "kein lerninhalt" in n or "unbrauchbar" in n:
        return "2 kein Lerninhalt"
    if "ocr" in n:
        return "3 OCR unklar"
    return "4 Hinweis"


def build(match: str) -> list[dict]:
    man = PROJECT / f"manifest_{match}.csv"
    res_path = PROJECT / f"manifest_{match}.result.csv"
    if not man.exists():
        raise SystemExit(f"fehlt: {man}")
    res = {}
    if res_path.exists():
        res = {r["datei"]: r for r in csv.DictReader(
            res_path.open(newline="", encoding="utf-8"), delimiter=";")}

    PRUEF.mkdir(exist_ok=True)
    out = []
    for r in csv.DictReader(man.open(newline="", encoding="utf-8"), delimiter=";"):
        if not r.get("notiz"):
            continue
        src = PROJECT / "sortiert" / r["datei"]
        if src.exists():
            shutil.copy2(src, PRUEF / r["datei"])
        r2 = res.get(r["datei"], {})
        out.append({
            "kategorie": kategorie(r["notiz"]), "fach": r["fach"], "kurs": r["kurs"],
            "art": r["art"], "titel": r["titel"], "notiz": r["notiz"], "datei": r["datei"],
            "aktion": r2.get("aktion", ""), "thread_url": r2.get("url", ""),
            "lokal": f"_pruefen/{r['datei']}",
        })
    out.sort(key=lambda x: x["kategorie"])
    write(PROJECT / f"problematisch_{match}.csv", out)
    return out


def write(path: pathlib.Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--match", required=True)
    args = ap.parse_args()

    rows = build(args.match)
    print(f"problematisch_{args.match}.csv: {len(rows)} Zeilen "
          + str(dict(collections.Counter(r["kategorie"] for r in rows))))

    # Gesamtliste über alle Fächer
    alle: list[dict] = []
    for p in sorted(PROJECT.glob("problematisch_*.csv")):
        alle += list(csv.DictReader(p.open(newline="", encoding="utf-8"), delimiter=";"))
    write(PROJECT / "problematisch.csv", alle)
    print(f"problematisch.csv: {len(alle)} Zeilen aus "
          f"{len(list(PROJECT.glob('problematisch_*.csv')))} Fachlisten")
    print(f"_pruefen/: {len(list(PRUEF.glob('*')))} Dateien "
          f"({sum(f.stat().st_size for f in PRUEF.glob('*') if f.is_file())/1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
