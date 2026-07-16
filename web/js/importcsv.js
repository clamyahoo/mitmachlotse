/**
 * CSV-Parsing und Spalten-Erkennung für den Import — Web-Gegenstück zu den
 * Erkennungs-Helfern in importexport.py (vereinfachte, aber regelgleiche
 * Untermenge: Trennzeichen-Erkennung, Alias-Zuordnung, Name-/Klassen-Split,
 * Zahlen-Koersion für Excel-Artefakte wie "1.0").
 */

import { labelFormen } from "./db.js";

/** Trennzeichen automatisch erkennen (';' , '\t' '|'), Fallback ';'. */
export function erkenneTrennzeichen(text) {
  const erste = text.split(/\r?\n/, 1)[0] || "";
  const kandidaten = [";", ",", "\t", "|"];
  let bester = ";", max = 0;
  for (const d of kandidaten) {
    const n = erste.split(d).length - 1;
    if (n > max) { max = n; bester = d; }
  }
  return bester;
}

/** CSV-Text in Zeilen-Arrays parsen (mit Anführungszeichen-Behandlung). */
export function parseCsv(text, delim) {
  const rows = [];
  let zeile = [], feld = "", inQuote = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQuote) {
      if (c === '"') {
        if (text[i + 1] === '"') { feld += '"'; i++; }
        else inQuote = false;
      } else feld += c;
    } else if (c === '"') {
      inQuote = true;
    } else if (c === delim) {
      zeile.push(feld); feld = "";
    } else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      zeile.push(feld); feld = "";
      rows.push(zeile); zeile = [];
    } else {
      feld += c;
    }
  }
  if (feld !== "" || zeile.length) { zeile.push(feld); rows.push(zeile); }
  // Komplett leere Zeilen entfernen
  return rows.filter((r) => r.some((z) => String(z).trim() !== ""));
}

// ── Auto-Zuordnung: Aliaslisten (Untermenge der Desktop-Regeln) ──────────────
// Wichtig wie im Desktop: "Name" zählt NUR für "Ganzer Name", "Nachname"/
// "Familienname" NUR für das Nachname-Feld — damit eine Spalte nie zwei
// Feldern gleichzeitig zugeordnet wird.

const TN_ALIASE = {
  nachname:     ["nachname", "familienname", "last name", "lastname"],
  vorname:      ["vorname", "first name", "firstname", "rufname"],
  ganzer_name:  ["name", "ganzer name", "teilnehmer", "teilnehmer/in",
                 "schülername", "schuelername"],
  stufe:        ["stufe", "jgst", "jgst.", "jahrgangsstufe", "gruppenbereich",
                 "jahrgang"],
  stufenzusatz: ["zusatz", "klassenzusatz", "gruppenzusatz", "abteilung",
                 "untergruppe"],
  klasse_kombi: ["klasse", "gruppe", "klasse/gruppe"],
  geschlecht:   ["geschlecht", "geschl", "geschl.", "m/w", "sex"],
};

const PROJEKT_ALIASE = {
  nummer:      ["nr", "nr.", "nummer", "number"],
  projektname: ["projektname", "optionsname", "kursname", "titel", "name",
                "angebot", "projekt", "option"],
  leitung:     ["leitung", "leiter", "leiter/in", "ansprechperson",
                "lehrkraft", "betreuer", "betreuer/in"],
  stufenmin:   ["stufenmin", "stufe min", "gruppenbereich min", "jgst min",
                "min stufe", "von", "ab stufe"],
  stufenmax:   ["stufenmax", "stufe max", "gruppenbereich max", "jgst max",
                "max stufe", "bis", "bis stufe"],
  tnmin:       ["tnmin", "tn min", "plätze min", "plaetze min", "min",
                "mindestteilnehmer", "min. teilnehmer"],
  tnmax:       ["tnmax", "tn max", "plätze max", "plaetze max", "max",
                "maximalteilnehmer", "max. teilnehmer"],
};

const RAUM_ALIASE = {
  name:         ["raumname", "raum", "name", "bezeichnung"],
  kapazitaet:   ["kapazität", "kapazitaet", "plätze", "plaetze", "größe", "groesse"],
  beschreibung: ["beschreibung", "bemerkung", "info", "hinweis"],
};

function findeAlias(aliase, headers) {
  const norm = headers.map((h) => String(h).trim().toLowerCase());
  for (const alias of aliase) {
    const idx = norm.indexOf(alias);
    if (idx >= 0) return idx;
  }
  return null;
}

/**
 * Automatische Zuordnung Quellspalte → App-Feld.
 * feldKey "wunsch_N" wird per Muster erkannt ("Wunsch 1", "W1", "wunsch1").
 * Rückgabe: Spaltenindex oder null.
 */
export function autoMatch(art, feldKey, headers) {
  const wunsch = feldKey.match(/^wunsch_(\d)$/);
  if (wunsch) {
    const n = wunsch[1];
    const muster = new RegExp(`^(wunsch\\s*${n}|w${n}|${n}\\.\\s*wunsch)$`, "i");
    const idx = headers.findIndex((h) => muster.test(String(h).trim()));
    return idx >= 0 ? idx : null;
  }
  const tabelle = art === "teilnehmer" ? TN_ALIASE
    : art === "raeume" ? RAUM_ALIASE : PROJEKT_ALIASE;
  return tabelle[feldKey] ? findeAlias(tabelle[feldKey], headers) : null;
}

