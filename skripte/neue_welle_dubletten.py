#!/usr/bin/env python3
"""Dubletten-Vorprüfung für die neue Welle — read-only, postet nichts.

Domenic: „prüfen was schon vorhanden ist damit sich nichts doppelt, wenn dann inhalt
zu bestehendem Forum hinzufügen". Genau das macht post_neu beim Posten selbst
(find_duplicate -> reply-existing). Hier wird es VORHER sichtbar gemacht:

  NEU          kein Thread mit ähnlichem Titel im Forum -> neuer Thread
  ANTWORT      Thread vorhanden -> der Inhalt geht als Antwort dorthin

Die Threadlisten werden je Forum EINMAL geholt (nicht je Post) — sonst wären es
~200 Discord-Abfragen statt 10 und die Rate-Grenze schnell erreicht.

Aufruf:  python3 neue_welle_dubletten.py [--zeigen]
"""
from __future__ import annotations

import argparse
import csv
import difflib
import pathlib
import sys
import time

S = pathlib.Path(__file__).resolve().parent
PROJECT = S.parent
sys.path.insert(0, str(S))
from agy_discord import Client, get_token                   # noqa: E402
from post_neu import DEDUP_RATIO, load_map, norm_title       # noqa: E402

AUS = PROJECT / "_pruefen" / "welle_dubletten.csv"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zeigen", action="store_true")
    args = ap.parse_args()

    rows = list(csv.DictReader((PROJECT / "manifest_neu.csv").open(
        newline="", encoding="utf-8"), delimiter=";"))
    client = Client(get_token("AGY_TOKEN_NEU"))
    kanal_map = load_map(PROJECT / "foren-map.resolved.csv")

    threads: dict[str, list] = {}
    for forum in sorted({r["ziel_kanal"] for r in rows}):
        cid = kanal_map[forum]["id"]
        gid = client.get(f"/channels/{cid}").get("guild_id")
        threads[forum] = client.forum_threads(cid, gid)
        print(f"  {forum:<14} {len(threads[forum]):>3} Threads im Forum")
        time.sleep(0.6)

    ergebnis, neu, antwort = [], 0, 0
    for r in rows:
        ziel_norm = norm_title(r["titel"])
        # Die zwei ähnlichsten vorhandenen Titel: der nächste entscheidet (Schwelle),
        # der zweite macht benachbarte Themen sichtbar — die will Domenic sehen,
        # ohne dass die Schwelle sie zusammenlegt (Französische vs. Amerikanische
        # Revolution: 0,79, also thematisch verschieden trotz Textähnlichkeit).
        nah = sorted(((difflib.SequenceMatcher(None, ziel_norm, norm_title(t.get("name", ""))).ratio(),
                       t) for t in threads.get(r["ziel_kanal"], [])), key=lambda z: -z[0])[:2]
        beste, bester = (nah[0][0], nah[0][1]) if nah else (0.0, None)
        if bester and beste >= DEDUP_RATIO:
            antwort += 1
            status, wo = "ANTWORT", bester["name"]
        else:
            neu += 1
            status, wo = "NEU", ""
        ergebnis.append({"forum": r["ziel_kanal"], "titel": r["titel"], "art": r["tags"],
                         "status": status, "bestehender_thread": wo,
                         "aehnlichkeit": f"{beste:.2f}" if wo else "",
                         "nachbar1": f"{nah[0][1]['name'][:44]} ({nah[0][0]:.2f})" if nah and nah[0][0] >= 0.45 else "",
                         "nachbar2": f"{nah[1][1]['name'][:44]} ({nah[1][0]:.2f})" if len(nah) > 1 and nah[1][0] >= 0.45 else "",
                         "datei": r["datei"]})

    with AUS.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(ergebnis[0].keys()), delimiter=";")
        w.writeheader()
        w.writerows(ergebnis)
    print(f"\n  {len(ergebnis)} Posts: {neu} neu, {antwort} als Antwort in bestehenden Thread")
    print(f"-> {AUS.relative_to(PROJECT)}")
    if args.zeigen:
        for e in ergebnis:
            zusatz = (f"   -> {e['bestehender_thread'][:36]} ({e['aehnlichkeit']})"
                      if e["bestehender_thread"] else "")
            print(f"  {e['status']:<8} {e['forum']:<13} {e['titel'][:46]:<46}{zusatz}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
