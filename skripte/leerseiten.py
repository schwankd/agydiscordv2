#!/usr/bin/env python3
"""Leere Seiten entfernen — mit Nachweis, dass KEINE andere Seite verändert wird.

Zwei Sicherungen:
  1. Original wird vorher nach `_pruefen/leerseiten_original/` gesichert.
  2. Jede verbleibende Seite wird vor und nach dem Umbau gerendert und
     pixelweise verglichen. Weicht eine Seite ab, wird abgebrochen.

Eine Seite gilt nur dann als leer, wenn es praktisch KEINEN nicht-weißen Pixel
gibt (gemessen bei 200 dpi) und kein Textlayer vorhanden ist. Blasse Schrift
zählt als Inhalt — der frühere Test (36 dpi, Pixel unter 200) hat genau das
übersehen und Seiten mit Bleistift als leer gemeldet.

Aufruf:
    python3 leerseiten.py --liste leerseiten.csv          # nur prüfen, nichts ändern
    python3 leerseiten.py --liste leerseiten.csv --machen # wirklich entfernen
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import pathlib
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import fitz  # noqa: E402
from PIL import Image  # noqa: E402

PROJECT = pathlib.Path(__file__).resolve().parent.parent
SORTIERT = PROJECT / "sortiert"
SICHERUNG = PROJECT / "_pruefen" / "leerseiten_original"
DPI = 200
KEIN_PIXEL = 200          # so viele nicht-weiße Pixel erlaubt (Rauschen)
WEISS = 250


def seiten_hash(page) -> str:
    pix = page.get_pixmap(dpi=100)
    return hashlib.sha256(pix.samples).hexdigest()


def wirklich_leer(page) -> tuple[bool, str]:
    pix = page.get_pixmap(dpi=DPI)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("L")
    daten = list(img.getdata())
    unter = sum(1 for x in daten if x < WEISS)
    text = len((page.get_text() or "").strip())
    if text:
        return False, f"Textlayer ({text} Zeichen)"
    if unter > KEIN_PIXEL:
        return False, f"{unter} nicht-weiße Pixel (min {min(daten)})"
    return True, f"leer (nur {unter} nicht-weiße Pixel)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--liste", required=True, help="CSV: datei;seite;...")
    ap.add_argument("--machen", action="store_true", help="wirklich entfernen")
    args = ap.parse_args()

    eintraege: dict[str, list[int]] = {}
    for r in csv.DictReader(pathlib.Path(args.liste).open(newline="", encoding="utf-8"),
                            delimiter=";"):
        eintraege.setdefault(r["datei"], []).append(int(r["seite"]))

    print(f"{len(eintraege)} PDFs, {sum(len(v) for v in eintraege.values())} Seiten\n")
    gesamt_ok = True
    for name, seiten in sorted(eintraege.items()):
        quelle = SORTIERT / name
        if not quelle.exists():
            print(f"!! fehlt: {name}")
            gesamt_ok = False
            continue
        doc = fitz.open(quelle)
        vorher = {i: seiten_hash(doc[i]) for i in range(doc.page_count)}
        n_vorher = doc.page_count
        doc.close()

        # Gegenprüfung: ist jede gemeldete Seite wirklich leer?
        doc = fitz.open(quelle)
        for s in seiten:
            leer, warum = wirklich_leer(doc[s - 1])
            if not leer:
                print(f"!! ABBRUCH {name} Seite {s}: {warum} — NICHT entfernt")
                gesamt_ok = False
                doc.close()
                return 1
        doc.close()

        if not args.machen:
            print(f"  {name[:58]:<58} {len(seiten)} Seite(n): {seiten} — geprüft, leer")
            continue

        SICHERUNG.mkdir(parents=True, exist_ok=True)
        ziel_sicherung = SICHERUNG / name
        if not ziel_sicherung.exists():
            shutil.copy2(quelle, ziel_sicherung)

        doc = fitz.open(quelle)
        neu = fitz.open()
        behalten = [i for i in range(doc.page_count) if (i + 1) not in seiten]
        for i in behalten:
            neu.insert_pdf(doc, from_page=i, to_page=i)
        tmp = quelle.with_suffix(".tmp.pdf")
        neu.save(tmp, deflate=True, garbage=4)
        neu.close()
        doc.close()

        # Nachweis: jede behaltene Seite muss identisch gerendert werden
        a = fitz.open(quelle)
        b = fitz.open(tmp)
        if b.page_count != len(behalten):
            print(f"!! {name}: Seitenzahl {b.page_count} != erwartet {len(behalten)} — abgebrochen")
            tmp.unlink(missing_ok=True)
            gesamt_ok = False
            a.close(); b.close()
            continue
        abweichung = []
        for neupos, alt in enumerate(behalten):
            if seiten_hash(a[alt]) != seiten_hash(b[neupos]):
                abweichung.append(alt + 1)
        a.close(); b.close()
        if abweichung:
            print(f"!! {name}: Seiten {abweichung} verändert — abgebrochen, Original bleibt")
            tmp.unlink(missing_ok=True)
            gesamt_ok = False
            continue

        tmp.replace(quelle)
        print(f"  {name[:58]:<58} {n_vorher} -> {len(behalten)} Seiten, "
              f"alle übrigen {len(behalten)} pixelgleich ✓  (Original gesichert)")

    print("\n" + ("Alle Prüfungen bestanden." if gesamt_ok else "MIT FEHLERN — siehe !! oben"))
    return 0 if gesamt_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
