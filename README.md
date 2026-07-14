# Mitmach-Lotse

Verwaltung und Zuteilung von Teilnehmer/innen zu Optionen, Projekten, Workshops, Kursen
oder ähnlichen Gruppenveranstaltungen — für Schulen, Ferienprogramme, Vereine und mehr.

Alle zentralen Bezeichnungen sind frei konfigurierbar. Die App passt sich vollständig
an den jeweiligen Kontext an, inklusive Grammatikanpassung aller Buttons, Menüs und Dialoge.

---

## Schnellstart

```bash
pip install PyQt6 openpyxl odfpy
python3 mitmachlotse.py
```

---

## Aufbau der Oberfläche

### Hauptfenster — vier Tabs

Oberhalb der Tabs liegt eine globale **Suchleiste** (`Strg+F`): Eingabe
durchsucht die Teilnehmer/innen-Tabelle spaltenübergreifend und markiert
Treffer, `▲ Zurück` / `▼ Weiter` (oder Eingabetaste) springt zum
vorherigen/nächsten Treffer, `Esc` leert das Feld und setzt den Fokus
zurück auf die Tabelle. Eine Sucheingabe schaltet automatisch auf Tab 1 um.

**Tab 1 – Teilnehmer/innen**
Tabellarische Verwaltung aller Teilnehmer/innen. Spalten: Name, Gruppenbereich,
Gruppenzusatz, Wünsche 1–n (konfigurierbare Anzahl), aktuelle Zuteilung, Fixiert.
Buttons: `+ Hinzufügen`, `✗ Zeile löschen`, `[Begriff] fix zuweisen`, `✗ Fixierung aufheben`.
Beim Bearbeiten eines Wunschfelds (Wert eintippen, dann Tab) rückt die
Markierung genau ein Feld weiter (W1 → W2 → … → Wn); bei reiner Navigation
ohne Bearbeitung springt Tab von Wn zur ersten Wunschspalte der nächsten
Zeile. Wunsch-Änderungen werden sofort gespeichert, lösen aber **kein**
Neuladen/Neusortieren aus, damit die Eingabe mehrerer Wünsche hintereinander
flüssig bleibt. Nur bei Änderungen an Name, Gruppenbereich oder
Gruppenzusatz wird die Tabelle automatisch neu sortiert; der bearbeitete
Eintrag bleibt dabei markiert.

**Tab 2 – Optionen** *(Bezeichnung konfigurierbar)*
Verwaltung aller Angebote: Nr., Leitung/Ansprechperson (optional), Optionsname,
optionale Zusatzfelder, Gruppenbereich min/max, Plätze min/max.
Buttons: `+ Option hinzufügen`, `✗ Zeile löschen`, `Exportieren`, `Drucken`,
`Druckvorschau`.

