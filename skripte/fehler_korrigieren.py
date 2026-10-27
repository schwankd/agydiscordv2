"""Korrektur der zwei echten Fehler aus der Sichtprüfung.

Fall 2 (biologie-gk „Nanotechnologie und Kohlenstoff"): Die Quell-PDF enthält auf
Seite 2 ein Foto-Arbeitsblatt „Bau und Funktionen der Zelle" (Zellbiologie). Die
Textprüfung hat es nie gesehen, weil diese Seite ein Foto ohne brauchbaren
Textlayer ist. Korrektur: Nanotechnologie-Seite bleibt eigener Thread, die
Zell-Seite geht als Antwort in den passenden bestehenden Zell-Thread.

Beide Seiten sind vorher pixelgleich gegen das Original geprüft worden, und beide
Threads hatten 0 fremde Nachrichten (Löschen verliert also nichts von anderen).

Aufruf:  python3 fehler_korrigieren.py [--nur-pruefen]
"""
import argparse
import csv
import pathlib
import sys

S = pathlib.Path(__file__).resolve().parent
BASE = S.parent
sys.path.insert(0, str(S))
from agy_discord import Client, DiscordError, get_token   # noqa: E402
from post_neu import load_map                             # noqa: E402

GUILD = "1539350758481469500"             # neuer Server „Abendschule Dresden"
NANO_ALT = "1558820521410428980"          # Thread biologie-gk, enthält beide Seiten
BANK_ALT = "1558812863009783809"          # Thread englisch-lk, nur Banknoten-Fotos
NANO_DATEI = "Biologie_GK_Nanotechnologie_kleinste_Teilchen_Sonstiges.pdf"
ZELL_DATEI = "Biologie_GK_Zellaufbau_Bau_und_Funktionen_der_Zelle_Sonstiges.pdf"
NANO_TITEL = "Nanotechnologie – kleinste Teilchen und Kohlenstoff"
ZELL_TITEL = "Zellaufbau – Bau und Funktionen der Zelle"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nur-pruefen", action="store_true")
    ap.add_argument("--banknoten-loeschen", action="store_true",
                    help="Thread mit den Banknoten-Fotos entfernen (nicht Schulinhalt)")
    args = ap.parse_args()

    kanal_map = load_map(BASE / "foren-map.resolved.csv")
    client = Client(get_token("AGY_TOKEN_NEU"))
    bio = kanal_map["biologie-gk"]

    # Ziel-Thread für die Zell-Seite suchen. Wichtig: Discord liefert AKTIVE
    # Threads nur mit Guild-ID (ohne sie sind alle 356 unsichtbar — siehe Skill).
    zell_thread = None
    for t in client.forum_threads(bio["id"], GUILD):
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
    client.request("DELETE", f"/channels/{NANO_ALT}")
    print(f"alter Nanotech-Thread {NANO_ALT} entfernt")

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
        nach = client.get(f"/channels/{BANK_ALT}/messages?limit=50")
        fremd = [m for m in nach if not m.get("author", {}).get("bot")]
        if fremd:
            print(f"!! {len(fremd)} fremde Nachrichten — NICHT gelöscht", file=sys.stderr)
        else:
            client.request("DELETE", f"/channels/{BANK_ALT}")
            print(f"Banknoten-Thread {BANK_ALT} entfernt (Datei bleibt lokal)")
    else:
        print(f"Banknoten-Thread {BANK_ALT} unberührt (Freigabe fehlt: --banknoten-loeschen)")

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
    raise SystemExit(main())
