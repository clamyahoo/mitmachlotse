/**
 * Export-Dialog für Listen — Web-Gegenstück zu FensterExportDialog +
 * SpaltenauswahlDialog(mit_kopfzeile) der Desktop-App: Format wählen
 * (Excel/ODS/CSV/PDF), Kopfzeile (Titel) und „Datum in der Fußzeile"
 * festlegen, Spalten auswählen. Erzeugt die Datei und lädt sie herunter;
 * PDF läuft über den Browser-Druck (dort „Als PDF speichern").
 *
 * Nimmt Gruppen entgegen ([{titel, headers, rows}]) — für einfache Listen mit
 * genau einer Gruppe, für Gesamtlisten mit mehreren (je Option/Gruppe eine).
 * rows dürfen Arrays oder {klasse, zellen} sein (Nachbearbeitungs-Marker).
 */

import { alsCsv, downloadText } from "./csv.js";
import { ladeSheetJs } from "./tabellendatei.js";
import { filterGruppen } from "./spaltenwahl.js";
import * as druck from "./druck.js";

const $ = (id) => document.getElementById(id);

const FORMATE = [
  { key: "xlsx", label: "Excel-Datei (.xlsx)", ext: ".xlsx" },
  { key: "ods",  label: "OpenDocument-Tabelle (.ods)", ext: ".ods" },
  { key: "csv",  label: "CSV-Datei (.csv)", ext: ".csv" },
  { key: "pdf",  label: "PDF (über den Druckdialog)", ext: ".pdf" },
];

const zellenVon = (row) => (Array.isArray(row) ? row : row.zellen);

function datumsText() {
  return new Date().toLocaleDateString("de-DE",
    { year: "numeric", month: "long", day: "numeric" });
}

function sichererName(basis, ext) {
  const s = String(basis).replace(/[^0-9A-Za-zÄÖÜäöüß _-]+/g, "_")
    .trim().replace(/\s+/g, "_") || "liste";
  return s + ext;
}

/**
 * @param {object} o
 *   titel:            Kopfzeilen-Vorgabe / Fallback-Dateiname
 *   dateiBasis:       Vorschlag für den Dateinamen (ohne Endung)
 *   gruppen:          [{titel, headers, rows}] — mind. eine Gruppe
 *   kopfzeileVorgabe: Vorbelegung der Kopfzeile (Default: titel)
 *   datumVorgabe:     Datum-Fußzeile vorangehakt (Default: true)
 *   status:           optionale Statusausgabe
 */
