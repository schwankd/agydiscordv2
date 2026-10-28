#!/usr/bin/env python3
"""Räumt Sammel-Titel auf: Material richtig benennen oder in bestehende Threads legen.

Auftrag (Domenic): „manche posts sind mit 'Mitschriften' betitelt was nicht sonderlich
zielführend ist, diese sollten gescanned, und wenn nötig separiert werden, dann sollte
das Material richtig benannt bzw. in bestehende Foren einsortiert werden" — später
„keine Ahnung mach das beste".

Zwei Phasen, damit die Reihenfolge erzwungen ist (erst neu, dann alt):

  --vorbereiten   Dateien nach _pruefen/umbau/ kopieren (zu große komprimieren) und
                  _pruefen/umbau_manifest.csv schreiben. Gepostet wird mit post_neu.py
                  (kein eigener Post-Code):
                    python3 post_neu.py --manifest ../_pruefen/umbau_manifest.csv \
                        --dir ../_pruefen/umbau --result ../_pruefen/umbau_result.csv
  --loeschen      Die ersetzten Sammel-Threads löschen — aber NUR, wenn der Ersatz
                  nachweisbar da ist (Thread mit neuem Titel vorhanden bzw. die
                  Ziel-Threads haben die zusätzlichen Nachrichten). Zusätzlich:
                  keine fremde Nachricht im alten Thread.

Ein Ziel-Thread wird dadurch angesprochen, dass die Manifest-Zeile den **vorhandenen
Titel** trägt — post_neu findet ihn über die Titeldubletten-Prüfung und hängt an,
statt einen neuen Thread anzulegen.

Warum überhaupt neu anlegen statt umbenennen: PATCH /channels/<thread> (Rename) gibt
403 zurück; der Weg ist Neuanlage + Löschen.

Aufruf:  python3 sammeltitel_umbau.py --vorbereiten
         python3 sammeltitel_umbau.py --loeschen
"""
from __future__ import annotations

import argparse
import csv
import pathlib
import shutil
import sys
import unicodedata

S = pathlib.Path(__file__).resolve().parent
PROJECT = S.parent
sys.path.insert(0, str(S))
import classify                                         # noqa: E402
from agy_discord import Client, DiscordError, get_token, norm_title   # noqa: E402
from post_neu import load_map                           # noqa: E402

GILD = "1539350758481469500"
UMBAU = PROJECT / "_pruefen" / "umbau"


def N(s: str) -> str:
    return unicodedata.normalize("NFC", s or "")


def finde(verzeichnis: pathlib.Path, name: str) -> pathlib.Path:
    """Datei über den Namen finden — NFC-normalisiert (macOS speichert NFD)."""
    ziel = N(name)
    for p in verzeichnis.rglob("*"):
        if p.is_file() and N(p.name) == ziel:
            return p
    raise SystemExit(f"  Quelle nicht gefunden: {name} in {verzeichnis}")


def welle_datei(titel: str, forum: str) -> pathlib.Path:
    """Gebaute Datei der Tabelle-Welle über (Titel, Forum) im Ergebnis-Manifest."""
    p = PROJECT / "manifest_neu.result.csv"
    for r in csv.DictReader(p.open(newline="", encoding="utf-8"), delimiter=";"):
        if N(r["titel"]) == N(titel) and r["ziel_kanal"] == forum:
            f = PROJECT / "sortiert_neu" / r["datei"]
            if f.exists():
                return f
    raise SystemExit(f"  Wellendatei nicht gefunden: {titel} [{forum}]")


