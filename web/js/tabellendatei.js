/**
 * Tabellendateien lesen: CSV direkt (UTF-8 mit Windows-1252-Fallback),
 * xlsx/xls/ods über SheetJS — lazy vom CDN geladen, erst wenn wirklich
 * eine Excel-/ODS-Datei ausgewählt wird. Ergebnis ist immer CSV-Text
 * (Semikolon), der in die bestehende Import-Pipeline fließt.
 */

const SHEETJS_CDN = "https://cdn.sheetjs.com/xlsx-0.20.2/package/dist/xlsx.full.min.js";

let sheetJsPromise = null;

/** SheetJS (XLSX) lazy vom CDN laden und das globale XLSX-Objekt liefern —
 *  für Lesen (xlsx/xls/ods) und Schreiben (xlsx/ods) gleichermaßen. */
export function ladeSheetJs() {
  if (!sheetJsPromise) {
    sheetJsPromise = new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = SHEETJS_CDN;
      s.onload = () => resolve(globalThis.XLSX);
      s.onerror = () => {
        sheetJsPromise = null; // nächster Versuch darf neu starten
        reject(new Error("Tabellen-Leser (SheetJS) konnte nicht geladen werden."));
      };
      document.head.appendChild(s);
    });
  }
  return sheetJsPromise;
}

/** Datei → CSV-Text (Semikolon-getrennt). statusCb für Ladehinweise. */
export async function liesTabellenDatei(file, statusCb = () => {}) {
  const name = file.name.toLowerCase();
  if (/\.(xlsx|xls|ods)$/.test(name)) {
    statusCb("Lade Tabellen-Leser (einmalig) …");
    await ladeSheetJs();
    const wb = globalThis.XLSX.read(await file.arrayBuffer(), { type: "array" });
    const ws = wb.Sheets[wb.SheetNames[0]];
    if (!ws) throw new Error("Die Datei enthält kein lesbares Tabellenblatt.");
    return globalThis.XLSX.utils.sheet_to_csv(ws, { FS: ";" });
  }
  // CSV/TXT: UTF-8 zuerst; Windows-CSVs (Excel) sind oft cp1252 → Fallback
  const buf = await file.arrayBuffer();
  try { return new TextDecoder("utf-8", { fatal: true }).decode(buf); }
  catch { return new TextDecoder("windows-1252").decode(buf); }
}
