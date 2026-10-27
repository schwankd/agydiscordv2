#!/usr/bin/env python3
"""Tiefenprüfung des Material-Imports: Vollständigkeit, Dopplungen, Themengrenzen.

Arbeitet auf denselben Daten wie die Pipeline (klassify.load_kept = nach Inhalt
deduplizierte Liste, dieselbe Reihenfolge wie beim Klassifizieren) und den gebauten
Dateien in sortiert/. Ohne --live keine Discord-Aufrufe, nie Schreibzugriffe.

  1 Vollständigkeit   jede Quelldatei in genau einem Thema? nichts verloren
                      (absichtlich übersprungene Dubletten werden unterschieden)?
  2 Dopplungen        gleicher Inhalt/Titel zweimal im selben Forum — mit --live
                      gegen den echten Server statt gegen das Manifest
  3 Forum-übergreifend gleicher Inhalt in mehreren Foren (kann gewollt sein)
  4 Bündelung         Post aus mehreren Dateien — passen die inhaltlich zusammen?
  5 Themengrenzen     Quelldatei mit mehreren Seiten — springt das Thema?
                      (mit --pages; Seiten ohne Textlayer zusätzlich per OCR)

Aufruf:
    python3 deepcheck.py                      # 1-4, offline
    python3 deepcheck.py --live               # + Titel-Abgleich am Server
    python3 deepcheck.py --pages --limit 400  # + Seitenanalyse (OCR)
"""
from __future__ import annotations

import argparse
import collections
import csv
import difflib
import hashlib
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from agy_discord import CONTAINER_EXT  # noqa: E402
from classify import NOISE, PROJECT, SORTIERT, load_kept  # noqa: E402

def clusters(match: str) -> tuple[list[dict], list[dict]]:
    """Dateiliste in der Reihenfolge, in der klassifiziert wurde (= ID-Raum)."""
    klass = json.loads((PROJECT / f"_klass_{match}.json").read_text(encoding="utf-8"))
    return load_kept(match), klass


def subjects() -> list[str]:
    return sorted(p.name[len("_klass_"):-len(".json")] for p in PROJECT.glob("_klass_*.json"))


def tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-zäöüß]{4,}", (text or "").lower())}


