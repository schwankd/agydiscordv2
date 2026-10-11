#!/usr/bin/env python3
"""Poster (NEUER Server): erstellt Forum-Beiträge aus manifest.csv.

Ablauf pro Zeile:
  1. Ziel-Forum über 'ziel_kanal' in der Map auflösen  -> Kanal-ID
  2. passenden Tag auflösen (Name -> Tag-ID, aus dem Kanal gelesen)
  3. Datei in sortiert/ finden
  4. Dublettencheck: existiert ein Thread mit ähnlichem Titel?
        ja  -> Datei als ANTWORT in bestehenden Thread
        nein-> neuen Forum-Beitrag mit Tags + Datei anlegen

Ergebnis: manifest.result.csv (Aktion, Thread-ID/URL oder Fehler)

Aufruf:
    python3 post_neu.py --dry-run        # offline: nur Plan zeigen
    python3 post_neu.py                  # echt posten
    python3 post_neu.py --no-dedup       # ohne Dublettencheck
"""
from __future__ import annotations

import argparse
import csv
import difflib
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from agy_discord import Client, DiscordError, get_token, norm_title  # noqa: E402

PROJECT = pathlib.Path(__file__).resolve().parent.parent
RESULT_COLS = ["datei", "ziel_kanal", "titel", "tags", "aktion",
               "thread_id", "url", "fehler"]
DEDUP_RATIO = 0.85