**Tab 3 – Raumplan**
Räumliche und zeitliche Organisation der Optionen.
- **Raumliste** (oben): Räume mit Name, **Kapazität** und Beschreibung anlegen
  (`+ Raum hinzufügen` / `✗ Raum löschen`, Autospeicherung wie überall).
  `Strg+N` legt hier einen Raum an, `Entf` löscht den markierten Raum (nur bei
  Fokus auf der Raumliste). Buttons `Raumliste importieren` / `Raumliste
  exportieren` erlauben den Austausch als CSV/xlsx/ods; die Exportdatei
  (Spalten „Raumname", „Kapazität", „Beschreibung") passt beim Reimport
  automatisch ins Spaltenzuordnungsfenster.
- **Raumzuordnung** (unten): je Option ein **Raum** (Auswahlliste) und eine
  **Zeit** zuordnen. Angezeigt werden zusätzlich Plätze max und aktuelle
  Belegung. Ein Raum gilt für zwei Optionen nur dann als unkritisch, wenn
  **beide** eine Zeit eingetragen haben **und** sich diese unterscheiden.
  Andernfalls fragt die App beim Zuordnen nach: „Der Raum … ist bereits
  Option … zugeordnet. Möchten Sie eine Mehrfachbelegung erzwingen?" — bei
  **Nein** springt die Auswahl zurück (nichts wird geändert), bei **Ja** wird
  die Mehrfachbelegung bewusst gespeichert. Die Hinweisspalte markiert sie
  dann (wie jeden Konflikt) rot bei **Doppelbelegung** bzw. orange bei
  **Kapazitätsproblemen** (Raum kleiner als Belegung bzw. als die geplanten
  Plätze); dieselben Hinweise greifen auch, wenn ein Konflikt bereits in
  importierten oder älteren Daten steckt. Buttons `Exportieren`, `Drucken`,
  `Druckvorschau` erzeugen einen fertigen Raumplan (mit Feldauswahl, s. u.).
- **Räume automatisch zuweisen**: verteilt die Räume automatisch auf die
  Optionen. Gruppiert nach der eingetragenen **Zeit** (gleiche Zeit = verschiedene
  Räume, verschiedene Zeiten dürfen denselben Raum nutzen) und wählt je Option
  den kleinsten ausreichend großen freien Raum. Als **Bedarf** gilt die aktuelle
  Belegung, sonst die geplanten Plätze (max). Reicht kein Raum, erscheint ein
  Hinweis (keine harte Sperre). Voraussetzung: Zeiten sind eingetragen (Zeiten
  werden nicht automatisch vergeben). Die Spalte **Fix** hält eine Raumzuordnung
  fest – solche Zuordnungen lässt die Automatik unangetastet und plant um sie
  herum. `Raumzuteilung aufheben` entfernt alle nicht fixierten Raumzuordnungen.

**Tab 4 – Auswertung, Nachbearbeitung, Export**

Dieser Tab bündelt alle Auswertungs- und Exportfunktionen:

- **Wunschstatistik** (oben): wie viele TN haben Wunsch 1 / 2 / … / keinen Wunsch
  erhalten, mit Prozentwerten (Basis: zugeteilte TN). Daneben Button
  „Qualitätsprüfung Wunscheingaben".
- **Export-Buttons**: „Gesamtliste nach Gruppen exportieren" und
  „Gesamtliste nach Optionen exportieren" — dieselbe Funktion wie im Menü.
- **AktionButtons für markierte Option**: „Wunschauswertungsliste zu markierter Option",
  „Teilnehmerliste zur markierten Option", „Gruppenliste mit Zuteilung",
  „Wunschdetails zu markierter Option" — werden aktiviert sobald eine Option
  in der Tabelle markiert ist.
- **Optionstabelle**: Nr., Optionsname, Plätze min/max, aktuell zugeteilt.
  Doppelklick öffnet die Teilnehmerliste zur Option.
- **Disketten-Icon** rechts in der Statusleiste blinkt nach jeder Änderung auf.
  Alle Änderungen werden automatisch sofort gespeichert (SQLite).

---

### Listenfenster

Listenfenster sind **nicht-modal** — mehrere können gleichzeitig offen sein.
Verfügbar über das Menü **Auswertung/Export** oder die Buttons im Tab
„Auswertung, Nachbearbeitung, Export":

| Listenfenster | Kürzel | Inhalt |
|---|---|---|
| **Wunschauswertungsliste nach Option** | `Strg+Shift+W` | Wer hat welche Option mit welchem Rang gewählt? Filterbar. |
| **Teilnehmerliste nach Option** | `Strg+Shift+P` | Alle einer Option zugeteilten TN. |
| **Gruppenliste mit Zuteilung** | `Strg+Shift+K` | Zuteilungen nach Gruppe sortiert. |
| **Qualitätsprüfung Wunscheingaben** | `Strg+Shift+Q` | Vier Kategorien von Eingabeproblemen. |

Alle Listenfenster bieten: Exportieren, Drucken, Druckvorschau.
Listenfenster mit gefilterter Option zeigen zusätzlich „[Begriff] fix zuweisen"
und „Wunschdetails zu dieser Option".

Gesamtlisten-Export: nach Gruppen oder nach Optionen, mit Optionen für Kopfzeile,
Wünsche, Seitenumbrüche, Datum in der Fußzeile (PDF/xlsx), Einzeldateien als ZIP
oder direkt in Ordner.

---

### Wunschdetailfenster

Das **Wunschdetailfenster** öffnet sich aus dem Auswertungs-Tab (Button
„Wunschdetails") oder aus einem Listenfenster, wenn eine konkrete Option gefiltert ist.

Es zeigt für eine einzelne Option:
- Wie oft wurde sie gewünscht (nach Wunschrang 1–n aufgeteilt)?
- Mit welchem Wunschrang wurden die zugeteilten TN zugeteilt?
- Plätze min/max und aktuelle Belegung.
- Button „Wunschauswertungsliste zu dieser Option".

Doppelklick auf eine Zeile öffnet die gefilterte Wunschauswertungsliste direkt.

---

### Qualitätsprüfungsfenster

Unter **Auswertung/Export → Qualitätsprüfung Wunscheingaben** (`Strg+Shift+Q`)
oder über den Button im Auswertungs-Tab. Zeigt vier Kategorien:

- **⚠ Unzulässig**: Optionen außerhalb des erlaubten Stufenbereichs gewählt.
- **✎ Unvollständig**: Weniger als die konfigurierte Anzahl Wunschränge ausgefüllt.
- **○ Keine Wünsche**: Alle Felder = 0 — Person bleibt unzugeteilt.
- **↻ Mehrfach**: Dieselbe Option mehrmals eingetragen. *Kann bewusst sein*,
  um Teilnehmer/innen gezielt in bestimmte Optionen einzuplanen
  (z. B. auf Wunsch von Gruppenverantwortlichen). Daher möglicherweise
  nur optionale Hinweise, keine Fehler.

Die Tabelle zeigt Name, Gruppe, alle Wunschränge (als Nummern) und Details.
**Pro Person nur eine Zeile je Kategorie**: Treten bei einer Person mehrere
Probleme derselben Kategorie auf (z. B. zwei unzulässige Wünsche), werden
diese in einer einzigen Zeile zusammengefasst; die Details-Spalte listet
alle betroffenen Wunschränge auf. Die konkret betroffenen Wunschfelder sind
zusätzlich mit ⚠ markiert (z. B. „24 ⚠") — analog zur Markierung, die auch
bei der Zulässigkeitsprüfung direkt nach dem Import erscheint. Bei „Keine
Wünsche" sind alle Wunschfelder mit ⚠ markiert, da hier jedes einzelne
Feld betroffen ist.
Doppelklick springt zur Person im Hauptfenster (bleibt dabei offen).
Export und Drucken direkt aus dem Fenster.

---

## Feldauswahl beim Drucken und Exportieren

Vor **jedem** Ausdruck und **jedem** Dateiexport – Optionen, Raumplan,
Gesamtlisten, Listenfenster und Qualitätsprüfung – erscheint eine
**Feldauswahl**: eine Liste aller Spalten (standardmäßig alle angehakt), mit
`Alle` / `Keine` als Schnellschalter. So lässt sich der Druckbereich bzw. der
Dateiinhalt pro Ausgabe frei zusammenstellen. Wer alles möchte, bestätigt
einfach mit `OK`. Die Auswahl wirkt gleichermaßen für PDF, Excel (.xlsx),
OpenDocument (.ods), CSV und den direkten Ausdruck.

## Vorkonfigurierte Speicherorte (u. a. Nextcloud/WebDAV)

Unter **Datei → Speicherorte verwalten** lassen sich benannte Ziel-Ordner
hinterlegen. Sie erscheinen anschließend beim Exportieren in der **Seitenleiste
des Speichern-Dialogs** – für schnellen Zugriff, ohne sich durch den
Verzeichnisbaum zu klicken. Für **Nextcloud/WebDAV** wird der lokal
eingebundene Ordner eingetragen (Nextcloud-Desktop-Client oder eine
Betriebssystem-Einbindung via `davs://`); ein direkter Upload mit Zugangsdaten
findet bewusst nicht statt (keine Passwortspeicherung, keine zusätzlichen
Abhängigkeiten).

---

## Automatische Zuteilung — drei Algorithmen

Alle drei Algorithmen basieren auf **Min-Cost-Flow (MCMF)**, einem mathematischen
Optimierungsverfahren. Garantien für alle drei:

- **Kapazitätsgrenzen (Plätze max) werden niemals überschritten** — harte Grenze
- **Niemals ungewünschte Optionen** — nur tatsächlich gewählte Wünsche
- **Mathematisch maximale Versorgungsrate** — beweisbar optimal
- **Laufzeit** < 1 Sekunde für 500 TN / 30 Optionen

**Algorithmus A** — Wunsch-Priorisierung (W1 vor W2 usw.), leichte Mindest-TN-Stütze.
**Algorithmus B** — Mindest-Teilnehmerzahl zuverlässig erreichen, Wünsche zweitrangig.
**Algorithmus C** — Alle versorgen (empfohlen als Standard).

Soft-Kriterien: Gruppenkohäsion (gleiche Stufe + Zusatz) und Freundeserkennung
(identische Wunschliste) werden bei Engpässen leicht bevorzugt.

---

## Beispieldaten ausprobieren

Unter **Hilfe → Beispieldaten ausprobieren** lässt sich die App unverbindlich
ausprobieren, ohne eigene Daten anzulegen:

- **Beispiel-Planungsmappe öffnen** (ausgefüllt, bereit zum Zuteilen) — öffnet
  eine temporäre Kopie einer fertig eingerichteten Beispielmappe inkl. Optionen
  und Teilnehmer/innen, direkt bereit für einen Algorithmus-Testlauf. Wer das
  Beispiel dauerhaft behalten möchte, nutzt anschließend „Planungsmappe
  speichern als".
- **Beispiel-Teilnehmerliste importieren** / **Beispiel-Optionsliste
  importieren** — importiert direkt (nicht exportiert) eine Beispieldatei in
  die aktuell geöffnete Planungsmappe über das gewohnte
  Spaltenzuordnungsfenster, um den Import-Workflow selbst auszuprobieren.

---

## Einrichtungsassistent für neue Planungsmappen

Bei einer leeren Planungsmappe (Neuanlage oder erster Start) öffnet sich
automatisch ein Einrichtungsassistent. Die Willkommensseite gibt einen
kurzen Überblick, was mit Mitmach-Lotse alles möglich ist (automatische
Zuteilung per Algorithmus, Export/Import-Workflow für externe Bearbeitung,
Qualitätsprüfung, frei konfigurierbare Begriffe u. a.), bevor zwischen
geführtem Assistenten, Standardbezeichnungen oder dem Laden einer
bestehenden Planungsmappe gewählt wird.

---

## Konfigurierbare Bezeichnungen

Unter **Datei → Spaltenbezeichnungen anpassen** (`Strg+B`):

- **Gruppenbereich** (z. B. „Jgst.", „Klasse", „Jahrgang")
- **Gruppenzusatz** (z. B. „Klassenzusatz", „Untergruppe")
- **Optionsbezeichnung** (z. B. „Option", „Projekt", „Kurs", „Workshop")
- **Anzahl Wunschränge** (1–5)
- **Optionale Zusatzfelder Teilnehmer/innen** (bis zu 3, leer = ausgeblendet)
- **Veranstaltungsleitung / Ansprechperson** (leer = Spalte ausgeblendet)
- **Optionale Zusatzfelder Optionen** (bis zu 3, leer = ausgeblendet)
- **Optionales Zusatzfeld Raumzuordnung** (leer = Spalte im Raumplan-Tab
  ausgeblendet, z. B. für zusätzliche Angaben wie Gebäude/Stockwerk)

Alle Buttons, Menüs, Dialoge und Listenfenster passen sich automatisch an —
inklusive korrekter Grammatik (Genusanpassung, Fugen-S, Plural, Artikelwahl).

**Datenschutz beim Deaktivieren der Leitungsspalte**: Wird die Bezeichnung
für „Veranstaltungsleitung / Ansprechperson" geleert (Spalte damit
ausgeblendet), erscheint zuerst eine Sicherheitsabfrage. Bei Zustimmung
werden die bisher eingetragenen Namen **vollständig aus der Datenbank
gelöscht**, nicht nur ausgeblendet — sie kommen auch bei erneuter
Aktivierung der Spalte nicht zurück und müssten neu eingegeben werden.

---

## Import

Teilnehmer/innen und Optionen können aus **CSV**, **Excel (.xlsx)** und
**OpenDocument (.ods)** importiert werden.

### Spaltenzuordnungsfenster

Beim Import öffnet sich das **Spaltenzuordnungsfenster**:

- **Automatische Zuordnung**: Bekannte Spaltenbezeichnungen (z. B. „Wunsch 1",
  „Klasse", „Name, Vorname") werden automatisch erkannt und vorbelegt.
  Bei „Ganzer Name in einer Spalte" wird dafür die Spaltenbezeichnung
  „Name" erkannt — eindeutig getrennt von „Nachname" (dafür zählt nur
  „Nachname"/„Familienname"/"Last Name"), damit eine Spalte nicht
  versehentlich zwei Feldern gleichzeitig zugeordnet wird.
- **Manuell anpassen**: Jedes App-Feld hat eine Dropdown-Liste mit allen Spalten.
- **CSV**: Trennzeichen wird automatisch erkannt; manuell änderbar.
- **Vorschau in zwei Tabs**:
  - **Einblick Quelldatei** — ungefilterte Rohdatei mit allen Spalten und
    bis zu 50 Zeilen, unabhängig von der aktuellen Zuordnung. Praktisch,
    um sich erst einmal einen Überblick zu verschaffen, was die Datei
    überhaupt enthält.
  - **Vorschau Zieldatei** — Ergebnis-Simulation: zeigt, wie die ersten 5
    Zeilen nach dem Import aussehen würden. Optionale Felder ohne
    Zuordnung (z. B. Leitung) werden ausgeblendet, mit dem Zielfeld-Namen
    als Titel (z. B. „Name" statt „Ganzer Name in einer Spalte
    (Spaltentitel „Name")"). **Pflichtfelder** bleiben dagegen auch ohne
    Zuordnung sichtbar und zeigen den Standardwert, der beim Import
    tatsächlich eingetragen würde: **0** bei Zahlenfeldern, **„-"** bei
    Textfeldern als Hinweis, was dort eigentlich stehen müsste. Bei
    Optionen betrifft das Nummer, Titel und Gruppenbereich/Plätze
    min+max; bei Teilnehmer/innen Name, Gruppenbereich, Gruppenzusatz
    sowie alle konfigurierten Wunschränge — wobei z. B. kein
    Gruppenbereich-Platzhalter erscheint, wenn stattdessen die
    kombinierte Spalte „Gruppenbereich + Gruppenzusatz" zugeordnet ist
    (die deckt beides bereits ab). „Option" und „Fixiert" haben eigene
    Sonderregelungen und bleiben davon unberührt. Die Vorschau
    aktualisiert sich bei jeder Änderung in den Zuordnungs-Dropdowns,
    sodass auch vertauschte Zuordnungen sofort an den angezeigten Werten
    erkennbar sind.
- **Anhängen oder Ersetzen**: Checkbox „Bestehende Daten behalten (anhängen
  statt ersetzen)". Beim Anhängen von Optionen überschreibt eine in der
  Quelldatei vorkommende Nummer nie eine bereits vorhandene Option — bei
  Kollision oder fehlender Nummer wird automatisch fortlaufend
  weiternummeriert.

**Wunschanzahl-Erkennung**: Wenn die Quelldatei eine andere Anzahl Wunschspalten
enthält, erscheint eine Rückfrage — Planungsmappe beibehalten oder anpassen.

**Automatische Titelzeilen-Erkennung**: Steht vor der eigentlichen Kopfzeile
noch eine Zier-/Titelzeile — z. B. weil die Datei mit „Gesamtliste
exportieren" erzeugt wurde und dort Kopfzeile/Gruppenname über der Tabelle
stehen —, wird das beim Import automatisch erkannt und übersprungen. Damit
sind auch für Menschen aufbereitete Exportdateien direkt reimportierbar,
ohne sie vorher manuell bereinigen zu müssen. Bei mehrteiligen Gesamtlisten
(nach Gruppen **oder** nach Optionen) werden zusätzlich die je Abschnitt
**wiederholten Kopfzeilen** und die **Abschnittsüberschriften** (Gruppen- bzw.
Optionsname) mitten im Datenbereich erkannt und übersprungen — sonst
entstünden daraus fehlerhafte Datensätze (etwa ein „Teilnehmer" namens
„1: Holzwerkstatt").

**Qualitätsprüfung nach dem Teilnehmer/innen-Import**: Nach jedem Import
fragt die App, ob die importierten Wunscheingaben geprüft werden sollen.
Bei Zustimmung öffnet sich dasselbe Qualitätsprüfungsfenster wie unter
Auswertung/Export (s. u.) — mit allen vier Kategorien (Zulässigkeit,
Vollständigkeit, Null-Wünsche, Mehrfachnennungen), Filter-Checkboxen und
Warndreieck-Markierung —, jedoch beschränkt auf die gerade importierten
Datensätze.

**Leitungsspalte beim Optionen-Import**: „Leitung" wird im
Spaltenzuordnungsfenster immer als App-Feld angeboten (zwischen Nummer und
Optionsname) — auch wenn sie unter Datei → Spaltenbezeichnungen anpassen
noch nicht aktiviert wurde. Bleibt sie auf „nicht importieren", taucht sie
weder in der Vorschau noch im Import auf. Wird ihr dagegen eine Quellspalte
zugeordnet, während sie in der aktuellen Planungsmappe noch nicht aktiv
ist, fragt die App nach, ob die Spalte jetzt eingerichtet werden soll —
unter Übernahme der Spaltenbezeichnung aus der Quelldatei. Praktisch beim
Import von Optionslisten aus einer anderen Planungsmappe, in der die
Veranstaltungsleitung bereits aktiviert war.

**Zahlenwerte aus Excel/LibreOffice**: Nummern-, Platz- und
Gruppenbereichs-Spalten werden auch dann korrekt erkannt, wenn Excel oder
LibreOffice sie beim Bearbeiten und Speichern in Kommazahlen umgewandelt
haben (z. B. „1.0" statt „1") — vorher führte das beim Optionen-Import
dazu, dass Zeilen ohne Fehlermeldung stillschweigend übersprungen wurden.

### Mehrere Dateien zusammenführen (nur Teilnehmer/innen-Import)

Checkbox **„Mehrere Dateien zusammenführen"** im Import-Dialog für
Teilnehmer/innen: Mehrfachauswahl statt Einzeldatei — praktisch für den
Rückweg des Excel-Workflows, wenn pro Gruppe eine eigene Datei ausgefüllt
zurückgekommen ist. Beim Optionen-Import gibt es diese Checkbox nicht, da
es dort immer nur eine einzige Liste gibt.

- Jede Datei wird zunächst einzeln um Titelzeilen bereinigt (s. o.), dann
  werden die Spalten anhand ihres Namens zusammengeführt (Reihenfolge der
  ersten Datei bleibt maßgeblich), fehlende Spalten werden mit Leerwerten
  aufgefüllt.
- Formate können gemischt sein (.xlsx, .ods, .csv nebeneinander).
- **Abweichungserkennung**: Werte in Gruppenbereich/Gruppenzusatz mit
  Klammerzusatz (z. B. „a (MüS)"), deren Basisform auch in anderen Zeilen
  vorkommt, werden erkannt — mit Rückfrage, ob sie auf die Basisform
  zurückgekürzt werden sollen.
- Danach läuft der Import wie gewohnt über ein einziges
  Spaltenzuordnungsfenster für alle zusammengeführten Zeilen.

---

## Manuelle Zuteilung und Fixierungen

- **fix zuweisen** (`Strg+Shift+F`): manuell einer markierten Person eine Option
  zuweisen. Diese Zuteilung wird durch Algorithmen nicht überschrieben. Aus
  der Teilnehmer/innentabelle und den Listenfenstern heraus zeigt der
  Auswahldialog zunächst nur die von der Person gewählten Wunschoptionen. Ein
  zusätzlicher Eintrag **„Zuteilung zu einer anderen Option erzwingen …"**
  (Formulierung passt sich grammatikalisch an den konfigurierten Begriff an)
  blendet bei Bedarf alle übrigen, nicht gewünschten Optionen mit ein, statt
  die kurze Liste standardmäßig zu überladen.
- **Fixierung aufheben** (`Strg+Shift+R`)
- **Alle fixen Zuweisungen löschen**
- **Automatische Zuweisung aufheben**

---

## Nachbearbeitungsmodus

Über **Einteilung → Bearbeitungsmodus Ein/Aus** lässt sich ein bestimmter
Zuteilungsstand als Ausgangsstand („Basis") festhalten. Solange der Modus aktiv
ist (Hinweis in der Statusleiste), werden alle späteren Umverteilungen sichtbar
gemacht — ohne den Algorithmus oder die Raumzuteilung zu beeinflussen:

- In **Gruppenlisten** (Haupttabelle Teilnehmer/innen, Gruppenliste-Fenster und
  Gesamtliste-Export nach Gruppen) zeigt die Zuteilungsspalte bei geänderten
  Personen die **alte Nummer durchgestrichen → neue Nummer** und ist farblich
  hervorgehoben.
- In den **Teilnehmerlisten einer Option** (sowohl im eigenen Listenfenster
  als auch in der **Gesamtliste-Export nach Optionen**, jeweils gruppenweise)
  wird jede Umverteilung von beiden Seiten sichtbar: Personen, die zur
  Basis-Zeit dort waren, jetzt aber woanders zugeteilt sind, erscheinen
  **durchgestrichen am Ende der Gruppe** als Hinweis („verlassen"); **neu
  hinzugekommene** Personen sind **gelb hervorgehoben** und tragen einen
  Vermerk zu ihrer Herkunft ("… · neu (vorher: N)" bzw. eigene Spalte
  „Änderung" im Gesamtlisten-Export), so dass man sofort sieht, wer neu ist
  und woher er/sie kommt. Nur die durchgestrichenen Abgänge zählen nicht zur
  aktuellen Teilnehmerzahl.
- Über **Einteilung → Übersicht der Änderungen** öffnet sich eine Liste, die
  **alle umverteilten Teilnehmer/innen auf einen Blick** zeigt (Name, Gruppe,
  Vorher, Jetzt, erhaltener Wunschrang) — bequem druck- und exportierbar.

Die Hervorhebung erscheint einheitlich am Bildschirm, im Druck und in allen
Exportformaten (bei CSV mangels Formatierung nur die Durchstreichung als
Textzeichen, ohne Farbe). Der Bearbeitungsmodus wird **mit der Planungsmappe
gespeichert**: Beim erneuten Öffnen der Datei ist er wieder genau im selben
Zustand wie zuvor (inkl. Basis-Stand). **Bearbeitungsmodus Aus** macht den
aktuellen Stand endgültig fest: alle Markierungen und durchgestrichenen
Einträge verschwinden.

---

## Tastaturkürzel

| Kürzel | Funktion |
|---|---|
| `Strg+O` | Planungsmappe öffnen |
| `Strg+Shift+N` | Neue Planungsmappe |
| `Strg+W` | Planungsmappe schließen |
| `Strg+Q` | App schließen |
| `Strg+S` | Speichern bestätigen |
| `Strg+Shift+S` | Speichern als |
| `Strg+B` | Spaltenbezeichnungen anpassen |
| `Strg+F` | Suche fokussieren (springt zu Tab 1) |
| `Esc` | Suche leeren, Fokus zurück zur Tabelle |
| `Strg+1/2/3/4` (auch `Alt+1/2/3/4`) | Zwischen den vier Tabs wechseln (3 = Raumplan, 4 = Auswertung) |
| `Strg+N` | Hinzufügen (Teilnehmer/in oder Option, je nach aktivem Tab) |
| `Strg+I` | Teilnehmer/innen importieren |
| `Strg+Shift+I` | Optionen importieren |
| `Strg+Shift+A/B/C` | Algorithmus A / B / C |
| `Strg+Shift+F` | fix zuweisen |
| `Strg+Shift+R` | Fixierung aufheben |
| `Strg+Shift+W` | Wunschauswertungsliste |
| `Strg+Shift+P` | Teilnehmerliste nach Option |
| `Strg+Shift+K` | Gruppenliste mit Zuteilung |
| `Strg+Shift+Q` | Qualitätsprüfung Wunscheingaben |
| `Entf` | Zeile löschen (aktiver Tab) |
| `F5` | Aktuellen Tab neu laden |
| `F1` | Tastaturkürzel-Übersicht |

---

## Dateiformat

- Primäres Format: `.plf` (Mitmach-Lotse Planning File) — technisch SQLite
- Alternativ als `.db` öffnen/speichern
- **Speichern als** (`Strg+Shift+S`): Kopie unter neuem Namen

---

## Workflow-Tipps

### Geführter Assistent: Tabellen extern ausfüllen lassen

**Datei → Tabellen-Export- und Importassistenten starten** führt in fünf
Schritten (Einführung → Tabellen einrichten → Exportieren → Extern
ausfüllen lassen → Reimportieren) durch genau den Workflow, der unten
unter „Wunscheingabe per Excel oder OpenDocument" beschrieben ist — mit
Erklärtext zu jedem Schritt und Buttons, die direkt die passenden Dialoge
öffnen („Gesamtliste exportieren", „Teilnehmer/innen importieren"). Bei
den Schritten „Tabellen einrichten" und „Exportieren" heißt der
Weiter-Button bewusst „Weiter / Schritt überspringen", da diese Schritte
optional sind, falls schon alles vorbereitet ist. Erwähnt wird im
Assistenten auch das Szenario, Einzeldateien je Gruppe in einem
Zielverzeichnis abzulegen, das über eine Cloud mit Gruppenverantwortlichen
geteilt wird, die dann die Wünsche ihrer Gruppe einsammeln und auf
Zulässigkeit achten. Der Assistent ist bewusst nicht-modal, damit das am
Ende geöffnete Qualitätsprüfungsfenster nicht dahinter verschwindet und
parallel zum Hauptfenster bedienbar bleibt. Empfiehlt sich für alle, die
den Ablauf nicht auswendig kennen oder ihn neuen Kolleg/innen zeigen
möchten.

### Wunscheingabe per Excel oder OpenDocument

1. **Export**: Auswertungs-Tab → „Gesamtliste nach Gruppen exportieren",
   Format **Excel (.xlsx)** oder **OpenDocument (.ods)**, „Jede Gruppe als
   separate Datei" → ZIP oder Ordner. Die Wunschspalten sind dabei immer
   enthalten — welche Spalten in der Ausgabe tatsächlich erscheinen,
   entscheidet die anschließende Feldauswahl (s. o.). Für diesen Rückweg
   (Export → Ausfüllen → Reimport) ist „Seitenumbruch nach jeder Gruppe"
   bereits sinnvoll voreingestellt, „Datum in der Fußzeile" aus. Die
   Kopfzeile (z. B. Veranstaltungsname) bleibt sichtbar und gibt
   ausfüllenden Personen (z. B. Klassenlehrkräften) Orientierung — sie wird
   beim Reimport automatisch erkannt und übersprungen (s. o.).
2. **Ausfüllen**: Wunschspalten werden von Tutoren oder TN eingetragen —
   sowohl .xlsx- als auch .ods-Dateien lassen sich mit Excel, LibreOffice
   Calc oder anderer Tabellenkalkulation bearbeiten
3. **Reimport**: Datei → Teilnehmer/innen importieren, Spaltenzuordnungsfenster
   (funktioniert gleichermaßen für .xlsx, .ods und .csv). Kommen die Dateien
   pro Gruppe einzeln zurück, Checkbox „Mehrere Dateien zusammenführen"
   aktivieren und alle auf einmal auswählen — siehe Abschnitt „Mehrere
   Dateien zusammenführen" oben.

### Optionsliste erstellen

**Direkte Eingabe** im Tab Optionen oder **Import-Export-Workflow**:

1. Export: Tab Optionen → Exportieren (Excel .xlsx oder OpenDocument .ods)
2. Weitergeben zum Ausfüllen (Optionsname, Plätze, ggf. Leitung)
3. Reimport: Datei → Optionen importieren (`Strg+Shift+I`) — akzeptiert
   ebenfalls .xlsx, .ods und .csv

**Veranstaltungsleitung aktivieren**: Datei → Spaltenbezeichnungen anpassen →
„Bezeichnung Leitung / Ansprechperson" ausfüllen (leer = Spalte ausgeblendet).

### Qualitätsprüfung vor Algorithmuslauf

Auswertungs-Tab → „Qualitätsprüfung Wunscheingaben" prüft: unzulässige Wünsche,
unvollständige Eingaben, fehlende Wünsche, Mehrfachnennungen.
Doppelklick springt direkt zur Person im Hauptfenster.

### Gruppenbereich-Werte nach Excel-Import bereinigen

Excel wandelt reine Zahlenspalten (z. B. Jahrgangsstufe „5") gerne in
Kommazahlen um, sodass nach dem Import „5.0" statt „5" in der Tabelle steht.
Solche Werte verhindern eine korrekte automatische Zuteilung, da sie nicht
mehr zum Gruppenbereich einer Option passen. Abhilfe: **Datei →
Gruppenbereich-Werte bereinigen** normalisiert alle betroffenen Einträge
in einem Schritt.

---

## Installation & Build

```bash
pip install PyQt6 openpyxl odfpy
python3 mitmachlotse.py
```

Build-Skripte für Linux (.deb), Windows (.exe), macOS (.dmg) und Flatpak
im Ordner `build_scripts/`.

---

## Dateistruktur

```
mitmachlotse.py          Einstiegspunkt, globales Stylesheet
hauptfenster.py          Hauptfenster (4 Tabs inkl. Raumplan), StatistikWidget, Tabellen
dialoge.py               Alle modalen Dialoge (inkl. Feldauswahl, Speicherorte)
database.py              SQLite-Datenbankschicht (inkl. Räume, Speicherorte), get_label_formen()
algorithmen.py           Algorithmen A/B/C (MCMF-Wrapper)
_mcmf.py                 Min-Cost-Flow (Dijkstra + Johnson-Potentiale)
_zuteilungsplaner.py     MCMF-basierter Zuteilungs-Solver
importexport.py          Import (CSV/xlsx/ods) und Export (xlsx/ods/csv/pdf), Spaltenfilter
listenabfragen.py        DB-Abfragen für Listen- und Qualitätsprüfungsfenster
listenfenster.py         Nicht-modales Listenfenster
validierung.py           Prüfung auf zulässige Wünsche und Raumkonflikte
raumzuteilung.py         Automatische Raumzuteilung (Greedy First-Fit-Decreasing)
build_scripts/           Build-Skripte für alle Plattformen
README.md                Diese Datei
```

---

## Technische Hinweise

- Python ≥ 3.10 erforderlich
- Abhängigkeiten: `PyQt6`, `openpyxl`, `odfpy`
- Keine weiteren externen Abhängigkeiten
- SQLite schreibt alle Änderungen sofort — kein manuelles Speichern nötig
- MCMF-Solver ist reines Python, läuft auf allen Plattformen

---

## Autor

Clemens Arnold (siehe auch Hilfe → Über Mitmach-Lotse in der App)
