#!/usr/bin/env python3
"""Baut ein Ergebnis-Manifest (manifest_<x>.result.csv) aus Server + Bau-Manifest neu.

Warum es das gibt: das Ergebnis-Manifest ist die Aufzeichnung, was im Server liegt —
Datei, Titel, Thread, URL. Es entstand während des Postens. Am 28.10. wurde es beim
Nachbuchen versehentlich geleert (Datei im Schreibmodus geöffnet, Schreiben brach ab).

Wiederherstellung ohne Rätselraten: der Titel im Bau-Manifest bestimmt den Thread im
Forum; die Zuordnung Titel -> Thread ist eindeutig (geteilte Sammel-PDFs landen als
Antwort im selben Thread). Die vier Antworten des Laufs sind zusätzlich protokolliert
und werden mit ihrer Nachrichten-URL übernommen.

Aufruf:  python3 result_rekonstruieren.py --manifest ../manifest_neu.csv \
             --result ../manifest_neu.result.csv [--schreiben]
"""
from __future__ import annotations

import argparse
import csv
import pathlib
import sys
import unicodedata

S = pathlib.Path(__file__).resolve().parent
PROJECT = S.parent
sys.path.insert(0, str(S))
from agy_discord import Client, get_token, norm_title      # noqa: E402
from post_neu import load_map                             # noqa: E402

GILD = "1539350758481469500"
COLS = ["datei", "ziel_kanal", "titel", "tags", "aktion", "thread_id", "url", "fehler"]

# Antworten des Wellenlaufs: (forum, Titel) -> (Thread-ID, Nachrichten-URL).
# Aus dem Laufprotokoll dieses Tages — sie stehen nicht im Bau-Manifest, weil die
# Entscheidung „neu oder Antwort" erst beim Posten fällt.
BEKANNTE_ANTWORTEN = {
    ("biologie", "LB 3 - Ökologie"):
        ("1564940426190913567", "https://discord.com/channels/1539350758481469500/1564940426190913567/1564940535129702460"),
    ("mathematik", "11 Stochastik"):
        ("1564943924798169142", "https://discord.com/channels/1539350758481469500/1564943924798169142/1564944041051824160"),
    ("mathematik", "3 Logarithmen Logarithmengesetze"):
        ("1558809882436829238", "https://discord.com/channels/1539350758481469500/1558809882436829238/1564944239677415594"),
    ("physik", "2. Dynamik"):
        ("1564945018643423335", "https://discord.com/channels/1539350758481469500/1564945018643423335/1564945067334959237"),
}

# Ersetzungen des Sammel-Titel-Umbaus (alter Titel -> neuer/ziel-Titel je Forum).
ERSETZT = {
    ("biologie", "Alte Tests und Klassenarbeiten"): "Test: Zellaufbau (tierische und pflanzliche Zelle) (04.11.)",
    ("biologie", "Übungsaufgaben"): "Übungen und Lerntabelle: Zellaufbau, Mitose, Meiose",
    ("chemie", "Online - Aufgaben"): "LB 2 - Chemische Bindungen",
    ("geschichte", "Mitschriften"): "Industrialisierung",
    ("englisch", "Mitschriften"): "Unit 6 - Writing a summary",
    ("englisch", "Online - Aufgaben"): "Habits – Arbeitsblatt (Vocabulary & Grammar)",
    ("englisch", "Common mistakes"): "Häufige Fehler in Englisch – Arbeitsblätter",
    ("physik", "Teste und EB"): "Test und EB: Bewegungsdiagramme (E1, 2022)",
}

N = lambda s: unicodedata.normalize("NFC", s or "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(PROJECT / "manifest_neu.csv"))
    ap.add_argument("--result", default=str(PROJECT / "manifest_neu.result.csv"))
    ap.add_argument("--schreiben", action="store_true")
    args = ap.parse_args()

    bau = list(csv.DictReader(pathlib.Path(args.manifest).open(newline="", encoding="utf-8"),
                              delimiter=";"))
    client = Client(get_token("AGY_TOKEN_NEU"))
    kanaele = load_map(PROJECT / "foren-map.resolved.csv")
    threads = client.get(f"/guilds/{GILD}/threads/active").get("threads", [])
    index = {}
    for t in threads:
        for forum, info in kanaele.items():
            if t.get("parent_id") == info["id"]:
                index.setdefault((forum, norm_title(t["name"])), t)

    # Geteilte Sammel-PDFs: Teil 1 und Teil 2 tragen DENSELBEN Titel. Antwort ist
    # nur der jeweils LETZTE Post dieses Titels — sonst wären beide als Antwort
    # markiert und der Thread-Erzeuger fehlte.
    letzter = {}
    for i, r in enumerate(bau):
        ersatz = ERSETZT.get((r["ziel_kanal"], N(r["titel"])))
        letzter[(r["ziel_kanal"], N(ersatz or r["titel"]))] = i

    zeilen, fehlend = [], []
    for i, r in enumerate(bau):
        forum, titel = r["ziel_kanal"], r["titel"]
        ersatz = ERSETZT.get((forum, N(titel)))
        if ersatz:
            titel = ersatz
        antwort = (BEKANNTE_ANTWORTEN.get((forum, N(titel)))
                   if letzter.get((forum, N(titel))) == i else None)
        t = index.get((forum, norm_title(titel)))
        if antwort:
            tid, url, aktion = antwort[0], antwort[1], "reply-existing"
        elif t:
            tid, aktion = t["id"], "created"
            url = f"https://discord.com/channels/{GILD}/{tid}"
        else:
            tid, url, aktion = "", "", "FEHLT"
            fehlend.append(f"[{forum}] {titel}")
        zeilen.append({"datei": r["datei"], "ziel_kanal": forum, "titel": titel,
                       "tags": r.get("tags", ""), "aktion": aktion,
                       "thread_id": tid, "url": url, "fehler": ""})

    if args.schreiben:
        tmp = pathlib.Path(args.result).with_suffix(".tmp")
        with tmp.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=COLS, delimiter=";")
            w.writeheader()
            w.writerows(zeilen)
        tmp.replace(args.result)          # atomar: nie eine halbe Datei hinterlassen
    print(f"  {len(zeilen)} Zeilen rekonstruiert ({sum(1 for z in zeilen if z['aktion']=='created')} neu, "
          f"{sum(1 for z in zeilen if z['aktion']=='reply-existing')} Antworten)"
          + ("" if args.schreiben else "  (Probelauf)"))
    print(f"  ohne Thread: {len(fehlend)}")
    for f in fehlend:
        print(f"     {f}")
    return 0 if not fehlend else 1


if __name__ == "__main__":
    raise SystemExit(main())
