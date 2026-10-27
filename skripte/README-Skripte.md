# AGY-Discord — Skripte

Werkzeuge rund um den Server: **zwei Bots** (holen und posten) und eine lokale
**Material-Pipeline** (PDF/Foto → Themenbeitrag).

Kein `discord.py`, kein Gateway — reine REST-Calls über die Standardbibliothek.
Läuft mit jedem `python3` (getestet mit 3.9.6 und 3.11).

## Bots

| Skript | Token | Rolle | Schreibt |
|---|---|---|---|
| `agy_discord.py` | — | gemeinsame REST-Helfer (nur stdlib): Auth, Rate-Limit, Multipart-Anhang, Forum-Threads | — |
| `discover.py` | `AGY_TOKEN_NEU` | Foren + Tag-IDs des neuen Servers auslesen | `foren-map.resolved.csv` |
| `scrape_alt.py` | `AGY_TOKEN_ALT` | **read-only** Material aus den Alt-Servern laden | `eingang/alt-*/…` + `_index_alt.csv` |
| `post_neu.py` | `AGY_TOKEN_NEU` | Forum-Beiträge aus dem Manifest posten (Titel + Tags + Datei) | `manifest.result.csv` |
| `selftest.py` | `AGY_TOKEN_NEU` | ein Testbeitrag zum Prüfen der Bot-Rechte, danach gelöscht | — |
| `invites.py` | `AGY_TOKEN_NEU` | **Einmal-Einladungen** erzeugen/auflisten/widerrufen (Zugang, s. u.) | Ledger `~/.config/agy-discord/invites.json` |

Der Archivar bekommt bewusst nur Lese-Rechte: er kann in den Alt-Servern nichts
verändern. Es werden ausschließlich GET-Requests und CDN-Downloads gemacht.

## Material-Pipeline (lokal, ohne Discord-Zugriff)

| Skript | Rolle |
|---|---|
| `add_material.py` | **Eingang** für neu abgelegtes Material: `eingang/neu/<forum>/` in den Index aufnehmen; Ordnername tolerant, Fach und Stufe getrennt aufgelöst |
| `zuordnen.py` | **Zuordnung aus dem Inhalt**: neues Material gegen das Archiv (beschriftete Referenz) halten. `--pruefen` misst die Trefferquoten, `--offen` schreibt `zuordnung_vorschlag.csv` |
| `unpack_zips.py` | ZIP-Sammlungen entpacken und als Index-Zeilen nachtragen (mit CP1252-Mojibake-Fix) |
| `extract_text.py` | Textebene (pymupdf) bzw. OCR (Apple Vision) je Datei → `_text_<fach>.json` |
| `digest.py` | Kurzvorschau je Datei als Hilfe beim Themen-Clustering |
| `classify.py` | Themen bündeln → je Thema EINE PDF in `sortiert/` + `manifest_<fach>.csv` (komprimiert auf < 9,4 MB) |
| `pruef_csv.py` | Prüfliste `problematisch_<fach>.csv` (Rechte/§4, kein Lerninhalt, OCR unklar) + Dateikopien in `_pruefen/` |
| `deepcheck.py` | Nachkontrolle: Vollständigkeit (nichts verloren), Dopplungen (auch am Live-Server), Bündelung, leere Seiten |
| `sheet.py` | Kontaktbogen — alle Seiten einer PDF als ein Bild, für die Sichtprüfung gemischter Quellen |

> **Ein Thema darf bewusst in mehreren Foren stehen** (`"ziele": ["x-gk", "x-lk"]` im
> `_klass_…json`): der Inhalt wird einmal gebaut und je Ziel unter eigenem Namen kopiert,
> es entsteht eine Manifest-Zeile pro Forum. Für Inhalte, die in GK *und* LK behandelt
> werden — lieber doppelt als eine Lücke. Die Dublettenprüfung schlägt dabei nicht an,
> weil die Indizes einmalig bleiben.
>
> **Zuordnung aus dem Inhalt ist ein Vorschlag, keine Wahrheit.** Gemessen per
> Leave-one-out über 583 Archivdokumente: Fach 89 %, Fach **und** Stufe 78 %. Die Grenze
> liegt nicht am Textumfang, sondern daran, dass derselbe Inhalt im Alt-Server real in
> zwei Stufen lag (90 Fälle) und viele Beispiele Handyfotos mit dünnem OCR sind. Deshalb:
> identischer Inhalt im Archiv → dessen Stufen (kein Raten); sonst Mehrheitsentscheid;
> bei unklarer Stufe **beide** Foren; bei unlesbarem Text `OFFEN` zum Ansehen.

> **Gemischte Quelldateien sind nicht automatisch erkennbar.** Gemessen und verworfen:
> Seiten-Ähnlichkeit, „fremde Seite im eigenen Dokument", Seitengrößen-Wechsel — alle drei
> trennen eine PDF mit zwei Themen nicht von einer normalen Zusammenfassung. Verlässlich ist
> nur der Blick auf die Seiten (`sheet.py`). Priorität: mehrseitige PDFs ohne Textlayer über
> 6 Seiten, weil die Text-Extraktion dort nur die ersten 6 Seiten liest.

