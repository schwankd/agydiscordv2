"""Korrektur der zwei echten Fehler aus der Sichtprüfung.

Fall 2 (biologie-gk „Nanotechnologie und Kohlenstoff"): Die Quell-PDF enthält auf
Seite 2 ein Foto-Arbeitsblatt „Bau und Funktionen der Zelle" (Zellbiologie). Die
Textprüfung hat es nie gesehen, weil diese Seite ein Foto ohne brauchbaren
Textlayer ist. Korrektur: Nanotechnologie-Seite bleibt eigener Thread, die
Zell-Seite geht als Antwort in den passenden bestehenden Zell-Thread.

Beide Seiten sind vorher pixelgleich gegen das Original geprüft worden, und beide
Threads hatten 0 fremde Nachrichten (Löschen verliert also nichts von anderen).

Server- und Thread-Kennungen stehen NICHT im Repo (siehe README-Skripte.md) —
sie kommen aus der Umgebung:

    GUILD=<server-id> NANO_ALT=<thread-id> BANK_ALT=<thread-id> \
      python3 fehler_korrigieren.py [--nur-pruefen]
"""
import argparse
import csv
import os
import pathlib
import sys

S = pathlib.Path(__file__).resolve().parent
BASE = S.parent
sys.path.insert(0, str(S))
from agy_discord import Client, DiscordError, get_token   # noqa: E402
from post_neu import load_map                             # noqa: E402

NANO_DATEI = "Biologie_GK_Nanotechnologie_kleinste_Teilchen_Sonstiges.pdf"
ZELL_DATEI = "Biologie_GK_Zellaufbau_Bau_und_Funktionen_der_Zelle_Sonstiges.pdf"
NANO_TITEL = "Nanotechnologie – kleinste Teilchen und Kohlenstoff"
ZELL_TITEL = "Zellaufbau – Bau und Funktionen der Zelle"


