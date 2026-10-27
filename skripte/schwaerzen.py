#!/usr/bin/env python3
"""Namen auf Tests/Klausuren schwärzen — anonyme Fassung erzeugen.

Warum nicht einfach ein schwarzes Rechteck über den Text:
  - Handschriftliche Namen erkennt die OCR meist GAR NICHT (nur das Label
    „Name, Vorname"). Schwärzen nach erkanntem Text würde den Namen stehen lassen.
  - Ein Rechteck über einem Textlayer ist keine Schwärzung — der Text bleibt
    herausziehbar. Deshalb wird jede Seite nach dem Schwärzen als BILD neu
    aufgebaut: danach ist nichts mehr rückholbar.

Vorgehen je Seite (ein Durchgang):
  1. Seite bei 200 dpi rastern.
  2. OCR MIT Positionen (Apple Vision, ocr-vision-boxes.swift).
  3. Kopfdaten-Block bestimmen: die oberen Zeilen, die Name/Datum/Punkte/Zensur/
     Klasse/Kurs/Test/Klausur/BE/NP enthalten — samt allem darüber.
  4. Diesen Block über die VOLLE Breite schwärzen (der Name steht rechts vom
     Label und wird von der OCR oft nicht gelesen).
  5. Seite aus dem geschwärzten Bild neu aufbauen.

Aufruf:
    python3 schwaerzen.py --datei ../sortiert/X.pdf --bogen /tmp/x.png   # nur schauen
    python3 schwaerzen.py --datei ../sortiert/X.pdf --machen             # Fassung schreiben
"""
from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys
import tempfile

import fitz
from PIL import Image, ImageDraw

SKRIPTE = pathlib.Path(__file__).resolve().parent
PROJECT = SKRIPTE.parent
CACHE = SKRIPTE / ".cache"
QUELLE_SWIFT = (pathlib.Path.home() / ".hermes/skills/note-taking/schul-archiv-ocr-pdf"
                / "scripts/ocr-vision-boxes.swift")
DPI = 200
BAND_MAX = 0.40          # höchstens die oberen 40 % werden geschwärzt
FELDER = re.compile(
    r"\b(name|vorname|datum|punkte|zensur|note|klasse|kurs|kursart|fach|test|"
    r"klausur|klassenarbeit|kursarbeit|lernkontrolle|be|np|jahrgang|schuljahr|"
    r"bewertung|erreicht)\b", re.IGNORECASE)


def ocr_binary() -> pathlib.Path:
    """Swift-Werkzeug einmal kompilieren, dann Binary wiederverwenden."""
    CACHE.mkdir(parents=True, exist_ok=True)
    binary = CACHE / "ocrboxes"
    if not binary.exists() or binary.stat().st_mtime < QUELLE_SWIFT.stat().st_mtime:
        print("  kompiliere OCR-Werkzeug mit Positionen (einmalig) ...", file=sys.stderr)
        subprocess.run(["swiftc", "-O", str(QUELLE_SWIFT), "-o", str(binary)], check=True)
    return binary


def ocr_zeilen(binary: pathlib.Path, bild: pathlib.Path
               ) -> list[tuple[float, float, float, float, str]]:
    """OCR-Zeilen mit normalisierten Kästen (Ursprung links oben)."""
    res = subprocess.run([str(binary), str(bild)], capture_output=True, text=True, timeout=300)
    aus = []
    for line in res.stdout.splitlines():
        teile = line.split("\t")
        if len(teile) < 5:
            continue
        try:
            x, y, w, h = (float(v) for v in teile[:4])
        except ValueError:
            continue
        aus.append((x, y, w, h, teile[4]))
    return aus


def kopfband(zeilen: list[tuple[float, float, float, float, str]]) -> tuple[float, list[str]]:
    """Untere Kante des Kopfdatenblocks (normalisiert 0..1) + erkannte Felder.

    Nur der ZUSAMMENHÄNGENDE Block ganz oben wird geschwärzt — nicht alles, was
    irgendwo auf der Seite ein Feldwort enthält. Vorher wurde das Maximum aller
    Treffer genommen; eine Aufgabe mit „BE" oder „Note" im Text zog das Band dann
    bis 40 % der Seite hoch und hätte Aufgabentext mitgeschwärzt (im Testfall genau
    so passiert). Deshalb: obersten Treffer nehmen und nur so lange erweitern, wie
    die nächste Zeile direkt darunter liegt (max. 4 % Seitenhöhe Abstand).
    """
    treffer = sorted(((y, y + h, t.strip()) for _x, y, _w, h, t in zeilen if FELDER.search(t)),
                     key=lambda z: z[0])
    if not treffer:
        return 0.0, []
    unten, felder = treffer[0][1], [treffer[0][2]]
    for y, yh, t in treffer[1:]:
        if y - unten > 0.04:
            break
        unten, _ = max(unten, yh), felder.append(t)
    return min(unten, BAND_MAX), felder[:6]


