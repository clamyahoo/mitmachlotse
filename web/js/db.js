/**
 * Datenbank-Schicht der Web-Version: SQLite im Browser via sql.js (WASM).
 *
 * Das Schema ist 1:1 das der Desktop-App (database.py, init_db() inklusive
 * aller Migrations-Spalten) — eine hier erzeugte .plf lässt sich in der
 * Desktop-App öffnen und umgekehrt. Bei Schemaänderungen an database.py
 * muss dieses Schema mitgezogen werden.
 */

/* global initSqlJs */

let SQL = null;   // sql.js-Modul (einmalig initialisiert)
let db = null;    // aktuelle Datenbank (sql.js Database)

const SQL_WASM_CDN = "https://cdn.jsdelivr.net/npm/sql.js@1.10.2/dist/";

// Spiegel von database.FELDKONFIG_DEFAULTS (Desktop)
export const FELDKONFIG_DEFAULTS = {
  stufe_label: "Gruppenbereich",
  stufenzusatz_label: "Gruppenzusatz",
  projekt_label: "Option",
  extra_1_label: "",
  extra_2_label: "",
  extra_3_label: "",
  max_wuensche: "5",
  leitung_label: "",
  projekt_extra_1_label: "",
  projekt_extra_2_label: "",
  projekt_extra_3_label: "",
  raumzuordnung_extra_label: "",
  export_speicherorte: "",
  bearbeitungsmodus_aktiv: "0",
};

// Vollständiges aktuelles Desktop-Schema (CREATE + alle nachmigrierten Spalten)
const SCHEMA = `
CREATE TABLE IF NOT EXISTS projekte (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nummer      INTEGER UNIQUE NOT NULL,
    projektname TEXT NOT NULL,
    stufenmin   INTEGER DEFAULT 0,
    stufenmax   INTEGER DEFAULT 99,
    tnmin       INTEGER DEFAULT 0,
    tnmax       INTEGER DEFAULT 30,
    leitung     TEXT DEFAULT '',
    extra_1     TEXT DEFAULT '',
    extra_2     TEXT DEFAULT '',
    extra_3     TEXT DEFAULT '',
    raum_id     INTEGER DEFAULT 0,
    zeit        TEXT DEFAULT '',
    raumzuordnung_extra TEXT DEFAULT '',
    raum_fixiert INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS teilnehmer (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    nachname          TEXT NOT NULL DEFAULT '-',
    vorname           TEXT NOT NULL DEFAULT '-',
    ganzer_name       TEXT GENERATED ALWAYS AS (nachname || ', ' || vorname) STORED,
    stufe             TEXT DEFAULT '-',
    stufenzusatz      TEXT DEFAULT '-',
    geschlecht        TEXT DEFAULT '-',
    wunsch_1          INTEGER DEFAULT 0,
    wunsch_2          INTEGER DEFAULT 0,
    wunsch_3          INTEGER DEFAULT 0,
    wunsch_4          INTEGER DEFAULT 0,
    wunsch_5          INTEGER DEFAULT 0,
    projekt           INTEGER DEFAULT 0,
    fest_zugewiesen   INTEGER DEFAULT 0,
    extra_1           TEXT DEFAULT '',
    extra_2           TEXT DEFAULT '',
    extra_3           TEXT DEFAULT '',
    projekt_baseline  INTEGER DEFAULT NULL
);
CREATE TABLE IF NOT EXISTS raeume (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL DEFAULT '-',
    kapazitaet   INTEGER DEFAULT 0,
    beschreibung TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS feldkonfiguration (
    schluessel TEXT PRIMARY KEY,
    wert       TEXT NOT NULL DEFAULT ''
);
`;

/** sql.js einmalig initialisieren. */
async function ensureSql() {
  if (!SQL) {
    SQL = await initSqlJs({ locateFile: (f) => SQL_WASM_CDN + f });
  }
  return SQL;
}

/** Neue, leere Planungsmappe mit Desktop-Schema anlegen. */
export async function neueMappe() {
  await ensureSql();
  if (db) db.close();
  db = new SQL.Database();
  db.run(SCHEMA);
  const stmt = db.prepare(
    "INSERT OR IGNORE INTO feldkonfiguration (schluessel, wert) VALUES (?, ?)"
  );
  for (const [k, v] of Object.entries(FELDKONFIG_DEFAULTS)) stmt.run([k, v]);
  stmt.free();
  return db;
}

