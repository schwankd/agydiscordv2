#!/usr/bin/env python3
"""AGY-Discord — Einladungs-System (nur Standardbibliothek, REST).

Erzeugt **Einmal-Einladungen** (max_uses=1) mit Ablaufdatum, verwaltet sie in
einem lokalen Ledger außerhalb des Vaults und gibt sie als druckbare Liste aus.

Warum Einmal-Codes: der Besitz des Links ist der einzige Vertrauensanker, der
**keine personenbezogenen Daten** braucht. Ein Link, der nur einmal funktioniert
und nach X Tagen verfällt, kann nicht in Gruppen weitergegeben oder auf
Invite-Indexern gefunden werden.

Datenschutz: Das Ledger enthält NUR Codes + Metadaten (Kohorte, Ablauf).
Labels sind **Klasse/Kohorte** (E1, GK-Mathe), NIE Personennamen.

Aufrufe:
    python3 invites.py gen --count 30 --label E1        # 30 Einmal-Codes erzeugen
    python3 invites.py list                             # Ledger + echte Nutzung
    python3 invites.py export --label E1 --out liste.txt
    python3 invites.py revoke --code abc123
    python3 invites.py revoke --label E1 --unused       # ungenutzte einer Kohorte
    python3 invites.py gen --count 5 --label test --dry-run   # offline, tut nichts

Rechte: Die Bot-Rolle braucht **Create Invite** (CREATE_INSTANT_INVITE) im
Zielkanal. Für `list` (echte Nutzung) genügt der öffentliche Invite-Endpunkt.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from agy_discord import Client, DiscordError, get_token  # noqa: E402

LEDGER = pathlib.Path.home() / ".config" / "agy-discord" / "invites.json"
DEFAULT_CHANNEL = "start-hier"      # Aufsetzpunkt; Sichtbarkeit regelt @everyone
DEFAULT_DAYS = 7


# --- Ledger ---------------------------------------------------------------
def load_ledger() -> list[dict]:
    if LEDGER.exists():
        try:
            return json.loads(LEDGER.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            raise DiscordError(f"Ledger defekt: {LEDGER}") from None
    return []


def save_ledger(rows: list[dict]) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    tmp = LEDGER.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(LEDGER)
    LEDGER.chmod(0o600)


# --- Server-Auflösung -----------------------------------------------------
def resolve_guild(client: Client, wanted: str | None) -> str:
    guilds = client.get("/users/@me/guilds")
    if not guilds:
        raise DiscordError("Bot ist in keinem Server (scope=bot? Rechte?)")
    if wanted:
        hit = next((g for g in guilds if g["id"] == wanted or g["name"] == wanted), None)
        if not hit:
            raise DiscordError(f"Server '{wanted}' nicht gefunden: {[g['name'] for g in guilds]}")
        return hit["id"]
    if len(guilds) > 1:
        raise DiscordError(f"Mehrere Server — --guild angeben: {[(g['id'], g['name']) for g in guilds]}")
    return guilds[0]["id"]


def resolve_channel(client: Client, gid: str, name: str) -> tuple[str, str]:
    chans = client.get(f"/guilds/{gid}/channels")
    hit = next((c for c in chans if c.get("name", "").lower() == name.lower() and c.get("type") in (0, 5)), None)
    if hit:
        return hit["id"], hit["name"]
    if name == DEFAULT_CHANNEL:      # Fallback: Regel-Kanal
        gd = client.get(f"/guilds/{gid}")
        rid = gd.get("rules_channel_id")
        if rid:
            rc = next((c for c in chans if c["id"] == rid), None)
            return rid, (rc or {}).get("name", "rules")
    raise DiscordError(f"Textkanal '{name}' nicht gefunden")


# --- Nutzungs-Status (öffentlicher Endpunkt, keine Guild-Rechte nötig) ----
def invite_meta(client: Client, code: str) -> dict:
    try:
        return client.get(f"/invites/{code}?with_counts=true&with_expiration=true")
    except DiscordError:
        return {}


def expires_epoch(m: dict) -> float | None:
    """expires_at kommt je nach API-Stand als Epoch-Zahl ODER ISO-8601-String."""
    exp = m.get("expires_at")
    if exp is None:
        return None
    if isinstance(exp, (int, float)):
        return float(exp)
    try:
        return dt.datetime.fromisoformat(str(exp).replace("Z", "+00:00")).timestamp()
    except ValueError:
        try:                                   # ohne Zeitzone -> als UTC lesen
            return dt.datetime.fromisoformat(str(exp)[:19]).replace(
                tzinfo=dt.timezone.utc).timestamp()
        except ValueError:
            return None


def status_from_meta(m: dict, row: dict) -> tuple[int, bool, str]:
    if not m:
        return row.get("uses", 0) or 0, True, "gelöscht/ungültig"
    uses = m.get("uses", 0)
    exp = expires_epoch(m)
    if m.get("max_uses") and uses >= m["max_uses"]:
        state = "verbraucht"
    elif exp and exp < time.time():
        state = "abgelaufen"
    else:
        state = "offen"
    return uses, exp is None, state


def live_status(client: Client, row: dict) -> tuple[int, bool, str]:
    return status_from_meta(invite_meta(client, row["code"]), row)


# --- Kommandos ------------------------------------------------------------
def cmd_gen(args) -> int:
    if not 1 <= args.count <= 200:
        raise DiscordError("--count zwischen 1 und 200 (versehentliche Massenanlage).")
    if not args.no_expiry and args.days < 1:
        raise DiscordError("Ablauf >= 1 Tag. Dauer-Links nur bewusst mit --no-expiry.")
    client = Client(get_token(args.token))
    gid = resolve_guild(client, args.guild)
    cid, cname = resolve_channel(client, gid, args.channel)
    days = args.days
    ablauf = "nie (Dauer-Link!)" if args.no_expiry else f"{days} Tage"
    print(f"Server {gid} · Kanal #{cname} ({cid}) · {args.count}× Einmal-Code"
          f" · Ablauf {ablauf} · Label {args.label or '(ohne)'!r}")
    if args.dry_run:
        print("DRY-RUN — es wird nichts erzeugt.")
        return 0

    rows = load_ledger()
    made = []
    for n in range(args.count):
        body = {"max_age": 0 if args.no_expiry else days * 86400, "max_uses": 1,
                "temporary": False, "unique": True}
        try:
            inv = client.post(f"/channels/{cid}/invites", body)
        except DiscordError as err:
            if "403" in str(err):
                print(f"\n403 — Einladung erstellen in #{cname} verweigert.\n"
                      "  Ursache 1: Bot-Rolle braucht 'Einladung erstellen' (CREATE_INSTANT_INVITE)\n"
                      "             → Server-Einstellungen → Rollen → 'Poster'.\n"
                      "  Ursache 2: Der KANAL verweigert es. Willkommens-/Regel-Kanäle haben für\n"
                      "             @everyone ein Deny. Fix: Kanal → Berechtigungen → Rolle 'Poster'\n"
                      "             → 'Einladung erstellen' erlauben, ODER anderen Kanal nehmen:\n"
                      f"             python3 invites.py gen ... --channel allgemein", file=sys.stderr)
            raise
        rows.append({
            "code": inv["code"], "label": args.label,
            "guild_id": gid, "channel_id": cid, "channel": cname,
            "created": dt.datetime.now().isoformat(timespec="seconds"),
            "max_age_days": days, "max_uses": 1, "uses": 0,
        })
        made.append(inv["code"])
        save_ledger(rows)          # nach jedem Code sichern
        if not args.quiet:
            print(f"  {n + 1:>3}/{args.count}  https://discord.gg/{inv['code']}")
    print(f"\n{len(made)} Codes → Ledger {LEDGER}")
    print(f"Weitergeben mit:  python3 invites.py export --label {args.label}")
    return 0


def cmd_list(args) -> int:
    rows = load_ledger()
    if args.label:
        rows = [r for r in rows if r.get("label") == args.label]
    if not rows:
        print("Ledger ist leer.")
        return 0
    client = Client(get_token(args.token))
    print(f"{'CODE':<12} {'LABEL':<10} {'ERSTELLT':<17} {'ABLAUF':<10} {'USES':<5} STATUS")
    for r in rows:
        uses, never, state = live_status(client, r)
        ablauf = "nie" if never else f"{r.get('max_age_days', '?')} T"
        print(f"{r['code']:<12} {r.get('label', ''):<10} {r.get('created', ''):<17} "
              f"{ablauf:<10} {uses:<5} {state}")
    return 0


def cmd_revoke(args) -> int:
    if not (args.code or args.label):
        raise DiscordError("--code oder --label angeben.")
    client = Client(get_token(args.token))
    rows = load_ledger()
    keep, gone = [], []
    for r in rows:
        match = (args.code and r["code"] == args.code) or \
                (bool(args.label) and r.get("label") == args.label and
                 (True if not args.unused else live_status(client, r)[2] != "verbraucht"))
        if not match:
            keep.append(r)
            continue
        try:
            client.request("DELETE", f"/invites/{r['code']}")
            gone.append(r["code"])
        except DiscordError as err:
            keep.append(r)                       # Fehlschlag: Eintrag bleibt im Ledger
            if "404" in str(err) or "403" in str(err):
                print(f"  {r['code']}: nicht widerrufbar — dem Bot fehlt MANAGE_CHANNELS im "
                      "Kanal\n      oder MANAGE_GUILD. Notfalls in der Discord-UI löschen:\n"
                      "      Server-Einstellungen → Einladungen.", file=sys.stderr)
            else:
                print(f"  {r['code']}: {err}", file=sys.stderr)
    save_ledger(keep)
    print(f"{len(gone)} Einladung(en) widerrufen, {len(keep)} im Ledger.")
    return 0 if gone or not rows else 1


def cmd_forget(args) -> int:
    """Ledger-Eintrag entfernen, ohne Discord anzufassen (nach Löschen in der UI)."""
    if not (args.code or args.label):
        raise DiscordError("--code oder --label angeben.")
    rows = load_ledger()
    keep = [r for r in rows
            if not (r["code"] == args.code if args.code else r.get("label") == args.label)]
    save_ledger(keep)
    print(f"{len(rows) - len(keep)} Eintrag/Einträge aus dem Ledger entfernt, {len(keep)} übrig.")
    return 0


MAIL_BETREFF = "Dein Zugang zum AGY-Discord"


def mail_text(link: str) -> str:
    return (
        "Hallo,\n\n"
        "hier ist dein persönlicher Zugang zum Discord-Server des AGY:\n"
        f"{link}\n\n"
        "Wichtig: Der Link funktioniert genau EINMAL und nur für dich. Bitte nicht "
        "weitergeben — ist er benutzt, ist er tot. Er läuft nach ein paar Tagen ab.\n\n"
        "Danach im Server die Regeln bestätigen und das Onboarding ausfüllen.\n"
        "Viele Grüße"
    )


def cmd_export(args) -> int:
    rows = load_ledger()
    if args.label:
        rows = [r for r in rows if r.get("label") == args.label]
    if not rows:
        print("Keine passenden Codes im Ledger.", file=sys.stderr)
        return 1
    client = Client(get_token(args.token))
    if args.unused:                       # schon verbrauchte Codes nicht mehr verschicken
        rows = [r for r in rows if live_status(client, r)[2] != "verbraucht"]
        if not rows:
            print("Alle Codes dieser Kohorte sind verbraucht.", file=sys.stderr)
            return 1
    stamp = dt.date.today().isoformat()
    out = pathlib.Path(args.out or (LEDGER.parent / f"einladungen-{args.label or 'alle'}-{stamp}.csv"))
    with out.open("w", newline="", encoding="utf-8-sig") as fh:   # BOM -> Excel/LibreOffice
        w = csv.writer(fh, delimiter=";")
        w.writerow(["Nr", "Kohorte", "Link", "gueltig_bis", "Status",
                    "Betreff", "Nachricht", "Empfaenger"])
        for n, r in enumerate(rows, 1):
            m = invite_meta(client, r["code"])
            link = f"https://discord.gg/{r['code']}"
            ts = expires_epoch(m)
            exp = dt.datetime.fromtimestamp(ts).strftime("%d.%m.%Y") if ts else "nie"
            w.writerow([n, r.get("label", ""), link, exp, status_from_meta(m, r)[2],
                        MAIL_BETREFF, mail_text(link), ""])
    out.chmod(0o600)
    print(f"{len(rows)} Links → {out}")
    print("Spalte 'Empfaenger' von Hand füllen (LernSax), dann Serienmail.\n"
          "ACHTUNG: gefüllt ist die Datei personenbezogen — nur lokal, nie in Vault/Repo/Cloud,\n"
          "und nach dem Versand löschen.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="AGY-Discord Einmal-Einladungen")
    ap.add_argument("--token", default="AGY_TOKEN_NEU")
    ap.add_argument("--guild", help="Server-ID oder -Name")
    ap.add_argument("--ledger", help="anderes Ledger (Tests) — Default ~/.config/agy-discord/invites.json")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("gen", help="N Einmal-Codes erzeugen")
    g.add_argument("--count", type=int, default=1, help="1..200")
    g.add_argument("--label", default="", help="Kohorte/Klasse (E1, GK-Mathe) — NIE Namen")
    g.add_argument("--days", type=int, default=DEFAULT_DAYS, help="Ablauf in Tagen (>=1)")
    g.add_argument("--no-expiry", action="store_true", help="Dauer-Link — nur bewusst")
    g.add_argument("--channel", default=DEFAULT_CHANNEL)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--quiet", action="store_true")
    g.set_defaults(func=cmd_gen)

    l = sub.add_parser("list", help="Ledger + echte Nutzung")
    l.add_argument("--label")
    l.set_defaults(func=cmd_list)

    r = sub.add_parser("revoke", help="Einladung(en) widerrufen")
    r.add_argument("--code")
    r.add_argument("--label")
    r.add_argument("--unused", action="store_true", help="nur noch nicht genutzte")
    r.set_defaults(func=cmd_revoke)

    f = sub.add_parser("forget", help="Ledger-Eintrag entfernen (nach UI-Löschung)")
    f.add_argument("--code")
    f.add_argument("--label")
    f.set_defaults(func=cmd_forget)

    e = sub.add_parser("export", help="als CSV (Serienmail-fähig) ausgeben")
    e.add_argument("--label")
    e.add_argument("--out")
    e.add_argument("--unused", action="store_true", help="verbrauchte Codes weglassen")
    e.set_defaults(func=cmd_export)
    return ap


def main() -> int:
    global LEDGER
    args = build_parser().parse_args()
    if getattr(args, "ledger", None):      # Test-/Alternativ-Ledger
        LEDGER = pathlib.Path(args.ledger).expanduser()
    try:
        return args.func(args)
    except DiscordError as err:
        print(err, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
