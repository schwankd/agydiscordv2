#!/usr/bin/env python3
"""Selbsttest (NEUER Server): einen Forum-Beitrag MIT Tag + Datei anlegen,
verifizieren und sofort wieder löschen.

Verifiziert den letzten offenen Integrationspunkt: akzeptiert Discord
Forum-Thread-Erstellung mit `applied_tags` UND Datei in einem Multipart-Request?

Aufruf:
    python3 selftest.py --forum mathematik-gk
    python3 selftest.py --forum mathematik-gk --keep   # nicht löschen
"""
from __future__ import annotations

import argparse
import csv
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from agy_discord import Client, DiscordError, get_token  # noqa: E402

PROJECT = pathlib.Path(__file__).resolve().parent.parent
TITLE = "ZZZ Selftest – bitte ignorieren (wird sofort gelöscht)"


def make_pdf(text: str = "AGY Selftest OK") -> bytes:
    stream = f"BT /F1 18 Tf 72 760 Td ({text}) Tj ET".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode() + b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def forum_id(name: str) -> str:
    with (PROJECT / "foren-map.resolved.csv").open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            if row["Forum_Kanal"] == name:
                return row["Kanal_ID"]
    raise SystemExit(f"Forum '{name}' nicht in foren-map.resolved.csv")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--forum", default="mathematik-gk")
    ap.add_argument("--token", default="AGY_TOKEN_NEU")
    ap.add_argument("--keep", action="store_true", help="Beitrag nicht löschen")
    args = ap.parse_args()

    client = Client(get_token(args.token))
    cid = forum_id(args.forum)
    detail = client.get(f"/channels/{cid}")
    tags = {t["name"]: t["id"] for t in detail.get("available_tags", [])}
    print(f"Forum: {args.forum} ({cid})  Tags: {list(tags)}")
    tag_name = "Sonstiges" if "Sonstiges" in tags else next(iter(tags))
    tag_id = tags[tag_name]

    pdf = pathlib.Path("/tmp/agy_selftest.pdf")
    pdf.write_bytes(make_pdf())
    print(f"Testdatei: {pdf} ({pdf.stat().st_size} B)")

    print("\n-> POST /channels/<forum>/threads (multipart: payload_json + files[0])")
    thread = client.post_file(
        f"/channels/{cid}/threads",
        {"name": TITLE, "applied_tags": [tag_id],
         "auto_archive_duration": 60, "message": {"content": "Selbsttest – automatisch gelöscht."}},
        [str(pdf)],
    )
    tid = thread["id"]
    print(f"   Thread angelegt: {tid}  name={thread.get('name')!r}")

    got = client.get(f"/channels/{tid}")
    got_tags = got.get("applied_tags", [])
    msgs = client.get(f"/channels/{tid}/messages?limit=5")
    atts = [a for m in msgs for a in m.get("attachments", [])]

    ok_tag = tag_id in got_tags
    ok_file = len(atts) == 1
    print(f"\nVERIFIKATION")
    print(f"  Tag gesetzt   : {'JA ' if ok_tag else 'NEIN'} ({got_tags} == [{tag_id}])")
    print(f"  Datei hängt   : {'JA ' if ok_file else 'NEIN'} "
          f"({[ (a['filename'], a['size']) for a in atts ]})")

    if args.keep:
        print(f"\nBehalten: https://discord.com/channels/{got.get('guild_id','@me')}/{tid}")
    else:
        client.request("DELETE", f"/channels/{tid}")
        try:
            client.get(f"/channels/{tid}")
            print("\nLöschen: NOCH DA (unerwartet)")
        except DiscordError:
            print("\nLöschen: OK (Thread weg)")
    pdf.unlink(missing_ok=True)
    return 0 if (ok_tag and ok_file) else 1


if __name__ == "__main__":
    raise SystemExit(main())
