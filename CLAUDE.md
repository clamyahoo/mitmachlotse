# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**Mitmach-Lotse** is a German-language PyQt6 desktop app for assigning participants
(students, club members, etc.) to options/projects/workshops based on ranked wishes,
using a min-cost-max-flow optimizer. All UI terminology is runtime-configurable (see
"Configurable labels" below) — the app can be relabeled for schools, holiday programs,
clubs, etc. without touching code.

## Running

```bash
pip install PyQt6 openpyxl odfpy
python3 mitmachlotse.py
```

No test suite, linter, or formatter config exists in this repo — there is nothing to
run beyond starting the app and exercising it manually.

## Building packages

```bash
bash build_scripts/build_linux_deb.sh      # .deb
bash build_scripts/build_windows.bat       # .exe (Windows only)
bash build_scripts/build_macos.sh          # .dmg
```

Details in [build_scripts/README_BUILD.md](build_scripts/README_BUILD.md). The primary
data file format is `.plf` (SQLite under the hood, interchangeable with `.db`).

## Architecture

Flat module layout, no packages. Each file is a layer:

| Module | Responsibility |
|---|---|
| `mitmachlotse.py` | Entry point, `QApplication` setup, global stylesheet |
| `hauptfenster.py` | `MainWindow` (4 tabs incl. Raumplan), `AngebotsTable`/`TeilnehmerTable`/`RaeumeTable`/`RaumplanTable`, `StatistikWidget` |
| `dialoge.py` | All modal dialogs (import wizard, setup wizard, quality-check window, `SpaltenauswahlDialog`, `SpeicherorteDialog`, etc.) — largest file |
| `listenfenster.py` | `ListenFenster` — non-modal list windows (multiple can be open at once) |
| `listenabfragen.py` | Read-only DB queries backing the list/quality-check windows |
| `database.py` | SQLite schema, migrations, CRUD, room CRUD, save-location config, and the configurable-label system |
| `importexport.py` | CSV/xlsx/ods import, xlsx/ods/csv/pdf/html export, column-mapping/merge logic, `filter_spalten` |
| `validierung.py` | Wish-eligibility checks (grade-range validation) and `pruefe_raumkonflikte` |
| `algorithmen.py` | Algorithms A/B/C — build weighted flow networks, wrap `_zuteilungsplaner` |
| `_zuteilungsplaner.py` | Translates participants/projects into an MCMF graph, calls `_mcmf`, extracts assignment |
| `_mcmf.py` | Generic min-cost-max-flow solver (successive shortest paths, Dijkstra + Johnson potentials) |

Layering is strict top-to-bottom: UI (`hauptfenster`/`dialoge`/`listenfenster`) calls
`database`/`listenabfragen`/`importexport`/`validierung`/`algorithmen`; the algorithm
layer calls `_zuteilungsplaner`, which calls the generic `_mcmf` solver. `_mcmf.py` has
no domain knowledge at all.

### Internal names vs. displayed labels — the key gotcha

Database columns, Python variable names, and internal function names use the
**original school-specific vocabulary** (`teilnehmer`/`schueler`, `stufe` = grade level,
`stufenzusatz` = class suffix, `projekt`/`projekte` = option/project, `jgst` =
Jahrgangsstufe) even though the app was generalized so **every user-facing label is
configurable** at runtime via `Datei → Spaltenbezeichnungen anpassen`. The mapping lives
in `database.get_feldkonfig()` / `FELDKONFIG_DEFAULTS` (table `feldkonfiguration`) and
`database.get_label_formen()`/`pluralisiere_label()`, which also drive German grammar
agreement (gender, Fugen-s, dative form, plural) across buttons, menus, and dialogs.
When changing UI text, always go through the label-config functions rather than
hardcoding a German term — a hardcoded "Option" or "Projekt" will look wrong once the
user renames that concept to "Kurs" or "Workshop".

Consequence: don't assume a DB/variable name (`stufe`, `projekt`, `teilnehmer`) reflects
what's shown in the UI. Check `get_feldkonfig()` / the relevant `*_label` key.

### Assignment algorithms (`algorithmen.py` + `_zuteilungsplaner.py` + `_mcmf.py`)

