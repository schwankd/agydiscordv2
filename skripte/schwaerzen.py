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
  3. Kopfzone bestimmen (siehe kopfzone): bevorzugt alles OBERHALB der ersten
     Aufgabenzeile über die volle Breite. Grund: der Name steht oft rechts vom
     Label UND zusätzlich oben rechts ohne Label — ein Band, das nur das
     beschriftete Feld trifft, lässt ihn stehen. Die erste Aufgabenzeile ist die
     Grenze, die das Papier selbst zieht; darüber ist Kopfbereich.
     Findet die OCR keine Aufgabenzeile, greift das Kopfdatenfeld, sonst die
     obere rechte Ecke (kleinster möglicher Eingriff).
  4. Für jede Seite wird ausgegeben, WELCHER Text unter das Band fällt — damit
     die Schwärzung nachprüfbar ist und nicht stillschweigend Inhalt verschwindet.
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
ECKE_X, ECKE_H = 0.45, 0.16   # Fallback ohne Erkennung: obere rechte Ecke
FELDER = re.compile(
    r"\b(name|vorname|datum|punkte|zensur|note|klasse|kurs|kursart|fach|test|"
    r"klausur|klassenarbeit|kursarbeit|lernkontrolle|np|jahrgang|schuljahr|"
    r"bewertung|erreicht)\b", re.IGNORECASE)
# „BE" steht bewusst NICHT in FELDER: „Erreichbare BE-Anzahl: 10" steht auf JEDER
# Klausur unter jeder Aufgabe. Als Feldwort hat es das Schwärzband über die erste
# Aufgabenzeile hinausgezogen und Aufgabentext verschluckt (im Testfall belegt).
# Personenbezogene Felder — auch unterhalb der ersten Aufgabenzeile prüfenswert.
NAMENAH = re.compile(r"\b(name|vorname|klasse|kurs|kursart|zensur|note|datum|"
                     r"bewertung|erreicht)\b", re.IGNORECASE)
# Zeilen, in denen eine Aufgabe beginnt: "1.", "a)", "Aufgabe 2", "Teil B"
AUFGABE = re.compile(r"^\s*(?:\d{1,2}\s*[.)]\s|[a-e]\s*[.)]\s|Aufgabe\b|Teil\s+[AB]\b)",
                     re.IGNORECASE)
# Aufgabenverben — zusammen mit Länge ein guter Hinweis auf Aufgabentext
TUN_WORT = re.compile(
    r"\b(berechne|bestimme|gib|erläutere|erkläre|begründe|beschreibe|zeige|ermittle|"
    r"skizziere|nenne|ordne|vervollständige|löse|zeichne|ergänze|benenne|vergleiche|"
    r"diskutiere|analysiere|interpretiere|beschrifte|notiere|untersuche|entscheide|"
    r"trage|stelle|fasse|weise|beantworte|formuliere)\w*\b", re.IGNORECASE)


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


def aufgabe_oben(zeilen: list[tuple[float, float, float, float, str]]) -> float:
    """Oberkante der ersten AUFGABENZEILE (normalisiert) oder 0.

    Der Name steht nicht nur im beschrifteten Feld: auf mehreren Tests stand er
    oben rechts OHNE Label (nachgewiesen im Kontaktbogen). Ein Band, das nur das
    Feld trifft, lässt ihn stehen. Zuverlässiger ist die Grenze, die das Papier
    selbst zieht: die erste Zeile, in der eine Aufgabe beginnt. Alles darüber ist
    Kopfbereich (Name, Datum, Punkte, Titel) — und wird geschwärzt.
    """
    for _x, y, _w, _h, t in sorted(zeilen, key=lambda z: z[1]):
        if y > BAND_MAX:
            break
        sauber = t.strip()
        if FELDER.search(sauber) and not AUFGABE.search(sauber):
            continue                                  # Kopfzeile, keine Aufgabe
        if AUFGABE.search(sauber) or (TUN_WORT.search(sauber) and len(sauber) > 25):
            return y
    return 0.0


