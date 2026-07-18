/**
 * Minimaler CSV-Export (Semikolon, UTF-8 mit BOM — öffnet sauber in
 * Excel/LibreOffice). Für den mächtigen Import (Spaltenzuordnung,
 * Titelzeilen-Erkennung, Mehrdatei-Zusammenführung) bleibt die Desktop-App
 * zuständig — die .plf ist ja dateikompatibel.
 */

function feld(wert) {
  const s = String(wert ?? "");
  return /[";\n]/.test(s) ? '"' + s.replaceAll('"', '""') + '"' : s;
}

export function alsCsv(headers, rows) {
  const zeilen = [headers.map(feld).join(";")];
  for (const row of rows) zeilen.push(row.map(feld).join(";"));
  return "﻿" + zeilen.join("\r\n");
}

export function downloadText(dateiname, text, mime = "text/csv") {
  const blob = new Blob([text], { type: mime + ";charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = dateiname;
  a.click();
  URL.revokeObjectURL(url);
}