/** Bestehende .plf/.db aus Datei-Bytes öffnen. */
export async function oeffneMappe(bytes) {
  await ensureSql();
  const kandidat = new SQL.Database(new Uint8Array(bytes));
  // Plausibilitätsprüfung, bevor die aktuelle Mappe ersetzt wird
  const probe = kandidat.exec(
    "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('teilnehmer','schueler')"
  );
  if (!probe.length) {
    kandidat.close();
    throw new Error("Datei enthält keine Mitmach-Lotse-Planungsmappe.");
  }
  // Migrationen wie database.init_db() der Desktop-App (idempotent):
  // Tabellen-/Spalten-Umbenennungen und nachträglich ergänzte Spalten,
  // damit auch ältere .plf-Dateien vollständig funktionieren.
  const alt = probe[0].values.map((r) => r[0]);
  if (alt.includes("schueler") && !alt.includes("teilnehmer")) {
    kandidat.run("ALTER TABLE schueler RENAME TO teilnehmer");
  }
  kandidat.run(SCHEMA); // fehlende Tabellen (raeume, feldkonfiguration) ergänzen
  migriereSpalten(kandidat);
  if (db) db.close();
  db = kandidat;
  return db;
}

/** Spalten-Migrationen (Spiegel von database.init_db): Umbenennungen und
 *  ADD COLUMN für alles, was ältere Planungsmappen noch nicht haben. */
function migriereSpalten(d) {
  const spalten = (tabelle) => {
    const res = d.exec(`PRAGMA table_info(${tabelle})`);
    return res.length ? res[0].values.map((r) => r[1]) : [];
  };
  const renames = {
    teilnehmer: [["jgst", "stufe"], ["abteilung", "stufenzusatz"],
                 ["manuell_zugeteilt", "fest_zugewiesen"]],
    projekte:   [["jgstmin", "stufenmin"], ["jgstmax", "stufenmax"]],
  };
  for (const [tabelle, paare] of Object.entries(renames)) {
    let vorhanden = spalten(tabelle);
    for (const [altN, neu] of paare) {
      if (vorhanden.includes(altN) && !vorhanden.includes(neu)) {
        d.run(`ALTER TABLE ${tabelle} RENAME COLUMN ${altN} TO ${neu}`);
        vorhanden = spalten(tabelle);
      }
    }
  }
  const zusaetze = {
    teilnehmer: [["fest_zugewiesen", "INTEGER DEFAULT 0"],
                 ["extra_1", "TEXT DEFAULT ''"],
                 ["extra_2", "TEXT DEFAULT ''"],
                 ["extra_3", "TEXT DEFAULT ''"],
                 ["projekt_baseline", "INTEGER DEFAULT NULL"]],
    projekte:   [["leitung", "TEXT DEFAULT ''"],
                 ["extra_1", "TEXT DEFAULT ''"],
                 ["extra_2", "TEXT DEFAULT ''"],
                 ["extra_3", "TEXT DEFAULT ''"],
                 ["raum_id", "INTEGER DEFAULT 0"],
                 ["zeit", "TEXT DEFAULT ''"],
                 ["raumzuordnung_extra", "TEXT DEFAULT ''"],
                 ["raum_fixiert", "INTEGER DEFAULT 0"]],
  };
  for (const [tabelle, defs] of Object.entries(zusaetze)) {
    const vorhanden = spalten(tabelle);
    for (const [name, typ] of defs) {
      if (!vorhanden.includes(name)) {
        d.run(`ALTER TABLE ${tabelle} ADD COLUMN ${name} ${typ}`);
      }
    }
  }
}

/** Aktuelle Mappe als Bytes (Uint8Array) exportieren — für Speichern & Solver. */
export function exportiereBytes() {
  return db.export();
}

/** Nach dem Solver-Lauf: Mappe durch neue Bytes ersetzen. */
export async function ersetzeAusBytes(bytes) {
  await ensureSql();
  if (db) db.close();
  db = new SQL.Database(new Uint8Array(bytes));
  return db;
}

export function istOffen() {
  return db !== null;
}

/** SELECT → Array von Objekten. */
export function query(sql, params = []) {
  const stmt = db.prepare(sql);
  stmt.bind(params);
  const rows = [];
  while (stmt.step()) rows.push(stmt.getAsObject());
  stmt.free();
  return rows;
}

/** INSERT/UPDATE/DELETE. */
export function run(sql, params = []) {
  db.run(sql, params);
}

// ── Domänen-Abfragen (Spiegel der database.py-Zugriffe) ──────────────────────

export function getFeldkonfig() {
  const konfig = { ...FELDKONFIG_DEFAULTS };
  try {
    for (const r of query("SELECT schluessel, wert FROM feldkonfiguration")) {
      konfig[r.schluessel] = r.wert;
    }
  } catch { /* alte Datei ohne Tabelle: Defaults */ }
  konfig.max_wuensche = Math.max(1, Math.min(5, parseInt(konfig.max_wuensche, 10) || 5));
  return konfig;
}