/**
 * Mehrere bereits eingelesene Tabellen-Texte zusammenführen (Mehrdatei-Import,
 * wie am Desktop): jede Datei mit eigenem Trennzeichen parsen, Spalten anhand
 * ihres Namens zuordnen — die Reihenfolge der ERSTEN Datei bleibt maßgeblich,
 * in einzelnen Dateien fehlende Spalten werden mit Leerwerten aufgefüllt.
 * Rückgabe: { headers, rows }
 */
export function mergeTabellen(texte) {
  const tabellen = [];
  for (const text of texte) {
    const rows = parseCsv(text, erkenneTrennzeichen(text));
    if (rows.length < 2) continue; // Kopf + mindestens eine Datenzeile
    tabellen.push({
      headers: rows[0].map((h) => String(h).trim()),
      rows: rows.slice(1),
    });
  }
  if (!tabellen.length) return { headers: [], rows: [] };
  const master = tabellen[0].headers;
  const rows = [];
  for (const t of tabellen) {
    const norm = t.headers.map((h) => h.toLowerCase());
    const map = master.map((mh) => norm.indexOf(mh.toLowerCase()));
    for (const row of t.rows) {
      rows.push(master.map((_, i) =>
        map[i] >= 0 && map[i] < row.length ? row[map[i]] : ""));
    }
  }
  return { headers: master, rows };
}

// ── Wert-Helfer (Spiegel der Desktop-Koersionen) ─────────────────────────────

/** "Nachname, Vorname" (Komma) oder "Vorname Nachname" (letztes Leerzeichen). */
export function splitGanzerName(s) {
  const roh = String(s).trim();
  if (!roh) return ["", ""];
  if (roh.includes(",")) {
    const [n, ...rest] = roh.split(",");
    return [n.trim(), rest.join(",").trim()];
  }
  const teile = roh.split(/\s+/);
  if (teile.length === 1) return [teile[0], ""];
  return [teile[teile.length - 1], teile.slice(0, -1).join(" ")];
}

/** "5a" → ["5", "a"]; "10 b" → ["10", "b"]; "EF" → ["EF", ""]. */
export function splitKlasse(s) {
  const roh = String(s).trim();
  const m = roh.match(/^(\d+)\s*(.*)$/);
  if (m) return [m[1], m[2].trim()];
  return [roh, ""];
}

/** Excel-tolerantes int: "1", "1.0", "1,0" → 1; sonst default. */
export function zahl(v, def = 0) {
  const s = String(v ?? "").trim().replace(",", ".");
  if (s === "") return def;
  const f = parseFloat(s);
  return Number.isNaN(f) ? def : Math.trunc(f);
}

/** Stufe normalisieren: "5.0"/"5,0" → "5"; "5a"/"EF" bleiben unangetastet. */
export function normStufe(v) {
  const s = String(v ?? "").trim();
  if (/^\d+([.,]\d+)?$/.test(s)) return String(Math.trunc(parseFloat(s.replace(",", "."))));
  return s;
}

// ── Feldlisten für den Zuordnungsdialog ──────────────────────────────────────

export function teilnehmerFelder(konfig) {
  const felder = [
    { key: "nachname",     label: "Nachname" },
    { key: "vorname",      label: "Vorname" },
    { key: "ganzer_name",  label: "Ganzer Name in einer Spalte" },
    { key: "stufe",        label: konfig.stufe_label },
    { key: "stufenzusatz", label: konfig.stufenzusatz_label },
    { key: "klasse_kombi", label: `${konfig.stufe_label} + ${konfig.stufenzusatz_label} kombiniert (z. B. „5a")` },
    { key: "geschlecht",   label: "Geschlecht" },
  ];
  for (let i = 1; i <= konfig.max_wuensche; i++) {
    felder.push({ key: `wunsch_${i}`, label: `Wunsch ${i}` });
  }
  // Optionale Zusatzfelder — nur anbieten, wenn benannt (wie am Desktop)
  for (let i = 1; i <= 3; i++) {
    const lbl = (konfig[`extra_${i}_label`] || "").trim();
    if (lbl) felder.push({ key: `extra_${i}`, label: lbl });
  }
  return felder;
}

export function projektFelder(konfig) {
  const felder = [
    { key: "nummer",      label: "Nummer" },
    { key: "leitung",     label: konfig.leitung_label || "Leitung / Ansprechperson" },
    { key: "projektname", label: labelFormen(konfig.projekt_label).name },
    { key: "stufenmin",   label: `${konfig.stufe_label} min` },
    { key: "stufenmax",   label: `${konfig.stufe_label} max` },
    { key: "tnmin",       label: "Plätze min" },
    { key: "tnmax",       label: "Plätze max" },
  ];
  for (let i = 1; i <= 3; i++) {
    const lbl = (konfig[`projekt_extra_${i}_label`] || "").trim();
    if (lbl) felder.push({ key: `extra_${i}`, label: lbl });
  }
  return felder;
}

export function raumFelder() {
  return [
    { key: "name",         label: "Raumname" },
    { key: "kapazitaet",   label: "Kapazität" },
    { key: "beschreibung", label: "Beschreibung" },
  ];
}