export function zeigeExportDialog({ titel, dateiBasis, gruppen, kopfzeileVorgabe,
                                    datumVorgabe = true, status = () => {} }) {
  const headers = gruppen[0]?.headers || [];
  const dlg = $("dlg-export");
  dlg.innerHTML = "";

  const h2 = document.createElement("h2");
  h2.textContent = "Liste exportieren";
  dlg.appendChild(h2);

  // ── Format ──
  const fmtGroup = document.createElement("fieldset");
  fmtGroup.className = "export-gruppe";
  fmtGroup.innerHTML = "<legend>Format</legend>";
  for (const f of FORMATE) {
    const lab = document.createElement("label");
    lab.className = "export-radio";
    const rb = document.createElement("input");
    rb.type = "radio"; rb.name = "export-fmt"; rb.value = f.key;
    if (f.key === "xlsx") rb.checked = true;
    lab.append(rb, document.createTextNode(" " + f.label));
    fmtGroup.appendChild(lab);
  }
  dlg.appendChild(fmtGroup);

  // ── Kopfzeile (Titel) — Block-Layout, damit nichts abgeschnitten wird ──
  const kz = document.createElement("div");
  kz.className = "export-kopf";
  const kzLabel = document.createElement("label");
  kzLabel.textContent = "Kopfzeile (Titel)";
  kzLabel.htmlFor = "export-kopfzeile";
  const kzInput = document.createElement("input");
  kzInput.type = "text"; kzInput.id = "export-kopfzeile";
  kzInput.value = kopfzeileVorgabe !== undefined ? kopfzeileVorgabe : (titel || "");
  kz.append(kzLabel, kzInput);
  dlg.appendChild(kz);

  const datumZeile = document.createElement("label");
  datumZeile.className = "export-check";
  const datumCb = document.createElement("input");
  datumCb.type = "checkbox"; datumCb.id = "export-datum"; datumCb.checked = !!datumVorgabe;
  datumZeile.append(datumCb, document.createTextNode(" Datum in der Fußzeile"));
  dlg.appendChild(datumZeile);

  // ── Spaltenauswahl ──
  const feldGruppe = document.createElement("fieldset");
  feldGruppe.className = "export-gruppe";
  feldGruppe.innerHTML = "<legend>Felder / Spalten für die Ausgabe</legend>";
  const schalter = document.createElement("div");
  schalter.className = "aktionszeile";
  const bAlle = document.createElement("button");
  bAlle.type = "button"; bAlle.className = "sekundaer"; bAlle.textContent = "Alle";
  const bKeine = document.createElement("button");
  bKeine.type = "button"; bKeine.className = "sekundaer"; bKeine.textContent = "Keine";
  schalter.append(bAlle, bKeine);
  feldGruppe.appendChild(schalter);
  const liste = document.createElement("div");
  liste.className = "spalten-liste";
  const checks = [];
  headers.forEach((h, i) => {
    const lab = document.createElement("label");
    const cb = document.createElement("input");
    cb.type = "checkbox"; cb.checked = true; cb.dataset.idx = String(i);
    lab.append(cb, document.createTextNode(h || `Spalte ${i + 1}`));
    liste.appendChild(lab);
    checks.push(cb);
  });
  bAlle.addEventListener("click", () => checks.forEach((c) => (c.checked = true)));
  bKeine.addEventListener("click", () => checks.forEach((c) => (c.checked = false)));
  feldGruppe.appendChild(liste);
  dlg.appendChild(feldGruppe);

  // ── Buttons ──
  const btns = document.createElement("div");
  btns.className = "dialog-buttons";
  const bAbbr = document.createElement("button");
  bAbbr.className = "sekundaer"; bAbbr.textContent = "Abbrechen";
  bAbbr.addEventListener("click", () => dlg.close());
  const bOk = document.createElement("button");
  bOk.textContent = "Exportieren";
  bOk.addEventListener("click", async () => {
    const fmt = dlg.querySelector('input[name="export-fmt"]:checked').value;
    const kept = checks.filter((c) => c.checked).map((c) => parseInt(c.dataset.idx, 10));
    if (!kept.length) { alert("Bitte mindestens eine Spalte auswählen."); return; }
    const kopf = kzInput.value.trim();
    const mitDatum = datumCb.checked;
    const gefiltert = filterGruppen(gruppen, kept);
    try {
      await exportiere(fmt, dateiBasis || titel, kopf, mitDatum, gefiltert);
      dlg.close();
      status(`Liste als ${fmt.toUpperCase()} ${fmt === "pdf" ? "gedruckt" : "exportiert"}.`);
    } catch (e) {
      alert("Export fehlgeschlagen: " + e.message);
    }
  });
  btns.append(bAbbr, bOk);
  dlg.appendChild(btns);

  if (!dlg.open) dlg.showModal();
}

/** Baut die Zeilen (Array von Arrays) aus gefilterten Gruppen. */
function baueZeilen(gruppen, kopfzeile, mitDatum) {
  const aoa = [];
  if (kopfzeile) aoa.push([kopfzeile]);
  const mehrere = gruppen.length > 1;
  gruppen.forEach((g, gi) => {
    if (mehrere) {
      if (gi > 0 || kopfzeile) aoa.push([]);
      aoa.push([g.titel]);
    }
    aoa.push(g.headers);
    for (const row of g.rows) aoa.push(zellenVon(row));
  });
  if (mitDatum) { aoa.push([]); aoa.push([`Stand: ${datumsText()}`]); }
  return aoa;
}

async function exportiere(fmt, basis, kopfzeile, mitDatum, gruppen) {
  if (fmt === "pdf") {
    // PDF über den Browser-Druck (dort „Als PDF speichern")
    druck.drucke(kopfzeile || (gruppen[0]?.titel ?? "Liste"), gruppen);
    return;
  }
  const aoa = baueZeilen(gruppen, kopfzeile, mitDatum);
  if (fmt === "csv") {
    downloadText(sichererName(basis, ".csv"), alsCsv(aoa[0] || [], aoa.slice(1)));
    return;
  }
  // xlsx / ods über SheetJS
  const XLSX = await ladeSheetJs();
  const ws = XLSX.utils.aoa_to_sheet(aoa);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Liste");
  const bin = XLSX.write(wb, { type: "array", bookType: fmt });
  const mime = fmt === "xlsx"
    ? "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    : "application/vnd.oasis.opendocument.spreadsheet";
  const blob = new Blob([bin], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = sichererName(basis, fmt === "xlsx" ? ".xlsx" : ".ods");
  a.click();
  URL.revokeObjectURL(url);
}