def kopfblaetter(quelle: pathlib.Path, ordner: pathlib.Path, hoehe: float = 0.25,
                 spalten: int = 3, kachel: int = 1100) -> int:
    """Je Datei EIN lesbares Blatt mit den Kopfstreifen aller Seiten (Original).

    Miniaturansichten ganzer Seiten sind zu klein für Handschrift. Namen stehen
    im Kopfbereich — deshalb nur die oberen 25 % der Seite, dafür groß. Damit kann
    ein Mensch die Namen finden, die eine Maschine nicht verlässlich erkennt.
    """
    ordner.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(quelle)
    ks = []
    for i, page in enumerate(doc):
        px = page.get_pixmap(dpi=110, clip=fitz.Rect(0, 0, page.rect.width,
                                                    page.rect.height * hoehe))
        img = Image.frombytes("RGB", (px.width, px.height), px.samples)
        img.thumbnail((kachel, 340), Image.LANCZOS)
        k = Image.new("RGB", (kachel, 340 + 24), "white")
        k.paste(img, (0, 0))
        ImageDraw.Draw(k).text((8, 346), f"{quelle.name[:46]}  —  Seite {i + 1}",
                               fill="black")
        ks.append(k)
    doc.close()
    z = (len(ks) + spalten - 1) // spalten
    blatt = Image.new("RGB", (spalten * kachel, z * 364), "white")
    for i, k in enumerate(ks):
        blatt.paste(k, ((i % spalten) * kachel, (i // spalten) * 364))
    aus = ordner / f"{quelle.stem[:60]}.png"
    blatt.save(aus)
    print(f"  {quelle.name[:50]:<50} {len(ks)} Seiten -> {aus.name}")
    return 0


def boegen(teile_vor: list, teile_nach: list, ziel: pathlib.Path, kachel: int = 420) -> None:
    """Zwei Kontaktbögen (vorher/nachher) für die Sichtprüfung."""
    spalten = 4
    for teile, name in ((teile_vor, "-vorher"), (teile_nach, "-nachher")):
        if not teile:
            continue
        ks = []
        for k in teile[:16]:
            kk = k.copy()
            kk.thumbnail((kachel, kachel), Image.LANCZOS)
            t = Image.new("RGB", (kachel, kachel), "white")
            t.paste(kk, (0, 0))
            ks.append(t)
        zeilen = (len(ks) + spalten - 1) // spalten
        blatt = Image.new("RGB", (spalten * kachel, zeilen * kachel), "white")
        for j, k in enumerate(ks):
            blatt.paste(k, ((j % spalten) * kachel, (j // spalten) * kachel))
        aus = ziel.with_name(ziel.stem + name + ziel.suffix)
        aus.parent.mkdir(parents=True, exist_ok=True)
        blatt.save(aus)
        print(f"  Bogen: {aus}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--datei", required=True)
    ap.add_argument("--machen", action="store_true", help="geschwärzte Fassung schreiben")
    ap.add_argument("--bogen", default=None, help="Kontaktbogen vorher/nachher hierhin")
    ap.add_argument("--max-seiten", type=int, default=0, help="nur die ersten N Seiten")
    ap.add_argument("--qualitaet", type=int, default=72, help="JPEG-Qualität (kleiner = kleinere Datei)")
    ap.add_argument("--kopfblaetter", default=None,
                    help="Ordner: je Datei ein lesbares Kopfstreifen-Blatt (Original) ablegen")
    args = ap.parse_args()

    quelle = pathlib.Path(args.datei)
    if not quelle.is_absolute():
        kandidat = PROJECT / args.datei
        quelle = kandidat if kandidat.exists() else pathlib.Path.cwd() / args.datei
    quelle = quelle.resolve()
    if not quelle.exists():
        print(f"!! nicht gefunden: {quelle}")
        return 1

    if args.kopfblaetter:
        return kopfblaetter(quelle, pathlib.Path(args.kopfblaetter))

    binary = ocr_binary()
    doc = fitz.open(quelle)
    gesamt = doc.page_count
    n_seiten = min(args.max_seiten, gesamt) if args.max_seiten else gesamt
    neu = fitz.open()
    vor_tiles, nach_tiles, geschwaerzt = [], [], 0
    print(f"{quelle.name}: {gesamt} Seiten"
          + (f", Probe auf {n_seiten}" if args.max_seiten else ""))

    for i in range(gesamt):
        pix = doc[i].get_pixmap(dpi=DPI)
        bild = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

        if i < n_seiten:
            with tempfile.NamedTemporaryFile(suffix=".png", dir=CACHE, delete=False) as fh:
                tmp = pathlib.Path(fh.name)
            bild.save(tmp, "PNG")
            unten, erkannt = kopfband(ocr_zeilen(binary, tmp))
            tmp.unlink(missing_ok=True)
            vorher = bild.copy()          # VOR dem Schwärzen sichern, sonst sind
            if unten > 0:                 # beide Bögen identisch (im Test aufgefallen)
                ImageDraw.Draw(bild).rectangle([0, 0, bild.width, int(unten * bild.height)],
                                               fill=(0, 0, 0))
                geschwaerzt += 1
                print(f"  Seite {i + 1:>3}: Band bis {unten:>5.1%} geschwärzt — "
                      f"erkannt: {' | '.join(erkannt[:4])}")
            else:
                print(f"  Seite {i + 1:>3}: kein Kopfdatenfeld erkannt")
            vor_tiles.append(vorher)
            nach_tiles.append(bild.copy())

        if args.machen:
            zt = CACHE / f"_anom{i}.jpg"
            bild.save(zt, "JPEG", quality=args.qualitaet)
            seite = neu.new_page(width=bild.width, height=bild.height)
            seite.insert_image(fitz.Rect(0, 0, bild.width, bild.height), filename=str(zt))
            zt.unlink(missing_ok=True)

    doc.close()
    if args.bogen:
        boegen(vor_tiles, nach_tiles, pathlib.Path(args.bogen))

    if args.machen:
        ziel = quelle.with_name(quelle.stem + "_anonym.pdf")
        neu.save(ziel, deflate=True, garbage=4)
        neu.close()
        print(f"\n-> {ziel.name} ({ziel.stat().st_size / 1e6:.2f} MB), "
              f"{geschwaerzt} von {n_seiten} Seiten geschwärzt")
        print("   Seiten sind BILDER: kein Textlayer, nichts rückholbar.")
    else:
        neu.close()
        print("\nVorschau — nichts geschrieben.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
