# Mitmach-Lotse — Web-Version (Prototyp)

Browserbasierte Variante von Mitmach-Lotse: Daten eingeben, Planungsmappe
(`.plf`) lokal öffnen/speichern und die automatische Zuteilung laufen lassen —
**ohne Server-Datenhaltung**. Der Webserver liefert nur den Programmcode aus;
alle Daten bleiben im Browser bzw. in der lokal gespeicherten Datei.

## Starten

Die Seite muss aus dem **Repository-Wurzelverzeichnis** ausgeliefert werden
(der Solver holt die Python-Module `database.py`, `algorithmen.py`,
`_zuteilungsplaner.py`, `_mcmf.py` per `fetch` aus `../`):

```bash
cd mitmachlotse           # Repo-Root
python3 -m http.server 8000
# dann im Browser: http://localhost:8000/web/
```

Internetzugang wird beim Start (sql.js von CDN) und beim ersten
Zuteilungslauf (Pyodide von CDN, ~10 MB) benötigt. Danach cached der Browser.

## Architektur

| Datei | Aufgabe |
|---|---|
| `index.html` / `style.css` | Oberfläche (drei Tabs, an die Desktop-Optik angelehnt), Dialoge, Druck-Stylesheet |
| `js/app.js` | UI-Logik: Tabellen, Datei-Öffnen/Speichern, Bezeichnungen-Dialog, Verkabelung |
| `js/db.js` | SQLite im Browser (sql.js); **1:1 das Desktop-Schema inkl. Spalten-Migrationen** für ältere Dateien → `.plf` ist mit der Desktop-App austauschbar; Label-Grammatik (`labelFormen`) |
| `js/solver.js` | Lädt Pyodide **lazy** (erst beim Klick auf „Automatisch zuweisen") und führt die **unveränderten** Desktop-Algorithmen aus |
| `js/kontext.js` | Kontext-Schicht: Nutzer/Rolle/Gruppen — heute „lokal, ohne Anmeldung", vorbereitet für Server-Login und Moodle/LTI |
| `js/csv.js` | Einfacher CSV-Export |
| `js/importcsv.js` / `js/importdialog.js` | Import mit Spaltenzuordnung (Auto-Erkennung, Vorschau, Anhängen/Ersetzen) |
| `js/assistenten.js` | Mehrstufige Assistenten: Einrichtung (nach „Neue Planungsmappe") und Tabellen-Export-/Importworkflow — Web-Gegenstücke zu `EinrichtungsassistentDialog`/`TabellenAssistentDialog` |
| `js/tabellendatei.js` | Liest CSV direkt; xlsx/xls/ods über SheetJS (lazy vom CDN, erst bei Bedarf) |
| `js/quali.js` | Qualitätsprüfung der Wunscheingaben (4 Kategorien wie Desktop) |
| `js/druck.js` | Druck-Listen (Gesamtliste nach Optionen/Gruppen, Einzellisten, Raumplan) über den Browser-Druckdialog — dort auch „Als PDF speichern" |
| `js/raumplan.js` | Raumplan-Tab: Raumliste, Zuordnung mit Konfliktprüfung/Erzwingen-Rückfrage; automatische Raumzuteilung führt das **unveränderte** `raumzuteilung.py` via Pyodide aus |

### Warum Pyodide für den Solver?

`_mcmf.py` (Min-Cost-Max-Flow) ist korrektheitskritisch und in der Desktop-App
gründlich getestet. Statt ihn nach JavaScript zu portieren (Risiko subtiler
Fehler, doppelte Pflege), laufen exakt dieselben Dateien im Browser: Die
aktuellen DB-Bytes werden ins Pyodide-Dateisystem geschrieben, `db.DB_PATH`
darauf gesetzt, `algorithmus_a/b/c` + `apply_ergebnis` unverändert ausgeführt
und die geänderten Bytes zurückgelesen. **Eine Quelle der Wahrheit.**

### Kontext-Schicht (wichtig für spätere Ausbaustufen)

Die UI fragt Rechte nie direkt ab, sondern immer über `Kontext` in
`kontext.js` (`darfTeilnehmerSehen`, `darfZuteilen`, …). Heute liefert die
Betriebsart „lokal" überall `true`. Später kann der Kontext aus drei Quellen
befüllt werden, ohne die App umzubauen:

1. **lokal** — heutiger Zustand, kein Login
2. **server** — eigener Server mit Nutzerverwaltung
3. **lti** — Start aus Moodle (LTI 1.3): Nutzer, Rolle und Gruppen kommen
   fertig aus dem signierten Launch

„Kein Login" ist also bewusst **nicht** fest verdrahtet.

## Was der Prototyp kann

- Neue Planungsmappe anlegen, `.plf`/`.db` öffnen und speichern
  (Chrome/Edge: direkt in die Datei; Firefox/Safari: über den Download-Ordner);
  ältere Desktop-Dateien werden beim Öffnen automatisch migriert
- **Beispieldaten ausprobieren** (ein Klick lädt die Beispiel-Planungsmappe)
- Teilnehmer/innen und Optionen anlegen, bearbeiten, löschen, suchen
- **Bezeichnungen anpassen** (Angebots-/Gruppenbegriffe, Leitungsspalte,
  Anzahl Wunschränge, bis zu je drei benannte **Zusatzfelder** für
  Teilnehmer/innen und Optionen) — mit Grammatikanpassung (Fugen-s, Plural) und
  Datenschutz-Löschung beim Deaktivieren der Leitungsspalte, wie am Desktop.
  Benannte Zusatzfelder erscheinen als eigene Spalten in den Tabellen, im
  Import (Auto-Zuordnung bei Namensgleichheit) und im CSV-Export
- **Import (CSV, xlsx, xls, ods)** für Teilnehmer/innen, Optionen und Räume:
  Spaltenzuordnung mit Auto-Erkennung (inkl. „Ganzer Name"- und „Klasse
  kombiniert"-Aufteilung), Vorschau, Anhängen/Ersetzen, Excel-tolerante
  Zahlen („1.0"), UTF-8/Windows-1252-Erkennung; kollidierende oder fehlende
  Optionsnummern werden automatisch weitergezählt. Excel-/ODS-Dateien liest
  SheetJS (wird erst bei Bedarf geladen). Beim Teilnehmer-Import können
  **mehrere Dateien auf einmal** gewählt werden — sie werden anhand der
  Spaltennamen zusammengeführt (Reihenfolge der ersten Datei maßgeblich),
  auch bei gemischten Formaten und Trennzeichen
- Automatische Zuteilung mit Algorithmus A/B/C, Zuweisung aufheben,
  Fixierungen (werden vom Algorithmus respektiert — derselbe Code wie Desktop)
- **Qualitätsprüfung** der Wunscheingaben (Unzulässig/Unvollständig/Keine/
  Mehrfach — dieselben Kategorien wie am Desktop)
- **Listen & Druck**: Gesamtliste nach Optionen oder Gruppen sowie
  Einzellisten je Option über den Browser-Druckdialog (dort „Als PDF
  speichern" wählen) — mit Seitenumbruch je Gruppe und **Feldauswahl vor
  jedem Druck** (Spalten an-/abwählbar, „Alle"/„Keine")
- **Raumplan**: Raumliste (Name/Kapazität/Beschreibung) mit
  **CSV-Import/-Export** (Exportdatei passt beim Reimport automatisch ins
  Zuordnungsfenster), Raum- und Zeitzuordnung je Option mit Konfliktprüfung
  (Doppelbelegung rot, Kapazität orange) und „Mehrfachbelegung
  erzwingen?"-Rückfrage wie am Desktop; **Fix**-Spalte schützt Zuordnungen;
  **automatische Raumzuteilung** über das unveränderte Desktop-Modul
  `raumzuteilung.py` (Pyodide), „Raumzuteilung aufheben", Raumplan drucken
- **Nachbearbeitungsmodus**: hält den Zuteilungsstand als Basis fest;
  Umverteilungen erscheinen in der Teilnehmertabelle (gelbe Zelle,
  „vorher: N" durchgestrichen), in der automatischen **Übersicht der
  Änderungen** (Vorher/Jetzt/Wunschrang) und in den gedruckten
  Gruppenlisten (Neuzugänge gelb mit Herkunft, Abgänge durchgestrichen
  am Gruppenende). Der Modus wird mit der `.plf` gespeichert und ist mit
  der Desktop-App austauschbar; Ausschalten macht den Stand endgültig fest
- Wunschstatistik, Belegungsübersicht, CSV-Export der Gesamtliste
- **Mehrstufiger Einrichtungsassistent** nach „Neue Planungsmappe": Willkommen
  (mit Auswahl Assistent / sofort mit Standardwerten / bestehende Mappe öffnen)
  → Bezeichnungen → Optionen-Import → Teilnehmer-Import, mit
  Zurück/Weiter/Überspringen/Fertig — Gegenstück zum
  `EinrichtungsassistentDialog` der Desktop-App
- **Tabellen-Export-/Importassistent** („Tabellen-Assistent …"): führt in fünf
  Schritten durch den Weg „Tabellen extern ausfüllen lassen" (einrichten →
  exportieren → extern ausfüllen → reimportieren), öffnet an den passenden
  Stellen die bestehenden Dialoge und exportiert im Exportschritt eine
  **Wunschlisten-Vorlage** (wahlweise je Gruppe eine eigene Datei)

## Was (noch) fehlt

- Zusatzfelder erscheinen bisher in den Tabellen, im Import und im CSV-Export,
  aber noch nicht in den gedruckten Gruppenlisten
- Weitere Komfort-Randthemen des Desktop-Funktionsumfangs
