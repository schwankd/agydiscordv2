# agydiscordv2
Discord Server für AGY Klassenübergreifend

# 🎓 Konzept: Inoffizieller Discord-Server AGY Dresden

**Zielsetzung & Philosophie:**
Schaffung einer intuitiven, barrierearmen und sicheren Plattform für die Lernenden des Abendgymnasiums (AGY) Dresden. Der Server dient dem Austausch, der Vernetzung und der zentralen, filterbaren Sammlung von Lernmaterialien (E-Phase, Jg. 11 und 12). Das Wording auf dem Server ist inklusiv und wertschätzend (z. B. *Lernende* statt Schüler, *Lehrkräfte* statt Lehrer). Die Struktur ist minimalistisch gehalten, um auch Discord-Neulingen einen leichten Einstieg zu ermöglichen.

---

## 🛡️ 1. Das Rollen- und Berechtigungskonzept

Wir setzen auf ein System der **reaktiven Moderation**. Es gibt keine manuellen Freischaltungen durch das Team, was den Verwaltungsaufwand minimiert. Die Sicherheit wird durch klare Regeln, die Melde-Kultur der Community und die Discord-AutoMod-Funktion (automatisches Blockieren von Schimpfwörtern) gewährleistet.

| Rollenname | Farbe/Status | Rechte & Funktion |
| :--- | :--- | :--- |
| **@Admin** | Rot (Sichtbar) | Volle Serverkontrolle, Technik, Rechtemanagement. |
| **@Moderation** | Orange (Sichtbar) | Nachrichten löschen, User verwarnen/kicken, Chat-Pflege. |
| **@Schülerrat** | Blau (Sichtbar) | Offizielle Ansprechpersonen der Schülerschaft. |
| **@Jahrgang 12 / 11 / E-Phase** | Farblich getrennt | Dienen der Gruppierung in der rechten Mitgliederliste. |
| **@LK / @GK / @Klasse** | Unsichtbar im Menü | Dienen als Profil-Tags zur leichteren Erkennung im Chat. |
| **@Lernende** | Standard | Basis-Rolle, die jeder automatisch nach dem Onboarding erhält. Darf überall schreiben und Forenposts erstellen. |
| **@everyone** | Keine | Sieht nur das Onboarding und die Regeln (Bot-Schutz). |

---

## 📂 2. Die Kanal- und Kategorienstruktur

Der Server wird in vier übersichtliche Kategorien unterteilt. 

### 📌 WILLKOMMEN & INFOS
*(Lesezugriff für alle, Schreibzugriff nur Admin/Mod)*
- `#start-hier` – Empfangshalle mit Wegweiser und Erklärung der Foren.
- `#regelwerk` – Die verbindlichen Server-Regeln (zum Nachlesen).
- `#ankündigungen` – Wichtige Meldungen von Moderation oder Schülerrat.
- `#bafög-und-soziales` – Tipps und Links mit festem Disclaimer im Kanalthema: *"Infos von Lernenden für Lernende. Keine Gewähr. Bitte bei offiziellen Stellen prüfen."*

### 💬 AUSTAUSCH & COMMUNITY
*(Schreibzugriff für alle @Lernende)*
- `#allgemein` – Der Hauptchat für den täglichen Austausch, Fragen, Smalltalk und schnelle Anliegen an den `@Schülerrat`.

### 📚 LERNBEREICH
*(Foren-Kanäle)*
- `#deutsch`, `#englisch`, `#mathematik`, `#physik`, `#chemie`, `#biologie`, `#französisch`, `#daz`, `#geschichte`, `#geographie`, `#ethik`
> **Struktur-Hinweis:** In den Foren werden **Pflicht-Tags** eingerichtet (z. B. `[E-Phase]`, `[Jg 11]`, `[Jg 12]`, `[LK]`, `[GK]`, `[Zusammenfassung]`, `[Klausur-Tipps]`). 

### 🔒 INTERNER BEREICH
*(Unsichtbar für normale Lernende)*
- `#mod-admin-intern` – Für technische und moderative Abstimmungen.
- `#schülerrat-intern` – Geschützter Raum für die schulpolitische Arbeit des Schülerrats.

---

## 🚪 3. Das automatisierte Onboarding

Dieses Menü wird über die Discord-Einstellungen ("Community-Onboarding") konfiguriert. Es weist neuen Lernenden beim Betreten des Servers vollautomatisch die richtigen Rollen zu.

1. **In welcher Phase befindest du dich?** *(Pflichtfrage, 1 Antwort)*
   - E-Phase (Einführungsphase) ➔ *Vergibt Rolle: @E-Phase*
   - Jahrgang 11 (Kursphase) ➔ *Vergibt Rolle: @Jahrgang 11*
   - Jahrgang 12 (Kursphase) ➔ *Vergibt Rolle: @Jahrgang 12*
2. **Welche Stammklasse besuchst du?** *(Pflichtfrage, 1 Antwort)*
   - Auswahlmöglichkeiten der Klassen (z. B. E1, E2...). ➔ *Vergibt entsprechende Klassen-Rollen.*
