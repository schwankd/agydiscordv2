#!/usr/bin/env python3
"""Tests/Arbeiten/Klausuren vom Discord-Server nehmen.

Die Menge wird NICHT nach Gefühl bestimmt, sondern über den Server-Tag
`Klausur/Test`: jedes Forum hat diesen Tag, jeder Test-, Arbeits- und
Klausurbeitrag trägt ihn. Damit ist die Liste nachprüfbar und deckt sich mit
dem, was im Server wirklich steht — auch mit Dateien, die nur noch dort liegen.

Drei Stufen, jede einzeln aufrufbar:

    python3 klausur_runter.py --pruefen                   # read-only: Liste + CSV
    python3 klausur_runter.py --holen                     # Dateien in den Desktop-Ordner
    python3 klausur_runter.py --loeschen --bestaetigen    # Threads entfernen

Zielordner ist die bestehende Mappe fürs Hand-Schwärzen
(`~/Desktop/AGY-manuell-schwaerzen`, siehe manuell_ordner.py) — dieselbe Mappe,
jetzt vollständig aus dem Server statt aus den Manifesten. `--holen` baut
`01_schwaerzen/` neu auf.

`--loeschen` prüft vor jedem Thread, ob fremde (nicht-Bot-)Nachrichten daran
hängen — dann wird NICHT gelöscht — und schreibt vorher ein Rollback-Manifest
(`_pruefen/klausur_wiederpost.csv`), mit dem alles erneut gepostet werden kann.
"""
from __future__ import annotations

import argparse
import csv
import pathlib
import shutil
import sys

S = pathlib.Path(__file__).resolve().parent
BASE = S.parent
sys.path.insert(0, str(S))
from agy_discord import Client, DiscordError, download_attachment, get_token, safe  # noqa: E402
from post_neu import load_map                                                      # noqa: E402

PRUEF = BASE / "_pruefen"
ZIEL = pathlib.Path.home() / "Desktop" / "AGY-manuell-schwaerzen"
ORDNER = ZIEL / "01_schwaerzen"
TAG = "Klausur/Test"
LISTE = PRUEF / "klausur_posts.csv"
COLS = ["forum", "titel", "art", "thread_id", "erstellt", "nachrichten", "fremde",
        "originaldatei", "dateiname_zum_schwaerzen", "bytes", "lokal", "url"]


def guild_of(client: Client, channel_id: str) -> str:
    """Server-Kennung aus dem Kanal holen — Kennungen stehen nicht im Repo."""
    return client.get(f"/channels/{channel_id}").get("guild_id", "")


def finde_threads(client: Client) -> list[dict]:
    """Alle Forum-Beiträge mit dem Tag `Klausur/Test` — über alle Foren."""
    kanal_map = load_map(BASE / "foren-map.resolved.csv")
    treffer: list[dict] = []
    for forum, info in sorted(kanal_map.items()):
        tag_id = info["tags"].get(TAG)
        if not tag_id:
            print(f"  !! {forum}: kein Tag '{TAG}' in der Map — übersprungen",
                  file=sys.stderr)
            continue
        guild = guild_of(client, info["id"])
        for t in client.forum_threads(info["id"], guild):
            if tag_id in (t.get("applied_tags") or []):
                t["_forum"] = forum
                treffer.append(t)
    return treffer


def sammle(client: Client, threads: list[dict]) -> list[dict]:
    """Je Anhang eine Zeile: Forum, Titel, Thread, Datei, Größe, lokaler Fund."""
    zeilen: list[dict] = []
    for t in threads:
        nachrichten = client.all_messages(t["id"], pause=0.15)
        fremde = [m for m in nachrichten if not m.get("author", {}).get("bot")]
        anhaenge = [a for m in nachrichten for a in m.get("attachments", [])]
        basis = {
            "forum": t["_forum"], "titel": t["name"], "art": TAG, "thread_id": t["id"],
            "erstellt": (t.get("thread_metadata") or {}).get("create_timestamp", ""),
            "nachrichten": len(nachrichten), "fremde": len(fremde),
        }
        if not anhaenge:
            zeilen.append({**basis, "originaldatei": "(kein Anhang)", "bytes": 0,
                           "lokal": "-", "url": "", "dateiname_zum_schwaerzen": ""})
            continue
        for a in anhaenge:
            lokal = BASE / "sortiert" / a["filename"]
            stamm = pathlib.Path(a["filename"]).stem
            endung = pathlib.Path(a["filename"]).suffix
            zeilen.append({
                **basis, "originaldatei": a["filename"],
                "dateiname_zum_schwaerzen": f"{t['_forum']}__{safe(stamm, 88)}{endung}",
                "bytes": a.get("size", 0),
                "lokal": "ja" if lokal.exists() else "nein",
                "url": a.get("url", ""),
            })
    return zeilen


