/**
 * Mitmach-Lotse Web — UI-Schicht.
 *
 * Grundsätze:
 *  - Alle Daten leben in einer SQLite-DB im Browser (db.js / sql.js);
 *    "Speichern" schreibt die .plf-Datei aufs Gerät. Nichts verlässt den
 *    Browser Richtung Server.
 *  - Jede Rechtefrage läuft über die Kontext-Schicht (kontext.js) — heute
 *    Betriebsart "lokal" mit vollen Rechten, später befüllbar aus
 *    Server-Login oder Moodle/LTI.
 *  - Der Zuteilungs-Solver (solver.js) lädt Pyodide erst bei Bedarf.
 */

import { Kontext } from "./kontext.js";
import * as db from "./db.js";
import * as solver from "./solver.js";
import { alsCsv, downloadText } from "./csv.js";
import { oeffneImportDialog } from "./importdialog.js";
import * as druck from "./druck.js";
import { pruefeQualitaet, wunschZulaessig } from "./quali.js";
import * as auswertung from "./auswertung.js";
import { liesTabellenDatei } from "./tabellendatei.js";
import { initRaumplan, renderRaumplan } from "./raumplan.js";
import { waehleSpalten, filterGruppen } from "./spaltenwahl.js";
import { mergeTabellen } from "./importcsv.js";
import { initAssistenten, zeigeEinrichtungsassistent, zeigeTabellenassistent }
  from "./assistenten.js";

// Grammatik-Formen der Labels kommen zentral aus db.labelFormen()
// (Fugen-s, Plural Nominativ/Dativ) — gespiegelt von der Desktop-App.
const pluralDativ = (label) => db.labelFormen(label).pluralDat;

// ── Zustand ──────────────────────────────────────────────────────────────────
let dateiname = "";
let dateiHandle = null;   // File System Access API (Chrome/Edge), sonst null
let dirty = false;

const $ = (id) => document.getElementById(id);

// ── Status & Kopfzeile ───────────────────────────────────────────────────────
function status(text) { $("status").textContent = text; }

function setzeDirty(neu) {
  dirty = neu;
  $("dirty-badge").hidden = !dirty;
}

function aktualisiereKopf() {
  $("dateiname").textContent = dateiname || "(keine Planungsmappe)";
  $("kontext-badge").textContent = Kontext.beschreibung();
  const offen = db.istOffen();
  for (const id of ["btn-speichern", "btn-speichern-als", "btn-tn-neu",
                    "btn-tn-loeschen", "btn-opt-neu", "btn-opt-loeschen",
                    "btn-csv-gesamt", "btn-zuteilung-aufheben",
                    "btn-labels", "btn-tabellen", "btn-tn-import", "btn-opt-import",
                    "btn-quali", "btn-quali-export", "btn-druck-optionen",
                    "btn-druck-gruppen", "btn-druck-einzeloption",
                    "btn-druck-einzelgruppe", "btn-aenderungen-export", "btn-raum-neu",
                    "btn-raum-loeschen", "btn-raum-auto", "btn-raum-reset",
                    "btn-raum-druck", "btn-bearbeitungsmodus",
                    "btn-raum-import", "btn-raum-export"]) {
    $(id).disabled = !offen;
  }
  syncBearbeitungsmodus();
  $("tn-suche").disabled = !offen;
  $("druck-option-select").disabled = !offen;
  $("druck-gruppe-select").disabled = !offen;
  $("quali-filter").disabled = !offen;
  const darfZuteilen = offen && Kontext.darfZuteilen();
  for (const id of ["btn-algo-a", "btn-algo-b", "btn-algo-c"]) {
    $(id).disabled = !darfZuteilen;
  }
  if (!Kontext.darfOptionenBearbeiten()) {
    // Struktur-Eingriffe (Optionen, Räume, Import, Bezeichnungen) nur für Admin
    for (const id of ["btn-opt-neu", "btn-opt-loeschen", "btn-labels",
                      "btn-tabellen", "btn-tn-import", "btn-opt-import",
                      "btn-raum-neu", "btn-raum-loeschen", "btn-raum-auto",
                      "btn-raum-reset", "btn-bearbeitungsmodus", "btn-raum-import"]) {
      $(id).disabled = true;
    }
  }
}

function syncBearbeitungsmodus() {
  const aktiv = db.istOffen() && db.istBearbeitungsmodus();
  $("bm-badge").hidden = !aktiv;
  $("btn-bearbeitungsmodus").textContent =
    aktiv ? "Bearbeitungsmodus Aus" : "Bearbeitungsmodus Ein";
}

// ── Tabs ─────────────────────────────────────────────────────────────────────
function zeigeTab(name) {
  for (const btn of document.querySelectorAll(".tab")) {
    btn.classList.toggle("aktiv", btn.dataset.tab === name);
  }
  for (const sec of document.querySelectorAll(".tab-inhalt")) {
    sec.classList.toggle("aktiv", sec.id === "tab-" + name);
  }
  renderAktuellenTab(name);
}

function renderAktuellenTab(name) {
  if (!db.istOffen()) return;
  if (name === "teilnehmer") renderTeilnehmer();
  else if (name === "optionen") renderOptionen();
  else if (name === "raumplan") renderRaumplan();
  else if (name === "zuteilung") renderZuteilung();
}

function aktiverTab() {
  return document.querySelector(".tab.aktiv")?.dataset.tab || "teilnehmer";
}

function renderAlles() {
  aktualisiereKopf();
  renderAktuellenTab(aktiverTab());
}

// ── Hilfen ───────────────────────────────────────────────────────────────────
function inputZelle(typ, wert, onChange, opts = {}) {
  const td = document.createElement("td");
  const input = document.createElement("input");
  input.type = typ;
  input.value = wert ?? "";
  if (typ === "number") { input.min = opts.min ?? 0; td.className = "zahl"; }
  if (opts.disabled) input.disabled = true;
  input.addEventListener("change", () => onChange(input));
  td.appendChild(input);
  return td;
}