export function getAlleTeilnehmer() {
  return query(
    "SELECT * FROM teilnehmer ORDER BY stufe, stufenzusatz, nachname, vorname"
  );
}

export function getAlleProjekte() {
  return query("SELECT * FROM projekte ORDER BY nummer");
}

export function insertTeilnehmer() {
  run("INSERT INTO teilnehmer (nachname, vorname, stufe, stufenzusatz) VALUES ('-', '-', '-', '-')");
  return query("SELECT last_insert_rowid() AS id")[0].id;
}

export function updateTeilnehmerFeld(id, feld, wert) {
  const erlaubt = new Set([
    "nachname", "vorname", "stufe", "stufenzusatz", "geschlecht",
    "wunsch_1", "wunsch_2", "wunsch_3", "wunsch_4", "wunsch_5",
    "projekt", "fest_zugewiesen", "extra_1", "extra_2", "extra_3",
  ]);
  if (!erlaubt.has(feld)) throw new Error(`Unbekanntes Teilnehmer-Feld: ${feld}`);
  run(`UPDATE teilnehmer SET ${feld} = ? WHERE id = ?`, [wert, id]);
}

export function deleteTeilnehmer(ids) {
  for (const id of ids) run("DELETE FROM teilnehmer WHERE id = ?", [id]);
}

export function naechsteProjektnummer() {
  const r = query("SELECT COALESCE(MAX(nummer), 0) + 1 AS n FROM projekte");
  return r[0].n;
}

export function insertProjekt(nummer) {
  run(
    "INSERT INTO projekte (nummer, projektname) VALUES (?, '-')",
    [nummer]
  );
}

export function updateProjektFeld(id, feld, wert) {
  const erlaubt = new Set([
    "nummer", "projektname", "leitung", "stufenmin", "stufenmax",
    "tnmin", "tnmax", "extra_1", "extra_2", "extra_3",
  ]);
  if (!erlaubt.has(feld)) throw new Error(`Unbekanntes Projekt-Feld: ${feld}`);
  run(`UPDATE projekte SET ${feld} = ? WHERE id = ?`, [wert, id]);
}

export function deleteProjekte(ids) {
  for (const id of ids) run("DELETE FROM projekte WHERE id = ?", [id]);
}

/** Automatische Zuweisungen aufheben (fixierte bleiben) — wie Desktop. */
export function zuteilungAufheben() {
  run("UPDATE teilnehmer SET projekt = 0 WHERE fest_zugewiesen = 0");
}

/** Belegung je Projektnummer. */
export function getBelegung() {
  const map = {};
  for (const r of query(
    "SELECT projekt, COUNT(*) AS n FROM teilnehmer WHERE projekt != 0 GROUP BY projekt"
  )) {
    map[r.projekt] = r.n;
  }
  return map;
}

/** Wunschstatistik direkt aus der DB (Rang des zugeteilten Projekts). */
export function getWunschstatistik(maxWuensche) {
  const treffer = { 0: 0 };
  for (let i = 1; i <= maxWuensche; i++) treffer[i] = 0;
  let zugeteilt = 0;
  const alle = getAlleTeilnehmer();
  for (const t of alle) {
    if (t.projekt === 0) { treffer[0]++; continue; }
    zugeteilt++;
    const wuensche = [t.wunsch_1, t.wunsch_2, t.wunsch_3, t.wunsch_4, t.wunsch_5]
      .slice(0, maxWuensche).filter((w) => w !== 0);
    const rang = wuensche.indexOf(t.projekt) + 1;
    if (rang >= 1) treffer[rang] = (treffer[rang] || 0) + 1;
    else treffer[0] += 0; // zugeteilt ohne eigenen Wunsch (fix) — separat zählbar
  }
  return { gesamt: alle.length, zugeteilt, treffer };
}

// ── Wunschauswertung / Projektdetails (Spiegel von listenabfragen.py) ────────

const _wuensche = (t) =>
  [t.wunsch_1, t.wunsch_2, t.wunsch_3, t.wunsch_4, t.wunsch_5];

/** Detailstatistik zu einer Option (Spiegel von get_projektdetails):
 *  Gesamtnachfrage, Nachfrage je Wunschrang, Zuteilung je Wunschrang. */