def schreibe_csv(zeilen: list[dict], pfad: pathlib.Path) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    with pfad.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, delimiter=";", extrasaction="ignore")
        w.writeheader()
        for z in zeilen:
            w.writerow({k: z.get(k, "") for k in COLS})


def bericht(zeilen: list[dict]) -> None:
    threads = {z["thread_id"] for z in zeilen}
    foren: dict[str, int] = {}
    for z in zeilen:
        foren[z["forum"]] = foren.get(z["forum"], 0) + 1
    mb = sum(int(z["bytes"] or 0) for z in zeilen) / 1e6
    fremd = sum(1 for z in zeilen if int(z["fremde"] or 0))
    print(f"\n  {len(threads)} Beiträge mit Tag '{TAG}', {len(zeilen)} Dateien, "
          f"{mb:.1f} MB")
    print(f"  Beiträge mit fremden Nachrichten: {fremd} (dort wird nie gelöscht)")
    print(f"  in sortiert/ vorhanden: "
          f"{sum(1 for z in zeilen if z['lokal'] == 'ja')}/{len(zeilen)}"
          f" — der Rest liegt nur im Server")
    for f, n in sorted(foren.items()):
        print(f"    {f:<22} {n:>3}")
    print(f"\n  Liste: {LISTE}")


def schreibe_liesmich(zeilen: list[dict]) -> None:
    threads = {z["thread_id"] for z in zeilen}
    nach_forum: dict[str, list[dict]] = {}
    for z in zeilen:
        nach_forum.setdefault(z["forum"], []).append(z)
    gruppen = []
    for forum, zs in sorted(nach_forum.items()):
        gruppen.append(f"\n{forum}  ({len(zs)} Datei(en))")
        for z in zs:
            gruppen.append(f"   - {z.get('dateiname_zum_schwaerzen') or '(kein Anhang)'}")
    nur_server = sum(1 for z in zeilen if z["lokal"] == "nein")
    txt = f"""DATEIEN ZUM MANUELLEN SCHWÄRZEN — aus dem Server geholt
=======================================================

01_schwaerzen/   {len(zeilen)} PDFs: ALLE Beiträge, die im Discord den Tag
                 "Klausur/Test" tragen ({len(threads)} Beiträge in {len(nach_forum)} Foren) —
                 also Tests, Arbeiten und Klausuren. Im Namen steht vorn das
                 Ziel-Forum, damit beim Posten klar ist, wohin jede Datei gehört:
                       <forum>__<dateiname>.pdf
                 Beispiel: mathematik-gk__Mathematik_GK_Mathe_Test_3_..._Klausur_Test.pdf

03_Liste.csv     Zuordnung als Tabelle: forum · titel · art · thread_id · erstellt ·
                 nachrichten · fremde · originaldatei · dateiname_zum_schwaerzen ·
                 bytes · lokal · url
                 `fremde` = Nachrichten anderer Leute im Beitrag. Steht dort > 0,
                 wird dieser Beitrag beim Aufräumen NICHT gelöscht.
                 Bei {nur_server} Dateien steht `lokal = nein`: die liegen nur noch im
                 Server, nicht mehr in sortiert/ — sie wurden hier mitgeladen.

WIE SCHWÄRZEN
-------------
Egal womit — die Stellen müssen nur SICHTBAR markiert sein (schwarzer Balken,
Kasten, Übermalen). Vorschlag für macOS-Vorschau: Werkzeuge > Anmerkungen >
Rechteck, Füllfarbe schwarz, dann über das Namensfeld ziehen.

Wichtig: Du musst nicht auf den Textlayer achten und nichts exportieren.
Ich brenne deine Markierungen anschließend ein:
      schwaerzen.py --datei <datei> --nur-rastern
Dabei wird jede Seite als Bild neu aufgebaut. Erst danach ist die Schwärzung
echt — ein schwarzes Rechteck über einem Textlayer lässt den Namen weiter
herausziehen, und eine Anmerkung im PDF kann jeder wieder wegklicken.

DIES IST EINE KOPIE. Originale bleiben:
{BASE}
{' '.join(gruppen)}
"""
    (ZIEL / "LIESMICH.txt").write_text(txt, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Tests/Klausuren vom Server nehmen")
    ap.add_argument("--pruefen", action="store_true", help="read-only: nur Liste")
    ap.add_argument("--holen", action="store_true", help="Dateien in den Desktop-Ordner")
    ap.add_argument("--loeschen", action="store_true", help="Threads entfernen")
    ap.add_argument("--bestaetigen", action="store_true", help="Freigabe für --loeschen")
    ap.add_argument("--liste", default=None, help="statt Server zu fragen: vorhandene CSV")
    args = ap.parse_args()
    if not (args.pruefen or args.holen or args.loeschen):
        ap.print_help()
        return 1

    client = Client(get_token("AGY_TOKEN_NEU"))

    if args.liste and pathlib.Path(args.liste).exists():
        with open(args.liste, newline="", encoding="utf-8") as fh:
            zeilen = list(csv.DictReader(fh, delimiter=";"))
    else:
        threads = finde_threads(client)
        print(f"  {len(threads)} Beiträge gefunden — Nachrichten werden gelesen …")
        zeilen = sammle(client, threads)

    if args.pruefen:
        schreibe_csv(zeilen, LISTE)
        bericht(zeilen)
        return 0

    if args.holen:
        if ORDNER.exists():
            shutil.rmtree(ORDNER)
        ORDNER.mkdir(parents=True)
        gesehen: dict[str, int] = {}
        for z in zeilen:
            if not z.get("url"):
                print(f"    (kein Anhang) {z['forum']} / {z['titel'][:50]}")
                continue
            name = z["dateiname_zum_schwaerzen"]
            gesehen[name] = gesehen.get(name, 0) + 1
            if gesehen[name] > 1:
                stamm, endung = name.rsplit(".", 1) if "." in name else (name, "")
                name = (f"{stamm}-{gesehen[name]}.{endung}" if endung
                        else f"{name}-{gesehen[name]}")
                z["dateiname_zum_schwaerzen"] = name
            download_attachment(z["url"], ORDNER / name)
            print(f"    {name}")
        schreibe_csv(zeilen, LISTE)
        shutil.copy2(LISTE, ZIEL / "03_Liste.csv")
        schreibe_liesmich(zeilen)
        bericht(zeilen)
        groesse = sum(p.stat().st_size for p in ORDNER.iterdir() if p.is_file())
        print(f"  Ordner: {ORDNER}  ({groesse / 1e6:.1f} MB)")
        return 0

    # --- loeschen ---------------------------------------------------------
    if not args.bestaetigen:
        print("  --loeschen braucht --bestaetigen (Freigabe). Nichts getan.",
              file=sys.stderr)
        return 2
    ziele: dict[str, dict] = {}
    for z in zeilen:
        ziele.setdefault(z["thread_id"], z)
    # Rollback VOR dem Löschen: ein Manifest, mit dem alles wieder gepostet
    # werden kann (die Dateien dafür liegen im Desktop-Ordner).
    wieder = PRUEF / "klausur_wiederpost.csv"
    with wieder.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["datei", "fach", "kurs", "thema", "art", "titel",
                    "ziel_kanal", "tags", "status", "notiz"])
        for z in zeilen:
            forum = z["forum"]
            kurs = ("LK" if forum.endswith("-lk")
                    else "GK" if forum.endswith("-gk") else "E-Phase")
            w.writerow([z["dateiname_zum_schwaerzen"], forum.split("-")[0].capitalize(),
                        kurs, z["titel"], TAG, z["titel"], forum, TAG, "neu",
                        f"Wiederherstellung (thread {z['thread_id']})"])
    print(f"  Rollback-Manifest: {wieder}\n  Dateien dafür: {ORDNER}")

    entfernt, geskippt = [], []
    for tid, z in ziele.items():
        nachrichten = client.all_messages(tid, limit=100)
        fremde = [m for m in nachrichten if not m.get("author", {}).get("bot")]
        if fremde:
            geskippt.append(tid)
            print(f"    !! {len(fremde)} fremde Nachrichten — NICHT gelöscht: "
                  f"{z['titel'][:50]}")
            continue
        client.request("DELETE", f"/channels/{tid}")
        entfernt.append(tid)
        print(f"    gelöscht: {z['forum']} / {z['titel'][:60]}  ({tid})")

    ergebnis = PRUEF / "klausur_runter.result.csv"
    with ergebnis.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["thread_id", "forum", "titel", "aktion", "url"])
        for tid, z in ziele.items():
            aktion = "deleted" if tid in entfernt else "behalten (fremde Nachrichten)"
            w.writerow([tid, z["forum"], z["titel"], aktion,
                        f"https://discord.com/channels/{guild_of(client, tid)}/{tid}"])
    print(f"\n  {len(entfernt)} von {len(ziele)} Threads entfernt")
    if geskippt:
        print(f"  {len(geskippt)} behalten (fremde Nachrichten)")
    print(f"  Ergebnis: {ergebnis}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DiscordError as err:
        print(err, file=sys.stderr)
        raise SystemExit(2)
