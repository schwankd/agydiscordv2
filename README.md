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
| **@Moderator** | Orange (Sichtbar) | Nachrichten löschen, User verwarnen/kicken, Chat-Pflege. |
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

## 📖 6. Begriffserklärung (Glossar)

Für alle, die Discord bisher nicht genutzt haben oder sich mit den Begriffen noch schwertun, hier eine kurze Übersetzung der wichtigsten Funktionen:

*   **Server:** Unser digitaler Treffpunkt. Man kann es sich wie das gesamte Schulgebäude des AGY im Internet vorstellen.
*   **Kanal (Channel):** Ein einzelner Raum innerhalb unseres Servers. Es gibt **Textkanäle** (wie ein virtuelles Klassenzimmer, in dem alle chatten) und **Foren**.
*   **Forum:** Ein spezieller Kanal, der nicht für wilde Chats gedacht ist, sondern wie ein digitales, gut sortiertes schwarzes Brett funktioniert. Perfekt, um Lernzettel und Zusammenfassungen hochzuladen, ohne dass sie im Chat-Verlauf verschwinden.
*   **Tag (Etikett):** Ein Schlagwort, das man an seinen Foren-Beitrag heften muss (z. B. `[E-Phase]` oder `[Klausur]`). Dadurch können andere Lernende das Forum filtern und finden sofort, was sie suchen.
*   **Rolle:** Ein virtuelles Namensschild oder eine Mitgliedschaft (z. B. `@E-Phase` oder `@Lernende`). Rollen legen fest, welche Farbe dein Name hat, welche Kanäle du sehen kannst und welche Rechte du besitzt.
*   **Onboarding:** Der Fragebogen, der direkt aufploppt, wenn man den Server zum ersten Mal betritt. Hier klickt man seine Fächer und Stufe an, damit der Server sich automatisch für einen einrichtet.
*   **Pingen / Erwähnen (@):** Wenn man ein `@` vor einen Namen oder eine Rolle setzt (z. B. `@Schülerrat`), bekommen diese Personen eine direkte Benachrichtigung auf ihr Handy/PC. Bitte sparsam verwenden!

---

## ❓ 7. FAQ (Häufig gestellte Fragen)

**Warum nutzen wir Discord und nicht einfach eine WhatsApp-Gruppe?**
WhatsApp-Gruppen werden bei mehr als 20 Leuten extrem unübersichtlich. Dokumente gehen unter, neue Mitglieder können alte Nachrichten nicht lesen und man muss seine private Handynummer preisgeben. Discord schützt unsere Privatsphäre und durch die Foren-Struktur ist alles perfekt geordnet nach Fächern und Jahrgängen auffindbar.

**Ist dieser Server offiziell vom AGY Dresden?**
Nein. Dieser Server ist ein reines "Von Lernenden für Lernende"-Projekt. Er wird unabhängig von der Schulleitung betrieben. Deshalb gilt auch bei Infos (wie z. B. zu BAföG) immer: Keine Gewähr.

**Muss ich meinen echten Namen angeben?**
Auf keinen Fall. Datenschutz steht an erster Stelle. Es reicht völlig, wenn du deinen Vornamen oder einen Nicknamen nutzt. Hauptsache, wir gehen respektvoll miteinander um.

**Können Lehrkräfte sehen, was ich hier hochlade oder schreibe?**
Nein. Der Server ist ein Safespace für uns Lernende. Es haben nur Personen Zutritt, die den Einladungslink besitzen, und wir passen gemeinsam auf, dass der Server ein Ort unter uns bleibt.

**Was passiert, wenn ich beim Onboarding aus Versehen die falschen Kurse angeklickt habe?**
Gar kein Problem! Du kannst deine Antworten jederzeit ändern. Klicke dazu am PC oder am Handy einfach oben links auf den Servernamen ("AGY Discord") und wähle im Menü "Kanäle & Rollen" (oder "Linked Roles"). Dort kannst du deine Fächer neu zusammenstellen.

**Darf ich meine benotete Klassenarbeit abfotografieren und teilen?**
Nein, offizielle, vom Lehrer gestempelte und korrigierte Klausuren unterliegen dem Urheberrecht. Was du aber immer machen darfst: Die Aufgaben aus dem Kopf in ein Textdokument abtippen (Gedächtnisprotokoll) oder deine eigenen, selbst geschriebenen Lernzettel und Hausaufgaben teilen!

**Ich verstehe die Foren immer noch nicht – was jetzt?**
Keine Panik! Komm einfach in den `#allgemein` Chat und frag nach Hilfe. Es ist immer jemand da, der dir kurz erklärt, wie du etwas hochladen oder finden kannst. Wir helfen uns gegenseitig!

---
> **🤖 Hinweis zur Entstehung:** 
> Die Struktur, Ausformulierung und Formatierung dieses Konzepts wurden zur besseren Übersichtlichkeit mit Unterstützung von Künstlicher Intelligenz (KI) ausgearbeitet. Die grundlegenden Ideen, Anforderungen und Entscheidungen stammen jedoch zu 100 % von den Lernenden und wurden manuell geprüft.
---