def read_csv(path: pathlib.Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        sample = fh.read(4096)
        fh.seek(0)
        delim = ";" if sample.count(";") >= sample.count(",") else ","
        return list(csv.DictReader(fh, delimiter=delim))


def load_map(path: pathlib.Path) -> dict:
    """Forum-Name -> {'id':..., 'tags': {name: id}} (tags ggf. leer)."""
    out: dict[str, dict] = {}
    for row in read_csv(path):
        name = (row.get("Forum_Kanal") or "").strip()
        if not name:
            continue
        tags: dict[str, str] = {}
        names = (row.get("Tag_Names") or row.get("Material_Tags") or "")
        ids = (row.get("Tag_IDs") or "")
        if names and ids:
            for n, i in zip(names.split("|"), ids.split("|")):
                if n.strip() and i.strip():
                    tags[n.strip()] = i.strip()
        out[name] = {"id": (row.get("Kanal_ID") or "").strip(), "tags": tags}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Forum-Beiträge aus manifest.csv posten")
    ap.add_argument("--manifest", default=str(PROJECT / "manifest.csv"))
    ap.add_argument("--map", default=None, help="Standard: foren-map.resolved.csv, sonst foren-map.csv")
    ap.add_argument("--dir", default=str(PROJECT / "sortiert"), help="Ordner mit den Dateien")
    ap.add_argument("--token", default="AGY_TOKEN_NEU")
    ap.add_argument("--dry-run", action="store_true", help="offline: nichts senden")
    ap.add_argument("--no-dedup", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="nur die ersten N Zeilen")
    ap.add_argument("--result", default=str(PROJECT / "manifest.result.csv"),
                    help="Wohin das Ergebnis-CSV geschrieben wird")
    args = ap.parse_args()

    mpath = pathlib.Path(args.manifest)
    if args.map:
        map_path = pathlib.Path(args.map)
    else:
        resolved = PROJECT / "foren-map.resolved.csv"
        map_path = resolved if resolved.exists() else PROJECT / "foren-map.csv"

    if not mpath.exists():
        print(f"manifest nicht gefunden: {mpath}", file=sys.stderr)
        return 2
    if not map_path.exists():
        print(f"Map nicht gefunden: {map_path}", file=sys.stderr)
        return 2

    kanal_map = load_map(map_path)
    rows = [r for r in read_csv(mpath) if (r.get("datei") or "").strip()]
    rows = [r for r in rows if not (r.get("datei") or "").startswith("BEISPIEL_")]
    if args.limit:
        rows = rows[: args.limit]
    print(f"Map: {map_path.name}  |  {len(rows)} Zeilen  "
          + ("[DRY-RUN]" if args.dry_run else "[ECHT]"))

    client = None
    if not args.dry_run:
        try:
            client = Client(get_token(args.token))
        except DiscordError as err:
            print(err, file=sys.stderr)
            return 2

    results: list[dict] = []
    for row in rows:
        datei = row["datei"].strip()
        ziel = (row.get("ziel_kanal") or "").strip()
        titel = (row.get("titel") or "").strip()[:100]
        tag_names = [t.strip() for t in (row.get("tags") or "").split("|") if t.strip()]
        res = {"datei": datei, "ziel_kanal": ziel, "titel": titel,
               "tags": "|".join(tag_names)}

        entry = kanal_map.get(ziel)
        if not entry:
            res["fehler"] = f"Ziel-Forum '{ziel}' nicht in Map"
            results.append(res); continue
        if not entry["id"]:
            res["fehler"] = f"Kanal_ID für '{ziel}' fehlt (discover.py laufen lassen)"
            results.append(res); continue
        fpath = (pathlib.Path(args.dir) / datei)
        if not fpath.exists():
            res["fehler"] = f"Datei fehlt: {fpath}"
            results.append(res); continue
        if not tag_names:
            res["fehler"] = "kein Tag angegeben"
            results.append(res); continue

        if args.dry_run:
            res["aktion"] = "create-thread"
            res["thread_id"] = f"(simuliert) kanal {entry['id']} | tags {tag_names} | {fpath.name}"
            results.append(res); continue

        # Tag-IDs besorgen (aus Map oder live aus dem Kanal)
        tags = dict(entry["tags"])
        if not tags:
            detail = client.get(f"/channels/{entry['id']}")
            tags = {t["name"]: t["id"] for t in detail.get("available_tags", [])}
        applied = [tags[t] for t in tag_names if t in tags]
        if not applied:
            res["fehler"] = f"kein passender Tag (vorhanden: {list(tags)})"
            results.append(res); continue

        content = (f"**{titel}**\n"
                   f"Fach: {row.get('fach','')} · Kurs: {row.get('kurs','')} · "
                   f"Art: {row.get('art','')}\n"
                   f"Originaldatei: `{datei}`")
        if row.get("notiz"):
            content += f"\n\n_{row['notiz']}_"

        try:
            if not args.no_dedup:
                dup = find_duplicate(client, entry["id"], titel)
                if dup:
                    msg = client.post_file(f"/channels/{dup['id']}/messages",
                                           {"content": content}, [str(fpath)])
                    res.update(aktion="reply-existing", thread_id=dup["id"],
                               url=f"https://discord.com/channels/{dup['guild_id']}/{dup['id']}/{msg['id']}")
                    results.append(res); continue
            thread = client.post_file(
                f"/channels/{entry['id']}/threads",
                {"name": titel, "applied_tags": applied,
                 "auto_archive_duration": 10080, "message": {"content": content}},
                [str(fpath)],
            )
            gid = thread.get("guild_id", "@me")
            res.update(aktion="created", thread_id=thread["id"],
                       url=f"https://discord.com/channels/{gid}/{thread['id']}")
        except DiscordError as err:
            res["fehler"] = str(err)
        results.append(res)

    outp = pathlib.Path(args.result)
    with outp.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=RESULT_COLS, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(results)

    ok = sum(1 for r in results if r.get("aktion"))
    bad = sum(1 for r in results if r.get("fehler"))
    print(f"\n{ok} ok, {bad} Fehler -> {outp}")
    for r in results:
        flag = r.get("aktion") or f"FEHLER: {r.get('fehler')}"
        print(f"  {r['datei']:<45} {flag}")
    return 0 if bad == 0 else 1


def find_duplicate(client: Client, channel_id: str, titel: str):
    """Thread mit ähnlichem Titel im Forum finden (oder None).

    Wichtig: aktive Threads liefert Discord nur MIT Guild-ID mit (siehe
    Client.forum_threads). Ohne sie sieht der Check nur archivierte Threads
    und greift bei frisch angelegten Posts nie — Dublettencheck liefe ins Leere.
    """
    target = norm_title(titel)
    guild_id = client.get(f"/channels/{channel_id}").get("guild_id")
    best = None
    best_ratio = 0.0
    for th in client.forum_threads(channel_id, guild_id):
        ratio = difflib.SequenceMatcher(None, target, norm_title(th.get("name", ""))).ratio()
        if ratio > best_ratio:
            best_ratio, best = ratio, th
    if best and best_ratio >= DEDUP_RATIO:
        return best
    return None


if __name__ == "__main__":
    raise SystemExit(main())