def tags_waehlen(client: Client, forum: str, art: str, kanaele: dict) -> str:
    """Tag wählen, der im Forum wirklich existiert.

    post_neu bricht ab, wenn keiner der Namen passt. Deshalb gegen die
    tatsächlich verfügbaren Tags prüfen: erst die gewünschte Art, sonst ein
    neutraler Ersatz. So scheitert kein Umbau an einem Tag-Namen.
    """
    if not hasattr(tags_waehlen, "_cache"):
        tags_waehlen._cache = {}
    if forum not in tags_waehlen._cache:
        detail = client.get(f"/channels/{kanaele[forum]['id']}")
        tags_waehlen._cache[forum] = {t["name"] for t in detail.get("available_tags", [])}
    da = tags_waehlen._cache[forum]
    for kandidat in (art, "Sonstiges", "Hausaufgabe", "Zusammenfassung"):
        if kandidat in da:
            return kandidat
    return next(iter(da), "Sonstiges")


# (neuer/ziel-Titel, forum, fach, quelle, art, notiz, zieldatei)
# quelle: ("welle", titel, forum) | ("datei", verzeichnis, dateiname) | ("umbau", dateiname)
# zieldatei: Name, unter dem die Datei gepostet wird. Bei Umbauten auf einen NEUEN Titel
#   nach der Projekt-Konvention (Fach_Kurs_Thema_Art) gebildet — sonst stünde der alte
#   Themenslug im Beitrag ("..._U_bungsaufgaben_Klausur_Test.pdf" für ein Übungsblatt).
#   None = Name der Quelle behalten (Einzeldateien wie Arbeitsblätter).
PLAN = [
    # --- A: richtiger Name (neuer Thread, alter wird danach gelöscht) -------------
    ("Übungen und Lerntabelle: Zellaufbau, Mitose, Meiose", "biologie", "Biologie",
     ("welle", "Übungsaufgaben", "biologie"), "Hausaufgabe",
     "Sammel-Titel 'Übungsaufgaben' ersetzt: alle Blätter behandeln Zellaufbau, Mitose, Meiose"),
    ("Häufige Fehler in Englisch – Arbeitsblätter", "englisch", "Englisch",
     ("welle", "Common mistakes", "englisch"), "Hausaufgabe",
     "Sammel-Titel 'Common mistakes' ersetzt: 23 Arbeitsblätter der Reihe 'Häufige Fehler'"),
    ("Häufige Fehler in Englisch – Arbeitsblätter", "englisch", "Englisch",
     ("umbau", "Englisch_Ab_und_Uebungen_S1-19_Haeufige_Fehler.pdf"), "Hausaufgabe",
     "aus dem Sammel-Post 'Mitschriften' (Ab und übungen.pdf, S. 1-19)"),
    ("Habits – Arbeitsblatt (Vocabulary & Grammar)", "englisch", "Englisch",
     ("welle", "Online - Aufgaben", "englisch"), "Hausaufgabe",
     "Sammel-Titel 'Online - Aufgaben' ersetzt: das Blatt heißt 'Habits'"),
    ("Test und EB: Bewegungsdiagramme (E1, 2022)", "physik", "Physik",
     ("welle", "Teste und EB", "physik"), "Klausur/Test",
     "Sammel-Titel 'Teste und EB' ersetzt: Test + EB zu Bewegungsdiagrammen (E1, 2022)"),
    # --- B: Datums-Titel nach Inhalt benennen (Bestands-Threads) -----------------
    ("Test: Zellaufbau (tierische und pflanzliche Zelle) (04.11.)", "biologie", "Biologie",
     ("datei", "sortiert", "Biologie_E-Phase_Test_Biologie_04_11_Klausur_Test.pdf"), "Klausur/Test",
     "Titel nannte nur das Datum; Testinhalt: tierische/pflanzliche Zelle, Bestandteile und Funktionen"),
    ("Test: Wirbeltiere, Samenpflanzen und Fotosynthese (13.05.)", "biologie", "Biologie",
     ("datei", "sortiert", "Biologie_E-Phase_Test_Biologie_13_05_Klausur_Test.pdf"), "Klausur/Test",
     "Titel nannte nur das Datum; Testinhalt: Feuchtlufttiere/Amphibien, Wasserbedarf der Samenpflanzen, Fotosynthese"),
    ("Test: Reaktionsgleichungen, Oxidation und Reduktion (Redox)", "chemie", "Chemie",
     ("datei", "sortiert", "Chemie_E-Phase_Test_Chemie_E_Phase_Klausur_Test.pdf"), "Klausur/Test",
     "Titel nannte nur das Datum; Testinhalt: Formeln, Oxidationszahlen, Reaktionsgleichungen, Redox"),
    # --- C: in bestehende Threads einsortieren (Antwort, kein neuer Thread) ------
    ("LB 2 - Chemische Bindungen", "chemie", "Chemie",
     ("datei", "eingang/neu/Chemie/Online -Aufgaben", "Abl_B13 Metallbindung.pdf"), "Hausaufgabe",
     "Arbeitsblatt Metallbindung — gehört zum Lernbereich Bindungen (aus dem Sammel-Post 'Online - Aufgaben')"),
    ("LB 3 - Chemische Reaktionen", "chemie", "Chemie",
     ("datei", "eingang/neu/Chemie/Online -Aufgaben", "Abl_B14 Chemische Reaktionen.pdf"), "Hausaufgabe",
     "Arbeitsblatt Chemische Reaktionen — gehört zum Lernbereich Reaktionen (aus dem Sammel-Post 'Online - Aufgaben')"),
    ("Industrialisierung", "geschichte", "Geschichte",
     ("welle", "Mitschriften", "geschichte"), "Zusammenfassung",
     "Mitschriften und Hefter zur Industrialisierung (aus dem Sammel-Post 'Mitschriften')"),
    ("Unit 6 - Writing a summary", "englisch", "Englisch",
     ("datei", "eingang/neu/Englisch/Mitschriften", "Hefter e1.pdf"), "Klausur/Test",
     "Writing a Summary - Exam (Gutenberg) — gehört zu Unit 6 (aus dem Sammel-Post 'Mitschriften')"),
    ("Unit 6 - Writing a summary", "englisch", "Englisch",
     ("umbau", "Englisch_Ab_und_Uebungen_S20_Writing_a_Summary.pdf"), "Hausaufgabe",
     "Writing a Summary - Review Exercise 2 (S. 20 aus 'Ab und übungen.pdf')"),
]