Format des Manifests: siehe `manifest.beispiel.csv` (Spalten
`datei;fach;kurs;thema;art;titel;ziel_kanal;tags;status;notiz`).

## Was NICHT im Repo liegt

- **Tokens** — liegen außerhalb: `~/.config/agy-discord/tokens.env`, `chmod 600`.
- **Einladungs-Ledger** — `~/.config/agy-discord/invites.json` (enthält Zugangscodes), `chmod 600`.
- **Server-/Kanal-IDs** — werden zur Laufzeit von `discover.py` gelesen, nie committet.
- **Material und Metadaten** — Dateien, Indizes, Manifeste, Prüflisten. Siehe `.gitignore`.

---

## 1. Bots anlegen (Discord Developer Portal)

https://discord.com/developers/applications → **New Application**

### Bot A — Poster (neuer Server)
1. Name z. B. `AGY Material Post` → **Bot** → *Reset Token* → Token kopieren.
2. Privileged Intents: **keine** nötig.
3. Einladen (Server-Owner/Admin): **OAuth2 → URL Generator**
   - Scope: `bot`
   - Rechte: *View Channels, Send Messages, **Send Messages in Threads**, Create Public Threads, Manage Threads, Attach Files, Read Message History, Embed Links*
     (`Send Messages in Threads` ist Pflicht, sonst schlägt jede ANTWORT in einem bestehenden
     Beitrag mit `403 Forbidden` fehl — Thread-Erstellen selbst geht auch ohne.)
   - Fertige URL: `https://discord.com/oauth2/authorize?client_id=<APP_ID>&scope=bot&permissions=326417632256`

### Bot B — Archivar (beide Alt-Server)
1. Name z. B. `AGY Material Archiv` → **Bot** → *Reset Token* → Token kopieren.
2. **Privileged Gateway Intent: `MESSAGE CONTENT INTENT` aktivieren** — nur so werden auch die
   Nachrichtentexte gesammelt. (Anhänge kommen auch ohne; der Text ist fürs Einsortieren nützlich.)
3. Einladen in **beide** Alt-Server, Rechte: *View Channels, Read Message History*
   - URL: `https://discord.com/oauth2/authorize?client_id=<APP_ID>&scope=bot&permissions=66560`

> Der Archivar bekommt bewusst nur Lese-Rechte. Er kann in den Alt-Servern nichts verändern.

## 2. Token ablegen

```bash
mkdir -p ~/.config/agy-discord && chmod 700 ~/.config/agy-discord
# ~/.config/agy-discord/tokens.env  (chmod 600)
```

```ini
AGY_TOKEN_NEU=dein_poster_token
AGY_TOKEN_ALT=dein_archivar_token
```

## 3. Reihenfolge

```bash
# a) Foren des neuen Servers + Tag-IDs holen
python3 discover.py

# b) Material aus den Alt-Servern laden (erst Dry-Run zum Zählen)
python3 scrape_alt.py --dry-run
python3 scrape_alt.py

# c) kategorisieren → manifest.csv füllen
#    (Kurs steckt im Dateinamen-Konvention Fach_Kurs_Thema_Art, siehe classify.py)

# d) Vorschau, dann echt posten
python3 post_neu.py --dry-run
python3 post_neu.py
```

`post_neu.py` prüft vor jedem Beitrag, ob im Ziel-Forum schon ein Thread mit
ähnlichem Titel existiert (fuzzy, `--no-dedup` schaltet das ab). Treffer werden als
Antwort in den bestehenden Thread gehängt statt als neuer Beitrag.

## 4. Kanal-IDs in die Map

`discover.py` schreibt `foren-map.resolved.csv` (mit `Kanal_ID` + `Tag_IDs`).
Diese Datei hat Vorrang vor `foren-map.csv`. Du kannst die IDs aber auch von Hand in
`foren-map.csv` (Spalte `Kanal_ID`) eintragen — dann braucht `post_neu.py` keine Tag-IDs,
sie werden zur Laufzeit aus dem Kanal gelesen.

## Diagnose: „0 Anhänge / 0 Text" trotz Nachrichten

Symptom: `scrape_alt.py` zählt Nachrichten, aber `att=0 emb=0`, und alle
`content` sind leer (Keys vorhanden, Werte leer) → **MESSAGE CONTENT INTENT ist AUS**.
Ohne diesen Intent liefert Discord `content`, `attachments`, `embeds` und `components`
leer — **auch über REST**, nicht nur am Gateway.

Fix: Dev-Portal → Application → **Bot** → *Privileged Gateway Intents* →
**MESSAGE CONTENT INTENT** einschalten → Save. Kein Redeploy nötig; greift sofort
für nachfolgende Requests (auch für alte Nachrichten).

`403 Forbidden` auf einzelne Kanäle = Bot fehlt dort *Kanäle ansehen* bzw. *Nachrichtenverlauf*.

`403 Forbidden` auf `POST /channels/<thread>/messages` (nur beim Antworten, Erstellen klappt)
= **Send Messages in Threads** fehlt. Rolle des Bots im Server anpassen oder neu einladen.