function checkboxZelle(checked, onChange, disabled = false) {
  const td = document.createElement("td");
  td.className = "zahl";
  const cb = document.createElement("input");
  cb.type = "checkbox";
  cb.checked = !!checked;
  cb.disabled = disabled;
  cb.addEventListener("change", () => onChange(cb.checked));
  td.appendChild(cb);
  return td;
}

function textZelle(text, klasse = "") {
  const td = document.createElement("td");
  td.textContent = text;
  if (klasse) td.className = klasse;
  return td;
}

function kopfzeile(theadEl, spalten) {
  theadEl.innerHTML = "";
  const tr = document.createElement("tr");
  for (const s of spalten) {
    const th = document.createElement("th");
    th.textContent = s;
    tr.appendChild(th);
  }
  theadEl.appendChild(tr);
}

/** Benannte Zusatzfelder (DB-Spalten extra_1..3) als [{key, label}] — nur die,
 *  deren Bezeichnung gesetzt ist. praefix: "extra" (Teilnehmer/innen) oder
 *  "projekt_extra" (Optionen). Spiegel der Desktop-Spaltenlogik. */
function aktiveExtras(k, praefix) {
  const felder = [];
  for (let i = 1; i <= 3; i++) {
    const label = (k[`${praefix}_${i}_label`] || "").trim();
    if (label) felder.push({ key: `extra_${i}`, label });
  }
  return felder;
}

// ── Tab 1: Teilnehmer ────────────────────────────────────────────────────────
const tnMarkiert = new Set();

/** Nachbearbeitungs-Markierung einer Projekt-Zelle setzen/entfernen:
 *  gelber Hintergrund + "vorher: N" (durchgestrichen), wie am Desktop. */
function markiereProjektZelle(td, baseline, aktuell) {
  td.classList.remove("bm-geaendert");
  td.querySelector(".bm-vorher")?.remove();
  if (baseline === null || baseline === undefined || baseline === aktuell) return;
  td.classList.add("bm-geaendert");
  const hinweisEl = document.createElement("span");
  hinweisEl.className = "bm-vorher";
  const s = document.createElement("s");
  s.textContent = `vorher: ${baseline || "–"}`;
  hinweisEl.appendChild(s);
  td.appendChild(hinweisEl);
}

/** Füllt das Zuteilungs-Dropdown einer Teilnehmerzeile. Standardmäßig nur die
 *  gewählten Wünsche (in Wunschreihenfolge) + „(keine)" + Ausklapp-Eintrag;
 *  mit zeigeAlle=true zusätzlich alle übrigen Optionen. Spiegel von
 *  hauptfenster._feste_zuweisung. */
function fuelleProjektSelect(sel, t, projekte, projekteDict, zeigeAlle) {
  sel.innerHTML = "";
  const wunschNrn = [t.wunsch_1, t.wunsch_2, t.wunsch_3, t.wunsch_4, t.wunsch_5]
    .filter((w) => w !== 0);
  const keinWunsch = wunschNrn.length === 0;
  sel.appendChild(new Option("0 – (keine)", "0", false, t.projekt === 0));
  const drin = new Set([0]);
  wunschNrn.forEach((nr, i) => {
    if (drin.has(nr)) return;                    // Duplikate nur einmal
    const p = projekteDict[nr];
    sel.appendChild(new Option(
      `Wunsch ${i + 1}: ${nr} – ${p ? p.projektname : "?"}`,
      String(nr), false, t.projekt === nr));
    drin.add(nr);
  });
  if (zeigeAlle || keinWunsch) {
    const uebrige = projekte.filter((p) => !drin.has(p.nummer));
    if (uebrige.length && !keinWunsch) {
      const sep = new Option("── weitere Optionen ──", "__sep__");
      sep.disabled = true;
      sel.appendChild(sep);
    }
    for (const p of uebrige) {
      sel.appendChild(new Option(
        `${p.nummer}: ${p.projektname}`, String(p.nummer), false, t.projekt === p.nummer));
      drin.add(p.nummer);
    }
  } else {
    // aktuelle Zuteilung sichtbar halten, auch wenn sie kein Wunsch war
    if (t.projekt && !drin.has(t.projekt)) {
      const p = projekteDict[t.projekt];
      sel.appendChild(new Option(
        `${t.projekt}: ${p ? p.projektname : "?"}`, String(t.projekt), false, true));
      drin.add(t.projekt);
    }
    if (projekte.some((p) => !drin.has(p.nummer))) {
      sel.appendChild(new Option("➕ weitere Optionen anzeigen …", "__alle__"));
    }
  }
}