def jaccard(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    return len(ta & tb) / len(ta | tb) if ta and tb else -1.0


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------- 1 Vollständig

def check_coverage() -> tuple[list[str], set[str]]:
    print("=" * 78)
    print("1  VOLLSTÄNDIGKEIT — jede Quelldatei in genau einem Thema?")
    print("=" * 78)
    problems: list[str] = []
    used_paths: set[str] = set()
    for m in subjects():
        files, klass = clusters(m)
        used = collections.Counter(i for c in klass for i in c["ids"])
        dup = {i: n for i, n in used.items() if n > 1}
        oob = [i for i in used if not 0 <= i < len(files)]
        unused = [i for i in range(len(files)) if i not in used]
        used_paths |= {files[i]["pfad"] for i in used if 0 <= i < len(files)}
        flag = "OK " if not (dup or oob or unused) else "!! "
        print(f"  {flag}{m:<14} {len(files):>4} Dateien | {len(klass):>3} Themen | "
              f"doppelt verwendet {len(dup)} | ohne Thema {len(unused)} | ungültig {len(oob)}")
        for i in sorted(dup):
            problems.append(f"{m}: Datei {i} in {dup[i]} Themen gleichzeitig")
        for i in oob:
            problems.append(f"{m}: Index {i} außerhalb der Dateiliste")
        for i in unused:
            problems.append(f"{m}: ohne Thema -> {files[i]['datei']}")
    return problems, used_paths


def check_coverage_global(used_paths: set[str]) -> list[str]:
    """Dateien im Index, die in keinem Thema gelandet sind — echte Verluste vs. Dubletten."""
    rows = []
    for idx in sorted((PROJECT / "eingang").glob("_index*.csv")):
        rows += [r for r in csv.DictReader(idx.open(newline="", encoding="utf-8"), delimiter=";")
                 if (r.get("dateiname") or "").strip()
                 and not r.get("fehler")
                 and pathlib.Path(r["dateiname"]).suffix.lower() not in CONTAINER_EXT
                 and r.get("gespeichert")
                 and r["kanal"] not in NOISE]
    index = {r["gespeichert"]: r for r in rows}
    fehlend = [p for p in index if p not in used_paths]

    benutzt_hashes = {}
    for p in used_paths:
        f = pathlib.Path(p)
        if f.exists():
            benutzt_hashes.setdefault(sha(f), p)

    verloren, dubl = [], []
    for p in fehlend:
        f = pathlib.Path(p)
        h = sha(f) if f.exists() else None
        if h and h in benutzt_hashes:
            dubl.append((p, benutzt_hashes[h]))
        else:
            verloren.append(p)

    print(f"\n  Global: {len(index)} Material-Dateien im Index | {len(used_paths)} in Themen verarbeitet")
    print(f"  Übersprungen als Inhalts-Dublette: {len(dubl)}  |  WIRKLICH VERLOREN: {len(verloren)}")
    for p, twin in dubl:
        print(f"    Dublette  {pathlib.Path(p).name[:44]:<44} = {pathlib.Path(twin).name[:40]}")
    for p in verloren:
        print(f"    VERLOREN  {pathlib.Path(p).name[:66]}")
    return [f"verloren: {pathlib.Path(p).name}" for p in verloren]


# ---------------------------------------------------------------- 2/3 Dopplungen

def forum_manifest_rows() -> dict[str, list[tuple[str, str, str]]]:
    pro_forum: dict[str, list[tuple[str, str, str]]] = collections.defaultdict(list)
    for m in subjects():
        man = PROJECT / f"manifest_{m}.csv"
        if not man.exists():
            print(f"  !! manifest_{m}.csv fehlt")
            continue
        for r in csv.DictReader(man.open(newline="", encoding="utf-8"), delimiter=";"):
            f = SORTIERT / r["datei"]
            if not f.exists():
                print(f"  !! Datei fehlt in sortiert/: {r['datei']}")
                continue
            pro_forum[r["ziel_kanal"]].append((sha(f), r["titel"], r["datei"]))
    return pro_forum


def check_dupes(pro_forum: dict) -> list[str]:
    print()
    print("=" * 78)
    print("2  DOPPLUNGEN im Manifest — gleicher Inhalt/Titel zweimal im selben Forum?")
    print("=" * 78)
    problems = []
    for forum in sorted(pro_forum):
        rows = pro_forum[forum]
        by_hash, by_title = collections.defaultdict(list), collections.defaultdict(list)
        for h, t, d in rows:
            by_hash[h].append((t, d))
            by_title[t.strip().lower()].append(d)
        dh = {h: v for h, v in by_hash.items() if len(v) > 1}
        dt = {t: v for t, v in by_title.items() if len(v) > 1}
        print(f"  {'OK ' if not (dh or dt) else '!! '}{forum:<18} {len(rows):>3} Beiträge | "
              f"Inhalts-Dubletten {len(dh)} | Titel-Dubletten {len(dt)}")
        for h, v in dh.items():
            problems.append(f"{forum}: gleicher Inhalt in {len(v)} Beiträgen {[x[0][:30] for x in v]}")
        for t, v in dt.items():
            print(f"       Titel doppelt -> {t[:66]}")
    return problems


def check_live() -> list[str]:
    """Titel-Dubletten am echten Server (Manifest sagt nichts über Antworten)."""
    print()
    print("=" * 78)
    print("2b LIVE-SERVER — welche Themen haben dort doppelte Titel?")
    print("=" * 78)
    from agy_discord import Client, get_token
    c = Client(get_token("AGY_TOKEN_NEU"))
    gid = c.get("/users/@me/guilds")
    if not gid:
        print("  !! Bot sieht keine Server"); return []
    guild = gid[0]["id"]
    ids = {r["Forum_Kanal"]: r["Kanal_ID"] for r in
           csv.DictReader((PROJECT / "foren-map.resolved.csv").open(newline="", encoding="utf-8"), delimiter=";")}
    problems = []
    for forum in sorted(ids):
        threads = c.forum_threads(ids[forum], guild)
        if not threads:
            continue
        cnt = collections.Counter(t["name"].strip().lower() for t in threads)
        dt = {n: k for n, k in cnt.items() if k > 1}
        print(f"  {'OK ' if not dt else '!! '}{forum:<18} {len(threads):>3} Threads | Titel-Dubletten {len(dt)}")
        for n, k in dt.items():
            problems.append(f"LIVE {forum}: {k}x Titel '{n}'")
    return problems


def check_cross(pro_forum: dict) -> None:
    print()
    print("=" * 78)
    print("3  FORUM-ÜBERGREIFEND — gleicher Inhalt in mehreren Foren (ggf. gewollt)")
    print("=" * 78)
    cross = collections.defaultdict(set)
    for forum, rows in pro_forum.items():
        for h, _t, _d in rows:
            cross[h].add(forum)
    mehr = {h: f for h, f in cross.items() if len(f) > 1}
    for h, foren in mehr.items():
        print(f"  {sorted(foren)}")
    print(f"  {len(mehr)} Inhalte liegen in mehreren Foren (gleiche Datei, andere Stufe).")


# ---------------------------------------------------------------- 4 Bündelung

def check_bundles() -> list[str]:
    print()
    print("=" * 78)
    print("4  BÜNDELUNG — Posts aus mehreren Dateien: passen sie inhaltlich zusammen?")
    print("=" * 78)
    alle = []
    for m in subjects():
        files, klass = clusters(m)
        for c in klass:
            fs = [files[i] for i in c["ids"] if 0 <= i < len(files)]
            if len(fs) < 2:
                continue
            sims = [jaccard(fs[a]["text"], fs[b]["text"])
                    for a in range(len(fs)) for b in range(a + 1, len(fs))]
            sims = [s for s in sims if s >= 0]
            if sims:
                alle.append((min(sims), m, c, len(fs)))
    alle.sort(key=lambda x: (x[0], x[1], x[2]["titel"]))
    schwach = [a for a in alle if a[0] < 0.06]
    print(f"  {len(alle)} Bündel prüfbar | {len(schwach)} mit sehr geringer Textähnlichkeit (<0.06)")
    print("  (Handschrift/OCR streut — Liste zum Ansehen, kein Urteil; niedrigste zuerst)\n")
    for s, m, c, n in alle[:12]:
        print(f"  {s:.3f}  [{m}] {c['titel'][:52]:<52} {n} Dateien {c['ids']}")
    return [f"{m}: {c['titel']} (min {s:.3f}, {n} Dateien)" for s, m, c, n in schwach]


def check_title_content() -> list[str]:
    """Passt der Titel zum Inhalt? Sagt mehr als Textähnlichkeit: findet falsch
    gebündelte oder falsch benannte Themen — der Titel taucht im Text nicht auf."""
    print()
    print("=" * 78)
    print("4b TITEL gegen INHALT — kommt der Titel im Material überhaupt vor?")
    print("=" * 78)
    problems, geprüft = [], 0
    for m in subjects():
        files, klass = clusters(m)
        for c in klass:
            fs = [files[i] for i in c["ids"] if 0 <= i < len(files)]
            union = " ".join(f["text"] for f in fs).lower()
            if len(union) < 150:            # zu wenig OCR-Text -> nicht bewertbar
                continue
            titel_w = {w for w in re.findall(r"[a-zäöüß]{5,}", c["titel"].lower())}
            if not titel_w:
                continue
            text_w = set(re.findall(r"[a-zäöüß]{5,}", union))
            geprüft += 1
            treffer = [t for t in titel_w
                       if t in union or any(t in w or w in t for w in text_w)]
            if len(treffer) < max(1, len(titel_w) // 3):
                problems.append(f"{m}: Titel '{c['titel']}' kaum im Text "
                                f"({len(treffer)}/{len(titel_w)} Begriffe)")
    print(f"  {geprüft} Themen bewertbar | {len(problems)} mit schwachem Titelbezug")
    for p in problems:
        print(f"    {p}")
    return problems


# ---------------------------------------------------------------- 5 Themengrenzen

def check_blank_pages() -> list[str]:
    """Leere Seiten in den gebauten PDFs (Rückseiten von Scans) — messbar, nicht geraten.

    Eine Seite gilt als leer, wenn kaum Tinte auf dem Papier ist. Anders als die
    Themenerkennung ist das ein sauberes Maß.
    """
    print()
    print("=" * 78)
    print("5  LEERE SEITEN in den gebauten PDFs")
    print("=" * 78)
    import fitz
    from PIL import Image
    problems, gesamt, leer = [], 0, 0
    for m in subjects():
        man = PROJECT / f"manifest_{m}.csv"
        if not man.exists():
            continue
        for r in csv.DictReader(man.open(newline="", encoding="utf-8"), delimiter=";"):
            f = SORTIERT / r["datei"]
            if f.suffix.lower() != ".pdf" or not f.exists():
                continue
            doc = fitz.open(f)
            blank = []
            for i, page in enumerate(doc):
                pix = page.get_pixmap(dpi=36)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                grau = img.convert("L")
                dunkel = sum(1 for px in grau.getdata() if px < 200)
                if dunkel / (grau.width * grau.height) < 0.005:
                    blank.append(i + 1)
            n = doc.page_count
            doc.close()
            gesamt += n
            leer += len(blank)
            if blank:
                problems.append(f"{m}: {r['datei']} — {len(blank)}/{n} Seiten leer {blank[:12]}")
    print(f"  {gesamt} Seiten geprüft | {leer} davon leer | {len(problems)} PDFs betroffen")
    for p in problems[:20]:
        print(f"    {p}")
    if len(problems) > 20:
        print(f"    ... und {len(problems) - 20} weitere")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="Titel zusätzlich am echten Server prüfen")
    ap.add_argument("--blank", action="store_true", help="zusätzlich leere Seiten in den PDFs zählen (langsam)")
    args = ap.parse_args()

    problems, used_paths = check_coverage()
    problems += check_coverage_global(used_paths)
    pro_forum = forum_manifest_rows()
    problems += check_dupes(pro_forum)
    if args.live:
        problems += check_live()
    check_cross(pro_forum)
    bundle = check_bundles()
    titel = check_title_content()
    leer = check_blank_pages() if args.blank else []

    print()
    print("=" * 78)
    print("ERGEBNIS")
    print("=" * 78)
    print(f"  Vollständigkeit : {len([p for p in problems if 'verloren' in p or 'ohne Thema' in p or 'doppelt verwendet' in p or 'außerhalb' in p])} echte Probleme")
    print(f"  Dopplungen      : {len([p for p in problems if 'doppelt' in p or 'LIVE' in p])} Auffälligkeiten")
    print(f"  Bündelung       : {len(bundle)} schwache Bündel (Textähnlichkeit, kein Urteil)")
    print(f"  Titel↔Inhalt    : {len(titel)} Themen mit schwachem Titelbezug")
    print(f"  Leere Seiten    : {len(leer)} PDFs betroffen" if args.blank else "  Leere Seiten    : nicht geprüft (--blank)")
    print("  Themengrenzen   : NICHT automatisch prüfbar — Textstatistik trennt eine gemischte")
    print("                    PDF nicht von einer normalen Zusammenfassung. Sichtprüfung über")
    print("                    sheet.py (Kontaktbogen) + Blick auf die Seiten.")
    for p in problems:
        print(f"    - {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
