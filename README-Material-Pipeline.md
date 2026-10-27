---
tags: [projekt, schule, discord, agy, pipeline]
status: aktiv
erstellt: 2026-10-11
---

# AGY-Discord — Material-Pipeline

Zentrale Ablage + Ablauf zum Sortieren und Einpflegen von Lernmaterial in den AGY-Discord-Server.

## Ordner

| Pfad | Zweck |
|------|-------|
| [[eingang/neu/]] | **Eingang für neues Material** — Ordner = Ziel-Forum (`eingang/neu/mathematik-gk/`) |
| [[eingang/]] | Roh-Material + Index (`_index_alt.csv` Archiv, `_index_neu.csv` neu abgelegt) |
| [[sortiert/]] | fertig benannte, ggf. nach Thema gesplittete Dateien |
| [[skripte/]] | Hilfsskripte (OCR, Klassifikation, Posting) |
| [[foren-map.csv]] | Routing: Fach + Kurs → Forum-Kanal (+ Kanal-ID, Tags) |
| [[manifest.csv]] | Arbeitsliste / Ergebnis der Pipeline (das eigentliche Erzeugnis) |

## Neues Material ablegen

Ablage in `eingang/neu/<forum>/` — der **Ordnername ist das Ziel-Forum**
(`mathematik-gk`, `deutsch-lk`, `geschichte` …). Gültige Namen siehe `eingang/neu/README.md`.

```bash
python3 skripte/add_material.py                    # indexieren -> eingang/_index_neu.csv
python3 skripte/extract_text.py --match mathematik-gk
# danach wie gewohnt: Topics bündeln -> classify.py -> post_neu.py
```

Warum so: das Archiv-Material kommt über den Index (Server + Kanal aus dem Alt-Server).
Für selbst abgelegtes Material ist der Kanalname schon das Ziel-Forum, deshalb trägt
`ziel_of()` es unverändert durch — dieselbe Kette, dieselben Werkzeuge, keine Sonderfälle.

## Dateinamen-Konvention

GK/LK-Sortierung läuft **manuell über den Dateinamen**:

```
Fach_Kurs_Thema_Art.pdf
```

- **Fach**: Deutsch, Englisch, Mathematik, Physik, Chemie, Biologie, Französisch, DaZ, Geschichte, Geographie, Ethik, GRW
- **Kurs**: `E` (E-Phase) | `GK` | `LK`
- **Thema**: frei, für den Titel
- **Art**: `Zusammenfassung` | `Klausur` | `Hausaufgabe` | `Sonstiges`

Beispiel: `Deutsch_GK_Epochen_Zusammenfassung.pdf`

## Titel-Konvention (Discord-Post)

Nur das Thema, keine Stufe/Kurs im Titel (steckt schon im Forum):

- ✅ `Spanischer Bürgerkrieg`, `Epochen der Lyrik`, `Ableitungsregeln`
- ❌ `Hilfe`, `Hier Bio`, `Zusammenfassung Epochen GK`

## Ablauf (später, automatisiert)

1. Material in `eingang/`.
2. **Extraktion + OCR** — Textebene (pymupdf) bzw. Apple-Vision-OCR (Skill `schul-archiv-ocr-pdf`); gemischte PDFs nach Thema splitten.
3. **Klassifikation** (KI) → Zeile in `manifest.csv`: Fach, Kurs, Thema, Art, Titel-Entwurf.
4. **Routing + Dublettencheck** — Ziel-Forum aus `foren-map.csv`; Titel gegen bestehende Threads fuzzy-matchen. Treffer → als Antwort in bestehenden Post, kein neuer Thread.
5. **Posten** — Modus A: Bot-Skript (Forum-Thread mit Tags + Datei). Modus B: Copy-Paste-Liste aus `manifest.csv` + Datei aus `sortiert/`.

## Foren-Map (Stand Screenshot 11.10.2026)

Kurs steckt im Forum-Namen: ohne Suffix = E-Phase, `-gk` = Grundkurs, `-lk` = Leistungskurs.

LK gibt es real nur in **4 Fächern**: Deutsch, Englisch, Mathematik, Geschichte.
Kein GK: DaZ. Kein E-Phase-Fach: GRW.

Vollständige Liste siehe [[foren-map.csv]] (26 Foren).

## Tags

Existieren bereits in jedem Forum: `Zusammenfassung`, `Klausur/Test`, `Hausaufgabe`, `Sonstiges`.
Tags = **Materialart**. Kurs/Stufe steckt im Forum, nicht im Tag.
