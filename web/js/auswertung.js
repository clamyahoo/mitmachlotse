/**
 * Wunschdetailfenster + Listenfenster — Web-Gegenstück zu ProjektDetailDialog
 * (dialoge.py) und den Listenfenstern (listenfenster.py):
 *
 *  - zeigeProjektdetails(nr): Statistik zu einer Option — wie oft insgesamt und
 *    je Wunschrang gewünscht, und mit welchem Wunschrang die zugeteilten
 *    Personen sie bekommen haben. Doppelklick auf eine Wunschrang-Zeile öffnet
 *    die Namensliste; Buttons öffnen Wunschauswertungs- und Teilnehmerliste.
 *  - zeigeWunschauswertung(nr, rang?): Namensliste aller Personen, die die
 *    Option (auf einem bestimmten Rang) gewünscht haben.
 *  - zeigeTeilnehmerliste(nr): der Option aktuell zugeteilte Personen.
 *
 * Die Listenfenster lassen sich als CSV exportieren. Untergeordnete Fenster
 * stapeln modal über dem Detailfenster.
 */

import * as db from "./db.js";
import { alsCsv, downloadText } from "./csv.js";

const $ = (id) => document.getElementById(id);

const gruppeText = (t) => {
  const zusatz = t.stufenzusatz && t.stufenzusatz !== "-" ? t.stufenzusatz : "";
  return `${t.stufe}${zusatz}`;
};
const wuenscheVon = (t) =>
  [t.wunsch_1, t.wunsch_2, t.wunsch_3, t.wunsch_4, t.wunsch_5];

// ── Generisches Listenfenster (Titel + Tabelle + CSV-Export + Schließen) ─────

function zeigeListe(dlgId, titel, headers, rows, dateiname) {
  const dlg = $(dlgId);
  dlg.innerHTML = "";

  const h2 = document.createElement("h2");
  h2.textContent = titel;
  dlg.appendChild(h2);

  const info = document.createElement("p");
  info.className = "hinweis";
  info.textContent = `${rows.length} Eintrag/Einträge.`;
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
  for (const row of rows) {
    const tr = document.createElement("tr");
    for (const zelle of row) {
      const td = document.createElement("td"); td.textContent = zelle; tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  tbl.appendChild(tbody);
  scroll.appendChild(tbl);
  dlg.appendChild(scroll);

  const btns = document.createElement("div");
  btns.className = "dialog-buttons";
  const bExport = document.createElement("button");
  bExport.textContent = "Als CSV exportieren";
  bExport.disabled = !rows.length;
  bExport.addEventListener("click", () =>
    downloadText(dateiname, alsCsv(headers, rows)));
  const bClose = document.createElement("button");
  bClose.className = "sekundaer";
  bClose.textContent = "Schließen";
  bClose.addEventListener("click", () => dlg.close());
  btns.append(bExport, bClose);
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
    `${t.nachname}, ${t.vorname}`, gruppeText(t), `Wunsch ${r}`,
    ...wuenscheVon(t).slice(0, mw),
    t.projekt ? `${t.projekt}: ${projekte[t.projekt]?.projektname ?? "?"}` : "–",
    t.fest_zugewiesen ? "✓" : "",
  ]);

  const rangTeil = rang ? ` · nur Wunsch ${rang}` : "";
  zeigeListe("dlg-liste",
    `Wunschauswertung — ${nummer}: ${p?.projektname ?? "?"}${rangTeil}`,
    headers, rows, `wunschauswertung_${nummer}${rang ? "_w" + rang : ""}.csv`);
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
    return idx >= 0 ? `Wunsch ${idx + 1}` : "kein Wunsch";
  };
  const headers = ["Name", k.stufe_label, "Wunschrang erhalten", "Fixiert"];
  const rows = tn.map((t) => [
    `${t.nachname}, ${t.vorname}`, gruppeText(t), rangText(t),
    t.fest_zugewiesen ? "✓" : "",
  ]);
  zeigeListe("dlg-liste",
    `Teilnehmerliste — ${nummer}: ${p?.projektname ?? "?"} (${tn.length})`,
    headers, rows, `teilnehmerliste_${nummer}.csv`);
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
