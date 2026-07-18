/**
 * Wunschdetailfenster + Listenfenster — Web-Gegenstück zu ProjektDetailDialog
 * (dialoge.py) und ListenFenster (listenfenster.py):
 *
 *  - zeigeProjektdetails(nr): Statistik zu einer Option (Nachfrage/Zuteilung je
 *    Wunschrang) mit Wunschauswertungs- und Teilnehmerliste.
 *  - zeigeWunschauswertung(nr, rang?): Namensliste aller Personen, die die
 *    Option (auf einem Rang) gewünscht haben.
 *  - zeigeTeilnehmerliste(nr): der Option zugeteilte Personen.
 *  - zeigeAenderungsuebersicht(): alle im Nachbearbeitungsmodus umverteilten
 *    Personen.
 *
 * Die Listenfenster bieten wie am Desktop: „fix zuweisen" (Klick auf eine
 * Person + Button oder Doppelklick), „Exportieren" (Export-Dialog mit Format,
 * Kopfzeile, Fußzeilendatum, Spaltenauswahl → CSV/xlsx/ods) und „Drucken"
 * (Feldauswahl → Browser-Druck).
 */

import * as db from "./db.js";
import * as druck from "./druck.js";
import { waehleSpalten, filterGruppen } from "./spaltenwahl.js";
import { zeigeExportDialog } from "./exportdialog.js";

const $ = (id) => document.getElementById(id);

// Von app.js injizierte Zuweisungsfunktion: zuweisen(teilnehmerId, onDone)
let zuweisenCb = null;
let statusCb = () => {};

export function initAuswertung({ zuweisen, status }) {
  zuweisenCb = zuweisen || null;
  statusCb = status || (() => {});
}

const gruppeText = (t) => {
  const zusatz = t.stufenzusatz && t.stufenzusatz !== "-" ? t.stufenzusatz : "";
  return `${t.stufe}${zusatz}`;
};
const wuenscheVon = (t) =>
  [t.wunsch_1, t.wunsch_2, t.wunsch_3, t.wunsch_4, t.wunsch_5];

// ── Generisches Listenfenster ────────────────────────────────────────────────

/**
 * @param {object} o  { titel, headers, rows, rowIds?, dateiBasis, refresh? }
 *   rowIds: Teilnehmer-IDs parallel zu rows → aktiviert „fix zuweisen".
 *   refresh: Funktion, die das Fenster nach einer Zuweisung neu aufbaut.
 */
function zeigeListenfenster({ titel, headers, rows, rowIds = null, dateiBasis, refresh = null }) {
  const dlg = $("dlg-liste");
  const k = db.getFeldkonfig();
  dlg.innerHTML = "";

  const h2 = document.createElement("h2");
  h2.textContent = titel;
  dlg.appendChild(h2);

  const info = document.createElement("p");
  info.className = "hinweis";
  info.textContent = rowIds
    ? `${rows.length} Eintrag/Einträge · Zeile anklicken und „fix zuweisen" ` +
      "oder Doppelklick auf eine Zeile."
    : `${rows.length} Eintrag/Einträge.`;
  dlg.appendChild(info);

  const scroll = document.createElement("div");
  scroll.className = "tabellen-scroll liste-scroll";
  const tbl = document.createElement("table");
  const thead = document.createElement("thead");
  const trh = document.createElement("tr");
  for (const h of headers) {
    const th = document.createElement("th"); th.textContent = h; trh.appendChild(th);
  }
  thead.appendChild(trh);
  tbl.appendChild(thead);
  const tbody = document.createElement("tbody");
  let gewaehlteZeile = -1;
  const trs = [];
  rows.forEach((row, idx) => {
    const tr = document.createElement("tr");
    for (const zelle of row) {
      const td = document.createElement("td"); td.textContent = zelle; tr.appendChild(td);
    }
    if (rowIds) {
      tr.classList.add("waehlbar");
      tr.addEventListener("click", () => {
        gewaehlteZeile = idx;
        trs.forEach((x) => x.classList.remove("markiert"));
        tr.classList.add("markiert");
      });
      tr.addEventListener("dblclick", () => zuweisenFuer(idx));
    }
    trs.push(tr);
    tbody.appendChild(tr);
  });
  tbl.appendChild(tbody);
  scroll.appendChild(tbl);
  dlg.appendChild(scroll);

  function zuweisenFuer(idx) {
    if (!zuweisenCb || !rowIds || idx < 0 || idx >= rowIds.length) return;
    zuweisenCb(rowIds[idx], () => { if (refresh) refresh(); });
  }

  // ── Buttons ──
  const btns = document.createElement("div");
  btns.className = "dialog-buttons";

  if (rowIds && zuweisenCb) {
    const bZuweisen = document.createElement("button");
    bZuweisen.textContent = `${k.projekt_label} fix zuweisen`;
    bZuweisen.addEventListener("click", () => {
      if (gewaehlteZeile < 0) { alert("Bitte zuerst eine Zeile anklicken."); return; }
      zuweisenFuer(gewaehlteZeile);
    });
    btns.appendChild(bZuweisen);
  }

  const bExport = document.createElement("button");
  bExport.textContent = "Export";
  bExport.disabled = !rows.length;
  bExport.addEventListener("click", () =>
    zeigeExportDialog({ titel, dateiBasis, gruppen: [{ titel, headers, rows }],
                        status: statusCb }));

  const bDruck = document.createElement("button");
  bDruck.textContent = "Drucken";
  bDruck.disabled = !rows.length;
  bDruck.addEventListener("click", async () => {
    const kept = await waehleSpalten(headers);
    if (!kept) return;
    druck.drucke(titel, filterGruppen([{ titel, headers, rows }], kept));
  });

  const bClose = document.createElement("button");
  bClose.className = "sekundaer";
  bClose.textContent = "Schließen";
  bClose.addEventListener("click", () => dlg.close());

  btns.append(bExport, bDruck, bClose);
  dlg.appendChild(btns);

  if (!dlg.open) dlg.showModal();
}

