#!/usr/bin/env python3
"""Regelwerk aus regeln.md in den Kanal #regeln posten.

Eine Quelle der Wahrheit: ../regeln.md. Kein Kanal-/Server-ID im Repo — Server und
Kanäle werden zur Laufzeit über die API aufgelöst (wie discover.py).

Aufruf:  python3 post_regeln.py [--dry-run]
Rechte:  Der Bot braucht SEND_MESSAGES im Zielkanal. In #regeln verweigert @everyone
         (und damit die Bot-Rolle) das Schreiben — die Rolle des Bots muss dort
         einmalig „Nachrichten senden" erlauben.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import agy_discord as A  # noqa: E402

RULES_FILE = pathlib.Path(__file__).resolve().parent.parent / "regeln.md"
GUILD_NAME = "Abendschule Dresden"
CHANNEL = "regeln"
LINK_ALLGEMEIN = "#allgemein"     # wird zur Kanal-Verlinkung aufgelöst
LIMIT = 2000                       # Discord-Nachrichtenlimit


def unwrap(raw: str) -> str:
    """Harte Zeilenumbrüche des Markdown auflösen (Absätze/Aufzählungen bleiben)."""
    out: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            out.append("")
        elif stripped.startswith(("- ", "## ", "# ", ">", "---")):
            out.append(stripped)
        elif out and out[-1].strip() and not out[-1].startswith(("## ", "# ", ">", "---")):
            out[-1] += " " + stripped
        else:
            out.append(stripped)
    return "\n".join(out)


def discord_text(mention: str) -> str:
    raw = unwrap(RULES_FILE.read_text(encoding="utf-8"))
    body = raw[raw.index("## §"):]
    body = "\n".join(line for line in body.split("\n") if line.strip() != "---").strip()
    body = body.replace(f"`{LINK_ALLGEMEIN}`", mention)
    return "📜 **Server-Regeln**\n\n" + body


def sections(text: str) -> list[str]:
    """Text an den Paragraf-Überschriften teilen; der Titel bleibt eigener Block."""
    blocks: list[str] = []
    for chunk in text.split("\n\n"):
        if chunk.startswith("## §") or not blocks:
            blocks.append(chunk)
        else:
            blocks[-1] += "\n\n" + chunk
    return blocks


def pack(blocks: list[str], limit: int = LIMIT) -> list[str]:
    parts: list[str] = []
    cur = ""
    for b in blocks:
        cand = f"{cur}\n\n{b}" if cur else b
        if len(cand) > limit - 20 and cur:
            parts.append(cur)
            cur = b
        else:
            cur = cand
    if cur:
        parts.append(cur)
    return [f"{p}\n\n*({i}/{len(parts)})*" for i, p in enumerate(parts, 1)] if len(parts) > 1 else parts


def resolve(client: A.Client) -> tuple[str, str, str]:
    """(guild_id, regeln_id, allgemein_id) zur Laufzeit auflösen."""
    guilds = [g for g in client.get("/users/@me/guilds") if g["name"] == GUILD_NAME]
    if len(guilds) != 1:
        raise A.DiscordError(f"Server '{GUILD_NAME}' nicht eindeutig gefunden: {[g['name'] for g in guilds]}")
    gid = guilds[0]["id"]
    chans = {c["name"]: c["id"] for c in client.get(f"/guilds/{gid}/channels")}
    for need in (CHANNEL, LINK_ALLGEMEIN.lstrip("#")):
        if need not in chans:
            raise A.DiscordError(f"Kanal '#{need}' nicht gefunden")
    return gid, chans[CHANNEL], chans[LINK_ALLGEMEIN.lstrip("#")]


def main() -> int:
    c = A.Client(A.get_token("AGY_TOKEN_NEU"))
    _gid, regeln_id, allgemein_id = resolve(c)
    parts = pack(sections(discord_text(f"<#{allgemein_id}>")))
    for i, p in enumerate(parts, 1):
        print(f"Teil {i}: {len(p)} Zeichen")
    if "--dry-run" in sys.argv:
        print("\n--- VORSCHAU ---\n" + "\n\n=== NÄCHSTE NACHRICHT ===\n\n".join(parts))
        return 0

    ids = []
    for i, p in enumerate(parts, 1):
        try:
            m = c.post(f"/channels/{regeln_id}/messages", {"content": p})
        except A.DiscordError as e:
            print(f"POST Teil {i} FEHLGESCHLAGEN: {e}\nbereits gepostet: {ids}")
            return 2
        ids.append(m["id"])
        print(f"gepostet Teil {i}: {m['id']} {m['timestamp']}")
    for i, mid in enumerate(ids, 1):
        back = c.get(f"/channels/{regeln_id}/messages/{mid}")
        lines = back["content"].splitlines()
        print(f"verifiziert Teil {i}: {len(back['content'])} Zeichen | {back['author']['username']} | "
              f"{lines[0][:30]!r} … {lines[-1][:40]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
