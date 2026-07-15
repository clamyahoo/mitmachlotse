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
import { pruefeQualitaet } from "./quali.js";

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
                    "btn-labels", "btn-tn-import", "btn-opt-import",
                    "btn-quali", "btn-druck-optionen", "btn-druck-gruppen",
                    "btn-druck-einzeloption"]) {
    $(id).disabled = !offen;
  }
  $("tn-suche").disabled = !offen;
  $("druck-option-select").disabled = !offen;
  const darfZuteilen = offen && Kontext.darfZuteilen();
  for (const id of ["btn-algo-a", "btn-algo-b", "btn-algo-c"]) {
    $(id).disabled = !darfZuteilen;
  }
  if (!Kontext.darfOptionenBearbeiten()) {
    // Struktur-Eingriffe (Optionen, Import, Bezeichnungen) nur für Admin
    for (const id of ["btn-opt-neu", "btn-opt-loeschen", "btn-labels",
                      "btn-tn-import", "btn-opt-import"]) {
      $(id).disabled = true;
    }
  }
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

// ── Tab 1: Teilnehmer ────────────────────────────────────────────────────────
const tnMarkiert = new Set();

function renderTeilnehmer() {
  const k = db.getFeldkonfig();
  const mw = k.max_wuensche;
  const projekte = db.getAlleProjekte();
  const suchbegriff = $("tn-suche").value.trim().toLowerCase();

  const spalten = ["✓", "Nachname", "Vorname", k.stufe_label, k.stufenzusatz_label];
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
    tr.appendChild(textFeld("stufe"));
    tr.appendChild(textFeld("stufenzusatz"));

    for (let i = 1; i <= mw; i++) {
      const feld = `wunsch_${i}`;
      tr.appendChild(inputZelle("number", t[feld], (inp) => {
        db.updateTeilnehmerFeld(t.id, feld, parseInt(inp.value, 10) || 0);
        setzeDirty(true);
      }, { disabled: !darf }));
    }

    // Zuteilung: Auswahlliste 0 + alle Optionsnummern
    const tdProjekt = document.createElement("td");
    const sel = document.createElement("select");
    sel.disabled = !Kontext.darfZuteilen();
    const opt0 = new Option("0 – (keine)", 0, false, t.projekt === 0);
    sel.appendChild(opt0);
    for (const p of projekte) {
      sel.appendChild(new Option(
        `${p.nummer}: ${p.projektname}`, p.nummer, false, t.projekt === p.nummer
      ));
    }
    sel.addEventListener("change", () => {
      db.updateTeilnehmerFeld(t.id, "projekt", parseInt(sel.value, 10) || 0);
      setzeDirty(true);
      tr.querySelector(".fix-cb").disabled = sel.value === "0";
    });
    if (t.projekt === 0) tdProjekt.classList.add("warn");
    tdProjekt.appendChild(sel);
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

  const spalten = ["✓", "Nr."];
  if (mitLeitung) spalten.push(k.leitung_label);
  spalten.push(db.labelFormen(k.projekt_label).name,
               `${k.stufe_label} min`, `${k.stufe_label} max`,
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
  $("btn-druck-optionen").textContent =
    `Gesamtliste nach ${pluralDativ(k.projekt_label)}`;
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
  const projekte = Object.fromEntries(db.getAlleProjekte().map((p) => [p.nummer, p]));
  const headers = ["Name", k.stufe_label, k.stufenzusatz_label,
                   `${k.projekt_label}-Nr.`, k.projekt_label];
  const rows = db.getAlleTeilnehmer().map((t) => [
    `${t.nachname}, ${t.vorname}`, t.stufe, t.stufenzusatz,
    t.projekt || 0, t.projekt ? (projekte[t.projekt]?.projektname ?? "?") : "",
  ]);
  downloadText("gesamtliste.csv", alsCsv(headers, rows));
  status("Gesamtliste als CSV exportiert.");
}

// ── Bezeichnungen anpassen ───────────────────────────────────────────────────
function zeigeLabelsDialog() {
  const k = db.getFeldkonfig();
  $("lbl-projekt").value = k.projekt_label;
  $("lbl-stufe").value = k.stufe_label;
  $("lbl-zusatz").value = k.stufenzusatz_label;
  $("lbl-leitung").value = k.leitung_label;
  $("lbl-maxw").value = String(k.max_wuensche);
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

function starteImport(art) {
  importArt = art;
  $("import-datei").click();
}

async function liesDateiText(file) {
  // UTF-8 zuerst; Windows-CSVs (Excel) sind oft cp1252 → Fallback
  const buf = await file.arrayBuffer();
  try { return new TextDecoder("utf-8", { fatal: true }).decode(buf); }
  catch { return new TextDecoder("windows-1252").decode(buf); }
}

// ── Qualitätsprüfung ─────────────────────────────────────────────────────────
function zeigeQualitaet() {
  const eintraege = pruefeQualitaet();
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
  $("quali-zusammenfassung").textContent = eintraege.length
    ? `${eintraege.length} Hinweis(e)`
    : "Keine Auffälligkeiten ✓";
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
    const file = e.target.files[0];
    e.target.value = "";
    if (!file) return;
    const text = await liesDateiText(file);
    oeffneImportDialog(importArt, text, (anzahl) => {
      setzeDirty(true);
      renderAlles();
      status(`${anzahl} Datensätze importiert (${file.name}).`);
    });
  });

  // Qualitätsprüfung
  $("btn-quali").addEventListener("click", zeigeQualitaet);

  // Listen & Druck (Browser-Druckdialog, dort auch "Als PDF speichern")
  $("btn-druck-optionen").addEventListener("click", () => {
    const k = db.getFeldkonfig();
    druck.drucke(`Gesamtliste nach ${pluralDativ(k.projekt_label)}`,
                 druck.gesamtNachOptionen());
  });
  $("btn-druck-gruppen").addEventListener("click", () => {
    druck.drucke("Gesamtliste nach Gruppen", druck.gesamtNachGruppen());
  });
  $("btn-druck-einzeloption").addEventListener("click", () => {
    const nr = parseInt($("druck-option-select").value, 10);
    if (!nr) return;
    const k = db.getFeldkonfig();
    druck.drucke(`Teilnehmerliste — ${k.projekt_label} ${nr}`,
                 druck.einzelOption(nr));
  });

  window.addEventListener("beforeunload", (e) => {
    if (dirty) { e.preventDefault(); e.returnValue = ""; }
  });

  status(KANN_FS_API
    ? "Bereit. Dieser Browser unterstützt direktes Speichern in Dateien."
    : "Bereit. Hinweis: Dieser Browser speichert über den Download-Ordner.");
}

init();