Three algorithms (A/B/C) all reduce to the same min-cost-flow problem, differing only in
edge-cost weighting between wish rank, minimum-participant support, and "assign
everyone" priority. Invariants held by all three (see docstrings in `algorithmen.py`):
capacity (`tnmax`) is a hard limit that is never exceeded, only actually-chosen wishes
are ever assigned, and unserved-participant count is minimized mathematically rather
than heuristically. Soft criteria (group cohesion, matching wish lists = "friend
detection") are applied as small cost tie-breakers, not hard constraints.

### Database (`database.py`)

SQLite, four tables: `projekte`, `teilnehmer`, `feldkonfiguration`, `raeume`. `init_db()`
both creates tables and runs idempotent migrations (column/table renames, added columns) —
when changing schema, add a migration branch here rather than assuming a fresh DB.
Writes commit immediately; there is no explicit save step in the UI.

Rooms are keyed by their own stable `raeume.id`; each option references a room via
`projekte.raum_id` (plus a free-text `projekte.zeit`). Crucially, `upsert_projekt` and
`renumber_projekte_und_insert` must **not** touch `raum_id`/`zeit` — editing an option in
the Optionen tab or renumbering options must preserve the room assignment. Room/time are
written only through the dedicated `set_raum_zeit_for_projekt` (and `set_raum_for_projekt`
/ `set_raum_fixiert` for the auto-assigner). `pruefe_raumkonflikte`
(in `validierung.py`) reads `get_raumplan()` and flags double-bookings (same room+time)
and capacity issues as hints (text + cell color) — it is display-only and never blocks by
itself. The soft gate happens in `hauptfenster.RaumplanTable`: assigning a room (or a time)
that would create a same-room/same-time double-booking triggers a confirm dialog right in the
`_on_raum_changed`/`_on_cell_changed` handlers (`_frage_raum_konflikt` → `QMessageBox.question`
"Mehrfachbelegung erzwingen?"). Declining reverts the change; confirming saves the
double-booking anyway, which `pruefe_raumkonflikte` then flags red — same as conflicts already
present in imported/legacy data. So the UI discourages but no longer hard-blocks double-bookings.
Automatic room assignment
lives in `raumzuteilung.py` (greedy first-fit-decreasing per time group, respecting the
`projekte.raum_fixiert` flag) — it never touches the participant algorithm.

Preconfigured export folders are stored as a JSON list under the `export_speicherorte`
feldkonfig key (`get_speicherorte`/`set_speicherorte`); they surface as sidebar shortcuts
in the save dialogs, not as direct WebDAV uploads.

The **Nachbearbeitungsmodus** ("Einteilung → Bearbeitungsmodus Ein/Aus") snapshots the
current assignment into `teilnehmer.projekt_baseline` and sets the `bearbeitungsmodus_aktiv`
feldkonfig flag. Both live in the `.plf` (which *is* the SQLite DB), so the mode and its
baselines persist across save/load — reopening a planning file resumes exactly where it was
left (`init_db` uses `INSERT OR IGNORE`, so the stored flag survives; `_open_db → _refresh_all
→ _sync_bearbeitungsmodus_menu` restores the UI state). While active,
`database.zuteilung_anzeige(s)` returns a `Geaendert` (str subclass) marker `"old̶ → new"`
when a person's `projekt` differs from its baseline. `get_projektteilnehmerliste` shows both
sides of every move: people who **left** an option appear as appended `Geist`-marked
(grey, struck-through) rows, and people who **arrived** are highlighted inline as
`Geaendert` (yellow) rows whose "Wunschrang erhalten" cell notes their origin
("… · neu (vorher: N)"). `listenabfragen.get_aenderungsuebersicht()` backs the
"Einteilung → Übersicht der Änderungen" list window, which lists every reassigned
participant (Vorher/Jetzt/rank) at once. The markers are `str` subclasses, so they flow
unchanged through `filter_spalten`/CSV/Qt items; renderers additionally `isinstance`-check
them to apply the `HERVORHEBUNG_*_HEX` background color (screen, HTML/PDF via `_html_gruppen`,
xlsx, ods; CSV keeps only the Unicode strike-through). Turning the mode off clears all
baselines. The mode never affects the algorithm or room assignment — only display/export.

### Import/export (`importexport.py`)

Handles CSV (auto-detected delimiter/encoding), `.xlsx` (openpyxl), and `.ods` (odfpy)
on both import and export paths, plus PDF/HTML export for printable lists. Column
mapping between source-file headers and app fields happens in `dialoge.SpaltenzuordnungDialog`;
`importexport.py` provides the detection/normalization helpers it calls (title-row
stripping, wish-count detection, name/class splitting, value-variant detection for
merged multi-file imports).
