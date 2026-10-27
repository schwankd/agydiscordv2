#!/usr/bin/env python3
"""Baut pro Post genau EINE PDF aus dem Material und schreibt manifest.csv.

Eingabe : _text_<match>.json (aus extract_text.py) + _klass_<match>.json (Zuordnung)
Ausgabe : sortiert/<Fach>_<Kurs>_<Thema>_<Art>.pdf  +  manifest.csv

Regeln:
  - Bilder werden auf max. 1600 px verkleinert und als Seite eingebettet.
  - Alles eines Posts landet in EINER PDF (PDFs via insert_pdf, Bilder als Seiten).
  - Ergebnis > 10 MB (Discord-Limit) -> per Pixeldeckel/Qualität verkleinern.
  - Immer noch zu groß -> in Teile splitten; jeder Teil wird ein eigener
    Manifest-Eintrag mit gleichem Titel (post_neu hängt Teil 2+ als Antwort an).

Aufruf:
  python3 classify.py --match geschichte --list     # indizierte Dateiliste
  python3 classify.py --match geschichte            # bauen (leert sortiert/ vorher)
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pathlib
import re
import shutil
import sys

import fitz
from PIL import Image, ImageOps

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from agy_discord import ATTACH_EXT, IMG_EXT, XML_TEXT_EXT, office_text  # noqa: E402

PROJECT = pathlib.Path(__file__).resolve().parent.parent
EINGANG = PROJECT / "eingang"
SORTIERT = PROJECT / "sortiert"
NOISE = {"memes-agy", "chat-1-💌", "chat-2-💌", "allgemeines", "herzlich-willkommen",
         "diskussionen", "interessantes"}
LIMIT = 10 * 1024 * 1024
SAFE = 9_400_000          # Zielgröße mit Abstand zum harten 10-MiB-Limit
IMG_MAX_PX = 1600
IMG_QUALITY = 82
COLS = ["datei", "fach", "kurs", "thema", "art", "titel", "ziel_kanal", "tags", "status", "notiz"]


ALIAS = {"mathe": "mathematik"}   # Alt-Kanalkürzel -> offizieller Fachname


def ziel_of(kanal: str, server: str) -> str:
    """Kanalname (aus dem Index) -> Forum-Name auf dem neuen Server.

    Ohne Suffix = E-Phase, `gk-`/`lk-` = Kurs. Das Kürzel wird zuerst auf den
    offiziellen Fachnamen gebracht (gk-mathe -> mathematik-gk).
    Selbst abgelegtes Material (`add_material.py`) trägt das Ziel-Forum schon
    als Kanalnamen -> unverändert übernehmen.
    """
    if server.startswith("neu"):
        return kanal
    if kanal in NOISE:
        return ""
    if kanal.startswith(("gk-", "lk-")):
        kurs, rest = kanal.split("-", 1)
        return f"{ALIAS.get(rest, rest)}-{kurs}"
    fach = ALIAS.get(kanal, kanal)
    return fach if server.startswith("E-Phase") else f"{fach}-gk"


def kurs_of(ziel: str) -> str:
    return "GK" if ziel.endswith("-gk") else ("LK" if ziel.endswith("-lk") else "E-Phase")


def load_kept(match: str) -> list[dict]:
    """Indexierte Dateiliste nach Content-Dedup (nie nach Dateiname!)."""
    raw = json.loads((PROJECT / f"_text_{match}.json").read_text(encoding="utf-8"))
    # Container (.zip) sind hier nicht enthalten — extract_text.py schließt sie aus.
    data = [r for r in raw if match.lower() in r["kanal"].lower()]
    for r in data:
        p = pathlib.Path(r["pfad"])
        r["hash"] = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else "?"
        r["ziel"] = ziel_of(r["kanal"], r["server"])
        r["rel"] = str(p.relative_to(EINGANG))
    kept, seen = [], set()
    for r in sorted(data, key=lambda x: (x["ziel"], x["kanal"], x["zeit"], x["rel"])):
        key = (r["hash"], r["ziel"])
        if key in seen:
            continue
        seen.add(key)
        kept.append(r)
    return kept


def img_to_page(doc: fitz.Document, path: pathlib.Path) -> None:
    img = ImageOps.exif_transpose(Image.open(path))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    if max(img.size) > IMG_MAX_PX:
        img.thumbnail((IMG_MAX_PX, IMG_MAX_PX), Image.LANCZOS)
    tmp = pathlib.Path("/tmp") / f"_agy_{abs(hash(str(path)))}.jpg"
    img.save(tmp, "JPEG", quality=IMG_QUALITY)
    w, h = img.size
    page = doc.new_page(width=w, height=h)          # 1 px = 1 pt: Rasterung bleibt nativ
    page.insert_image(fitz.Rect(0, 0, w, h), filename=str(tmp))
    tmp.unlink(missing_ok=True)


def bundle(paths: list[pathlib.Path], dest: pathlib.Path) -> None:
    doc = fitz.open()
    for p in paths:
        if p.suffix.lower() == ".pdf":
            src = fitz.open(p)
            doc.insert_pdf(src)
            src.close()
        elif p.suffix.lower() in IMG_EXT:
            img_to_page(doc, p)
        elif p.suffix.lower() in XML_TEXT_EXT:
            # Büro-Datei in einer Sammel-PDF: Textseite statt Platzhalter
            page = doc.new_page()
            page.insert_textbox(fitz.Rect(56, 56, page.rect.width - 56, page.rect.height - 56),
                                f"{p.name}\n\n{office_text(p)}", fontsize=10)
        else:
            doc.new_page().insert_text((72, 100), f"[{p.name}] nicht konvertierbar", fontsize=14)
    dest.parent.mkdir(parents=True, exist_ok=True)
    doc.save(dest, deflate=True, garbage=4)
    doc.close()


def rasterize(src_path: pathlib.Path, dest: pathlib.Path, max_px: int, quality: int) -> None:
    """Seiten neu rastern; Pixeldeckel statt dpi, damit Riesen-MediaBoxen nicht explodieren."""
    src = fitz.open(src_path)
    out = fitz.open()
    for page in src:
        r = page.rect
        zoom = min(1.0, max_px / max(r.width, r.height))
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        new = out.new_page(width=pix.width, height=pix.height)
        new.insert_image(fitz.Rect(0, 0, pix.width, pix.height),
                         stream=pix.tobytes("jpeg", jpg_quality=quality))
    out.save(dest, deflate=True, garbage=4)
    out.close()
    src.close()


def compress(path: pathlib.Path) -> list[pathlib.Path]:
    """Bringt die PDF unter 10 MB. Rückgabe: 1 Datei oder mehrere Teile."""
    if path.stat().st_size <= SAFE:
        return [path]
    before = path.stat().st_size
    best, best_size = None, None
    for max_px, q in ((1600, 70), (1600, 52), (1300, 42)):
        tmp = path.with_name(f"{path.stem}.r{max_px}q{q}.pdf")
        rasterize(path, tmp, max_px, q)
        size = tmp.stat().st_size
        if size <= SAFE:
            if best is not None:
                best.unlink(missing_ok=True)
            tmp.replace(path)
            print(f"      komprimiert {before/1e6:.1f} -> {size/1e6:.1f} MB (max {max_px}px q{q})")
            return [path]
        if best_size is None or size < best_size:
            if best is not None:
                best.unlink(missing_ok=True)
            best, best_size = tmp, size
        else:
            tmp.unlink(missing_ok=True)
    best.replace(path)

    if path.stat().st_size <= SAFE:
        print(f"      komprimiert {before/1e6:.1f} -> {best_size/1e6:.1f} MB")
        return [path]

    doc = fitz.open(path)
    pages = doc.page_count
    parts = 2
    while parts <= 8:
        chunk = -(-pages // parts)
        outs = []
        for i in range(parts):
            part = path.with_name(f"{path.stem}-Teil{i + 1}.pdf")
            sub = fitz.open()
            sub.insert_pdf(doc, from_page=i * chunk,
                           to_page=min(pages - 1, (i + 1) * chunk - 1))
            sub.save(part, deflate=True, garbage=4)
            sub.close()
            outs.append(part)
        if all(p.stat().st_size <= LIMIT for p in outs):
            doc.close()
            path.unlink(missing_ok=True)
            print(f"      {before/1e6:.1f} MB -> {parts} Teile "
                  + ", ".join(f"{p.stat().st_size/1e6:.1f}MB" for p in outs))
            return outs
        for p in outs:
            p.unlink(missing_ok=True)
        parts += 1
    doc.close()
    return [path]


def slug(s: str) -> str:
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")[:70]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--match", required=True)
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    kept = load_kept(args.match)

    if args.list:
        print(f"{len(kept)} Dateien (nach Content-Dedup), Index für _klass_{args.match}.json\n")
        for i, r in enumerate(kept):
            hint = re.sub(r"\s+", " ", r["text"])[:70]
            print(f"{i:>3} | {r['ziel']:<14} | {r['rel'][-58:]:<58} | {hint}")
        return 0

    spec_path = PROJECT / f"_klass_{args.match}.json"
    posts = json.loads(spec_path.read_text(encoding="utf-8"))

    SORTIERT.mkdir(parents=True, exist_ok=True)
    # Nur die Dateien DIESES Fachs ersetzen — andere Wellen bleiben liegen.
    faecher = {slug(p["ziel"].split("-")[0].capitalize()) for p in posts}
    old = [p for p in SORTIERT.glob("*.pdf") if p.name.split("_")[0] in faecher]
    for p in old:
        p.unlink()
    if old:
        print(f"sortiert/: {len(old)} Datei(en) dieses Fachs ersetzt")

    used: set[int] = set()
    rows, problems = [], []
    for i, post in enumerate(posts, 1):
        ziel = post["ziel"]
        fach = ziel.split("-")[0].capitalize()
        kurs = post.get("kurs") or kurs_of(ziel)
        ids = post["ids"]
        for k in ids:
            if k in used:
                problems.append(f"Index {k} doppelt verwendet")
            used.add(k)
        files = [pathlib.Path(kept[k]["pfad"]) for k in ids if 0 <= k < len(kept)]
        if len(files) != len(ids):
            problems.append(f"Post {i}: ungültige Indizes {ids}")
            continue
        base = f"{slug(fach)}_{kurs}_{slug(post['thema'])}_{slug(post['art'])}"
        # Büro-Datei allein -> Original anhängen (verlustfrei), sonst alles in EINE PDF
        original = len(files) == 1 and files[0].suffix.lower() in ATTACH_EXT
        ext = files[0].suffix.lower() if original else ".pdf"
        dest = SORTIERT / f"{base}{ext}"
        n = 2
        while dest.exists():
            dest = SORTIERT / f"{base}-{n}{ext}"
            n += 1
        if original:
            shutil.copy2(files[0], dest)
            outs = [dest]
        else:
            bundle(files, dest)
            outs = compress(dest)
        print(f"[{i:>2}] {ziel:<14} {dest.name[:58]:<58} {len(files)} Datei(en) "
              f"{dest.stat().st_size/1e6:.1f} MB")
        for pi, fpart in enumerate(outs):
            notiz = post.get("notiz", "")
            if len(outs) > 1:
                notiz = (notiz + f" | Teil {pi + 1}/{len(outs)}").strip(" |")
            rows.append({
                "datei": fpart.name, "fach": fach, "kurs": kurs,
                "thema": post["thema"], "art": post["art"], "titel": post["titel"],
                "ziel_kanal": ziel, "tags": post["art"], "status": "neu", "notiz": notiz,
            })

    missing = [i for i in range(len(kept)) if i not in used]
    print(f"\n{len(rows)} Manifest-Zeilen aus {len(posts)} Posts")
    if missing:
        print(f"\nNICHT ZUGEORDNET ({len(missing)}):")
        for i in missing:
            print(f"   {i:>3} {kept[i]['rel']}")
    if problems:
        print("\nPROBLEME:")
        for p in problems:
            print("  ", p)

    # manifest.csv = aktueller Lauf (was post_neu ohne --manifest nimmt),
    # manifest_<fach>.csv = dauerhafte Ablage je Welle (kein Überschreiben anderer Fächer).
    outs = [PROJECT / "manifest.csv", PROJECT / f"manifest_{args.match}.csv"]
    for out in outs:
        with out.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=COLS, delimiter=";")
            w.writeheader()
            w.writerows(rows)
    # PDFs können komprimiert werden (Ziel SAFE); Original-Anhänge (Office, Medien)
    # nicht — für sie gilt das echte Discord-Limit.
    over = [r for r in rows
            if (SORTIERT / r["datei"]).stat().st_size
            > (LIMIT if pathlib.Path(r["datei"]).suffix.lower() != ".pdf" else SAFE)]
    print(f"\n{len(rows)} Zeilen -> " + ", ".join(o.name for o in outs))
    print(f"Dateien > 10 MB: {len(over)}" + (f" {[r['datei'] for r in over]}" if over else ""))
    return 0 if not missing and not problems and not over else 1


if __name__ == "__main__":
    raise SystemExit(main())
