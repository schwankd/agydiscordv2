#!/usr/bin/env python3
"""Kontaktbogen: alle Seiten einer PDF als Übersichtsbild — für die Sichtprüfung.

Textstatistik trennt "eine PDF mit zwei Themen" nicht von einer normalen
Zusammenfassung (gemessen: die Werte überlappen sich). Verlässlich ist nur der
Blick auf die Seiten. Dieser Bogen macht daraus EIN Bild statt N Einzelbilder.

Aufruf:
    python3 sheet.py --datei "../eingang/.../Datei.pdf"
    python3 sheet.py --risiko            # Kandidaten auflisten (mehrseitig, eine Quelle)
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from agy_discord import CONTAINER_EXT  # noqa: E402
from classify import PROJECT  # noqa: E402
from deepcheck import clusters, subjects  # noqa: E402

OUT = PROJECT / "_pruefen" / "bogen"
SPALTEN = 6
KACHEL = 300


def risiko() -> list[tuple[str, str, dict]]:
    """Mehrseitige PDFs, die als EIN Post hängen — je unsicherer, desto weiter oben.

    Ohne Textlayer und länger als 6 Seiten = die Zuordnung hat nur die ersten
    6 Seiten gesehen (pdf_text-Deckel) -> oben.
    """
    aus = []
    for m in subjects():
        files, klass = clusters(m)
        for c in klass:
            fs = [files[i] for i in c["ids"] if 0 <= i < len(files)]
            if len(fs) == 1 and fs[0]["typ"] == ".pdf" and fs[0]["seiten"] > 1:
                f = fs[0]
                ohne_text = f["seiten_mit_text"] < f["seiten"] // 3
                rang = (0 if (ohne_text and f["seiten"] > 6) else
                        1 if ohne_text else 2)
                aus.append((rang, m, f, c))
    aus.sort(key=lambda x: (x[0], -x[2]["seiten"]))
    return aus


def bogen(pfad: pathlib.Path, name: str, out: pathlib.Path) -> pathlib.Path:
    import fitz
    from PIL import Image, ImageDraw
    doc = fitz.open(pfad)
    kacheln = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=70)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        img.thumbnail((KACHEL, KACHEL), Image.LANCZOS)
        kachel = Image.new("RGB", (KACHEL, KACHEL + 18), "white")
        kachel.paste(img, ((KACHEL - img.width) // 2, 0))
        ImageDraw.Draw(kachel).text((6, KACHEL + 3), f"S{i + 1}", fill="black")
        kacheln.append(kachel)
    doc.close()
    zeilen = (len(kacheln) + SPALTEN - 1) // SPALTEN
    sheet = Image.new("RGB", (SPALTEN * KACHEL, zeilen * (KACHEL + 18)), "white")
    for i, k in enumerate(kacheln):
        sheet.paste(k, ((i % SPALTEN) * KACHEL, (i // SPALTEN) * (KACHEL + 18)))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print(f"{name}: {len(kacheln)} Seiten -> {out} ({sheet.width}x{sheet.height})")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--datei", help="Pfad zur Quell-PDF")
    ap.add_argument("--risiko", action="store_true", help="Kandidaten auflisten")
    ap.add_argument("--top", type=int, default=0, help="Bögen für die ersten N Kandidaten bauen")
    args = ap.parse_args()

    if args.risiko or args.top:
        for rang, m, f, c in risiko()[:args.top or 40]:
            stufe = ["OHNE TEXTLAYER, >6 Seiten (nur 6 bewertet)",
                     "ohne Textlayer", "mit Textlayer"][rang]
            print(f"  [{m}] {c['titel'][:46]:<46} {f['seiten']:>3} S.  {stufe}")
            print(f"         {f['datei'][:70]}")
        if args.top:
            for rang, m, f, c in risiko()[:args.top]:
                bogen(pathlib.Path(f["pfad"]), f"{m} — {c['titel'][:40]}",
                      OUT / f"{m}_{pathlib.Path(f['datei']).stem[:40]}.png")
        return 0

    if args.datei:
        p = pathlib.Path(args.datei)
        bogen(p, p.stem, OUT / f"{p.stem[:50]}.png")
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