def ecke_rechteck(zeilen: list[tuple[float, float, float, float, str]]
                  ) -> tuple[float, float, float, float]:
    """Obere rechte Ecke, aber höchstens bis zur ersten erkannten Textzeile darin.

    Ein Band über die Ecke kann eine gedruckte Zeile anschneiden (im Testfall
    passiert: der erste Satz des Quellenmaterials lag halb in der Ecke). Deshalb
    endet es über der ersten Zeile, deren Mitte in der Ecke liegt — geschwärzt
    wird dann nur der Rand darüber, wo ein handschriftlicher Name steht.
    """
    drin = [y for x, y, w, h, _t in zeilen
            if x + w / 2 > ECKE_X and y + h / 2 < ECKE_H]
    # Fließtext in der Ecke? Kriterium ist die ÜBERLAPPUNG, nicht der Mittelpunkt:
    # ein Blocksatz-Aufgabentext endet bei x≈55 %, sein Mittelpunkt liegt aber bei
    # 34 % — mit dem Mittelpunkt geprüft blieb er unentdeckt und das Eckband schnitt
    # die Zeilenenden ab (im Testfall bei „Flächenberechnungen" passiert).
    fliess = [t.strip() for x, y, w, h, t in zeilen
              if y < ECKE_H and (x + w) > ECKE_X + 0.03 and len(t.strip()) > 25]
    if fliess:
        # In der Ecke steht Fließtext — also keine Handschrift, sondern Aufgabe
        # oder Material. Ein Band würde die rechte Hälfte dieser Zeilen abschneiden
        # (im Testfall bei „Flächenberechnungen" genau so passiert). Dann lieber
        # nichts schwärzen und melden: der Mensch schaut an dieser Stelle nach,
        # statt dass Inhalt verschwindet.
        return None
    hoehe = max(0.06, min(ECKE_H, min(drin) if drin else ECKE_H))
    return (ECKE_X, 0.0, 1.0, hoehe)


def kopfzone(zeilen: list[tuple[float, float, float, float, str]]
             ) -> tuple[list[tuple[float, float, float, float]], str, list[str]]:
    """Was geschwärzt wird: Rechtecke (x0,y0,x1,y1 normalisiert) + Begründung.

    Drei Fälle, absteigend nach Verlässlichkeit:
      1. Aufgabenzeile gefunden → ganzer Kopfbereich bis dorthin, volle Breite.
         Das ist die Regel, die auch den namenlosen Eintrag oben rechts erwischt.
      2. Nur Kopfdatenfeld gefunden → Feldblock plus eine Zeile Luft, volle Breite.
      3. Nichts erkannt → obere rechte Ecke. Dort sitzt der Name ohne Label, und
         anders als ein Band über die ganze Breite kostet das auf Notizseiten
         praktisch keinen Inhalt (die Ecke ist fast immer leer oder Datum).
    """
    felder_unten, felder = kopfband(zeilen)
    aufg = aufgabe_oben(zeilen)
    if aufg > 0:
        # Über der ersten Aufgabenzeile enden — aber nur, wenn dort auch
        # KOPFBEREICH steht. Steht dort Fließtext (Quellenmaterial M 1/M 2, das in
        # Prüfungen oft VOR den Aufgaben abgedruckt ist), wäre ein Band bis zur
        # ersten Aufgabenzeile Inhaltsverlust. Kennzeichen Kopfbereich: wenige,
        # kurze Zeilen. Kennzeichen Material: viele Zeilen oder lange Zeilen.
        oben = [t.strip() for _x, y, _w, _h, t in zeilen if y < aufg]
        kopfartig = len(oben) <= 5 and all(len(t) < 45 for t in oben)
        warnung = ""
        drunter = [(y, t) for _x, y, _w, _h, t in zeilen
                   if aufg < y < BAND_MAX and NAMENAH.search(t)]
        if drunter:
            warnung = ("  !! GRENZFALL: personenbezogenes Feld unterhalb der ersten "
                       f"Aufgabenzeile: {drunter[0][1][:40]!r} (bei {drunter[0][0]:.1%})")
        if kopfartig:
            return [(0.0, 0.0, 1.0, aufg)], \
                f"Kopfbereich bis über die erste Aufgabenzeile ({aufg:.1%}){warnung}", felder
        # Material über den Aufgaben: nur den Feldblock bzw. die Ecke schwärzen,
        # damit der Quellentext erhalten bleibt.
        ecke = ecke_rechteck(zeilen)
        if felder_unten > 0:
            # Vor der Aufgabenzeile abdeckeln: der Feldblock darf das Band nicht in
            # den Aufgabentext ziehen (0,3 % Überschuss schnitt im Testfall die
            # Oberkante der ersten Aufgabe an). Überlappen Feld und Aufgabenzeile,
            # hat das Feld Vorrang — ein Name darf nicht überleben, und die
            # angeschnittene Aufgabe wird ausdrücklich gemeldet.
            grenze = aufg - 0.004
            if grenze >= felder_unten:
                unten = min(felder_unten + 0.03, grenze, BAND_MAX)
            else:
                unten = min(felder_unten, BAND_MAX)
                warnung += ("  !! Feld und erste Aufgabenzeile überlappen — Feld hat "
                            "Vorrang, Aufgabe an dieser Stelle prüfen")
            return ([(0.0, 0.0, 1.0, unten)]
                    + ([ecke] if ecke is not None and unten < ecke[3] else [])), \
                (f"Material über den Aufgaben → Feldblock ({unten:.1%}){warnung}"), felder
        # Kein Feld, kein Kopfbereich: nur die Ecke. Enthält sie aber Fließtext,
        # wird NICHT geschwärzt — dann würde die rechte Hälfte von Aufgabenzeilen
        # abgeschnitten — sondern gemeldet, damit der Mensch dort nachsieht.
        if ecke is None:
            return [], (f"Material über den Aufgaben → Ecke enthält Fließtext, "
                        f"NICHT geschwärzt, bitte ansehen{warnung}"), felder
        return [ecke], \
            (f"Material über den Aufgaben → obere rechte Ecke "
             f"({ecke[3]:.0%}){warnung}"), felder
    if felder_unten > 0:
        unten = min(felder_unten + 0.03, BAND_MAX)
        return [(0.0, 0.0, 1.0, unten)], f"Kopfdatenfeld + Zeilenabstand ({unten:.1%})", felder
    ecke = ecke_rechteck(zeilen)
    if ecke is None:
        return [], ("kein Feld/Aufgabe → Ecke enthält Fließtext, NICHT geschwärzt, "
                    "bitte ansehen"), []
    return [ecke], f"kein Feld/Aufgabe → obere rechte Ecke ({ecke[3]:.0%})", []


