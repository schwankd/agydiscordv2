#!/usr/bin/env python3
"""Text-Extraktion (Alt-Material): PDF-Textlayer oder Apple-Vision-OCR.

Für jedes Material an einem Kanal, der auf das Suchwort passt:
  - PDF mit Textlayer  -> Text direkt (pymupdf), sonst Seiten rastern + OCR
  - Bild               -> OCR (Apple Vision, de-DE), vorher auf max. 2400 px verkleinern
Ergebnis: JSON-Cache mit Text + Metadaten pro Datei (Basis für die Klassifikation).

Aufruf:
    python3 extract_text.py --match geschichte --out _text_geschichte.json
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import subprocess
import sys
import tempfile
import time

import fitz  # pymupdf
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from agy_discord import CONTAINER_EXT, IMG_EXT, XML_TEXT_EXT, office_text  # noqa: E402

PROJECT = pathlib.Path(__file__).resolve().parent.parent
EINGANG = PROJECT / "eingang"
CACHE = pathlib.Path(__file__).resolve().parent / ".cache"
SKILL_OCR = pathlib.Path.home() / ".hermes/skills/note-taking/schul-archiv-ocr-pdf/scripts/ocr-vision-swift.swift"
MAXDIM = 2400
MAXCHARS = 4000


def ocr_binary() -> pathlib.Path:
    """Swift-OCR einmal kompilieren, dann Binary wiederverwenden."""
    CACHE.mkdir(parents=True, exist_ok=True)
    binary = CACHE / "ocrvision"
    if not binary.exists() or binary.stat().st_mtime < SKILL_OCR.stat().st_mtime:
        print("  kompiliere OCR-Binary (einmalig) ...", file=sys.stderr)
        subprocess.run(["swiftc", "-O", str(SKILL_OCR), "-o", str(binary)], check=True)
    return binary


def ocr(binary: pathlib.Path, path: pathlib.Path) -> str:
    tmp = None
    try:
        img = Image.open(path)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        if max(img.size) > MAXDIM:
            img.thumbnail((MAXDIM, MAXDIM), Image.LANCZOS)
        fd, name = tempfile.mkstemp(suffix=".png", dir=CACHE)
        tmp = pathlib.Path(name)
        img.save(tmp, "PNG")
        res = subprocess.run([str(binary), str(tmp)], capture_output=True, text=True, timeout=180)
        lines = [l for l in res.stdout.splitlines()
                 if not l.strip().startswith(".hermes/") and "warning:" not in l.lower()]
        return "\n".join(lines).strip()
    except Exception as err:  # noqa: BLE001
        return f"[OCR-Fehler: {err}]"
    finally:
        if tmp and tmp.exists():
            tmp.unlink()


def pdf_text(path: pathlib.Path, binary: pathlib.Path) -> tuple[str, int, int]:
    """(Text, Seitenzahl, Seiten-mit-Text). Ohne Textlayer -> erste Seiten rastern + OCR."""
    doc = fitz.open(path)
    pages = doc.page_count
    parts, with_text = [], 0
    for i, page in enumerate(doc):
        t = (page.get_text() or "").strip()
        if t:
            with_text += 1
            parts.append(t)
    if with_text >= max(1, pages // 3):
        doc.close()
        return "\n".join(parts), pages, with_text
    # Kein/kaum Textlayer: bis zu 6 Seiten rastern + OCR
    out = []
    for i, page in enumerate(doc):
        if i >= 6:
            break
        pix = page.get_pixmap(dpi=200)
        tmp = CACHE / f"_p{i}.png"
        CACHE.mkdir(parents=True, exist_ok=True)
        pix.save(tmp)
        out.append(ocr(binary, tmp))
        tmp.unlink(missing_ok=True)
    doc.close()
    return "\n".join(out), pages, with_text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--match", required=True, help="Suchwort im Kanalnamen (z.B. geschichte)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    rows = [r for r in csv.DictReader((EINGANG / "_index_alt.csv").open(newline="", encoding="utf-8"),
                                     delimiter=";")
            if (r.get("dateiname") or "").strip()
            and args.match.lower() in r["kanal"].lower()
            and not r.get("fehler")
            and pathlib.Path(r["dateiname"] or "").suffix.lower() not in CONTAINER_EXT
            and r.get("gespeichert")]
    print(f"{len(rows)} Dateien im Kanal-Match '{args.match}'")

    binary = ocr_binary()
    result = []
    t0 = time.time()
    for i, r in enumerate(rows, 1):
        p = pathlib.Path(r["gespeichert"])
        if not p.exists():
            print(f"  [{i}] FEHLT {p}")
            continue
        ext = p.suffix.lower()
        if ext == ".pdf":
            text, pages, wt = pdf_text(p, binary)
        elif ext in IMG_EXT:
            text, pages, wt = ocr(binary, p), 1, 0
        elif ext in XML_TEXT_EXT:
            text, pages, wt = office_text(p), 1, 0
        else:
            text, pages, wt = f"[{ext} – nicht extrahierbar]", 1, 0
        result.append({
            "datei": r["dateiname"], "pfad": r["gespeichert"], "server": r["server"],
            "kanal": r["kanal"], "thread": r["thread"], "msg_id": r["nachricht_id"],
            "zeit": r["zeit"], "autor": r["autor"], "msg_text": r["text"],
            "bytes": int(r["bytes"] or 0), "typ": ext, "seiten": pages,
            "seiten_mit_text": wt, "text": text[:MAXCHARS],
        })
        mark = "PDF" if ext == ".pdf" else ("IMG" if ext in IMG_EXT else "???")
        print(f"  [{i}/{len(rows)}] {mark} {r['dateiname'][:44]:<44} "
              f"{len(text):>5} Zeichen  ({time.time()-t0:.0f}s)")

    outp = pathlib.Path(args.out) if args.out else (PROJECT / f"_text_{args.match}.json")
    outp.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    empty = sum(1 for r in result if len(r["text"]) < 20)
    print(f"\n{len(result)} Dateien -> {outp}")
    print(f"Ohne verwertbaren Text: {empty}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
