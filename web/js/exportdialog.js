/**
 * Export-Dialog für Listenfenster — Web-Gegenstück zu FensterExportDialog +
 * SpaltenauswahlDialog(mit_kopfzeile) der Desktop-App: Format wählen
 * (CSV/Excel/ODS), Kopfzeile (Titel) und „Datum in der Fußzeile" festlegen,
 * anschließend die auszugebenden Spalten auswählen. Erzeugt die Datei und
 * lädt sie herunter. xlsx/ods über SheetJS (lazy vom CDN).
 */

import { alsCsv, downloadText } from "./csv.js";
import { ladeSheetJs } from "./tabellendatei.js";

const $ = (id) => document.getElementById(id);

const FORMATE = [
  { key: "xlsx", label: "Excel-Datei (.xlsx)", ext: ".xlsx" },
  { key: "ods",  label: "OpenDocument-Tabelle (.ods)", ext: ".ods" },
  { key: "csv",  label: "CSV-Datei (.csv)", ext: ".csv" },
];

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
 * Öffnet den Export-Dialog. titel = Kopfzeilen-Vorgabe (lesbar), dateiBasis =
 * Vorschlag für den Dateinamen, status: optionale Statusausgabe.
 * headers/rows: die vollständige Liste (Spaltenauswahl passiert im Dialog).
 */
export function zeigeExportDialog(titel, dateiBasis, headers, rows, status = () => {}) {
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

  // ── Kopfzeile + Datum ──
  const kz = document.createElement("div");
  kz.className = "formzeile";
  const kzLabel = document.createElement("label");
  kzLabel.textContent = "Kopfzeile (Titel)";
  kzLabel.htmlFor = "export-kopfzeile";
  const kzInput = document.createElement("input");
  kzInput.type = "text"; kzInput.id = "export-kopfzeile"; kzInput.value = titel || "";
  kz.append(kzLabel, kzInput);
  dlg.appendChild(kz);

  const datumZeile = document.createElement("label");
  datumZeile.className = "export-check";
  const datumCb = document.createElement("input");
  datumCb.type = "checkbox"; datumCb.id = "export-datum"; datumCb.checked = true;
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
    const hSel = kept.map((i) => headers[i]);
    const rSel = rows.map((r) => kept.map((i) => r[i]));
    try {
      await exportiere(fmt, dateiBasis || titel, kopf, mitDatum, hSel, rSel);
      dlg.close();
      status(`Liste als ${fmt.toUpperCase()} exportiert.`);
    } catch (e) {
      alert("Export fehlgeschlagen: " + e.message);
    }
  });
  btns.append(bAbbr, bOk);
  dlg.appendChild(btns);

  if (!dlg.open) dlg.showModal();
}

async function exportiere(fmt, titel, kopfzeile, mitDatum, headers, rows) {
  if (fmt === "csv") {
    const zeilen = [];
    if (kopfzeile) zeilen.push([kopfzeile]);
    zeilen.push(headers);
    for (const r of rows) zeilen.push(r);
    if (mitDatum) { zeilen.push([]); zeilen.push([`Stand: ${datumsText()}`]); }
    // alsCsv nimmt (kopf, rows) — erste Zeile als „Kopf", Rest als Datenzeilen.
    downloadText(sichererName(titel, ".csv"), alsCsv(zeilen[0], zeilen.slice(1)));
    return;
  }
  // xlsx / ods über SheetJS
  const XLSX = await ladeSheetJs();
  const aoa = [];
  if (kopfzeile) aoa.push([kopfzeile]);
  aoa.push(headers);
  for (const r of rows) aoa.push(r);
  if (mitDatum) { aoa.push([]); aoa.push([`Stand: ${datumsText()}`]); }
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
  a.download = sichererName(titel, fmt === "xlsx" ? ".xlsx" : ".ods");
  a.click();
  URL.revokeObjectURL(url);
}
