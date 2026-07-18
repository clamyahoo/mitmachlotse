/**
 * PDF-Erzeugung im Browser (unabhängig vom Druckdialog) mit jsPDF +
 * jspdf-autotable, lazy vom CDN geladen. Das Layout ist an die Desktop-App
 * angelehnt (_html_gruppen in importexport.py): Titel in Dunkelblau (#1F3864),
 * Gruppentitel, Tabellenkopf mit blauem Hintergrund (#4472C4) und weißer
 * Schrift, Zebra-Zeilen (#f0f4f8), optionaler Seitenumbruch je Gruppe und
 * „Stand:"-Fußzeile. Nachbearbeitungs-Marker werden farblich übernommen
 * (Neuzugänge gelb, Abgänge grau).
 */

const JSPDF_CDN = "https://cdn.jsdelivr.net/npm/jspdf@2.5.2/dist/jspdf.umd.min.js";
const AUTOTABLE_CDN = "https://cdn.jsdelivr.net/npm/jspdf-autotable@3.8.4/dist/jspdf.plugin.autotable.min.js";

let ladePromise = null;

function skript(src) {
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = src;
    s.onload = resolve;
    s.onerror = () => reject(new Error(`Ressource konnte nicht geladen werden: ${src}`));
    document.head.appendChild(s);
  });
}

/** jsPDF (+autotable) einmalig laden; liefert die jsPDF-Klasse. */
export function ladeJsPdf() {
  if (!ladePromise) {
    ladePromise = (async () => {
      await skript(JSPDF_CDN);
      await skript(AUTOTABLE_CDN);   // erweitert jsPDF um autoTable
      const jsPDF = globalThis.jspdf?.jsPDF;
      if (!jsPDF) throw new Error("PDF-Bibliothek (jsPDF) nicht verfügbar.");
      return jsPDF;
    })().catch((e) => { ladePromise = null; throw e; });
  }
  return ladePromise;
}

const zellenVon = (row) => (Array.isArray(row) ? row : row.zellen);

/** Querformat, sobald echte Wunsch-Spalten (W1..W5 / „Wunsch 1"..) vorkommen. */
function querformatNoetig(gruppen) {
  return gruppen.some((g) => g.headers.some(
    (h) => /^W\d$/.test(String(h).trim()) || /^Wunsch \d$/.test(String(h).trim())));
}

function datumsText() {
  return new Date().toLocaleDateString("de-DE",
    { year: "numeric", month: "long", day: "numeric" });
}

/**
 * Erzeugt einen PDF-Blob aus Gruppen ([{titel, headers, rows}]).
 * opts: { kopfzeile, mitDatum, seitenumbrueche }
 */
export async function erzeugePdfBlob(gruppen, opts = {}) {
  const jsPDF = await ladeJsPdf();
  const quer = querformatNoetig(gruppen);
  const doc = new jsPDF({ orientation: quer ? "landscape" : "portrait", unit: "pt", format: "a4" });
  const M = 40;
  const seitenBreite = doc.internal.pageSize.getWidth();
  const seitenHoehe = doc.internal.pageSize.getHeight();
  let y = M;

  if (opts.kopfzeile) {
    doc.setFont("helvetica", "bold");
    doc.setFontSize(14);
    doc.setTextColor(31, 56, 100);           // #1F3864
    doc.text(String(opts.kopfzeile), M, y);
    y += 6;
    doc.setDrawColor(31, 56, 100);
    doc.setLineWidth(1.5);
    doc.line(M, y, seitenBreite - M, y);
    y += 16;
  }

  gruppen.forEach((g, gi) => {
    if (gi > 0 && opts.seitenumbrueche) { doc.addPage(); y = M; }

    if (g.titel) {
      if (y > seitenHoehe - 70) { doc.addPage(); y = M; }
      doc.setFont("helvetica", "bold");
      doc.setFontSize(11);
      doc.setTextColor(44, 62, 80);          // #2c3e50
      doc.text(String(g.titel), M, y);
      y += 4;
    }

    doc.autoTable({
      head: [g.headers.map(String)],
      body: g.rows.map((r) => zellenVon(r).map((z) => (z == null ? "" : String(z)))),
      startY: y + 6,
      margin: { left: M, right: M },
      styles: { fontSize: 8.5, cellPadding: 3, lineColor: [221, 221, 221],
                lineWidth: 0.5, textColor: [20, 20, 20], overflow: "linebreak" },
      headStyles: { fillColor: [68, 114, 196], textColor: 255, fontStyle: "bold", fontSize: 8.5 },
      alternateRowStyles: { fillColor: [240, 244, 248] },
      // Nachbearbeitungs-Marker einfärben (Neuzugänge gelb, Abgänge grau)
      didParseCell: (data) => {
        if (data.section !== "body") return;
        const row = g.rows[data.row.index];
        if (Array.isArray(row)) return;
        if (row.klasse === "neu") data.cell.styles.fillColor = [255, 243, 176];
        else if (row.klasse === "geist") data.cell.styles.textColor = [119, 119, 119];
      },
    });
    y = doc.lastAutoTable.finalY + 18;
  });

  if (opts.mitDatum) {
    const stand = `Stand: ${datumsText()}`;
    const n = doc.internal.getNumberOfPages();
    for (let i = 1; i <= n; i++) {
      doc.setPage(i);
      doc.setFont("helvetica", "normal");
      doc.setFontSize(7.5);
      doc.setTextColor(102, 102, 102);
      doc.text(stand, M, seitenHoehe - 20);
    }
  }

  return doc.output("blob");
}