# Neuer Dateiname für Umbauten, bei denen der alte Themenslug nicht mehr passt.
ZIELDATEI = {
    ("Übungen und Lerntabelle: Zellaufbau, Mitose, Meiose",
     ("welle", "Übungsaufgaben", "biologie")): "Biologie_E-Phase_Uebungen_Zellaufbau_Mitose_Meiose.pdf",
    ("Häufige Fehler in Englisch – Arbeitsblätter",
     ("welle", "Common mistakes", "englisch")): "Englisch_E-Phase_Haeufige_Fehler_Arbeitsblaetter.pdf",
    ("Häufige Fehler in Englisch – Arbeitsblätter",
     ("umbau", "Englisch_Ab_und_Uebungen_S1-19_Haeufige_Fehler.pdf")):
        "Englisch_E-Phase_Haeufige_Fehler_S1-19_Arbeitsblaetter.pdf",
    ("Habits – Arbeitsblatt (Vocabulary & Grammar)",
     ("welle", "Online - Aufgaben", "englisch")): "Englisch_E-Phase_Habits_Arbeitsblatt.pdf",
    ("Test und EB: Bewegungsdiagramme (E1, 2022)",
     ("welle", "Teste und EB", "physik")): "Physik_E-Phase_Test_und_EB_Bewegungsdiagramme_2022.pdf",
    ("Test: Zellaufbau (tierische und pflanzliche Zelle) (04.11.)",
     ("datei", "sortiert", "Biologie_E-Phase_Test_Biologie_04_11_Klausur_Test.pdf")):
        "Biologie_E-Phase_Test_Zellaufbau_04_11.pdf",
    ("Test: Wirbeltiere, Samenpflanzen und Fotosynthese (13.05.)",
     ("datei", "sortiert", "Biologie_E-Phase_Test_Biologie_13_05_Klausur_Test.pdf")):
        "Biologie_E-Phase_Test_Wirbeltiere_Pflanzen_Fotosynthese_13_05.pdf",
    ("Test: Reaktionsgleichungen, Oxidation und Reduktion (Redox)",
     ("datei", "sortiert", "Chemie_E-Phase_Test_Chemie_E_Phase_Klausur_Test.pdf")):
        "Chemie_E-Phase_Test_Redox_Reaktionsgleichungen.pdf",
    ("Industrialisierung", ("welle", "Mitschriften", "geschichte")):
        "Geschichte_E-Phase_Industrialisierung_Mitschriften_Hefter.pdf",
}