3. **Welche Leistungskurse (LK) belegst du?** *(Optional für E-Phase, Mehrfachauswahl)*
   - Auswahl aller LKs (Deutsch, Mathe, etc.). ➔ *Vergibt LK-Rollen.*
4. **Welche Grundkurse (GK) belegst du?** *(Optional für E-Phase, Mehrfachauswahl)*
   - Auswahl aller GKs. ➔ *Vergibt GK-Rollen.*

---

## ⚖️ 4. Das Regelwerk (Regel-Überprüfung / Rule Screening)

Bevor Lernende den Server betreten können, müssen sie in einem Pop-up diesen Regeln per Checkbox zustimmen:

- **§1 Inoffizieller Server & Haftungsausschluss:** Dieser Server wird privat verwaltet und ist kein offizielles Angebot des AGY Dresden. Alle Infos (auch zu BAföG und Sozialleistungen) sind von Lernenden gesammelt und ohne Gewähr.
- **§2 Respektvolles Miteinander:** Wir begegnen uns auf Augenhöhe. Diskriminierung, Rassismus, Sexismus, Mobbing oder toxisches Verhalten führen zum sofortigen Ausschluss.
- **§3 Datenschutz:** Es besteht keine Klarnamen-Pflicht. Das Teilen von privaten Daten (Adressen, Nummern, private Profile) von Mitlernenden oder Lehrkräften ist strengstens verboten.
- **§4 Urheberrecht:** Das Teilen von offiziellen, benoteten Klassenarbeiten (inkl. Korrekturen der Lehrkräfte) und geschützten Buchseiten ist untersagt. Erlaubt und erwünscht sind: Eigene Zusammenfassungen, Mitschriften, selbst erstellte Lernzettel und Gedächtnisprotokolle.
- **§5 Struktur bewahren:** Bitte nutzt für Lerninhalte die entsprechenden Foren und markiert eure Beiträge mit den passenden Tags (z. B. E-Phase, Zusammenfassung), damit alle Lernenden schnell finden, was sie suchen.

---

## 📝 5. Blaupause für den `#start-hier` Kanal

*Dieser Text wird als feste, angepinnte Nachricht im Info-Kanal platziert:*

> **Willkommen auf dem inoffiziellen AGY Discord! 👋**  
> Dieser Server ist von Lernenden für Lernende, um sich auszutauschen und Lernzettel zentral zu sammeln. 
> 
> ---
> 
> **🧭 Wegweiser:**
> * **#allgemein:** Hier könnt ihr euch jahrgangsübergreifend unterhalten, Smalltalk führen und schnelle Fragen stellen. Anliegen an den Schülerrat könnt ihr hier direkt posten (einfach `@Schülerrat` markieren).
> * **#bafög-und-soziales:** Hilfreiche Tipps zur Finanzierung und Unterstützung.
> * **📚 Der Lernbereich:** Hier gibt es für jedes Schulfach einen eigenen Kanal. Das sind allerdings keine normalen Text-Chats, sondern **Foren**.
> 
> ---
> 
> **💡 Wie funktionieren die Lern-Foren? (Bitte unbedingt lesen!)**  
> Foren sind wie ein digitales schwarzes Brett. Sie verhindern, dass wichtige Dateien in einem langen Chat-Verlauf untergehen.
> 
> * **Material finden (Filtern):** Ihr sucht Mathe-Lernzettel für die E-Phase? Geht in das Forum `#mathematik` und klickt oben auf das kleine Such- oder Tag-Symbol. Wählt den Tag `[E-Phase]` aus. Schwupps – der Server zeigt euch *nur* noch relevante Beiträge für eure Stufe an.
> * **Neues Material hochladen:** Klickt auf "Neuer Beitrag". Gebt eurem Post einen klaren, aussagekräftigen Titel (z. B. *"Zusammenfassung Zellbiologie Bio LK"*). 
> * **🏷️ Tags (Etiketten) sind Pflicht:** Bevor ihr den Beitrag absenden könnt, **müsst** ihr passende Tags auswählen. Wählt aus, für wen das Material ist (z. B. `[Jg 12]`, `[LK]`) und was es ist (z. B. `[Zusammenfassung]`, `[Klausur-Tipps]`). Ohne Tags entsteht Chaos!
> * **Fragen zum Material:** Wenn ihr eine Frage zu einer bestimmten Zusammenfassung habt, klickt auf den Beitrag und schreibt eure Frage dort hinein. So entsteht ein eigener, kleiner Chat nur für dieses eine Thema, ohne andere zu stören.
> 
> ---
> 
> **👥 Das Team:**
> * **@Admin / @Moderation:** Eure Ansprechpersonen bei technischen Problemen, Fehlern oder Regelverstößen.
> * **@Schülerrat:** Eure offizielle Vertretung bei schulischen und organisatorischen Anliegen.
> 
> ---
> 
> **🔗 Wichtige Links für den Schulalltag:**
> * [Website AGY Dresden](https://Beispiel-Link.de)
> * [LernSax / Schul-Cloud](https://Beispiel-Link.de)
> * [Vertretungsplan](https://Beispiel-Link.de)
> * [Offizielles BAföG-Portal](https://Beispiel-Link.de)