export function getProjektdetails(nummer) {
  const projekte = Object.fromEntries(getAlleProjekte().map((p) => [p.nummer, p]));
  const p = projekte[nummer];
  if (!p) return null;
  const alle = getAlleTeilnehmer();
  const wunschNachRang = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 };
  let gesamtGewuenscht = 0;
  for (const t of alle) {
    const idx = _wuensche(t).indexOf(nummer);
    if (idx >= 0) { wunschNachRang[idx + 1]++; gesamtGewuenscht++; }
  }
  const zugeteilt = alle.filter((t) => t.projekt === nummer);
  const zuteilungNachRang = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 };
  let ohneWunsch = 0;
  for (const t of zugeteilt) {
    const idx = _wuensche(t).indexOf(nummer);
    if (idx >= 0) zuteilungNachRang[idx + 1]++; else ohneWunsch++;
  }
  return {
    projekt: p, gesamtGewuenscht, wunschNachRang,
    anzahlZugeteilt: zugeteilt.length, zuteilungNachRang,
    zuteilungOhneWunsch: ohneWunsch,
  };
}

/** Personen, die eine Option gewünscht haben — optional gefiltert auf einen
 *  Wunschrang (Spiegel von get_wunschauswertung mit Projektfilter). */
export function getWunschauswertung(nummer, rang = null) {
  const alle = getAlleTeilnehmer();
  const treffer = [];
  for (const t of alle) {
    const w = _wuensche(t);
    if (rang) {
      if (w[rang - 1] === nummer) treffer.push({ t, rang });
    } else {
      const idx = w.indexOf(nummer);
      if (idx >= 0) treffer.push({ t, rang: idx + 1 });
    }
  }
  return treffer;
}

/** Einer Option zugeteilte Personen (Spiegel von get_projektteilnehmerliste). */
export function getProjektteilnehmerliste(nummer) {
  return getAlleTeilnehmer().filter((t) => t.projekt === nummer);
}

// ── Label-Grammatik (Spiegel von database.get_label_formen der Desktop-App) ──

const _FUGEN_S = new Set(["Option", "Veranstaltung", "Angebot", "Aktion"]);
const _PLURAL = {
  Option: ["Optionen", "Optionen"],
  Projekt: ["Projekte", "Projekten"],
  Kurs: ["Kurse", "Kursen"],
  Workshop: ["Workshops", "Workshops"],
  Angebot: ["Angebote", "Angeboten"],
  Gruppe: ["Gruppen", "Gruppen"],
  Aktion: ["Aktionen", "Aktionen"],
  Veranstaltung: ["Veranstaltungen", "Veranstaltungen"],
  Einheit: ["Einheiten", "Einheiten"],
};

/** Grammatik-Formen eines Labels: Kompositum ("Optionsname" mit Fugen-s,
 *  "Kursname" ohne), Plural Nominativ ("die Kurse") und Dativ ("nach Kursen"). */
export function labelFormen(label) {
  const [nom, dat] = _PLURAL[label] || [label + "en", label + "en"];
  return {
    name: label + (_FUGEN_S.has(label) ? "s" : "") + "name",
    pluralNom: nom,
    pluralDat: dat,
  };
}

// ── Feldkonfiguration schreiben (Bezeichnungen-Dialog) ───────────────────────

export function setFeldkonfig(werte) {
  const stmt = db.prepare(
    "INSERT INTO feldkonfiguration (schluessel, wert) VALUES (?, ?) " +
    "ON CONFLICT(schluessel) DO UPDATE SET wert = excluded.wert"
  );
  for (const [k, v] of Object.entries(werte)) stmt.run([k, String(v)]);
  stmt.free();
}

/** Leitungs-Einträge vollständig löschen (Datenschutz, wie die Desktop-App
 *  beim Deaktivieren der Leitungsspalte). */
export function loescheLeitungDaten() {
  run("UPDATE projekte SET leitung = ''");
}

// ── Import-Unterstützung ─────────────────────────────────────────────────────

export function clearTeilnehmer() {
  run("DELETE FROM teilnehmer");
}

export function clearProjekte() {
  run("DELETE FROM projekte");
}

export function insertTeilnehmerVoll(r) {
  run(
    `INSERT INTO teilnehmer
       (nachname, vorname, stufe, stufenzusatz, geschlecht,
        wunsch_1, wunsch_2, wunsch_3, wunsch_4, wunsch_5, projekt,
        extra_1, extra_2, extra_3)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)`,
    [r.nachname, r.vorname, r.stufe, r.stufenzusatz, r.geschlecht,
     r.wunsch_1, r.wunsch_2, r.wunsch_3, r.wunsch_4, r.wunsch_5,
     r.extra_1 || "", r.extra_2 || "", r.extra_3 || ""]
  );
}

