#!/usr/bin/env python3
"""Schlägt für unspezifisch benannte Beiträge das inhaltlich passende Ziel vor.

Domenic: „diese sollten gescanned, und wenn nötig separiert werden, dann sollte
das Material richtig benannt bzw. in bestehende Foren einsortiert werden".

Kein Raten nach Titelähnlichkeit: hier wird der **Inhalt** verglichen (Wortmengen
des extrahierten Textes). Für jedes Material werden die ähnlichsten Stücke aus dem
Bestand gesucht — und der Thread, in dem sie stecken (aus den Manifesten). Erst
wenn der Inhalt auf einen vorhandenen Thread zeigt, wird dieser zum Ziel.

Aufruf:  python3 einsortieren_vorschlag.py [--alle] [--top N]
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import re
import sys

S = pathlib.Path(__file__).resolve().parent
PROJECT = S.parent
sys.path.insert(0, str(S))
import classify                                    # noqa: E402

STOPP = set("""der die das und oder aber wenn dann als bei mit von zu im in am an auf fuer für
ist sind war waren wird werden kann können muss müssen soll sollen ein eine einer eines einem
den dem des sich auch noch nur schon sehr mehr wie was wer wo hier dort alle allen alles
the and for with that this from have has not you your are was were will would can could
seite seiten aufgabe aufgaben arbeitsblatt loesung lösung loesungen klasse""".split())


def worte(t: str, n: int = 400) -> set[str]:
    w = re.findall(r"[a-zäöüß]{4,}", (t or "").lower())
    return {x for x in w if x not in STOPP}


def containment(a: set[str], b: set[str]) -> float:
    """Wie viel von a steckt in b (0..1). Klein gegen groß ist gewollt."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a)


def lade_bestand() -> list[dict]:
    """Bestandsdateien mit Text + dem Thread, in dem sie gepostet wurden."""
    thread_von_datei = {}
    for p in PROJECT.glob("manifest*.result.csv"):
        fach = p.stem.replace("manifest_", "").replace(".result", "")
        try:
            for r in csv.DictReader(p.open(newline="", encoding="utf-8"), delimiter=";"):
                if r.get("thread_id"):
                    thread_von_datei[r["datei"]] = {"thread_id": r["thread_id"], "url": r.get("url", ""),
                                                    "titel": r.get("titel", ""), "fach": fach}
        except Exception:
            pass
    aus = []
    for p in PROJECT.glob("_text_*.json"):
        if p.name == "_text_neu.json":
            continue
        for r in json.load(p.open()):
            t = r.get("text") or ""
            if len(t) < 60:
                continue
            datei = r.get("datei") or pathlib.Path(r.get("pfad", "")).name
            th = thread_von_datei.get(datei, {})
            aus.append({"fach": r.get("kanal", ""), "datei": datei, "worte": worte(t),
                        "titel": th.get("titel", ""), "thread_id": th.get("thread_id", ""),
                        "url": th.get("url", "")})
    return aus


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--alle", action="store_true", help="alle Welle-Posts prüfen, nicht nur Sammel-Titel")
    args = ap.parse_args()

    sys.path.insert(0, str(S))
    from unspezifisch_scan import ist_sammel       # noqa: E402
    kept = classify.load_kept("neu")
    klass = json.load((PROJECT / "_klass_neu.json").open())
    bestand = lade_bestand()
    print(f"  Bestand mit Text: {len(bestand)} Dateien\n")

    for post in klass:
        if not args.alle and not ist_sammel(post["titel"]):
            continue
        roh = [kept[i] for i in post["ids"]]
        w = worte("\n".join(r.get("text", "") for r in roh))
        treffer = sorted(((containment(w, b["worte"]), b) for b in bestand
                          if b["fach"] == post["ziel"]), key=lambda z: -z[0])[:args.top]
        print(f"  [{post['ziel']}] {post['titel']}")
        print(f"     Dateien: {', '.join(d['datei'][:44] for d in roh)}")
        for q, b in treffer:
            if q >= 0.15:
                ziel = b["titel"] or "(Thread unbekannt)"
                print(f"     {q:4.2f}  inhaltlich am nächsten: {ziel[:52]:<52} [{b['fach']}] {b['datei'][:30]}")
        if not treffer or treffer[0][0] < 0.15:
            print(f"     kein Treffer >= 0,15 — eigenständiges Thema")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
