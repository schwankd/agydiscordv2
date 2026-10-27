#!/usr/bin/env python3
"""Inhalt -> Fach + Kurs, wenn Dateiname oder Ordner nichts hergeben.

Grundlage: das Archiv der Alt-Server ist ein **beschrifteter Referenzkorpus** —
jedes dort abgelegte Dokument weiß aus seinem Kanal, welches Fach und welche
Stufe es ist. Ein neues Dokument wird also nicht geraten, sondern über seinen
Inhalt den ähnlichsten Archivdokumenten gegenübergestellt; deren Beschriftung
entscheidet. Die Belege werden mitgeliefert („ähnlich wie …").

Bewertet wird über Wortmengen (Jaccard). Grenzen sind ehrlich eingebaut:
OCR-Rauschen, Handschrift und sehr kurze Texte liefern keine belastbare
Zuordnung — dann sagt das Werkzeug „offen" statt zu raten.

Aufruf:
    python3 zuordnen.py --pruefen              # Selbsttest (Leave-one-out) mit Trefferquoten
    python3 zuordnen.py --offen                # unzugeordnetes Material aus _index_neu.csv
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from classify import ziel_of  # noqa: E402

PROJECT = pathlib.Path(__file__).resolve().parent.parent
MIN_TOKENS = 15          # darunter ist ein Dokument kein brauchbares Beispiel
K = 5                    # Stimmen aus den k ähnlichsten Dokumenten
CLEAR = 0.60             # ab diesem Stimmenanteil gilt ein Ziel als klar
MARGIN = 0.15            # Abstand nötig, damit „klar" gilt statt „unklar"
ZWEIT = 0.20             # ab diesem Anteil kommt eine Stufe als zweites Ziel mit


def tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-zäöüß]{4,}", (text or "").lower())}


def thash(text: str) -> str:
    return hashlib.sha1((text or "").strip().lower().encode("utf-8")).hexdigest()


def kurs_von(ziel: str) -> str:
    return "GK" if ziel.endswith("-gk") else ("LK" if ziel.endswith("-lk") else "E-Phase")


def referenz() -> list[dict]:
    """Alle ARCHIV-Dokumente mit brauchbarem Text — die beschrifteten Beispiele.

    Selbst abgelegtes Material (`server = "neu (direkt)"`) gehört NICHT hinein:
    es hat keine echte Kanal-Herkunft, sein Kanalname ist nur ein Ordnername.
    Ohne diesen Ausschluss referenziert sich neues Material selbst und schlägt
    seinen eigenen Ordnernamen als Forum vor (im Test aufgefallen).
    """
    rows = []
    for f in sorted(PROJECT.glob("_text_*.json")):
        if f.name in ("_text_probe.json", "_text_neu.json"):
            continue
        for r in json.loads(f.read_text(encoding="utf-8")):
            if (r.get("server") or "").startswith("neu"):
                continue
            r["tokens"] = tokens(r["text"])
            if len(r["tokens"]) < MIN_TOKENS:
                continue
            r["ziel"] = ziel_of(r["kanal"], r["server"])
            if not r["ziel"]:
                continue
            r["fach"] = r["ziel"].split("-")[0]
            r["kurs"] = kurs_von(r["ziel"])
            r["thash"] = thash(r["text"])
            rows.append(r)
    return rows


def aehnliche(tok: set[str], ref: list[dict], k: int = K,
              ohne_thash: str | None = None) -> list[tuple[float, dict]]:
    """Die k ähnlichsten Referenzdokumente. Gleicher Inhalt wird ausgeschlossen."""
    aus = []
    for r in ref:
        if ohne_thash and r["thash"] == ohne_thash:
            continue
        inter = len(tok.intersection(r["tokens"]))
        if inter < 3:
            continue
        aus.append((inter / len(tok.union(r["tokens"])), r))
    aus.sort(key=lambda x: -x[0])
    return aus[:k]


def rangliste(treffer: list[tuple[float, dict]]) -> list[tuple[str, float]]:
    """Gewichtete Stimmen der ähnlichen Dokumente -> [(ziel, Anteil)], bester zuerst."""
    gewicht: dict[str, float] = collections.defaultdict(float)
    for score, r in treffer:
        gewicht[r["ziel"]] += max(score, 0.01)
    gesamt = sum(gewicht.values())
    if not gesamt:
        return []
    return sorted(((z, w / gesamt) for z, w in gewicht.items()), key=lambda x: -x[1])


def ziele_of(treffer: list[tuple[float, dict]]) -> tuple[list[str], str]:
    """Entscheidung: EIN Ziel, wenn klar — sonst mehrere (dann bewusst doppelt).

    Ein fast identischer Archivtreffer beweist die Stufe NICHT: gemessen war die
    Stufe dort nur zu 60 % richtig, weil derselbe Inhalt im Alt-Server real in
    zwei Stufen lag. Ist die Stufe nicht eindeutig, wird der Inhalt in beide
    Foren gepostet — lieber doppelt als eine Lücke. Genau deshalb ist die
    Trefferquote der Metrik „geht etwas verloren?" das Maß, nicht „exakt richtig?".
    """
    rang = rangliste(treffer)
    if not rang:
        return [], "keine vergleichbaren Dokumente"
    klar = rang[0][1] >= CLEAR and (len(rang) == 1 or rang[0][1] - rang[1][1] >= MARGIN)
    beleg = ", ".join(f"{z} {a:.0%}" for z, a in rang[:3])
    if klar:
        return [rang[0][0]], f"klar: {rang[0][0]} ({beleg})"
    fach = rang[0][0].split("-")[0]
    kandidaten = [z for z, a in rang if z.split("-")[0] == fach and a >= ZWEIT][:2]
    if not kandidaten:
        kandidaten = [rang[0][0]]
    return kandidaten, f"Stufe unklar -> {' + '.join(kandidaten)} ({beleg})"


def pruefen(zeigen: int = 0) -> int:
    """Leave-one-out: jedes Archivdokument gegen die übrigen zuordnen.

    Gemessen wird zuerst die Frage, die für „keine Lücken" zählt: **liegt das
    richtige Forum unter den vorgeschlagenen Zielen?** Bei unklarer Stufe werden
    bewusst zwei Ziele vorgeschlagen — dann ist nichts verloren, auch wenn die
    Stufe nicht exakt getroffen wurde. Die exakte Quote steht daneben.
    """
    ref = referenz()
    print(f"Referenz: {len(ref)} Dokumente mit brauchbarem Text (>= {MIN_TOKENS} Begriffe)")
    print(f"Fächer: {len(set(r['fach'] for r in ref))} | Stufen: "
          + ", ".join(f"{k} {v}" for k, v in collections.Counter(r["kurs"] for r in ref).items()))

    fach_ok = abgedeckt = exakt = leer = doppelt = 0
    ziele_summe = 0
    fehler, gefaehrdet = [], []
    for r in ref:
        treffer = aehnliche(r["tokens"], ref, ohne_thash=r["thash"])
        ziele, grund = ziele_of(treffer)
        if any(x["thash"] == r["thash"] and x["ziel"] != r["ziel"] for x in ref):
            doppelt += 1
        if not treffer:
            leer += 1
            continue
        ziele_summe += len(ziele)
        if ziele[0].split("-")[0] == r["fach"]:
            fach_ok += 1
        if r["ziel"] in ziele:
            abgedeckt += 1
        else:
            gefaehrdet.append((r, ziele, grund))
        if ziele == [r["ziel"]]:
            exakt += 1
        else:
            fehler.append((r, ziele, grund))

    n = len(ref)
    print(f"\n=== Leave-one-out über {n} Dokumente ===")
    print(f"  richtig Forum dabei (KEIN Verlust): {abgedeckt}/{n}  ({abgedeckt / n:.0%})")
    print(f"  Stufe exakt richtig               : {exakt}/{n}  ({exakt / n:.0%})")
    print(f"  Fach richtig (Vorschlag 1)        : {fach_ok}/{n}  ({fach_ok / n:.0%})")
    print(f"  Ziele je Dokument                 : {ziele_summe / max(1, n - leer):.2f}")
    print(f"  ohne Treffer                      : {leer}")
    print(f"  Inhalt lag im Archiv auch in anderer Stufe (echt mehrdeutig): {doppelt}")

    nach_kurs = collections.defaultdict(lambda: [0, 0])
    for r in ref:
        ziele, _ = ziele_of(aehnliche(r["tokens"], ref, ohne_thash=r["thash"]))
        nach_kurs[r["kurs"]][1] += 1
        nach_kurs[r["kurs"]][0] += (r["ziel"] in ziele)
    print("\n  kein Verlust, nach Stufe des Dokuments:")
    for k in ("E-Phase", "GK", "LK"):
        if k in nach_kurs:
            ok, tot = nach_kurs[k]
            print(f"    {k:<8} {ok:>3}/{tot:<3} ({ok / tot:.0%})")

    if gefaehrdet:
        print(f"\n  ACHTUNG, echtes Risiko ({len(gefaehrdet)}): richtiges Forum NICHT vorgeschlagen")
        for r, ziele, grund in gefaehrdet[:zeigen or 10]:
            print(f"    soll {r['ziel']:<14} bekam {','.join(ziele):<20} {r['datei'][:34]:<34} {grund[:44]}")

    if zeigen:
        print(f"\n  {min(zeigen, len(fehler))} Abweichungen (meist bewusst doppelt):")
        for r, ziele, grund in fehler[:zeigen]:
            print(f"    soll {r['ziel']:<14} bekam {','.join(ziele):<20} {r['datei'][:34]:<34} {grund[:44]}")

    # Entscheidend für die Regel: Wie sicher ist es, wenn der beste Treffer SEHR
    # ähnlich ist? Nur dort darf automatisch zugeordnet werden.
    grenzen = [(0.50, 9.0, ">= 0.50 (fast dasselbe Dokument)"),
               (0.30, 0.50, "0.30 - 0.50"),
               (0.15, 0.30, "0.15 - 0.30"),
               (0.00, 0.15, "< 0.15 (nur Themenverwandtschaft)")]
    print("\n  Trefferqualität des ähnlichsten Dokuments -> wie oft stimmt die Stufe:")
    for unten, oben, name in grenzen:
        ok = tot = mehrdeutig = 0
        for r in ref:
            treffer = aehnliche(r["tokens"], ref, k=1, ohne_thash=r["thash"])
            if not treffer or not (unten <= treffer[0][0] < oben):
                continue
            tot += 1
            ok += treffer[0][1]["ziel"] == r["ziel"]
            if any(x["thash"] == r["thash"] and x["ziel"] != r["ziel"] for x in ref):
                mehrdeutig += 1
        if tot:
            print(f"    {name:<36} {ok:>3}/{tot:<3} ({ok / tot:>4.0%})  "
                  f"davon in zwei Stufen vorhanden: {mehrdeutig}")

    # Wie viel Text braucht es? Dünne OCR (Handyfoto, Handschrift) trägt keine
    # Zuordnung. Diese Messung setzt die Grenze, ab der automatisch zugeordnet wird.
    print("\n  Textumfang -> wie oft ist das richtige Forum dabei:")
    for unten, oben, name in [(400, 10**9, ">= 400 Begriffe (echter Text)"),
                              (150, 400, "150 - 400"),
                              (50, 150, "50 - 150"),
                              (MIN_TOKENS, 50, f"< 50 (nur {MIN_TOKENS}-50)")]:
        ok = tot = 0
        for r in ref:
            if not (unten <= len(r["tokens"]) < oben):
                continue
            ziele, _ = ziele_of(aehnliche(r["tokens"], ref, ohne_thash=r["thash"]))
            if not ziele:
                continue
            tot += 1
            ok += r["ziel"] in ziele
        if tot:
            print(f"    {name:<28} {ok:>3}/{tot:<3} ({ok / tot:>4.0%})")

    if zeigen:
        print(f"\n  {min(zeigen, len(fehler))} Abweichungen im Detail:")
        for r, ziele, grund in fehler[:zeigen]:
            print(f"    soll {r['ziel']:<14} bekam {','.join(ziele):<24} "
                  f"{r['datei'][:34]:<34} {grund[:44]}")
    return 0


def offen() -> int:
    """Neu abgelegtes Material zuordnen -> Vorschlags-CSV (Grundlage: _index_neu.csv).

    Reihenfolge der Beweise, stärkster zuerst:
      1. Identischer Inhalt liegt im Archiv  -> dessen Stufen (kein Raten)
      2. Ähnliche Archivdokumente            -> Mehrheitsentscheid (gemessen ~80 %)
      3. Zu wenig Text (Handyfoto/Handschrift) -> offen, wird gemeldet
    """
    idx = PROJECT / "eingang" / "_index_neu.csv"
    if not idx.exists():
        print("Kein neues Material (eingang/_index_neu.csv fehlt).")
        return 0
    tex = PROJECT / "_text_neu.json"
    if not tex.exists() or tex.stat().st_mtime < idx.stat().st_mtime:
        print("Text fehlt/veraltet -> extrahiere ...")
        subprocess.run([sys.executable, str(pathlib.Path(__file__).resolve().parent / "extract_text.py"),
                        "--match", "neu"], check=True)

    rows = json.loads(tex.read_text(encoding="utf-8"))
    ref = referenz()
    archiv: dict[str, set[str]] = collections.defaultdict(set)
    for r in ref:
        archiv[r["thash"]].add(r["ziel"])

    aus, offen_zaehler, doppelt = [], 0, 0
    for r in rows:
        tok = tokens(r["text"])
        h = thash(r["text"])
        if len(tok) < MIN_TOKENS:
            ziele, grund = [], f"Text nicht lesbar ({len(tok)} Begriffe) — ansehen"
            offen_zaehler += 1
        elif h in archiv:
            ziele = sorted(archiv[h])
            grund = "identischer Inhalt im Archiv: " + " + ".join(ziele)
        else:
            ziele, grund = ziele_of(aehnliche(tok, ref, ohne_thash=h))
            if not ziele:
                grund, offen_zaehler = "keine vergleichbaren Dokumente — ansehen", offen_zaehler + 1
        if len(ziele) > 1:
            doppelt += 1
        aus.append({"datei": r["datei"], "ordner": r["kanal"],
                    "vorschlag": " + ".join(ziele) or "OFFEN",
                    "beleg": grund, "bytes": r["bytes"]})

    out = PROJECT / "zuordnung_vorschlag.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["datei", "ordner", "vorschlag", "beleg", "bytes"],
                           delimiter=";")
        w.writeheader()
        w.writerows(aus)

    print(f"\n{len(aus)} Dokumente -> {out.name}")
    print(f"  eindeutig zugeordnet : {len(aus) - offen_zaehler - doppelt}")
    print(f"  bewusst doppelt      : {doppelt}  (Stufe unklar -> beide Foren)")
    print(f"  OFFEN (ansehen)      : {offen_zaehler}")
    print("\n  Belegte Zuordnung ist ein VORSCHLAG: Fach 89 %, Fach+Stufe 78 % gemessen.")
    print("  Vor dem Posten prüfen (Vorschau-CSV), bei OFFEN selbst entscheiden.")
    for r in aus[:20]:
        print(f"    {r['vorschlag']:<34} {r['datei'][:34]:<34} {r['beleg'][:44]}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pruefen", action="store_true", help="Selbsttest mit Trefferquoten")
    ap.add_argument("--offen", action="store_true", help="neu abgelegtes Material zuordnen")
    ap.add_argument("--zeigen", type=int, default=0, help="Abweichungen anzeigen")
    args = ap.parse_args()
    if args.pruefen:
        return pruefen(args.zeigen)
    if args.offen:
        return offen()
    print(__doc__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
