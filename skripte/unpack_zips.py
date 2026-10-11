#!/usr/bin/env python3
"""ZIP-Container aus dem Archiv aufpacken und als Index-Zeilen nachtragen.

Die Alt-Server enthalten ZIPs mit fertigen Materialsammlungen. Ein ZIP lässt sich
nicht in eine PDF wandeln — es ist ein Container. Also: entpacken, jede innere
Datei als eigene Index-Zeile eintragen (Metadaten vom ZIP geerbt). Danach sind
extract_text.py / classify.py unverändert anwendbar.

Eigenheit: ZIP-Eintragsnamen sind oft CP437-kodiert (Umlaute kaputt, z. B.
"▄bungsaufgaben"). Wird erkannt und korrigiert.

Aufruf:
    python3 unpack_zips.py --match mathe        # nur ZIPs, deren Kanal passt
    python3 unpack_zips.py --match mathe --dry-run
"""
from __future__ import annotations

import argparse
import csv
import pathlib
import shutil
import zipfile

PROJECT = pathlib.Path(__file__).resolve().parent.parent
INDEX = PROJECT / "eingang" / "_index_alt.csv"
COLS = ["server", "kanal", "thread", "nachricht_id", "zeit", "autor",
        "dateiname", "bytes", "gespeichert", "text", "embed_urls", "fehler"]


_MOJIBAKE = set("▄ⁿΣ÷─╓▀Θ")   # CP437-Grafikzeichen, die aus CP1252-Umlauten entstehen


def decode_name(raw: str) -> str:
    """Umlaut-Mojibake aus ZIP-Einträgen zurückkorrigieren.

    Ü=0xDC→'▄', ü=0xFC→'ⁿ', ä=0xE4→'Σ', ö=0xF6→'÷'.
    Wichtig: Archive mischen Encodings — manche Einträge sind schon korrekt (CP437
    geschrieben, z. B. 'ä'=0x84). Deshalb NUR umkodieren, wenn echte Mojibake-Zeichen
    vorkommen; sonst bliebe ein korrektes 'ä' als '„' zerstört.
    """
    if not any(c in _MOJIBAKE for c in raw):
        return raw
    try:
        return raw.encode("cp437").decode("cp1252")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return raw


def safe(name: str) -> str:
    import re
    name = re.sub(r"[\x00-\x1f/\\:]", "_", name)
    return re.sub(r"\s+", " ", name).strip().strip(".") or "unbenannt"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--match", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows = list(csv.DictReader(INDEX.open(newline="", encoding="utf-8"), delimiter=";"))
    known = {r["gespeichert"] for r in rows}
    zips = [r for r in rows
            if r["dateiname"].lower().endswith(".zip")
            and args.match.lower() in r["kanal"].lower()]

    new_rows, n_files = [], 0
    for z in zips:
        src = pathlib.Path(z["gespeichert"])
        dest_dir = src.parent / safe(src.stem)
        if not src.exists():
            print(f"  FEHLT {src}")
            continue
        print(f"\n=== {z['kanal']} / {z['dateiname']} -> {dest_dir.relative_to(PROJECT)}")
        if not args.dry_run:
            dest_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(src) as zf:
            for info in zf.infolist():
                if info.is_dir() or "__MACOSX" in info.filename:
                    continue
                name = safe(decode_name(pathlib.Path(info.filename).name))
                target = dest_dir / name
                if not args.dry_run:
                    with zf.open(info) as fh, target.open("wb") as out:
                        shutil.copyfileobj(fh, out)
                    if target.stat().st_size != info.file_size:
                        print(f"    WARNUNG Größe weicht ab: {name}")
                rel = str(target)
                if rel in known:
                    print(f"    (schon im Index) {name}")
                    continue
                new_rows.append({
                    "server": z["server"], "kanal": z["kanal"], "thread": z["thread"],
                    "nachricht_id": z["nachricht_id"], "zeit": z["zeit"], "autor": z["autor"],
                    "dateiname": name, "bytes": info.file_size, "gespeichert": rel,
                    "text": "", "embed_urls": z.get("embed_urls", ""), "fehler": "",
                })
                n_files += 1
                print(f"    + {name}  ({info.file_size/1e6:.2f} MB)")

    if not args.dry_run and new_rows:
        with INDEX.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=COLS, delimiter=";", extrasaction="ignore")
            w.writeheader()
            w.writerows(rows + new_rows)
    print(f"\n{len(zips)} ZIPs, {n_files} neue Index-Zeilen"
          + ("  [DRY-RUN]" if args.dry_run else f"  -> {INDEX.name}"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
