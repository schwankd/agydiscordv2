#!/usr/bin/env python3
"""Discovery (NEUER Server): listet Guilds, Foren-Kanäle und deren Tags.

Ergebnis: foren-map.resolved.csv  (Fach/Kurs-Kanal -> Kanal-ID + Tag-IDs),
damit du Kanal_ID + Tags in foren-map.csv eintragen (oder sie ersetzen) kannst.

Aufruf:
    python3 discover.py                 # nutzt AGY_TOKEN_NEU
    python3 discover.py --guild 123...  # Guild direkt angeben
"""
from __future__ import annotations

import argparse
import csv
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from agy_discord import Client, DiscordError, FORUM_TYPES, get_token  # noqa: E402

PROJECT = pathlib.Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser(description="Discord-Foren + Tags auflisten")
    ap.add_argument("--token", default="AGY_TOKEN_NEU", help="Token-Schlüssel (Default AGY_TOKEN_NEU)")
    ap.add_argument("--guild", help="Guild-ID; ohne: Auswahl/Auto")
    ap.add_argument("--out", default=str(PROJECT / "foren-map.resolved.csv"))
    args = ap.parse_args()

    try:
        client = Client(get_token(args.token))
    except DiscordError as err:
        print(err, file=sys.stderr)
        return 2

    me = client.get("/users/@me")
    guilds = client.get("/users/@me/guilds")
    print(f"Bot: {me['username']} (id {me['id']})")
    print(f"In {len(guilds)} Server(n):")
    for g in guilds:
        print(f"  {g['id']}  {g['name']}")

    gid = args.guild
    if not gid:
        if len(guilds) == 1:
            gid = guilds[0]["id"]
        elif not guilds:
            print("\nDer Bot ist in KEINEM Server. Erst einladen (Rechte: Manage Server):\n"
                  "  https://discord.com/oauth2/authorize"
                  f"?client_id={me['id']}&scope=bot&permissions=51539725312",
                  file=sys.stderr)
            return 3
        else:
            gid = input("Guild-ID des NEUEN Servers: ").strip()
    gname = next((g["name"] for g in guilds if g["id"] == gid), gid)

    channels = client.get(f"/guilds/{gid}/channels")
    by_id = {c["id"]: c for c in channels}
    rows = []
    print(f"\nForen auf '{gname}':")
    for ch in channels:
        if ch.get("type") not in FORUM_TYPES:
            continue
        detail = client.get(f"/channels/{ch['id']}")
        tags = detail.get("available_tags", []) or []
        cat = by_id.get(ch.get("parent_id"), {}).get("name", "")
        rows.append({
            "Kategorie": cat,
            "Forum_Kanal": ch["name"],
            "Kanal_ID": ch["id"],
            "Tag_Names": "|".join(t["name"] for t in tags),
            "Tag_IDs": "|".join(t["id"] for t in tags),
        })
        print(f"  {ch['name']:<24} id={ch['id']}  tags={[t['name'] for t in tags]}")

    out = pathlib.Path(args.out)
    if rows:
        with out.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), delimiter=";")
            w.writeheader()
            w.writerows(rows)
        print(f"\n{len(rows)} Foren -> {out}")
    else:
        print("\nKeine Foren gefunden (Bot eingeladen? Rechte 'Kanäle ansehen'?).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
