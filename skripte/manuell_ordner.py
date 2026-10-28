"""Dateien zum MANUELLEN Schwärzen auf den Desktop legen.

VERALTET — benutze `klausur_runter.py --holen`. Dieses Skript baut die Mappe aus
den Manifesten und kennt darum nur die Dateien, die noch in `sortiert/` liegen;
die vollständige Menge steht im Server (Tag `Klausur/Test`), und die holt
`klausur_runter.py`. Beide schreiben dieselbe Mappe
(`~/Desktop/AGY-manuell-schwaerzen`) — nur letzteres ist die Wahrheit.

Je Klausur/Test-Post eine Kopie, im Namen das Ziel-Forum vorangestellt
(`<forum>__<datei>.pdf`) — daran finde ich später beim Posten wieder, wohin
jede Datei gehört, auch wenn Domenic die Datei neu speichert. Dazu eine Liste
mit Forum/Titel und eine Liesmich.

Quelle ist `sortiert/` (die Dateien, die auch im Server liegen). Es wird nichts
verändert, nur kopiert.
"""
import csv
import pathlib
import shutil

BASE = pathlib.Path("/Users/schwank/Documents/05 Dokumentez/01 Projekte/Schule/Discord")
SORTIERT = BASE / "sortiert"
ZIEL = pathlib.Path.home() / "Desktop" / "AGY-manuell-schwaerzen"
ORDNER = ZIEL / "01_schwaerzen"

if ZIEL.exists():
    shutil.rmtree(ZIEL)
ORDNER.mkdir(parents=True)

# Alle Klausur/Test-Beiträge aus den Manifesten (die Datei ist die Wahrheit,
# nicht ein Ordnerinhalt — so kann keine Datei fehlen oder doppelt kommen).
gesehen, rows = set(), []
for mf in sorted(BASE.glob("manifest_*.csv")):
    if mf.stem.endswith(".result"):
        continue
    for r in csv.DictReader(mf.open(newline="", encoding="utf-8"), delimiter=";"):
        if ("klausur" in r["tags"].lower() or "test" in r["tags"].lower()) \
                and r["datei"].endswith(".pdf") and r["datei"] not in gesehen:
            gesehen.add(r["datei"])
            rows.append(r)

liste, fehlend = [], []
for r in rows:
    quelle = SORTIERT / r["datei"]
    if not quelle.exists():
        fehlend.append(r["datei"])
        continue
    name = f"{r['ziel_kanal']}__{r['datei']}"
    shutil.copy2(quelle, ORDNER / name)
    liste.append({"dateiname_zum_schwaerzen": name, "forum": r["ziel_kanal"],
                  "titel": r["titel"], "art": r["art"],
                  "seiten": "", "originaldatei": r["datei"]})

with (ZIEL / "03_Liste.csv").open("w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(liste[0].keys()), delimiter=";")
    w.writeheader()
    w.writerows(liste)

txt = f"""DATEIEN ZUM MANUELLEN SCHWÄRZEN
================================

01_schwaerzen/   {len(liste)} PDFs. Das sind genau die Klausur/Test-Beiträge,
                 die im Discord liegen (und die Namen enthalten können).
                 Im Dateinamen steht vorn das Ziel-Forum, damit ich beim
                 Posten wieder weiß, wohin jede Datei gehört:
                       <forum>__<dateiname>.pdf
                 Beispiel: mathematik-gk__Mathematik_GK_Mathe_Test_3_..._Test.pdf

03_Liste.csv     dieselbe Zuordnung als Tabelle: Dateiname, Forum, Titel, Art.

WIE SCHWÄRZEN
-------------
Egal womit — die Stellen müssen nur SICHTBAR markiert sein (schwarzer Balken,
Kasten, Übermalen). Vorschlag für macOS-Vorschau: Werkzeuge > Anmerkungen >
Rechteck, Füllfarbe schwarz, dann über das Namensfeld ziehen.

Wichtig: Du musst nicht auf den Textlayer achten und nichts exportieren.
Ich brenne deine Markierungen anschließend ein:
      schwaerzen.py --datei <datei> --nur-rastern
Dabei wird jede Seite als Bild neu aufgebaut. Erst danach ist die Schwärzung
echt — ein schwarzes Rechteck über einem Textlayer lässt den Namen weiter
herausziehen, und eine Anmerkung im PDF kann jeder wieder wegklicken.

ZURÜCKGEBEN
-----------
Markierte PDFs einfach liegen lassen oder in denselben Ordner speichern
(kein Umbenennen nötig). Ein Wort von Dir, dann brenne ich alles ein, prüfe
jede Datei gegen das Original (Seitenzahl, keine schwarzen Stellen vergessen)
und ersetze die 33 Threads im Server — vorher wird geprüft, ob fremde
Kommentare dranhängen; wenn ja, lösche ich nichts.

DIES IST EINE KOPIE. Originale bleiben:
{BASE}
"""
(ZIEL / "LIESMICH.txt").write_text(txt, encoding="utf-8")
gr = sum(p.stat().st_size for p in ZIEL.rglob("*") if p.is_file())
print(f"  {ZIEL}")
print(f"  {len(liste)} PDFs + Liste + LIESMICH  ({gr / 1e6:.1f} MB)")
if fehlend:
    print(f"  !! fehlten in sortiert/: {fehlend}")