# Zu löschende Sammel-Threads: (forum, alter Titel, Ersatz-Titel mit Mindest-Nachrichten)
LOESCHEN = [
    ("biologie", "Alte Tests und Klassenarbeiten",
     [("Test: Zellaufbau (tierische und pflanzliche Zelle) (04.11.)", 1)]),
    ("biologie", "Übungsaufgaben",
     [("Übungen und Lerntabelle: Zellaufbau, Mitose, Meiose", 1)]),
    ("chemie", "Online - Aufgaben",
     [("LB 2 - Chemische Bindungen", 2), ("LB 3 - Chemische Reaktionen", 2)]),
    ("geschichte", "Mitschriften", [("Industrialisierung", 2)]),
    ("englisch", "Mitschriften",
     [("Unit 6 - Writing a summary", 3), ("Häufige Fehler in Englisch – Arbeitsblätter", 2)]),
    ("englisch", "Online - Aufgaben", [("Habits – Arbeitsblatt (Vocabulary & Grammar)", 1)]),
    ("englisch", "Common mistakes", [("Häufige Fehler in Englisch – Arbeitsblätter", 2)]),
    ("physik", "Teste und EB", [("Test und EB: Bewegungsdiagramme (E1, 2022)", 1)]),
    ("biologie", "Test Biologie (04.11.)",
     [("Test: Zellaufbau (tierische und pflanzliche Zelle) (04.11.)", 1)]),
    ("biologie", "Test Biologie (13.05.)",
     [("Test: Wirbeltiere, Samenpflanzen und Fotosynthese (13.05.)", 1)]),
    ("chemie", "Test Chemie E-Phase",
     [("Test: Reaktionsgleichungen, Oxidation und Reduktion (Redox)", 1)]),
]


def vorbereiten() -> int:
    UMBAU.mkdir(parents=True, exist_ok=True)
    client = Client(get_token("AGY_TOKEN_NEU"))
    kanaele = load_map(PROJECT / "foren-map.resolved.csv")
    zeilen = []
    for titel, forum, fach, quelle, art, notiz in PLAN:
        if quelle[0] == "welle":
            src = welle_datei(quelle[1], quelle[2])
        elif quelle[0] == "datei":
            src = finde(PROJECT / quelle[1], quelle[2])
        else:
            src = UMBAU / quelle[1]
        ziel = UMBAU / (ZIELDATEI.get((titel, quelle)) or src.name)
        if src != ziel:
            shutil.copy2(src, ziel)
        dateien = classify.compress(ziel) if ziel.suffix.lower() == ".pdf" else [ziel]
        for d in dateien:
            zeilen.append({"datei": d.name, "fach": fach, "kurs": "E-Phase", "thema": titel,
                           "art": art, "titel": titel, "ziel_kanal": forum,
                           "tags": tags_waehlen(client, forum, art, kanaele), "status": "offen",
                           "notiz": notiz})
            print(f"  {forum:<10} {titel[:44]:<44} {d.name[:46]:<46} {d.stat().st_size/1e6:5.2f} MB")
    mf = PROJECT / "_pruefen" / "umbau_manifest.csv"
    with mf.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=classify.COLS, delimiter=";")
        w.writeheader()
        w.writerows(zeilen)
    gross = [z for z in zeilen if (UMBAU / z["datei"]).stat().st_size > classify.LIMIT]
    print(f"\n  {len(zeilen)} Posts, {len({z['titel'] for z in zeilen})} Threads/Ziele "
          f"| über 10 MB: {len(gross)}")
    print(f"-> {mf.relative_to(PROJECT)}   Dateien in {UMBAU.relative_to(PROJECT)}/")
    print("\n  Jetzt posten mit:\n"
          "    python3 post_neu.py --manifest ../_pruefen/umbau_manifest.csv \\\n"
          "        --dir ../_pruefen/umbau --result ../_pruefen/umbau_result.csv")
    return 0