function renderTeilnehmer() {
  const k = db.getFeldkonfig();
  const mw = k.max_wuensche;
  const projekte = db.getAlleProjekte();
  const projekteDict = Object.fromEntries(projekte.map((p) => [p.nummer, p]));
  const modusAktiv = db.istBearbeitungsmodus();
  const suchbegriff = $("tn-suche").value.trim().toLowerCase();

  const tnExtras = aktiveExtras(k, "extra");
  const spalten = ["✓", "Nachname", "Vorname", k.stufe_label, k.stufenzusatz_label];
  for (const e of tnExtras) spalten.push(e.label);
  for (let i = 1; i <= mw; i++) spalten.push(`W${i}`);
  spalten.push(k.projekt_label, "Fixiert");
  kopfzeile($("tn-tabelle").querySelector("thead"), spalten);

  const tbody = $("tn-tabelle").querySelector("tbody");
  tbody.innerHTML = "";

  // Kontext-Schicht: nur sichtbare Teilnehmer/innen rendern (heute: alle)
  const alle = db.getAlleTeilnehmer().filter((t) => Kontext.darfTeilnehmerSehen(t));
  let angezeigt = 0;

  for (const t of alle) {
    if (suchbegriff) {
      const heuhaufen = `${t.nachname} ${t.vorname} ${t.stufe} ${t.stufenzusatz}`.toLowerCase();
      if (!heuhaufen.includes(suchbegriff)) continue;
    }
    angezeigt++;
    const darf = Kontext.darfTeilnehmerBearbeiten(t);
    const tr = document.createElement("tr");
    if (tnMarkiert.has(t.id)) tr.classList.add("markiert");

    tr.appendChild(checkboxZelle(tnMarkiert.has(t.id), (an) => {
      if (an) tnMarkiert.add(t.id); else tnMarkiert.delete(t.id);
      tr.classList.toggle("markiert", an);
    }));

    const textFeld = (feld) => inputZelle("text", t[feld], (inp) => {
      db.updateTeilnehmerFeld(t.id, feld, inp.value);
      setzeDirty(true);
    }, { disabled: !darf });
    tr.appendChild(textFeld("nachname"));
    tr.appendChild(textFeld("vorname"));
    // Stufe wirkt auf die Wunsch-Zulässigkeit → bei Änderung Zeilen neu prüfen
    tr.appendChild(inputZelle("text", t.stufe, (inp) => {
      db.updateTeilnehmerFeld(t.id, "stufe", inp.value);
      setzeDirty(true);
      renderTeilnehmer();
    }, { disabled: !darf }));
    tr.appendChild(textFeld("stufenzusatz"));
    for (const e of tnExtras) tr.appendChild(textFeld(e.key));

    // Wunschfelder mit fortlaufender Zulässigkeitsprüfung (Punkt: Markierung
    // unzulässiger Wünsche direkt bei der Eingabe, wie am Desktop).
    for (let i = 1; i <= mw; i++) {
      const feld = `wunsch_${i}`;
      const td = document.createElement("td");
      td.className = "zahl";
      const input = document.createElement("input");
      input.type = "number"; input.min = 0;
      input.value = t[feld] ?? "";
      input.disabled = !darf;
      const markiere = (wert) => {
        const r = wunschZulaessig(t.stufe, wert, projekteDict, k);
        td.classList.toggle("wunsch-unzulaessig", !r.ok);
        input.title = r.ok ? "" : "⚠ " + r.grund;
      };
      markiere(t[feld]);
      input.addEventListener("change", () => {
        const wert = parseInt(input.value, 10) || 0;
        db.updateTeilnehmerFeld(t.id, feld, wert);
        t[feld] = wert;
        setzeDirty(true);
        markiere(wert);
      });
      td.appendChild(input);
      tr.appendChild(td);
    }

    // Zuteilung: zunächst nur die gewählten Wünsche + Ausklappen auf alle
    // Optionen (Punkt: fixe Zuweisung wie am Desktop).
    const tdProjekt = document.createElement("td");
    const sel = document.createElement("select");
    sel.disabled = !Kontext.darfZuteilen();
    fuelleProjektSelect(sel, t, projekte, projekteDict, false);
    sel.addEventListener("change", () => {
      if (sel.value === "__alle__") {
        fuelleProjektSelect(sel, t, projekte, projekteDict, true);
        return;
      }
      if (sel.value === "__sep__") { sel.value = String(t.projekt); return; }
      const neu = parseInt(sel.value, 10) || 0;
      db.updateTeilnehmerFeld(t.id, "projekt", neu);
      t.projekt = neu;
      setzeDirty(true);
      tr.querySelector(".fix-cb").disabled = neu === 0;
      tdProjekt.classList.toggle("warn", neu === 0);
      if (modusAktiv) markiereProjektZelle(tdProjekt, t.projekt_baseline, neu);
    });
    if (t.projekt === 0) tdProjekt.classList.add("warn");
    tdProjekt.appendChild(sel);
    if (modusAktiv) markiereProjektZelle(tdProjekt, t.projekt_baseline, t.projekt);
    tr.appendChild(tdProjekt);

    const tdFix = checkboxZelle(t.fest_zugewiesen, (an) => {
      db.updateTeilnehmerFeld(t.id, "fest_zugewiesen", an ? 1 : 0);
      setzeDirty(true);
    }, !Kontext.darfZuteilen());
    tdFix.querySelector("input").classList.add("fix-cb");
    tr.appendChild(tdFix);

    tbody.appendChild(tr);
  }
  $("tn-anzahl").textContent =
    suchbegriff ? `${angezeigt} von ${alle.length} Teilnehmer/innen`
                : `${alle.length} Teilnehmer/innen`;
}

// ── Tab 2: Optionen ──────────────────────────────────────────────────────────
const optMarkiert = new Set();

function renderOptionen() {
  const k = db.getFeldkonfig();
  const mitLeitung = !!k.leitung_label;
  const belegung = db.getBelegung();
  const darf = Kontext.darfOptionenBearbeiten();

  const optExtras = aktiveExtras(k, "projekt_extra");
  const spalten = ["✓", "Nr."];
  if (mitLeitung) spalten.push(k.leitung_label);
  spalten.push(db.labelFormen(k.projekt_label).name);
  for (const e of optExtras) spalten.push(e.label);
  spalten.push(`${k.stufe_label} min`, `${k.stufe_label} max`,
               "Plätze min", "Plätze max", "belegt");
  kopfzeile($("opt-tabelle").querySelector("thead"), spalten);

  const tbody = $("opt-tabelle").querySelector("tbody");
  tbody.innerHTML = "";
  const projekte = db.getAlleProjekte();

  for (const p of projekte) {
    const tr = document.createElement("tr");
    if (optMarkiert.has(p.id)) tr.classList.add("markiert");

    tr.appendChild(checkboxZelle(optMarkiert.has(p.id), (an) => {
      if (an) optMarkiert.add(p.id); else optMarkiert.delete(p.id);
      tr.classList.toggle("markiert", an);
    }));

    tr.appendChild(inputZelle("number", p.nummer, (inp) => {
      const neu = parseInt(inp.value, 10) || 0;
      try {
        db.updateProjektFeld(p.id, "nummer", neu);
        setzeDirty(true);
      } catch {
        alert(`Nummer ${neu} ist bereits vergeben.`);
        inp.value = p.nummer;
      }
    }, { min: 1, disabled: !darf }));

    if (mitLeitung) {
      tr.appendChild(inputZelle("text", p.leitung, (inp) => {
        db.updateProjektFeld(p.id, "leitung", inp.value);
        setzeDirty(true);
      }, { disabled: !darf }));
    }

    tr.appendChild(inputZelle("text", p.projektname, (inp) => {
      db.updateProjektFeld(p.id, "projektname", inp.value);
      setzeDirty(true);
    }, { disabled: !darf }));

    for (const e of optExtras) {
      tr.appendChild(inputZelle("text", p[e.key], (inp) => {
        db.updateProjektFeld(p.id, e.key, inp.value);
        setzeDirty(true);
      }, { disabled: !darf }));
    }

    for (const feld of ["stufenmin", "stufenmax", "tnmin", "tnmax"]) {
      tr.appendChild(inputZelle("number", p[feld], (inp) => {
        db.updateProjektFeld(p.id, feld, parseInt(inp.value, 10) || 0);
        setzeDirty(true);
      }, { disabled: !darf }));
    }

    const belegt = belegung[p.nummer] || 0;
    tr.appendChild(textZelle(String(belegt),
      "readonly" + (belegt > p.tnmax ? " warn" : "")));

    tbody.appendChild(tr);
  }
  $("opt-anzahl").textContent =
    `${projekte.length} ${db.labelFormen(k.projekt_label).pluralNom}`;
}