// ── Wunschauswertungsliste ───────────────────────────────────────────────────

export function zeigeWunschauswertung(nummer, rang = null) {
  const k = db.getFeldkonfig();
  const mw = k.max_wuensche;
  const projekte = Object.fromEntries(db.getAlleProjekte().map((p) => [p.nummer, p]));
  const p = projekte[nummer];
  const treffer = db.getWunschauswertung(nummer, rang);
  treffer.sort((a, b) =>
    `${a.t.stufe} ${a.t.nachname}`.localeCompare(`${b.t.stufe} ${b.t.nachname}`, "de", { numeric: true }));

  const headers = ["Name", k.stufe_label, "Wunschrang"];
  for (let i = 1; i <= mw; i++) headers.push(`W${i}`);
  headers.push("Zuteilung", "Fixiert");
  const rows = treffer.map(({ t, rang: r }) => [
    `${t.nachname}, ${t.vorname}`, gruppeText(t), `W${r}`,
    ...wuenscheVon(t).slice(0, mw),
    t.projekt ? `${t.projekt}: ${projekte[t.projekt]?.projektname ?? "?"}` : "–",
    t.fest_zugewiesen ? "✓" : "",
  ]);
  const rowIds = treffer.map(({ t }) => t.id);

  const rangTeil = rang ? ` · nur Wunsch ${rang}` : "";
  zeigeListenfenster({
    titel: `Wunschauswertung — ${nummer}: ${p?.projektname ?? "?"}${rangTeil}`,
    headers, rows, rowIds,
    dateiBasis: `wunschauswertung_${nummer}${rang ? "_w" + rang : ""}`,
    refresh: () => zeigeWunschauswertung(nummer, rang),
  });
}

// ── Teilnehmerliste (zugeteilte Personen) ────────────────────────────────────

export function zeigeTeilnehmerliste(nummer) {
  const k = db.getFeldkonfig();
  const projekte = Object.fromEntries(db.getAlleProjekte().map((p) => [p.nummer, p]));
  const p = projekte[nummer];
  const tn = db.getProjektteilnehmerliste(nummer);
  tn.sort((a, b) =>
    `${a.stufe} ${a.nachname}`.localeCompare(`${b.stufe} ${b.nachname}`, "de", { numeric: true }));

  const rangText = (t) => {
    const idx = wuenscheVon(t).indexOf(nummer);
    return idx >= 0 ? `W${idx + 1}` : "kein Wunsch";
  };
  const headers = ["Name", k.stufe_label, "Wunschrang erhalten", "Fixiert"];
  const rows = tn.map((t) => [
    `${t.nachname}, ${t.vorname}`, gruppeText(t), rangText(t),
    t.fest_zugewiesen ? "✓" : "",
  ]);
  zeigeListenfenster({
    titel: `Teilnehmerliste — ${nummer}: ${p?.projektname ?? "?"} (${tn.length})`,
    headers, rows, rowIds: tn.map((t) => t.id),
    dateiBasis: `teilnehmerliste_${nummer}`,
    refresh: () => zeigeTeilnehmerliste(nummer),
  });
}

// ── Übersicht der Änderungen (Nachbearbeitungsmodus) ─────────────────────────

export function zeigeAenderungsuebersicht() {
  const k = db.getFeldkonfig();
  const projekte = Object.fromEntries(db.getAlleProjekte().map((p) => [p.nummer, p]));
  const nameVon = (nr) => nr ? `${nr}: ${projekte[nr]?.projektname ?? "?"}` : "–";
  const liste = db.getAenderungen().slice().sort((a, b) =>
    `${a.stufe} ${a.nachname}`.localeCompare(`${b.stufe} ${b.nachname}`, "de", { numeric: true }));

  const headers = ["Name", k.stufe_label, k.stufenzusatz_label,
                   "Vorher", "Jetzt", "Wunschrang erhalten"];
  const rows = liste.map((t) => {
    const wuensche = wuenscheVon(t).slice(0, k.max_wuensche).filter((w) => w !== 0);
    const idx = wuensche.indexOf(t.projekt);
    const rang = !t.projekt ? "–" : idx >= 0 ? `W${idx + 1}` : "kein Wunsch";
    const zusatz = t.stufenzusatz && t.stufenzusatz !== "-" ? t.stufenzusatz : "";
    return [`${t.nachname}, ${t.vorname}`, t.stufe, zusatz,
            nameVon(t.projekt_baseline), nameVon(t.projekt), rang];
  });
  zeigeListenfenster({
    titel: `Übersicht der Änderungen (${rows.length})`,
    headers, rows, rowIds: liste.map((t) => t.id),
    dateiBasis: "aenderungsuebersicht",
    refresh: () => zeigeAenderungsuebersicht(),
  });
}