export function insertProjektVoll(r) {
  run(
    `INSERT INTO projekte
       (nummer, projektname, leitung, stufenmin, stufenmax, tnmin, tnmax,
        extra_1, extra_2, extra_3)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    [r.nummer, r.projektname, r.leitung, r.stufenmin, r.stufenmax,
     r.tnmin, r.tnmax, r.extra_1 || "", r.extra_2 || "", r.extra_3 || ""]
  );
}

// ── Räume + Raumplan (Spiegel der database.py-Zugriffe) ──────────────────────
// Wichtig wie am Desktop: raum_id/zeit/raum_fixiert werden NUR über die
// dedizierten Setter geschrieben — updateProjektFeld fasst sie nie an, damit
// Optionen-Bearbeitung die Raumzuordnung nicht überschreiben kann.

export function getAlleRaeume() {
  return query("SELECT * FROM raeume ORDER BY name");
}

export function insertRaum() {
  run("INSERT INTO raeume (name, kapazitaet, beschreibung) VALUES ('-', 0, '')");
  return query("SELECT last_insert_rowid() AS id")[0].id;
}

export function insertRaumVoll(r) {
  run("INSERT INTO raeume (name, kapazitaet, beschreibung) VALUES (?, ?, ?)",
      [r.name, r.kapazitaet, r.beschreibung]);
}

export function updateRaumFeld(id, feld, wert) {
  const erlaubt = new Set(["name", "kapazitaet", "beschreibung"]);
  if (!erlaubt.has(feld)) throw new Error(`Unbekanntes Raum-Feld: ${feld}`);
  run(`UPDATE raeume SET ${feld} = ? WHERE id = ?`, [wert, id]);
}

export function deleteRaeume(ids) {
  for (const id of ids) {
    run("UPDATE projekte SET raum_id = 0 WHERE raum_id = ?", [id]);
    run("DELETE FROM raeume WHERE id = ?", [id]);
  }
}

/** Raumplan-Zeilen: Optionen + zugeordneter Raum + Belegung (wie Desktop). */
export function getRaumplan() {
  return query(`
    SELECT p.nummer, p.projektname, p.leitung, p.tnmax,
           p.raum_id, p.zeit, p.raum_fixiert,
           r.name AS raum_name, r.kapazitaet AS raum_kapazitaet,
           (SELECT COUNT(*) FROM teilnehmer t WHERE t.projekt = p.nummer) AS belegt
    FROM projekte p
    LEFT JOIN raeume r ON r.id = p.raum_id
    ORDER BY p.nummer`);
}

export function setRaumZeit(nummer, raumId, zeit) {
  run("UPDATE projekte SET raum_id = ?, zeit = ? WHERE nummer = ?",
      [raumId, zeit, nummer]);
}

export function setRaumFixiert(nummer, fixiert) {
  run("UPDATE projekte SET raum_fixiert = ? WHERE nummer = ?",
      [fixiert ? 1 : 0, nummer]);
}

/** Nicht fixierte Raumzuordnungen entfernen; gibt die Anzahl zurück. */
export function raumzuteilungAufheben() {
  const n = query(
    "SELECT COUNT(*) AS n FROM projekte WHERE raum_id != 0 AND raum_fixiert = 0"
  )[0].n;
  run("UPDATE projekte SET raum_id = 0 WHERE raum_fixiert = 0");
  return n;
}

// ── Nachbearbeitungsmodus (Spiegel der database.py-Funktionen) ───────────────
// Basis-Zuteilung + Flag leben in der .plf → der Modus überlebt Speichern/
// Öffnen und ist mit der Desktop-App austauschbar.

export function istBearbeitungsmodus() {
  return getFeldkonfig().bearbeitungsmodus_aktiv === "1";
}

/** Aktuellen Zuteilungsstand als Basis festhalten und Modus aktivieren. */
export function bearbeitungsmodusEin() {
  run("UPDATE teilnehmer SET projekt_baseline = projekt");
  setFeldkonfig({ bearbeitungsmodus_aktiv: "1" });
}

/** Modus beenden: Basis verwerfen, aktueller Stand gilt als fest. */
export function bearbeitungsmodusAus() {
  run("UPDATE teilnehmer SET projekt_baseline = NULL");
  setFeldkonfig({ bearbeitungsmodus_aktiv: "0" });
}

/** Alle seit Modus-Start umverteilten Teilnehmer/innen. */
export function getAenderungen() {
  return getAlleTeilnehmer().filter(
    (t) => t.projekt_baseline !== null && t.projekt_baseline !== t.projekt
  );
}