// ── Tab 3: Zuteilung & Auswertung ────────────────────────────────────────────
function renderZuteilung() {
  const k = db.getFeldkonfig();
  const stat = db.getWunschstatistik(k.max_wuensche);

  kopfzeile($("statistik-tabelle").querySelector("thead"), ["", "Anzahl", "Anteil"]);
  const stTbody = $("statistik-tabelle").querySelector("tbody");
  stTbody.innerHTML = "";
  const zeile = (label, n, basis) => {
    const tr = document.createElement("tr");
    tr.appendChild(textZelle(label));
    tr.appendChild(textZelle(String(n), "zahl"));
    tr.appendChild(textZelle(basis ? `${Math.round((n / basis) * 100)} %` : "–", "zahl"));
    stTbody.appendChild(tr);
  };
  for (let i = 1; i <= k.max_wuensche; i++) {
    zeile(`Wunsch ${i} erhalten`, stat.treffer[i] || 0, stat.zugeteilt);
  }
  zeile("Ohne Zuteilung", stat.treffer[0] || 0, stat.gesamt);
  zeile("Gesamt", stat.gesamt, 0);

  $("uebersicht-titel").textContent =
    `Belegungsübersicht (${db.labelFormen(k.projekt_label).pluralNom})`;
  kopfzeile($("uebersicht-tabelle").querySelector("thead"),
    ["Nr.", db.labelFormen(k.projekt_label).name,
     "Plätze min", "Plätze max", "belegt"]);
  const uTbody = $("uebersicht-tabelle").querySelector("tbody");
  uTbody.innerHTML = "";
  const belegung = db.getBelegung();
  for (const p of db.getAlleProjekte()) {
    const belegt = belegung[p.nummer] || 0;
    const tr = document.createElement("tr");
    tr.className = "klickbar";
    tr.title = "Klick: Wunschdetails zu dieser Option";
    tr.addEventListener("click", () => auswertung.zeigeProjektdetails(p.nummer));
    tr.appendChild(textZelle(String(p.nummer), "zahl"));
    tr.appendChild(textZelle(p.projektname));
    tr.appendChild(textZelle(String(p.tnmin), "zahl"));
    tr.appendChild(textZelle(String(p.tnmax), "zahl"));
    let klasse = "zahl";
    if (belegt > p.tnmax) klasse += " warn";
    else if (p.tnmin && belegt > 0 && belegt < p.tnmin) klasse += " warn";
    tr.appendChild(textZelle(String(belegt), klasse));
    uTbody.appendChild(tr);
  }

  // Druck-Auswahl + dynamische Beschriftungen
  const dsel = $("druck-option-select");
  const vorher = dsel.value;
  dsel.innerHTML = "";
  for (const p of db.getAlleProjekte()) {
    dsel.appendChild(new Option(`${p.nummer}: ${p.projektname}`, p.nummer));
  }
  if (vorher) dsel.value = vorher;

  // Gruppen-Auswahl für den Einzel-Gruppendruck
  const gsel = $("druck-gruppe-select");
  const gvorher = gsel.value;
  gsel.innerHTML = "";
  for (const name of druck.gruppenNamen()) {
    gsel.appendChild(new Option(`${k.stufe_label} ${name}`, name));
  }
  if (gvorher) gsel.value = gvorher;

  $("btn-druck-optionen").textContent =
    `Gesamtliste nach ${pluralDativ(k.projekt_label)}`;

  renderAenderungen();
}

// ── Solver ───────────────────────────────────────────────────────────────────
async function starteZuteilung(variante) {
  const statusEl = $("solver-status");
  statusEl.hidden = false;
  statusEl.classList.remove("fehler");
  const buttons = ["btn-algo-a", "btn-algo-b", "btn-algo-c", "btn-zuteilung-aufheben"];
  for (const id of buttons) $(id).disabled = true;
  try {
    const { dbBytes, statistik } = await solver.zuteilen(
      variante, db.exportiereBytes(), (t) => { statusEl.textContent = t; }
    );
    await db.ersetzeAusBytes(dbBytes);
    setzeDirty(true);
    const wt = statistik.wunsch_treffer;
    const teile = [];
    for (const rang of Object.keys(wt).sort()) {
      if (rang === "0") continue;
      if (wt[rang]) teile.push(`Wunsch ${rang}: ${wt[rang]}`);
    }
    statusEl.textContent =
      `Zuteilung (Algorithmus ${variante.toUpperCase()}) abgeschlossen — ` +
      `${statistik.gesamt} Teilnehmer/innen verarbeitet.\n` +
      `${teile.join(" · ")}${wt["0"] ? ` · ohne Zuteilung: ${wt["0"]}` : ""}`;
    renderZuteilung();
  } catch (e) {
    statusEl.classList.add("fehler");
    statusEl.textContent = "Fehler bei der Zuteilung: " + e.message;
  } finally {
    for (const id of buttons) $(id).disabled = false;
    aktualisiereKopf();
  }
}

