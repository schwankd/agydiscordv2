#!/usr/bin/env python3
"""AGY-Discord — gemeinsame REST-Helfer (nur Standardbibliothek).

Kein discord.py, kein Gateway/Websocket: reine REST-Calls genügen zum
Scrapen (Alt-Server) und Posten (Neuer Server).

Token-Ablage: ~/.config/agy-discord/tokens.env  (chmod 600, NICHT im Vault)
Schlüssel: AGY_TOKEN_NEU (Poster, neuer Server)
           AGY_TOKEN_ALT (Archivar, beide Alt-Server)
Env-Variablen gleichen Namens übersteuern die Datei.
"""
from __future__ import annotations

import json
import mimetypes
import os
import pathlib
import re
import time
import urllib.error
import urllib.request
import uuid

API = "https://discord.com/api/v10"
TOKEN_FILE = pathlib.Path.home() / ".config" / "agy-discord" / "tokens.env"

# Kanaltypen (Discord)
T_TEXT, T_VOICE, T_CATEGORY, T_NEWS = 0, 2, 4, 5
T_ANNOUNCEMENT_THREAD, T_PUBLIC_THREAD, T_PRIVATE_THREAD = 10, 11, 12
T_FORUM, T_MEDIA = 15, 16
FORUM_TYPES = {T_FORUM, T_MEDIA}
TEXT_TYPES = {T_TEXT, T_NEWS}
THREAD_TYPES = {T_ANNOUNCEMENT_THREAD, T_PUBLIC_THREAD, T_PRIVATE_THREAD}

# Materialtypen (eine Quelle für alle Skripte)
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".tiff", ".tif", ".heic", ".bmp", ".gif"}
CONTAINER_EXT = {".zip"}      # kein Inhalt, sondern Sammlung -> unpack_zips.py
# Büro-Formate: nicht nach PDF wandeln (ginge nur mit LibreOffice), sondern im
# Original anhängen — verlustfrei. Text für Titel/Art wird trotzdem gezogen.
ATTACH_EXT = {".doc", ".docx", ".docm", ".ppt", ".pptx", ".xls", ".xlsx",
              ".odt", ".ods", ".odp", ".rtf",
              # Medien: nicht in PDF wandelbar -> ebenfalls im Original anhängen
              ".mov", ".mp4", ".m4v", ".avi", ".webm", ".mkv",
              ".mp3", ".m4a", ".ogg", ".wav", ".opus"}
XML_TEXT_EXT = {".docx", ".pptx", ".xlsx"}   # ZIP+XML -> Text mit Bordmitteln lesbar


class DiscordError(RuntimeError):
    pass


def load_tokens() -> dict:
    tokens: dict[str, str] = {}
    if TOKEN_FILE.exists():
        for line in TOKEN_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            tokens[key.strip()] = val.strip().strip('"').strip("'")
    for key in ("AGY_TOKEN_NEU", "AGY_TOKEN_ALT"):
        if os.environ.get(key):
            tokens[key] = os.environ[key]
    return tokens


def get_token(name: str) -> str:
    token = load_tokens().get(name)
    if not token:
        raise DiscordError(
            f"Kein Token '{name}' gefunden.\n"
            f"  Lege {TOKEN_FILE} an (chmod 600) oder exportiere ${name}.\n"
            f"  Beispiel:\n    {name}=dein_bot_token"
        )
    return token


def office_text(path) -> str:
    """Text aus .docx/.pptx/.xlsx ziehen (sind ZIPs mit XML — Bordmittel reicht).

    Typ wird am INHALT erkannt, nicht an der Endung: es gibt .doc/.ppt-Dateien,
    die in Wahrheit ZIPs mit den neuen XML-Pfaden sind. Alte Binärformate
    scheitern am ZIP-Öffnen; das Ergebnis sagt das dann selbst.
    """
    import re
    import zipfile
    path = pathlib.Path(path)
    try:
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            if "word/document.xml" in names:
                xml = zf.read("word/document.xml").decode("utf-8", "ignore")
            elif any(n.startswith("ppt/slides/slide") for n in names):
                slides = sorted(n for n in names if n.startswith("ppt/slides/slide"))
                xml = "\n".join(zf.read(n).decode("utf-8", "ignore") for n in slides)
            elif "xl/sharedStrings.xml" in names:
                xml = zf.read("xl/sharedStrings.xml").decode("utf-8", "ignore")
            else:
                return f"[Office-Format nicht erkannt: {path.name}]"
    except Exception as err:  # noqa: BLE001
        return f"[Office-Text nicht lesbar: {err}]"
    xml = re.sub(r"</w:p>|</a:p>", "\n", xml)
    return re.sub(r"[ \t]+", " ", re.sub(r"<[^>]+>", " ", xml)).strip()


def safe(name: str, maxlen: int = 120) -> str:
    """Dateinamen sicher machen (macOS/APFS, keine '/' oder NUL)."""
    name = re.sub(r"[\x00-\x1f/\\:]", "_", name)
    name = re.sub(r"\s+", " ", name).strip().strip(".")
    return (name or "unbenannt")[:maxlen]


