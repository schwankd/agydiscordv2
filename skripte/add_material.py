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
import difflib
import pathlib
import re
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


def norm(s: str) -> str:
    """Ordnernamen vergleichbar machen: Kleinschreibung, Umlaute, Trenner."""
    s = (s.strip().lower()
         .replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss"))
    return re.sub(r"[\s_]+", "-", s)


# Stufen-Wörter im Ordnernamen. E-Phase = Grundforum (ohne Suffix), deshalb ohne Endung.
STUFE_GK = {"gk", "grundkurs"}
STUFE_LK = {"lk", "leistungskurs"}
STUFE_E = {"e", "ephase", "einfuehrungsphase", "ephase11"}
STUFE_KURS = {"kurs", "kursphase"}      # Kursphase, aber GK/LK nicht gesagt


def resolve(name: str, gueltig: set[str]) -> tuple[str, str, bool]:
    """Ordnername -> (Kanal für den Index, Klartext, eindeutig?).

    Fach und Stufe werden GETRENNT aufgelöst — nicht der ganze Name auf einmal:
    `-gk` und `-lk` unterscheiden sich nur um einen Buchstaben, ein Vergleich
    ganzer Namen hielte jeden Tippfehler für mehrdeutig. So bleiben die Fächer
    weit auseinander (`mathematik` vs `geographie`) und die Stufe ist ein eigenes
    Wort (`gk`, `lk`, `grundkurs`, `leistungskurs`, `e`, `ephase`).

    Ohne Stufenwort bleibt die Stufe offen — sie entscheidet der Inhalt.
    Kein Treffer: Name bleibt stehen, nichts wird verworfen.
    """
    n = norm(name)
    tabelle = {norm(f): f for f in gueltig}
    if n in tabelle:
        return tabelle[n], "genau", True

    teile = [t for t in n.split("-") if t]
    stufe = ""
    rest = []
    for t in teile:
        if t in STUFE_GK:
            stufe = "gk"
        elif t in STUFE_LK:
            stufe = "lk"
        elif t in STUFE_E:
            stufe = ""
        elif t in STUFE_KURS:
            stufe = "kurs"
        else:
            rest.append(t)
    rest = "-".join(rest)
    if not rest:
        return name, "kein Fach erkannt — ich ordne beim Einsortieren zu", False

    faecher = sorted({f.split("-")[0] for f in gueltig})
    ftab = {norm(f): f for f in faecher}
    if rest in ftab:
        fach = ftab[rest]
    else:
        nah = difflib.get_close_matches(rest, list(ftab), n=1, cutoff=0.7)
        if nah:
            fach = ftab[nah[0]]
        else:
            stamm = [f for f in faecher if len(rest) >= 3 and f.startswith(rest)]
            if len(stamm) != 1:
                return name, "kein Forum-Treffer — ich ordne beim Einsortieren zu", False
            fach = stamm[0]

    if stufe == "kurs":
        # Kursphase ohne GK/LK-Angabe: GK als Vorgabe (größere Gruppe; LK-Material
        # ist fast immer als LK beschriftet). Fachlich falsch ist es nicht — ich
        # verschiebe es, wenn der Inhalt LK sagt, und schreibe das in die Notiz.
        for k in ("gk", "lk"):
            if f"{fach}-{k}" in gueltig:
                return f"{fach}-{k}", f"Kursphase ohne GK/LK -> {k.upper()} (aus '{name}')", True
        return fach, f"Kursphase, aber {fach} hat kein Kursforum — Stufe entscheidet der Inhalt", True
    if not stufe:
        return fach, f"Fach {fach}, Stufe entscheidet der Inhalt (aus '{name}')", True
    ziel = f"{fach}-{stufe}"
    if ziel not in gueltig:
        return fach, f"{fach} hat kein {stufe.upper()} — Stufe entscheidet der Inhalt", True
    return ziel, f"erkannt: {fach} {stufe.upper()}" + (f" (aus '{name}')" if name != ziel else ""), True


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

    neue_zeilen, unklar = [], []
    for d in ordner:
        kanal, hinweis, eindeutig = resolve(d.name, gueltig)
        if not eindeutig:
            unklar.append(d.name)
        dateien = sorted(p for p in d.rglob("*") if p.is_file()
                         and not p.name.startswith(".")
                         and p.suffix.lower() not in CONTAINER_EXT)
        for p in dateien:
            if str(p) in schon:
                continue
            neue_zeilen.append({
                "server": SERVER, "kanal": kanal, "thread": "", "nachricht_id": "",
                "zeit": dt.datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds"),
                "autor": "", "dateiname": p.name, "bytes": p.stat().st_size,
                "gespeichert": str(p), "text": "", "embed_urls": "", "fehler": "",
            })
        if dateien:
            marke = "  " if eindeutig else "!!"
            print(f"  {marke} {d.name:<20} -> {kanal:<16} {len(dateien):>3} Datei(en)  {hinweis}")
        elif d.name not in gueltig:
            print(f"  !! {d.name:<20} leer und kein Forum-Name")

    if unklar:
        print(f"\n  {len(unklar)} Ordner ohne eindeutiges Forum: "
              f"{', '.join(unklar)} -> ich entscheide die Stufe aus dem Inhalt")

    if not neue_zeilen:
        print("\nNichts Neues zu indexieren.")
        return 0

    print(f"\n{len(neue_zeilen)} neue Datei(en)" + (" [ZEIGEN]" if args.zeigen else ""))
    if args.zeigen:
        for r in neue_zeilen:
            print(f"   {r['kanal']:<18} {r['dateiname']}")
        return 1 if unklar else 0

    neu = not INDEX.exists()
    with INDEX.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, delimiter=";")
        if neu:
            w.writeheader()
        w.writerows(neue_zeilen)
    print(f"-> {INDEX.relative_to(PROJECT)}")
    print(f"\nWeiter mit:  python3 extract_text.py --match <forum>")
    # Nicht eindeutige Ordner sind kein Fehler, aber sichtbar: Rückgabewert 1,
    # damit ein Skript/eine Kette nicht stillschweigend darüber hinwegläuft.
    return 1 if unklar else 0


if __name__ == "__main__":
    raise SystemExit(main())
