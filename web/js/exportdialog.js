/**
 * Export-Dialog für Listen — Web-Gegenstück zu FensterExportDialog /
 * GesamtExportDialog + SpaltenauswahlDialog der Desktop-App: Format wählen
 * (Excel/ODS/CSV/PDF), Kopfzeile (Titel) und „Datum in der Fußzeile"
 * festlegen, Spalten auswählen. Erzeugt die Datei(en) und lädt sie herunter.
 * PDF entsteht als echte Datei (jsPDF, pdf.js) — unabhängig vom Druckdialog.
 *
 * Für Gesamtlisten (mehrere Gruppen) lassen sich zusätzlich wählen:
 *  - „Seitenumbruch nach jeder Option/Gruppe" (im PDF)
 *  - „Jede Option/Gruppe als eigene Datei" (eine Datei je Gruppe)
 *
 * Nimmt Gruppen entgegen ([{titel, headers, rows}]); rows dürfen Arrays oder
 * {klasse, zellen} sein (Nachbearbeitungs-Marker).
 */

import { alsCsv, downloadText } from "./csv.js";
import { ladeSheetJs } from "./tabellendatei.js";
import { filterGruppen } from "./spaltenwahl.js";
import { erzeugePdfBlob } from "./pdf.js";

const $ = (id) => document.getElementById(id);

const FORMATE = [
  { key: "xlsx", label: "Excel-Datei (.xlsx)" },
  { key: "ods",  label: "OpenDocument-Tabelle (.ods)" },
  { key: "csv",  label: "CSV-Datei (.csv)" },
  { key: "pdf",  label: "PDF-Datei (.pdf)" },
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

function ladeBlob(dateiname, blob) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = dateiname;
  a.click();
  URL.revokeObjectURL(url);
}

/**
 * @param {object} o
 *   titel:            Kopfzeilen-Vorgabe / Fallback-Dateiname
 *   dateiBasis:       Vorschlag für den Dateinamen (ohne Endung)
 *   gruppen:          [{titel, headers, rows}] — mind. eine Gruppe
 *   kopfzeileVorgabe: Vorbelegung der Kopfzeile (Default: titel)
 *   datumVorgabe:     Datum-Fußzeile vorangehakt (Default: true)
 *   gruppenoptionen:  bei true und >1 Gruppe: Seitenumbruch-/Separat-Optionen
 *   einheit:          Bezeichnung je Gruppe für die Optionen (z. B. „Option")
 *   status:           optionale Statusausgabe
 */
export function zeigeExportDialog({ titel, dateiBasis, gruppen, kopfzeileVorgabe,
                                    datumVorgabe = true, gruppenoptionen = false,
                                    einheit = "Gruppe", status = () => {} }) {
  const headers = gruppen[0]?.headers || [];
  const mehrgruppig = gruppenoptionen && gruppen.length > 1;
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

  // ── Gesamtlisten-Optionen (nur bei mehreren Gruppen) ──
  let umbruchCb = null;
  let separatCb = null;
  if (mehrgruppig) {
    const gGroup = document.createElement("fieldset");
    gGroup.className = "export-gruppe";
    gGroup.innerHTML = `<legend>Je ${einheit}</legend>`;

    const l1 = document.createElement("label");
    l1.className = "export-check";
    umbruchCb = document.createElement("input");
    umbruchCb.type = "checkbox"; umbruchCb.id = "export-umbruch"; umbruchCb.checked = true;
    l1.append(umbruchCb, document.createTextNode(` Seitenumbruch nach jeder ${einheit} (im PDF)`));
    gGroup.appendChild(l1);

    const l2 = document.createElement("label");
    l2.className = "export-check";
    separatCb = document.createElement("input");
    separatCb.type = "checkbox"; separatCb.id = "export-separat";
    l2.append(separatCb, document.createTextNode(` Jede ${einheit} als eigene Datei`));
    gGroup.appendChild(l2);

    dlg.appendChild(gGroup);
  }

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
    const seitenumbrueche = umbruchCb ? umbruchCb.checked : false;
    const separat = separatCb ? separatCb.checked : false;
    const gefiltert = filterGruppen(gruppen, kept);
    bOk.disabled = true;
    try {
      if (separat && gefiltert.length > 1) {
        for (const g of gefiltert) {
          const basis = `${dateiBasis || titel}_${g.titel}`;
          await ausgeben(fmt, basis, kopf, mitDatum, false, [g]);
        }
        status(`${gefiltert.length} Dateien als ${fmt.toUpperCase()} exportiert.`);
      } else {
        await ausgeben(fmt, dateiBasis || titel, kopf, mitDatum, seitenumbrueche, gefiltert);
        status(`Liste als ${fmt.toUpperCase()} exportiert.`);
      }
      dlg.close();
    } catch (e) {
      alert("Export fehlgeschlagen: " + e.message);
    } finally {
      bOk.disabled = false;
    }
  });
  btns.append(bAbbr, bOk);
  dlg.appendChild(btns);

  if (!dlg.open) dlg.showModal();
}

/** Zeilen (Array von Arrays) aus Gruppen — für CSV/xlsx/ods. */
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

/** Erzeugt eine Ausgabedatei für die übergebenen (gefilterten) Gruppen. */
async function ausgeben(fmt, basis, kopfzeile, mitDatum, seitenumbrueche, gruppen) {
  if (fmt === "pdf") {
    const blob = await erzeugePdfBlob(gruppen, { kopfzeile, mitDatum, seitenumbrueche });
    ladeBlob(sichererName(basis, ".pdf"), blob);
    return;
  }
  const aoa = baueZeilen(gruppen, kopfzeile, mitDatum);
  if (fmt === "csv") {
    downloadText(sichererName(basis, ".csv"), alsCsv(aoa[0] || [], aoa.slice(1)));
    return;
  }
  const XLSX = await ladeSheetJs();
  const ws = XLSX.utils.aoa_to_sheet(aoa);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Liste");
  const bin = XLSX.write(wb, { type: "array", bookType: fmt });
  const mime = fmt === "xlsx"
    ? "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    : "application/vnd.oasis.opendocument.spreadsheet";
  ladeBlob(sichererName(basis, fmt === "xlsx" ? ".xlsx" : ".ods"), new Blob([bin], { type: mime }));
}