def norm_title(s: str) -> str:
    """Für Dublettenvergleich: klein, Umlaute gefaltet, nur Alnum."""
    s = s.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


class Client:
    def __init__(self, token: str, user_agent: str = "AGY-Discord-Tool/1.0 (schwankd)"):
        self.token = token
        self.ua = user_agent

    def _base_headers(self, extra: dict | None = None) -> dict:
        h = {"Authorization": f"Bot {self.token}", "User-Agent": self.ua}
        if extra:
            h.update(extra)
        return h

    def request(self, method: str, path: str, *, body=None, data=None,
                content_type=None, retries: int = 5, expect_json: bool = True):
        url = path if path.startswith("http") else API + path
        attempt = 0
        while True:
            attempt += 1
            extra = {"Content-Type": content_type} if content_type else None
            req = urllib.request.Request(url, method=method)
            for k, v in self._base_headers(extra).items():
                req.add_header(k, v)
            payload = None
            if data is not None:
                payload = data
            elif body is not None:
                payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
                req.add_header("Content-Type", "application/json")
            try:
                with urllib.request.urlopen(req, data=payload, timeout=60) as resp:
                    raw = resp.read()
                    return json.loads(raw) if (expect_json and raw) else raw
            except urllib.error.HTTPError as err:
                raw = err.read()
                if err.code == 429 and attempt <= retries:
                    try:
                        wait = float(json.loads(raw).get("retry_after", 1.0))
                    except Exception:
                        wait = 1.0
                    time.sleep(wait + 0.25)
                    continue
                if 500 <= err.code < 600 and attempt <= retries:
                    time.sleep(1.5 * attempt)
                    continue
                if err.code == 403:
                    raise DiscordError(f"{method} {path} -> 403 Forbidden (fehlende Rechte)") from None
                raise DiscordError(f"{method} {path} -> HTTP {err.code}: {raw[:400]!r}") from None
            except urllib.error.URLError as err:
                if attempt <= retries:
                    time.sleep(1.5 * attempt)
                    continue
                raise DiscordError(f"{method} {path} -> {err}") from None

    def get(self, path: str, **kw):
        return self.request("GET", path, **kw)

    def post(self, path: str, body=None, **kw):
        return self.request("POST", path, body=body, **kw)

    def post_file(self, path: str, payload: dict, files: list[str]):
        """Multipart-POST mit payload_json + files[0..n]."""
        boundary = "----agy" + uuid.uuid4().hex
        chunks: list[bytes] = []

        chunks.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"payload_json\"\r\n\r\n"
            f"{json.dumps(payload, ensure_ascii=False)}\r\n".encode("utf-8")
        )
        for idx, fp in enumerate(files):
            fn = os.path.basename(fp)
            ctype = mimetypes.guess_type(fn)[0] or "application/octet-stream"
            chunks.append(
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"files[{idx}]\"; "
                f"filename=\"{fn}\"\r\nContent-Type: {ctype}\r\n\r\n".encode("utf-8")
            )
            chunks.append(pathlib.Path(fp).read_bytes())
            chunks.append(b"\r\n")
        chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
        return self.request(
            "POST", path, data=b"".join(chunks),
            content_type=f"multipart/form-data; boundary={boundary}",
        )

    # --- Pagination ---------------------------------------------------
    def all_messages(self, channel_id: str, limit: int | None = None, pause: float = 0.0):
        out: list = []
        before = None
        while True:
            query = "?limit=100" + (f"&before={before}" if before else "")
            batch = self.get(f"/channels/{channel_id}/messages{query}")
            if not batch:
                break
            out.extend(batch)
            if limit and len(out) >= limit:
                return out[:limit]
            if len(batch) < 100:
                break
            before = batch[-1]["id"]
            if pause:
                time.sleep(pause)
        return out

    def forum_threads(self, channel_id: str, guild_id: str | None = None):
        threads: list = []
        if guild_id:
            try:
                active = self.get(f"/guilds/{guild_id}/threads/active")
                threads += [t for t in active.get("threads", []) if t.get("parent_id") == channel_id]
            except DiscordError:
                pass
        before = None
        while True:
            query = "?limit=100" + (f"&before={before}" if before else "")
            try:
                page = self.get(f"/channels/{channel_id}/threads/archived/public{query}")
            except DiscordError:
                break
            got = page.get("threads", [])
            threads += got
            if not page.get("has_more") or not got:
                break
            before = got[-1].get("thread_metadata", {}).get("archive_timestamp")
            if not before:
                break
        return threads


def download_attachment(url: str, dest: pathlib.Path, retries: int = 3) -> int:
    """Lädt eine CDN-URL (kein Auth nötig) nach dest. Gibt Bytezahl zurück."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    attempt = 0
    while True:
        attempt += 1
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AGY-Discord-Tool/1.0"})
            with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, "wb") as fh:
                total = 0
                while True:
                    block = resp.read(1 << 16)
                    if not block:
                        break
                    fh.write(block)
                    total += len(block)
            tmp.replace(dest)
            return total
        except Exception:
            if attempt > retries:
                if tmp.exists():
                    tmp.unlink()
                raise
            time.sleep(1.5 * attempt)