def loeschen(echt: bool) -> int:
    client = Client(get_token("AGY_TOKEN_NEU"))
    kanaele = load_map(PROJECT / "foren-map.resolved.csv")
    threads = client.get(f"/guilds/{GILD}/threads/active").get("threads", [])

    def in_forum(forum: str, titel: str) -> dict | None:
        for t in threads:
            if t.get("parent_id") == kanaele[forum]["id"] and norm_title(t["name"]) == norm_title(titel):
                return t
        return None

    # message_count aus der Threadliste ist bei jüngeren Threads 0/unzuverlässig —
    # für die Prüfung „ist der Ersatz da?" wird wirklich gezählt.
    _msgs: dict[str, list] = {}

    def messages(tid: str) -> list:
        if tid not in _msgs:
            _msgs[tid] = client.get(f"/channels/{tid}/messages?limit=100")
        return _msgs[tid]

    gut, blockiert = [], []
    for forum, alt_titel, ersatz in LOESCHEN:
        t = in_forum(forum, alt_titel)
        if not t:
            blockiert.append(f"{forum}/{alt_titel}: nicht gefunden (schon erledigt?)")
            continue
        fehlt = []
        for etitel, minn in ersatz:
            e = in_forum(forum, etitel)
            if not e:
                fehlt.append(f"Ersatz fehlt: {etitel}")
            elif len(messages(e["id"])) < minn:
                fehlt.append(f"Ersatz unvollständig: {etitel} ({len(messages(e['id']))}/{minn} Nachr.)")
        if fehlt:
            blockiert.append(f"{forum}/{alt_titel}: " + "; ".join(fehlt))
            continue
        fremd = [m for m in messages(t["id"]) if not m["author"].get("bot")]
        if fremd:
            blockiert.append(f"{forum}/{alt_titel}: {len(fremd)} fremde Nachricht(en) — nicht angefasst")
            continue
        gut.append((forum, alt_titel, t))

    for forum, alt_titel, t in gut:
        if echt:
            try:
                client.request("DELETE", f"/channels/{t['id']}", expect_json=False)
                print(f"  gelöscht: [{forum}] {alt_titel}  ({t['id']})")
            except DiscordError as err:
                print(f"  FEHLER beim Löschen von [{forum}] {alt_titel}: {err}")
        else:
            print(f"  würde löschen: [{forum}] {alt_titel}  ({t['id']})")
    for b in blockiert:
        print(f"  ZURÜCKGEHALTEN: {b}")
    print(f"\n  {len(gut)} löschbar, {len(blockiert)} zurückgehalten"
          + ("" if echt else "  (Probelauf — nichts gelöscht)"))
    return 0 if not blockiert else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vorbereiten", action="store_true")
    ap.add_argument("--loeschen", action="store_true")
    ap.add_argument("--echt", action="store_true", help="bei --loeschen wirklich löschen")
    args = ap.parse_args()
    if args.loeschen:
        return loeschen(args.echt)
    return vorbereiten()


if __name__ == "__main__":
    raise SystemExit(main())
