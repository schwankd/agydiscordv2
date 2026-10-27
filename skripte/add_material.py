#!/usr/bin/env python3
"""Neues Material indexieren — Ablage in `eingang/neu/<forum>/`.

Der Ordnername ist das Ziel-Forum (z. B. `mathematik-gk`, `geschichte`, `deutsch-lk`).
Damit läuft dieselbe Kette wie beim Archiv-Material:

    add_material.py  ->  extract_text.py --match <forum>  ->  classify.py  ->  post_neu.py

Schreibt `eingang/_index_neu.csv` mit den gleichen Spalten wie das Archiv-Index.
Bereits indexierte Dateien werden nicht doppelt eingetragen.

Aufruf:
    python3 add_material.py             # indexieren
    python3 add_material.py --zeigen    # nur anzeigen (schreibt nichts)
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from agy_discord import CONTAINER_EXT  # noqa: E402

PROJECT = pathlib.Path(__file__).resolve().parent.parent
NEU = PROJECT / "eingang" / "neu"
INDEX = PROJECT / "eingang" / "_index_neu.csv"
COLS = ["server", "kanal", "thread", "nachricht_id", "zeit", "autor", "dateiname",
        "bytes", "gespeichert", "text", "embed_urls", "fehler"]
SERVER = "neu (direkt)"      # eigener Server-Kennwert: kanal ist hier das Ziel-Forum


def foren() -> set[str]:
    pfad = PROJECT / "foren-map.resolved.csv"
    return {r["Forum_Kanal"] for r in
            csv.DictReader(pfad.open(newline="", encoding="utf-8"), delimiter=";")}


def bekannt() -> set[str]:
    if not INDEX.exists():
        return set()
    return {r["gespeichert"] for r in
            csv.DictReader(INDEX.open(newline="", encoding="utf-8"), delimiter=";")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zeigen", action="store_true", help="nur anzeigen, nichts schreiben")
    args = ap.parse_args()

    if not NEU.exists():
        NEU.mkdir(parents=True)
        print(f"angelegt: {NEU.relative_to(PROJECT)}")

    gueltig = foren()
    schon = bekannt()
    ordner = sorted(p for p in NEU.iterdir() if p.is_dir())
    lose = sorted(p.name for p in NEU.iterdir()
                  if p.is_file() and not p.name.startswith(".") and p.suffix.lower() != ".md")

    if lose:
        print(f"\n  !! {len(lose)} Datei(en) liegen DIREKT in neu/ — ohne Fach-Ordner kein Ziel:")
        for n in lose[:10]:
            print(f"       {n}")
        if len(lose) > 10:
            print(f"       ... und {len(lose) - 10} weitere")
        print(f"     -> in einen Ordner verschieben, z. B. neu/mathematik-gk/")

    if not ordner:
        print(f"\nNoch nichts ablegbar: lege einen Ordner je Ziel-Forum an, z. B.:")
        print(f"  {NEU.relative_to(PROJECT)}/mathematik-gk/")
        print(f"  {NEU.relative_to(PROJECT)}/geschichte/")
        print(f"\nGültige Ordnernamen: {', '.join(sorted(gueltig))}")
        return 1 if lose else 0

    neue_zeilen, unbekannt = [], []
    for d in ordner:
        if d.name not in gueltig:
            unbekannt.append(d.name)
            continue
        dateien = sorted(p for p in d.rglob("*") if p.is_file()
                         and not p.name.startswith(".")
                         and p.suffix.lower() not in CONTAINER_EXT)
        for p in dateien:
            if str(p) in schon:
                continue
            neue_zeilen.append({
                "server": SERVER, "kanal": d.name, "thread": "", "nachricht_id": "",
                "zeit": dt.datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds"),
                "autor": "", "dateiname": p.name, "bytes": p.stat().st_size,
                "gespeichert": str(p), "text": "", "embed_urls": "", "fehler": "",
            })
        if dateien:
            print(f"  {d.name:<18} {len(dateien):>3} Datei(en)  "
                  f"({sum(p.stat().st_size for p in dateien) / 1e6:.1f} MB)")

    for name in unbekannt:
        print(f"  !! unbekannter Ordner: '{name}' — nicht in foren-map.resolved.csv")

    if not neue_zeilen:
        print("\nNichts Neues zu indexieren.")
        return 0 if not unbekannt else 1

    print(f"\n{len(neue_zeilen)} neue Datei(en)" + (" [ZEIGEN]" if args.zeigen else ""))
    if args.zeigen:
        for r in neue_zeilen:
            print(f"   {r['kanal']:<18} {r['dateiname']}")
        return 0

    neu = not INDEX.exists()
    with INDEX.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, delimiter=";")
        if neu:
            w.writeheader()
        w.writerows(neue_zeilen)
    print(f"-> {INDEX.relative_to(PROJECT)}")
    print(f"\nWeiter mit:  python3 extract_text.py --match <forum>")
    return 0 if not unbekannt else 1


if __name__ == "__main__":
    raise SystemExit(main())
