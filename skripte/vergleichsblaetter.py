"""Vergleichsblätter für die Sichtprüfung: Original oben, geschwärzt darunter.

Quelle sind die PDF-PAARE in `sortiert/` (`X.pdf` und `X_anonym.pdf`) — nicht die
beiden Blatt-Ordner. Grund: die Blattnamen werden auf 60 Zeichen gekürzt, dadurch
unterscheiden sich Original und geschwärzte Fassung im Namen manchmal nicht mehr,
und eine Paarung über Namen greift daneben (im ersten Anlauf passiert: 13 von 34
Blättern gepaart, der Rest still übergangen). Aus dem Paar selbst abgeleitet kann
das nicht passieren, und jede Datei wird genau einmal verarbeitet.
"""
import pathlib
import shutil
import sys
import tempfile

BASE = pathlib.Path("/Users/schwank/Documents/05 Dokumentez/01 Projekte/Schule/Discord")
sys.path.insert(0, str(BASE / "skripte"))
import schwaerzen as SW                     # noqa: E402
from PIL import Image, ImageDraw            # noqa: E402

SORTIERT = BASE / "sortiert"
AUS = BASE / "_pruefen" / "vergleich"
AUS.mkdir(parents=True, exist_ok=True)

paare = []
for anon in sorted(SORTIERT.glob("*_anonym.pdf")):
    orig = anon.with_name(anon.name.replace("_anonym.pdf", ".pdf"))
    if orig.exists():
        paare.append((orig, anon))
    else:
        print(f"  !! ohne Original: {anon.name}")

tmp = pathlib.Path(tempfile.mkdtemp(prefix="agy-vergleich-"))
for orig, anon in paare:
    SW.kopfblaetter(orig, tmp, name="orig.png")
    SW.kopfblaetter(anon, tmp, name="neu.png")
    oben, unten = Image.open(tmp / "orig.png"), Image.open(tmp / "neu.png")
    breite, kopf = max(oben.width, unten.width), 34
    blatt = Image.new("RGB", (breite, 2 * kopf + oben.height + unten.height),
                      (245, 245, 245))
    d = ImageDraw.Draw(blatt)
    d.rectangle([0, 0, breite, kopf], fill=(250, 226, 226))
    d.text((10, 9), f"ORIGINAL  —  {orig.name}", fill=(130, 0, 0))
    blatt.paste(oben, (0, kopf))
    y2 = kopf + oben.height
    d.rectangle([0, y2, breite, y2 + kopf], fill=(214, 232, 214))
    d.text((10, y2 + 9), f"GESCHWÄRZT  —  {anon.name}", fill=(0, 95, 0))
    blatt.paste(unten, (0, y2 + kopf))
    blatt.save(AUS / f"{orig.stem}.png")
shutil.rmtree(tmp, ignore_errors=True)

gr = sum(p.stat().st_size for p in AUS.glob("*.png"))
print(f"  {len(paare)} Vergleichsblätter -> {AUS}  ({gr / 1e6:.1f} MB)")
