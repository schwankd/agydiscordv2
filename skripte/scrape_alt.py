#!/usr/bin/env python3
"""Archivar (ALT-Server, read-only): lädt alles Material nach eingang/.

Ein Bot, eingeladen in BEIDE Alt-Server. Der Bot liest nur — er schreibt nie.

Gesammelt werden:
  - Anhänge (PDFs, Bilder, ...) aus Text- und Forum-Kanälen (inkl. Threads)
  - Nachrichtentext + Autor + Zeitstempel + Embed-URLs (als Index)

Ablage:  eingang/alt-<server>/<kanal>/[<thread>/]<datei>
Index:   eingang/_index_alt.csv

Aufruf:
    python3 scrape_alt.py --dry-run      # nur zählen, nichts laden
    python3 scrape_alt.py                # alles laden
    python3 scrape_alt.py --guilds 111,222
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from agy_discord import (Client, DiscordError, FORUM_TYPES, TEXT_TYPES,  # noqa: E402
                         download_attachment, get_token, safe)

PROJECT = pathlib.Path(__file__).resolve().parent.parent
INDEX_COLS = ["server", "kanal", "thread", "nachricht_id", "zeit", "autor",
              "dateiname", "bytes", "gespeichert", "text", "embed_urls", "fehler"]


def collect_group(client: Client, channel_id: str, pause: float):
    """Alle Nachrichten eines Kanals/Threads."""
    return client.all_messages(channel_id, pause=pause)


def main() -> int:
    ap = argparse.ArgumentParser(description="Alt-Server-Material archivieren")
    ap.add_argument("--token", default="AGY_TOKEN_ALT")
    ap.add_argument("--out", default=str(PROJECT / "eingang"))
    ap.add_argument("--guilds", help="Komma-Liste Guild-IDs; ohne: alle")
    ap.add_argument("--dry-run", action="store_true", help="nur zählen")
    ap.add_argument("--pause", type=float, default=0.3, help="Sekunden zwischen Seiten")
    args = ap.parse_args()

    try:
        client = Client(get_token(args.token))
    except DiscordError as err:
        print(err, file=sys.stderr)
        return 2

    me = client.get("/users/@me")
    guilds = client.get("/users/@me/guilds")
    if args.guilds:
        wanted = {g.strip() for g in args.guilds.split(",")}
        guilds = [g for g in guilds if g["id"] in wanted]

    if not guilds:
        print("Der Bot ist in KEINEM Server. Erst einladen (Rechte: Manage Server):\n"
              "  https://discord.com/oauth2/authorize"
              f"?client_id={me['id']}&scope=bot&permissions=66560",
              file=sys.stderr)
        return 3

    print(f"Bot: {me['username']}  |  Server: {[g['name'] for g in guilds]}"
          + ("  [DRY-RUN]" if args.dry_run else ""))

    out_root = pathlib.Path(args.out)
    index_rows: list[dict] = []
    n_files = n_bytes = 0

    for guild in guilds:
        gid, gname = guild["id"], guild["name"]
        channels = client.get(f"/guilds/{gid}/channels")

        # Arbeitsliste: (kanalname, threadname, container_id)
        jobs: list[tuple[str, str, str]] = []
        for ch in channels:
            cname, cid, ctype = ch["name"], ch["id"], ch.get("type")
            if ctype in TEXT_TYPES:
                jobs.append((cname, "", cid))
            elif ctype in FORUM_TYPES:
                threads = client.forum_threads(cid, gid)
                for th in threads:
                    jobs.append((cname, th.get("name", th["id"]), th["id"]))
                if not threads:
                    jobs.append((cname, "", cid))  # leeres Forum, evtl. Thread-Startposts

        # Zusätzlich aktive Threads an Textkanälen
        try:
            active = client.get(f"/guilds/{gid}/threads/active").get("threads", [])
        except DiscordError:
            active = []
        by_id = {c["id"]: c for c in channels}
        for th in active:
            parent = by_id.get(th.get("parent_id"))
            if parent and parent.get("type") in TEXT_TYPES:
                jobs.append((parent["name"], th.get("name", th["id"]), th["id"]))

        for cname, tname, container in jobs:
            try:
                messages = collect_group(client, container, args.pause)
            except DiscordError as err:
                index_rows.append({"server": gname, "kanal": cname, "thread": tname,
                                   "fehler": str(err)})
                continue

            for msg in messages:
                embeds = [e.get("image", {}).get("url") or e.get("thumbnail", {}).get("url")
                          for e in msg.get("embeds", [])]
                embed_urls = [u for u in embeds if u]
                author = msg.get("author", {}).get("username", "?")
                ts = msg.get("timestamp", "")
                text = (msg.get("content", "") or "")[:500]
                for att in msg.get("attachments", []):
                    fname = safe(att.get("filename", att["id"]))
                    sub = out_root / f"alt-{safe(gname)}" / safe(cname)
                    if tname:
                        sub = sub / safe(tname)
                    dest = sub / fname
                    if dest.exists() and dest.stat().st_size != att.get("size", -1):
                        dest = sub / f"{msg['id']}_{fname}"
                    row = {"server": gname, "kanal": cname, "thread": tname,
                           "nachricht_id": msg["id"], "zeit": ts, "autor": author,
                           "dateiname": fname, "text": text,
                           "embed_urls": " ".join(embed_urls)}
                    if args.dry_run:
                        n_files += 1
                    else:
                        try:
                            n = download_attachment(att["url"], dest)
                            n_files += 1
                            n_bytes += n
                            row["bytes"] = n
                            row["gespeichert"] = str(dest)
                        except Exception as err:  # noqa: BLE001
                            row["fehler"] = f"download: {err}"
                    index_rows.append(row)
            if messages:
                print(f"  {gname} / {cname}{'/' + tname if tname else ''}: "
                      f"{len(messages)} Nachrichten")

    if not args.dry_run and index_rows:
        out_root.mkdir(parents=True, exist_ok=True)
        idx = out_root / "_index_alt.csv"
        with idx.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=INDEX_COLS, delimiter=";", extrasaction="ignore")
            w.writeheader()
            for r in index_rows:
                w.writerow(r)
        print(f"\nIndex: {idx}")

    print(f"\nFertig: {n_files} Dateien"
          + ("" if args.dry_run else f", {n_bytes / 1e6:.1f} MB")
          + f"  ({dt.datetime.now():%H:%M:%S})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