def _env_id(name: str, zweck: str) -> str:
    """Kennung aus der Umgebung — bewusst keine IDs im Repository."""
    wert = os.environ.get(name, "").strip()
    if not wert:
        raise DiscordError(
            f"{name} fehlt ({zweck}).\n"
            f"  Kennungen stehen NICHT im Repo. Vor dem Aufruf setzen, z. B.:\n"
            f"    GUILD=<server-id> NANO_ALT=<thread-id> BANK_ALT=<thread-id> \\\n"
            f"      python3 {pathlib.Path(__file__).name}"
        )
    return wert


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nur-pruefen", action="store_true")
    ap.add_argument("--banknoten-loeschen", action="store_true",
                    help="Thread mit den Banknoten-Fotos entfernen (nicht Schulinhalt)")
    args = ap.parse_args()

    guild = _env_id("GUILD", "Server „Abendschule Dresden“")
    nano_alt = _env_id("NANO_ALT", "Thread biologie-gk, enthält beide Seiten")
    bank_alt = _env_id("BANK_ALT", "Thread englisch-lk, nur Banknoten-Fotos")

    kanal_map = load_map(BASE / "foren-map.resolved.csv")
    client = Client(get_token("AGY_TOKEN_NEU"))
    bio = kanal_map["biologie-gk"]

    # Ziel-Thread für die Zell-Seite suchen. Wichtig: Discord liefert AKTIVE
    # Threads nur mit Guild-ID (ohne sie sind alle 356 unsichtbar — siehe Skill).
    zell_thread = None
    for t in client.forum_threads(bio["id"], guild):
        if "Cytologie" in t["name"] and "Zellorganellen" in t["name"]:
            zell_thread = t
            break
    print(f"Zell-Thread: {zell_thread['name'] if zell_thread else 'NICHT GEFUNDEN'}"
          f"  ({zell_thread['id'] if zell_thread else '-'})")
    for w in (NANO_DATEI, ZELL_DATEI):
        p = BASE / "sortiert" / w
        print(f"  {w[:60]:<60} {'ok' if p.exists() else 'FEHLT'} "
              f"{p.stat().st_size/1e6:.2f} MB" if p.exists() else f"  {w} FEHLT")
    if args.nur_pruefen:
        return 0

    if not zell_thread:
        print("!! ohne Ziel-Thread keine Korrektur", file=sys.stderr)
        return 2

    tags = dict(bio["tags"])
    applied = [tags[t] for t in ["Sonstiges"] if t in tags]

    # 1) Alten Nanotech-Thread entfernen (0 fremde Nachrichten, Seiten gesichert)
    client.request("DELETE", f"/channels/{nano_alt}")
    print(f"alter Nanotech-Thread {nano_alt} entfernt")

    # 2) Nanotechnologie-Seite als eigener Thread neu anlegen
    content = (f"**{NANO_TITEL}**\nFach: biologie · Kurs: gk · Art: Sonstiges\n"
               f"Originaldatei: `{NANO_DATEI}`\n\n"
               f"_Korrigiert: die Quell-PDF enthielt auf Seite 2 ein Arbeitsblatt "
               f"\u201eBau und Funktionen der Zelle\u201c (anderes Thema). Diese "
               f"Seite steht jetzt im Zell-Thread._")
    neu = client.post_file(f"/channels/{bio['id']}/threads",
                           {"name": NANO_TITEL, "applied_tags": applied,
                            "auto_archive_duration": 10080, "message": {"content": content}},
                           [str(BASE / "sortiert" / NANO_DATEI)])
    print(f"neuer Nanotech-Thread: {neu['id']}")

    # 3) Zell-Seite als Antwort in den bestehenden Zell-Thread
    antwort = (f"**{ZELL_TITEL}**\nFach: biologie · Kurs: gk · Art: Sonstiges\n"
               f"Originaldatei: `{ZELL_DATEI}`\n\n"
               f"_Diese Seite steckte irrtümlich in einem Nanotechnologie-Beitrag "
               f"(Foto, deshalb in der Textprüfung unsichtbar) und gehört inhaltlich hierher._")
    msg = client.post_file(f"/channels/{zell_thread['id']}/messages",
                           {"content": antwort}, [str(BASE / "sortiert" / ZELL_DATEI)])
    print(f"Zell-Seite als Antwort: "
          f"https://discord.com/channels/{zell_thread.get('guild_id','@me')}/"
          f"{zell_thread['id']}/{msg['id']}")

    # 4) Banknoten-Thread nur mit ausdrücklicher Freigabe
    if args.banknoten_loeschen:
        nach = client.get(f"/channels/{bank_alt}/messages?limit=50")
        fremd = [m for m in nach if not m.get("author", {}).get("bot")]
        if fremd:
            print(f"!! {len(fremd)} fremde Nachrichten — NICHT gelöscht", file=sys.stderr)
        else:
            client.request("DELETE", f"/channels/{bank_alt}")
            print(f"Banknoten-Thread {bank_alt} entfernt (Datei bleibt lokal)")
    else:
        print(f"Banknoten-Thread {bank_alt} unberührt (Freigabe fehlt: --banknoten-loeschen)")

    # 5) Kontrolle am Server
    print("\n### Kontrolle")
    for t in client.forum_threads(bio["id"]):
        if NANO_TITEL[:20] in t["name"]:
            m = client.get(f"/channels/{t['id']}/messages?limit=5")
            an = [a["filename"] for x in m for a in x.get("attachments", [])]
            print(f"  Nanotech neu: \"{t['name'][:52]}\" Anhänge={an}")
    m = client.get(f"/channels/{zell_thread['id']}/messages?limit=5")
    an = [a["filename"] for x in m for a in x.get("attachments", [])]
    print(f"  Zell-Thread jetzt {len(m)} Nachrichten, Anhänge={an}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DiscordError as err:
        print(err, file=sys.stderr)
        raise SystemExit(2)