## 5. Zugang: Einmal-Einladungen

Der Server hat **keinen Schülernachweis** — der Schutz ist der Einladungscode selbst.
`invites.py` erzeugt **Einmal-Links** (`max_uses=1`) mit Ablaufdatum, die in der Schule
verteilt werden. Ein Link funktioniert genau einmal und verfällt danach: er kann nicht in
Gruppen weitergegeben und nicht dauerhaft auf Invite-Indexern gefunden werden.

```bash
python3 invites.py gen --count 30 --label E1     # 30 Einmal-Codes (= 1 pro Person), 7 Tage
python3 invites.py export --label E1 --unused    # Serienmail-CSV, Spalte "Empfaenger" leer
python3 invites.py list                          # Ledger + echte Nutzung
python3 invites.py revoke --label E1 --unused    # Leck eingrenzen (nur ungenutzte)
python3 invites.py forget --code abc123          # Ledger aufräumen (nach UI-Löschung)
```

**Ein Code = eine Person.** `gen --count N` erzeugt N Codes mit `max_uses=1` — der erste
Beitritt verbraucht den Code. Für Nachzügler ein paar Reserve-Codes erzeugen.

**Der Export ist serienmail-fähig**: `Nr;Kohorte;Link;gueltig_bis;Status;Betreff;Nachricht;Empfaenger`
(UTF-8 mit BOM, `;` — öffnet direkt in Excel/LibreOffice). Betreff und Nachrichtentext sind
fertig, du füllst nur **Empfaenger** aus.

> **Datenschutz — bitte einhalten:** Die **gefüllte** CSV verkettet Code und Mailadresse und ist
> damit personenbezogen. Sie bleibt lokal, kommt **nie** in Vault, Repo oder Cloud und wird nach
> dem Versand gelöscht. Das Ledger (`~/.config/agy-discord/invites.json`) enthält dagegen nur
> Codes und Kohorten — ohne jeden Personenbezug.

- **Rechte:** Die Bot-Rolle („Poster") braucht **Einladung erstellen**
  (`CREATE_INSTANT_INVITE`). Das Recht gilt **pro Kanal** — `#start-hier` und `#regeln`
  verweigern es @everyone per Deny. Damit der Default-Kanal funktioniert, dort einmalig
  erlauben: **#start-hier → Berechtigungen → Rolle „Poster" → Einladung erstellen**.
  Ohne diesen Klick: `--channel allgemein` nutzen (funktioniert sofort).
  Für `list`/`export` genügt der öffentliche Invite-Endpunkt — **kein** `MANAGE_GUILD` nötig.
- **Widerruf:** `DELETE /invites/{code}` braucht **`MANAGE_CHANNELS`** im Kanal (oder
  `MANAGE_GUILD` für alle). Hat der Bot das nicht, meldet `revoke` das und du löschst den
  Link in der UI: **Server-Einstellungen → Einladungen**. Danach den Eintrag lokal
  aufräumen: `python3 invites.py forget --code <code>`.
- **Labels sind Klasse/Kohorte** (`E1`, `GK-Mathe`), **nie Personennamen**. Bei einem Leck
  rotierst du genau diese Kohorte.
- Ledger außerhalb des Vaults: `~/.config/agy-discord/invites.json` (`chmod 600`).
- Die fertigen Link-Listen liegen in **`~/agy-einladungen/`** (`chmod 700`) — sichtbar im
  Home, aber lokal: kein Vault, kein Sync, kein Repo. Ein anderer Zielpfad geht mit `--out`.
- Zusätzlich von Hand: Server-Einstellungen → **Einladungen** → alte/Kanal-Links löschen;
  Server-**Discovery aus** lassen; Dauer-Links nur bewusst (`--no-expiry`).

> **Grenze (bewusst akzeptiert):** Wer den Code bekommt, ist drin. Der Vertrauensanker ist
> die Ausgabe (Klassengruppe/Lehrkraft), nicht der Server — ein echter Schülernachweis
> bräuchte entweder manuelle Freischaltung oder eine Datenquelle (Schul-Mail/LernSax).
> Weitergabe an eine Fremdperson bleibt möglich und ist nur über die Einmal-Regel
> abgemildert.

## Bekannte Grenzen

- **Discord-Dateilimit 10 MB** (nicht geboostet) → große Scan-PDFs vorher komprimieren.
- **Office- und Medien-Dateien** (`.doc/.docx/.pptx/.mov/…`) werden nicht nach PDF
  gewandelt, sondern im Original angehängt (`ATTACH_EXT` in `agy_discord.py`).
- `PATCH /channels/<thread>` (Umbenennen eines Threads) ist mit den Bot-Rechten nicht
  möglich — bei falschem Titel neu anlegen.
- Für die OCR-Stufe wird das Hermes-Skill-Skript
  `~/.hermes/skills/note-taking/schul-archiv-ocr-pdf/scripts/ocr-vision-swift.swift`
  erwartet (Apple Vision, macOS). Ohne diese Datei läuft `extract_text.py` nur für
  PDFs mit Textebene.