// ── Datei-Operationen ────────────────────────────────────────────────────────
const KANN_FS_API = "showSaveFilePicker" in window;

async function speichern(immerDialog = false) {
  const bytes = db.exportiereBytes();
  if (KANN_FS_API) {
    try {
      if (!dateiHandle || immerDialog) {
        dateiHandle = await window.showSaveFilePicker({
          suggestedName: dateiname || "planungsmappe.plf",
          types: [{ description: "Planungsmappe", accept: { "application/octet-stream": [".plf"] } }],
        });
      }
      const w = await dateiHandle.createWritable();
      await w.write(bytes);
      await w.close();
      dateiname = dateiHandle.name;
      setzeDirty(false);
      aktualisiereKopf();
      status(`Gespeichert: ${dateiname}`);
      return;
    } catch (e) {
      if (e.name === "AbortError") return; // Nutzer hat abgebrochen
      throw e;
    }
  }
  // Fallback (Firefox/Safari): Download
  const blob = new Blob([bytes], { type: "application/octet-stream" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = dateiname || "planungsmappe.plf";
  a.click();
  URL.revokeObjectURL(url);
  setzeDirty(false);
  aktualisiereKopf();
  status(`Heruntergeladen: ${a.download} (Browser ohne direkten Dateizugriff)`);
}

async function neueMappe() {
  if (dirty && !confirm("Ungespeicherte Änderungen verwerfen?")) return;
  await db.neueMappe();
  dateiname = "planungsmappe.plf";
  dateiHandle = null;
  tnMarkiert.clear(); optMarkiert.clear();
  setzeDirty(false);
  renderAlles();
  status("Neue, leere Planungsmappe angelegt (Desktop-kompatibles .plf-Schema).");
  // Mehrstufigen Einrichtungsassistenten anbieten (wie am Desktop)
  zeigeEinrichtungsassistent();
}

async function oeffneDatei(file) {
  try {
    const bytes = await file.arrayBuffer();
    await db.oeffneMappe(bytes);
    dateiname = file.name;
    dateiHandle = null; // Handle nur über FS-API-Speichern-Dialog
    tnMarkiert.clear(); optMarkiert.clear();
    setzeDirty(false);
    renderAlles();
    status(`Geöffnet: ${file.name}`);
  } catch (e) {
    alert("Öffnen fehlgeschlagen: " + e.message);
  }
}

function exportGesamtCsv() {
  const k = db.getFeldkonfig();
  const tnExtras = aktiveExtras(k, "extra");
  const projekte = Object.fromEntries(db.getAlleProjekte().map((p) => [p.nummer, p]));
  const headers = ["Name", k.stufe_label, k.stufenzusatz_label,
                   ...tnExtras.map((e) => e.label),
                   `${k.projekt_label}-Nr.`, k.projekt_label];
  const rows = db.getAlleTeilnehmer().map((t) => [
    `${t.nachname}, ${t.vorname}`, t.stufe, t.stufenzusatz,
    ...tnExtras.map((e) => t[e.key] || ""),
    t.projekt || 0, t.projekt ? (projekte[t.projekt]?.projektname ?? "?") : "",
  ]);
  downloadText("gesamtliste.csv", alsCsv(headers, rows));
  status("Gesamtliste als CSV exportiert.");
}

/** Wunschlisten-Vorlage zum externen Ausfüllen (Tabellen-Assistent, Schritt 3):
 *  Grunddaten + Wunschspalten (aktuelle Werte, meist leer). proGruppe = true →
 *  je Gruppe (Stufe+Zusatz) eine eigene Datei. Gibt die Dateianzahl zurück. */
function exportWunschlisten(proGruppe) {
  const k = db.getFeldkonfig();
  const mw = k.max_wuensche;
  const tnExtras = aktiveExtras(k, "extra");
  const headers = ["Nachname", "Vorname", k.stufe_label, k.stufenzusatz_label,
                   ...tnExtras.map((e) => e.label)];
  for (let i = 1; i <= mw; i++) headers.push(`Wunsch ${i}`);
  const zeileVon = (t) => [
    t.nachname, t.vorname, t.stufe, t.stufenzusatz,
    ...tnExtras.map((e) => t[e.key] || ""),
    ...Array.from({ length: mw }, (_, i) => t[`wunsch_${i + 1}`] || ""),
  ];
  const tn = db.getAlleTeilnehmer();
  if (!proGruppe) {
    downloadText("wunschlisten.csv", alsCsv(headers, tn.map(zeileVon)));
    status("Wunschlisten-Vorlage als CSV exportiert.");
    return 1;
  }
  const gruppen = new Map();
  for (const t of tn) {
    const zusatz = t.stufenzusatz && t.stufenzusatz !== "-" ? t.stufenzusatz : "";
    const key = `${t.stufe}${zusatz}`;
    if (!gruppen.has(key)) gruppen.set(key, []);
    gruppen.get(key).push(t);
  }
  let n = 0;
  for (const [name, mitglieder] of gruppen) {
    const sicher = name.replace(/[^0-9A-Za-zÄÖÜäöüß.-]+/g, "_") || "gruppe";
    downloadText(`wunschliste_${sicher}.csv`, alsCsv(headers, mitglieder.map(zeileVon)));
    n++;
  }
  status(`Wunschlisten-Vorlage: ${n} Gruppendatei(en) exportiert.`);
  return n;
}

/** Datei-Öffnen-Dialog auslösen (für den Einrichtungsassistenten). */
function oeffneDateiPicker() { $("datei-input").click(); }

// ── Bezeichnungen anpassen ───────────────────────────────────────────────────
function zeigeLabelsDialog(onClose) {
  const k = db.getFeldkonfig();
  $("lbl-projekt").value = k.projekt_label;
  $("lbl-stufe").value = k.stufe_label;
  $("lbl-zusatz").value = k.stufenzusatz_label;
  $("lbl-leitung").value = k.leitung_label;
  $("lbl-maxw").value = String(k.max_wuensche);
  for (let i = 1; i <= 3; i++) {
    $(`lbl-tn-extra${i}`).value = k[`extra_${i}_label`] || "";
    $(`lbl-opt-extra${i}`).value = k[`projekt_extra_${i}_label`] || "";
  }
  // Assistenten können auf das Schließen reagieren (Statuszeile aktualisieren).
  if (typeof onClose === "function") {
    $("dlg-labels").addEventListener("close", () => onClose(), { once: true });
  }
  $("dlg-labels").showModal();
}

function speichereLabels() {
  const k = db.getFeldkonfig();
  const neuLeitung = $("lbl-leitung").value.trim();
  if (k.leitung_label && !neuLeitung) {
    // Datenschutz wie in der Desktop-App: Deaktivieren der Leitungsspalte
    // löscht die eingetragenen Namen vollständig, nicht nur die Anzeige.
    if (!confirm(
      "Die Leitungsspalte wird ausgeblendet und die eingetragenen Namen " +
      "werden aus Datenschutzgründen vollständig gelöscht. Fortfahren?")) {
      return;
    }
    db.loescheLeitungDaten();
  }
  db.setFeldkonfig({
    projekt_label: $("lbl-projekt").value.trim() || "Option",
    stufe_label: $("lbl-stufe").value.trim() || "Gruppenbereich",
    stufenzusatz_label: $("lbl-zusatz").value.trim() || "Gruppenzusatz",
    leitung_label: neuLeitung,
    max_wuensche: $("lbl-maxw").value,
    extra_1_label: $("lbl-tn-extra1").value.trim(),
    extra_2_label: $("lbl-tn-extra2").value.trim(),
    extra_3_label: $("lbl-tn-extra3").value.trim(),
    projekt_extra_1_label: $("lbl-opt-extra1").value.trim(),
    projekt_extra_2_label: $("lbl-opt-extra2").value.trim(),
    projekt_extra_3_label: $("lbl-opt-extra3").value.trim(),
  });
  $("dlg-labels").close();
  setzeDirty(true);
  renderAlles();
  status("Bezeichnungen übernommen — sie gelten auch in der Desktop-App.");
}

// ── Beispieldaten ────────────────────────────────────────────────────────────
async function ladeBeispieldaten() {
  if (dirty && !confirm("Ungespeicherte Änderungen verwerfen?")) return;
  status("Lade Beispieldaten …");
  try {
    const resp = await fetch("../beispieldaten/planungsmappe_beispiel.plf");
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    await db.oeffneMappe(await resp.arrayBuffer());
    dateiname = "beispiel_planungsmappe.plf";
    dateiHandle = null;
    tnMarkiert.clear(); optMarkiert.clear();
    setzeDirty(false);
    renderAlles();
    status("Beispieldaten geladen — zum Ausprobieren; „Speichern als“ legt eine eigene Kopie an.");
  } catch (e) {
    alert("Beispieldaten konnten nicht geladen werden: " + e.message);
    status("Bereit.");
  }
}

// ── CSV-Import ───────────────────────────────────────────────────────────────
let importArt = "teilnehmer";
let importOnDone = null;   // optionaler Callback (Assistenten), erhält Anzahl

function starteImport(art, onDone = null) {
  importArt = art;
  importOnDone = onDone;
  // Mehrdatei-Zusammenführung nur für Teilnehmerlisten (wie am Desktop):
  // dort kommen Wunschlisten oft je Gruppe als eigene Datei zurück.
  $("import-datei").multiple = art === "teilnehmer";
  $("import-datei").click();
}

// Dateien liest tabellendatei.js (CSV direkt, xlsx/ods via SheetJS lazy).

// ── Nachbearbeitungsmodus ────────────────────────────────────────────────────
function toggleBearbeitungsmodus() {
  if (db.istBearbeitungsmodus()) {
    if (!confirm(
      "Bearbeitungsmodus ausschalten?\n\n" +
      "Der aktuelle Zuteilungsstand gilt damit als fest. Alle " +
      "Änderungsmarkierungen und durchgestrichenen Einträge verschwinden " +
      "endgültig.")) return;
    db.bearbeitungsmodusAus();
    status("Bearbeitungsmodus beendet — der aktuelle Stand gilt als fest.");
  } else {
    if (!confirm(
      "Bearbeitungsmodus einschalten?\n\n" +
      "Der aktuelle Zuteilungsstand wird als Ausgangsstand festgehalten. " +
      "Ab jetzt werden alle Umverteilungen sichtbar gemacht — in der " +
      "Teilnehmertabelle, in der Übersicht der Änderungen und in den " +
      "gedruckten Gruppenlisten.\n\n" +
      "Die Raumzuteilung und alle anderen Funktionen bleiben unberührt.")) return;
    db.bearbeitungsmodusEin();
    status("Bearbeitungsmodus aktiv.");
  }
  setzeDirty(true);
  renderAlles();
}

function renderAenderungen() {
  const k = db.getFeldkonfig();
  const aktiv = db.istBearbeitungsmodus();
  const thead = $("aenderungen-tabelle").querySelector("thead");
  const tbody = $("aenderungen-tabelle").querySelector("tbody");
  thead.innerHTML = "";
  tbody.innerHTML = "";
  if (!aktiv) {
    $("bm-anzahl").textContent = "";
    return;
  }
  const projekte = Object.fromEntries(db.getAlleProjekte().map((p) => [p.nummer, p]));
  const nameVon = (nr) => nr ? `${nr}: ${projekte[nr]?.projektname ?? "?"}` : "–";
  const liste = db.getAenderungen();
  $("bm-anzahl").textContent = liste.length
    ? `${liste.length} Umverteilung(en) seit Modus-Start`
    : "aktiv — noch keine Änderung";
  if (!liste.length) return;
  kopfzeile(thead, ["Name", k.stufe_label, "Vorher", "Jetzt", "Wunschrang erhalten"]);
  for (const t of liste) {
    const wuensche = [t.wunsch_1, t.wunsch_2, t.wunsch_3, t.wunsch_4, t.wunsch_5]
      .slice(0, k.max_wuensche).filter((w) => w !== 0);
    const rangIdx = wuensche.indexOf(t.projekt);
    const rang = !t.projekt ? "–"
      : rangIdx >= 0 ? `Wunsch ${rangIdx + 1}` : "kein Wunsch";
    const zusatz = t.stufenzusatz && t.stufenzusatz !== "-" ? t.stufenzusatz : "";
    const tr = document.createElement("tr");
    tr.appendChild(textZelle(`${t.nachname}, ${t.vorname}`));
    tr.appendChild(textZelle(`${t.stufe}${zusatz}`));
    tr.appendChild(textZelle(nameVon(t.projekt_baseline)));
    tr.appendChild(textZelle(nameVon(t.projekt)));
    tr.appendChild(textZelle(rang));
    tbody.appendChild(tr);
  }
}

function exportAenderungen() {
  const k = db.getFeldkonfig();
  const liste = db.getAenderungen();
  if (!liste.length) {
    alert(db.istBearbeitungsmodus()
      ? "Noch keine Umverteilungen seit Modus-Start."
      : "Der Bearbeitungsmodus ist nicht aktiv.");
    return;
  }
  const projekte = Object.fromEntries(db.getAlleProjekte().map((p) => [p.nummer, p]));
  const nameVon = (nr) => nr ? `${nr}: ${projekte[nr]?.projektname ?? "?"}` : "–";
  const headers = ["Name", k.stufe_label, "Vorher", "Jetzt", "Wunschrang erhalten"];
  const rows = liste.map((t) => {
    const wuensche = [t.wunsch_1, t.wunsch_2, t.wunsch_3, t.wunsch_4, t.wunsch_5]
      .slice(0, k.max_wuensche).filter((w) => w !== 0);
    const rangIdx = wuensche.indexOf(t.projekt);
    const rang = !t.projekt ? "–" : rangIdx >= 0 ? `Wunsch ${rangIdx + 1}` : "kein Wunsch";
    const zusatz = t.stufenzusatz && t.stufenzusatz !== "-" ? t.stufenzusatz : "";
    return [`${t.nachname}, ${t.vorname}`, `${t.stufe}${zusatz}`,
            nameVon(t.projekt_baseline), nameVon(t.projekt), rang];
  });
  downloadText("aenderungen.csv", alsCsv(headers, rows));
  status(`Änderungsliste als CSV exportiert (${rows.length}).`);
}

// ── Qualitätsprüfung ─────────────────────────────────────────────────────────
let letzteQualiEintraege = [];   // Ergebnis des letzten „Jetzt prüfen"-Laufs

function gefilterteQuali() {
  const f = $("quali-filter").value;
  return f === "alle" ? letzteQualiEintraege
    : letzteQualiEintraege.filter((e) => e.key === f);
}

function zeigeQualitaet() {
  letzteQualiEintraege = pruefeQualitaet();
  $("quali-details").open = true;
  renderQualiTabelle();
}

function renderQualiTabelle() {
  const eintraege = gefilterteQuali();
  kopfzeile($("quali-tabelle").querySelector("thead"),
    ["", "Kategorie", "Name", "Gruppe", "Details"]);
  const tbody = $("quali-tabelle").querySelector("tbody");
  tbody.innerHTML = "";
  for (const e of eintraege) {
    const tr = document.createElement("tr");
    const tdI = textZelle(e.icon);
    tdI.className = "icon";
    tr.appendChild(tdI);
    tr.appendChild(textZelle(e.kategorie));
    tr.appendChild(textZelle(e.name));
    tr.appendChild(textZelle(e.gruppe));
    tr.appendChild(textZelle(e.details));
    tbody.appendChild(tr);
  }
  const gesamt = letzteQualiEintraege.length;
  const gezeigt = eintraege.length;
  $("quali-zusammenfassung").textContent =
    gesamt === 0 ? "Keine Auffälligkeiten ✓"
    : $("quali-filter").value === "alle" ? `${gesamt} Hinweis(e)`
    : `${gezeigt} von ${gesamt} Hinweis(en)`;
}

function exportQualitaet() {
  if (!letzteQualiEintraege.length) {
    alert('Bitte zuerst „Jetzt prüfen" ausführen.');
    return;
  }
  const eintraege = gefilterteQuali();
  const headers = ["Kategorie", "Name", "Gruppe", "Details"];
  const rows = eintraege.map((e) => [e.kategorie, e.name, e.gruppe, e.details]);
  downloadText("qualitaetspruefung.csv", alsCsv(headers, rows));
  status(`Qualitätsprüfung als CSV exportiert (${rows.length} Einträge).`);
}

// ── Verkabelung ──────────────────────────────────────────────────────────────
function init() {
  aktualisiereKopf();

  for (const btn of document.querySelectorAll(".tab")) {
    btn.addEventListener("click", () => zeigeTab(btn.dataset.tab));
  }

  $("btn-neu").addEventListener("click", neueMappe);
  $("btn-oeffnen").addEventListener("click", () => $("datei-input").click());
  $("datei-input").addEventListener("change", (e) => {
    if (e.target.files[0]) oeffneDatei(e.target.files[0]);
    e.target.value = "";
  });
  $("btn-speichern").addEventListener("click", () => speichern(false));
  $("btn-speichern-als").addEventListener("click", () => speichern(true));

  $("btn-tn-neu").addEventListener("click", () => {
    db.insertTeilnehmer();
    setzeDirty(true);
    renderTeilnehmer();
  });
  $("btn-tn-loeschen").addEventListener("click", () => {
    if (!tnMarkiert.size) { alert("Bitte zuerst Zeilen ankreuzen."); return; }
    if (!confirm(`${tnMarkiert.size} Teilnehmer/in(nen) löschen?`)) return;
    db.deleteTeilnehmer([...tnMarkiert]);
    tnMarkiert.clear();
    setzeDirty(true);
    renderTeilnehmer();
  });
  $("tn-suche").addEventListener("input", renderTeilnehmer);

  $("btn-opt-neu").addEventListener("click", () => {
    db.insertProjekt(db.naechsteProjektnummer());
    setzeDirty(true);
    renderOptionen();
  });
  $("btn-opt-loeschen").addEventListener("click", () => {
    if (!optMarkiert.size) { alert("Bitte zuerst Zeilen ankreuzen."); return; }
    if (!confirm(`${optMarkiert.size} Option(en) löschen?`)) return;
    db.deleteProjekte([...optMarkiert]);
    optMarkiert.clear();
    setzeDirty(true);
    renderOptionen();
  });

  $("btn-algo-a").addEventListener("click", () => starteZuteilung("a"));
  $("btn-algo-b").addEventListener("click", () => starteZuteilung("b"));
  $("btn-algo-c").addEventListener("click", () => starteZuteilung("c"));
  $("btn-zuteilung-aufheben").addEventListener("click", () => {
    db.zuteilungAufheben();
    setzeDirty(true);
    renderZuteilung();
    status("Automatische Zuweisungen aufgehoben (fixierte bleiben).");
  });

  $("btn-csv-gesamt").addEventListener("click", exportGesamtCsv);

  // Bezeichnungen-Dialog
  $("btn-labels").addEventListener("click", zeigeLabelsDialog);
  $("lbl-ok").addEventListener("click", speichereLabels);
  $("lbl-abbrechen").addEventListener("click", () => $("dlg-labels").close());

  // Beispieldaten
  $("btn-beispiel").addEventListener("click", ladeBeispieldaten);

  // CSV-Import (Teilnehmer/innen + Optionen)
  $("btn-tn-import").addEventListener("click", () => starteImport("teilnehmer"));
  $("btn-opt-import").addEventListener("click", () => starteImport("optionen"));
  $("import-datei").addEventListener("change", async (e) => {
    const files = [...e.target.files];
    e.target.value = "";
    const onDone = importOnDone; importOnDone = null; // Callback für diesen Lauf
    if (!files.length) return;
    let text;
    try {
      if (files.length === 1) {
        text = await liesTabellenDatei(files[0], status);
      } else {
        // Mehrdatei-Zusammenführung: Spalten anhand ihres Namens zuordnen,
        // Reihenfolge der ersten Datei bleibt maßgeblich (wie am Desktop).
        status(`Führe ${files.length} Dateien zusammen …`);
        const texte = [];
        for (const f of files) texte.push(await liesTabellenDatei(f, status));
        const { headers, rows } = mergeTabellen(texte);
        if (!headers.length) throw new Error("Keine Datenzeilen gefunden.");
        text = alsCsv(headers, rows).replace(/^\uFEFF/, "");
      }
    } catch (fehler) {
      alert("Datei konnte nicht gelesen werden: " + fehler.message);
      status("Bereit.");
      return;
    }
    const quelle = files.length === 1 ? files[0].name : `${files.length} Dateien zusammengeführt`;
    oeffneImportDialog(importArt, text, (anzahl) => {
      setzeDirty(true);
      renderAlles();
      status(`${anzahl} Datensätze importiert (${quelle}).`);
      if (onDone) onDone(anzahl);
    });
  });

  // Qualitätsprüfung (einklappbar, Filter, CSV-Export)
  $("btn-quali").addEventListener("click", zeigeQualitaet);
  $("quali-filter").addEventListener("change", renderQualiTabelle);
  $("btn-quali-export").addEventListener("click", exportQualitaet);

  // Listen & Druck (Browser-Druckdialog, dort auch "Als PDF speichern").
  // Vor jedem Druck erscheint die Feldauswahl (wie am Desktop).
  const druckeMitAuswahl = async (titel, gruppen) => {
    if (!gruppen.length) { alert("Keine Daten zum Drucken vorhanden."); return; }
    const kept = await waehleSpalten(gruppen[0].headers);
    if (!kept) return;
    druck.drucke(titel, filterGruppen(gruppen, kept));
  };
  $("btn-druck-optionen").addEventListener("click", () => {
    const k = db.getFeldkonfig();
    druckeMitAuswahl(`Gesamtliste nach ${pluralDativ(k.projekt_label)}`,
                     druck.gesamtNachOptionen());
  });
  $("btn-druck-gruppen").addEventListener("click", () => {
    druckeMitAuswahl("Gesamtliste nach Gruppen", druck.gesamtNachGruppen());
  });
  $("btn-druck-einzeloption").addEventListener("click", () => {
    const nr = parseInt($("druck-option-select").value, 10);
    if (!nr) return;
    const k = db.getFeldkonfig();
    druckeMitAuswahl(`Teilnehmerliste — ${k.projekt_label} ${nr}`,
                     druck.einzelOption(nr));
  });
  $("btn-druck-einzelgruppe").addEventListener("click", () => {
    const name = $("druck-gruppe-select").value;
    if (!name) return;
    const k = db.getFeldkonfig();
    druckeMitAuswahl(`Gruppenliste — ${k.stufe_label} ${name}`,
                     druck.einzelGruppe(name));
  });

  // Nachbearbeitungsmodus
  $("btn-bearbeitungsmodus").addEventListener("click", toggleBearbeitungsmodus);
  $("btn-aenderungen-export").addEventListener("click", exportAenderungen);

  // Raumplan-Tab (eigenes Modul); der Raumlisten-Import nutzt den zentralen
  // Datei-Input hier in app.js
  initRaumplan({ setzeDirty, status });
  $("btn-raum-import").addEventListener("click", () => starteImport("raeume"));

  // Mehrstufige Assistenten (Einrichtung + Tabellen-Workflow)
  initAssistenten({
    status, renderAlles,
    zeigeLabelsDialog, starteImport, ladeBeispieldaten,
    oeffneDateiPicker, exportWunschlisten,
  });
  $("btn-tabellen").addEventListener("click", zeigeTabellenassistent);

  window.addEventListener("beforeunload", (e) => {
    if (dirty) { e.preventDefault(); e.returnValue = ""; }
  });

  status(KANN_FS_API
    ? "Bereit. Dieser Browser unterstützt direktes Speichern in Dateien."
    : "Bereit. Hinweis: Dieser Browser speichert über den Download-Ordner.");
}

init();