// ── Wunschdetailfenster ──────────────────────────────────────────────────────

export function zeigeProjektdetails(nummer) {
  const d = db.getProjektdetails(nummer);
  if (!d) return;
  const k = db.getFeldkonfig();
  const mw = k.max_wuensche;
  const p = d.projekt;
  const dlg = $("dlg-projektdetails");
  dlg.innerHTML = "";

  const h2 = document.createElement("h2");
  h2.textContent = `Wunschdetails — ${p.nummer}: ${p.projektname}`;
  dlg.appendChild(h2);

  const info = document.createElement("p");
  info.className = "hinweis";
  info.textContent =
    `Plätze: ${p.tnmin}–${p.tnmax}  ·  aktuell zugeteilt: ${d.anzahlZugeteilt}` +
    `  ·  insgesamt gewünscht: ${d.gesamtGewuenscht}×`;
  dlg.appendChild(info);

  // ── Nachfrage je Wunschrang (Doppelklick → Namensliste) ──
  const h3a = document.createElement("h3");
  h3a.textContent = "Wie oft gewünscht? (Doppelklick auf eine Zeile zeigt die Personen)";
  h3a.className = "detail-ueberschrift";
  dlg.appendChild(h3a);
  const t1 = document.createElement("table");
  t1.className = "kompakt";
  t1.innerHTML = "<thead><tr><th>Wunschrang</th><th>Anzahl</th></tr></thead>";
  const tb1 = document.createElement("tbody");
  for (let rang = 1; rang <= mw; rang++) {
    const n = d.wunschNachRang[rang] || 0;
    const tr = document.createElement("tr");
    tr.className = "klickbar";
    tr.title = "Doppelklick: Personen mit diesem Wunschrang anzeigen";
    tr.addEventListener("dblclick", () => zeigeWunschauswertung(nummer, rang));
    const td1 = document.createElement("td"); td1.textContent = `Wunsch ${rang}`;
    const td2 = document.createElement("td"); td2.textContent = String(n); td2.className = "zahl";
    tr.append(td1, td2);
    tb1.appendChild(tr);
  }
  t1.appendChild(tb1);
  dlg.appendChild(t1);

  // ── Zuteilung je Wunschrang ──
  const h3b = document.createElement("h3");
  h3b.textContent = "Zugeteilte Personen — mit welchem Wunschrang?";
  h3b.className = "detail-ueberschrift";
  dlg.appendChild(h3b);
  const t2 = document.createElement("table");
  t2.className = "kompakt";
  t2.innerHTML = "<thead><tr><th>Wunschrang</th><th>Anzahl Personen</th></tr></thead>";
  const tb2 = document.createElement("tbody");
  const zeilen = [];
  for (let rang = 1; rang <= mw; rang++) {
    const n = d.zuteilungNachRang[rang] || 0;
    if (n > 0) zeilen.push([`Wunsch ${rang}`, n]);
  }
  if (d.zuteilungOhneWunsch > 0)
    zeilen.push(["Ohne eigenen Wunsch (Ausweich-/Sonderzuteilung)", d.zuteilungOhneWunsch]);
  if (!zeilen.length) zeilen.push(["Noch niemand zugeteilt", "–"]);
  for (const [label, n] of zeilen) {
    const tr = document.createElement("tr");
    const td1 = document.createElement("td"); td1.textContent = label;
    const td2 = document.createElement("td"); td2.textContent = String(n); td2.className = "zahl";
    tr.append(td1, td2);
    tb2.appendChild(tr);
  }
  t2.appendChild(tb2);
  dlg.appendChild(t2);

  // ── Buttons ──
  const btns = document.createElement("div");
  btns.className = "dialog-buttons";
  const bWa = document.createElement("button");
  bWa.textContent = "Wunschauswertungsliste";
  bWa.addEventListener("click", () => zeigeWunschauswertung(nummer));
  const bTn = document.createElement("button");
  bTn.textContent = "Teilnehmerliste";
  bTn.addEventListener("click", () => zeigeTeilnehmerliste(nummer));
  const bClose = document.createElement("button");
  bClose.className = "sekundaer";
  bClose.textContent = "Schließen";
  bClose.addEventListener("click", () => dlg.close());
  btns.append(bWa, bTn, bClose);
  dlg.appendChild(btns);

  if (!dlg.open) dlg.showModal();
}