def gedeckt(zeilen: list[tuple[float, float, float, float, str]],
            rechtecke: list[tuple[float, float, float, float]]) -> list[str]:
    """Welcher erkannte Text fällt unter die Schwärzung? Zum Nachprüfen.

    Kriterium ist die ÜBERLAPPUNG des Zeilenkastens, nicht sein Mittelpunkt: eine
    halb angeschnittene Zeile ist genau der Schaden, den man sehen will. Mit dem
    Mittelpunkt als Kriterium rutschte eine angeschnittene Aufgabenzeile durch die
    Prüfung (im Testfall passiert).
    """
    aus = []
    for x, y, w, h, t in zeilen:
        x2, y2 = x + w, y + h
        if any(x < x1 and x2 > x0 and y < y1 and y2 > y0
               for x0, y0, x1, y1 in rechtecke):
            aus.append(t.strip())
    return aus


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
    vor_tiles, nach_tiles, geschwaerzt, ohne = [], [], 0, 0
    print(f"{quelle.name}: {gesamt} Seiten"
          + (f", Probe auf {n_seiten}" if args.max_seiten else ""))

    for i in range(gesamt):
        pix = doc[i].get_pixmap(dpi=DPI)
        bild = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

        if i < n_seiten:
            with tempfile.NamedTemporaryFile(suffix=".png", dir=CACHE, delete=False) as fh:
                tmp = pathlib.Path(fh.name)
            bild.save(tmp, "PNG")
            zeilen_ocr = ocr_zeilen(binary, tmp)
            rechtecke, grund, erkannt = kopfzone(zeilen_ocr)
            unter_dem_band = gedeckt(zeilen_ocr, rechtecke)
            tmp.unlink(missing_ok=True)
            vorher = bild.copy()          # VOR dem Schwärzen sichern, sonst sind
            if rechtecke:
                stift = ImageDraw.Draw(bild)  # Vorher-Kopie liegt bereits vor
                for x0, y0, x1, y1 in rechtecke:
                    stift.rectangle([x0 * bild.width, y0 * bild.height,
                                     x1 * bild.width, y1 * bild.height], fill=(0, 0, 0))
                geschwaerzt += 1
            else:
                ohne += 1
            print(f"  Seite {i + 1:>3}: {grund}"
                  + (f" — darunter: {' | '.join(t[:26] for t in unter_dem_band[:3])}"
                     if unter_dem_band else " — darunter kein erkannter Text"))
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
              f"{geschwaerzt} von {n_seiten} Seiten geschwärzt"
              + (f", {ohne} NICHT geschwärzt (bitte ansehen)" if ohne else ""))
        print("   Seiten sind BILDER: kein Textlayer, nichts rückholbar.")
    else:
        neu.close()
        print("\nVorschau — nichts geschrieben.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
