#!/usr/bin/env python3
"""Findet Beiträge mit Sammel-Titeln (`Mitschriften`, `Online - Aufgaben`, ...).

Domenic: „manche posts sind mit 'Mitschriften' betitelt was nicht sonderlich
zielführend ist, diese sollten gescanned, und wenn nötig separiert werden, dann
sollte das Material richtig benannt bzw. in bestehende Foren einsortiert werden".

Ein Titel gilt hier NICHT nach Gefühl als zu unspezifisch, sondern nach einer
nachvollziehbaren Regel: er besteht nur aus Behälter-Wörtern (Mitschriften,
Aufgaben, Sammlung, Sonstiges …) und enthält **kein** Fachwort. Damit ist die
Liste prüfbar statt bauchgefühlig.

Quellen: die eigene Welle (manifest_neu.csv, Inhalt über die IDs aus
_klass_neu.json) UND der Server (aktive Threads), damit auch die älteren Wellen
erfasst sind.

Aufruf:  python3 unspezifisch_scan.py [--zeigen]
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import pathlib
import re
import sys

S = pathlib.Path(__file__).resolve().parent
PROJECT = S.parent
sys.path.insert(0, str(S))
import classify                                # noqa: E402
from agy_discord import Client, get_token, ist_sammeltitel   # noqa: E402
from post_neu import load_map                  # noqa: E402

GILD = "1539350758481469500"


def ist_sammel(titel: str) -> bool:
    """Regel lebt in agy_discord.ist_sammeltitel — eine Stelle für alle Skripte."""
    return ist_sammeltitel(titel)


def kurz(t: str, n: int = 250) -> str:
    return re.sub(r"\s+", " ", (t or "")).strip()[:n]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zeigen", action="store_true")
    args = ap.parse_args()

    kept = classify.load_kept("neu")
    klass = json.load((PROJECT / "_klass_neu.json").open())
    welle = []
    for post in klass:
        roh = [kept[i] for i in post["ids"]]
        welle.append({"forum": post["ziel"], "titel": post["titel"], "art": post["art"],
                      "dateien": [r["datei"] for r in roh],
                      "text": kurz("\n".join(r.get("text", "") for r in roh))})
    welle_sammel = [w for w in welle if ist_sammel(w["titel"])]

    client = Client(get_token("AGY_TOKEN_NEU"))
    kanaele = load_map(PROJECT / "foren-map.resolved.csv")
    id_zu_forum = {v["id"]: k for k, v in kanaele.items()}
    threads_all = client.get(f"/guilds/{GILD}/threads/active").get("threads", [])
    server = sorted(({"forum": id_zu_forum.get(t.get("parent_id"), "?"), "titel": t["name"],
                      "thread_id": t["id"], "nachrichten": t.get("message_count", 0)}
                     for t in threads_all if ist_sammel(t.get("name", ""))),
                    key=lambda d: (d["forum"], d["titel"]))

    print(f"  Server: {len(threads_all)} aktive Threads | {len(server)} mit Sammel-Titel")
    for f, n in collections.Counter(d["forum"] for d in server).most_common():
        print(f"     {f:<14} {n}")
    print(f"\n  Eigene Welle: {len(welle)} Posts | {len(welle_sammel)} mit Sammel-Titel")
    if args.zeigen:
        print("\n  --- vorhandene Threads mit Sammel-Titel ---")
        for d in server:
            print(f"    {d['forum']:<13} {d['titel'][:48]:<48} {d['nachrichten']:>2}N  {d['thread_id']}")
        print("\n  --- Welle: Sammel-Titel mit Inhalt ---")
        for w in welle_sammel:
            print(f"\n    [{w['forum']}] {w['titel']}")
            for d in w["dateien"]:
                print(f"       Datei: {d}")
            print(f"       Inhalt: {w['text'][:300]}")
    with (PROJECT / "_pruefen" / "unspezifisch.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["quelle", "forum", "titel", "art", "dateien",
                                           "thread_id", "nachrichten", "text"], delimiter=";")
        w.writeheader()
        for d in server:
            w.writerow({"quelle": "server", "forum": d["forum"], "titel": d["titel"],
                        "thread_id": d["thread_id"], "nachrichten": d["nachrichten"]})
        for x in welle_sammel:
            w.writerow({"quelle": "welle", "forum": x["forum"], "titel": x["titel"],
                        "art": x["art"], "dateien": " | ".join(x["dateien"]), "text": x["text"]})
    print("\n-> _pruefen/unspezifisch.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
