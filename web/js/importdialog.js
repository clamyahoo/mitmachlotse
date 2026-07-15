/**
 * CSV-Import-Dialog: Spaltenzuordnung mit Auto-Erkennung, Vorschau der
 * Quelldatei, Anhängen/Ersetzen — vereinfachtes Web-Gegenstück zum
 * SpaltenzuordnungDialog der Desktop-App.
 *
 * Aufruf: oeffneImportDialog("teilnehmer"|"optionen", csvText, onFertig)
 * onFertig(anzahl) wird nach erfolgreichem Import aufgerufen.
 */

import * as db from "./db.js";
import {
  erkenneTrennzeichen, parseCsv, autoMatch,
  splitGanzerName, splitKlasse, zahl, normStufe,
  teilnehmerFelder, projektFelder,
} from "./importcsv.js";

const TRENNZEICHEN = [
  { wert: ";",  label: "Semikolon (;)" },
  { wert: ",",  label: "Komma (,)" },
  { wert: "\t", label: "Tabulator" },
  { wert: "|",  label: "Senkrechter Strich (|)" },
];

export function oeffneImportDialog(art, csvText, onFertig) {
  const dlg = document.getElementById("dlg-import");
  const konfig = db.getFeldkonfig();
  const felder = art === "teilnehmer" ? teilnehmerFelder(konfig) : projektFelder(konfig);
  const titel = art === "teilnehmer"
    ? "Teilnehmer/innen importieren"
    : `${db.labelFormen(konfig.projekt_label).pluralNom} importieren`;

  let delim = erkenneTrennzeichen(csvText);
  let mitKopf = true;

  function geparst() {
    const rows = parseCsv(csvText, delim);
    const headers = mitKopf && rows.length
      ? rows[0].map((h) => String(h).trim())
      : (rows[0] || []).map((_, i) => `Spalte ${i + 1}`);
    const daten = mitKopf ? rows.slice(1) : rows;
    return { headers, daten };
  }

  function render() {
    const { headers, daten } = geparst();
    dlg.innerHTML = "";

    const h2 = document.createElement("h2");
    h2.textContent = titel;
    dlg.appendChild(h2);

    // ── Trennzeichen + Kopfzeile ──
    const optZeile = document.createElement("div");
    optZeile.className = "formzeile";
    const lblT = document.createElement("label");
    lblT.textContent = "Trennzeichen";
    const selT = document.createElement("select");
    for (const t of TRENNZEICHEN) {
      selT.appendChild(new Option(t.label, t.wert, false, t.wert === delim));
    }
    selT.addEventListener("change", () => { delim = selT.value; render(); });
    const cbKopf = document.createElement("input");
    cbKopf.type = "checkbox";
    cbKopf.checked = mitKopf;
    cbKopf.id = "imp-kopf";
    cbKopf.addEventListener("change", () => { mitKopf = cbKopf.checked; render(); });
    const lblK = document.createElement("label");
    lblK.htmlFor = "imp-kopf";
    lblK.textContent = "1. Zeile ist Überschrift";
    lblK.style.minWidth = "0";
    optZeile.append(lblT, selT, cbKopf, lblK);
    dlg.appendChild(optZeile);

    // ── Zuordnungstabelle ──
    const map = document.createElement("table");
    map.className = "map-tabelle";
    map.innerHTML = "<thead><tr><th>App-Feld</th><th>Quell-Spalte</th></tr></thead>";
    const mtb = document.createElement("tbody");
    const selects = {};
    for (const feld of felder) {
      const tr = document.createElement("tr");
      const tdL = document.createElement("td");
      tdL.textContent = feld.label;
      const tdS = document.createElement("td");
      const sel = document.createElement("select");
      sel.appendChild(new Option("(nicht importieren)", ""));
      headers.forEach((h, i) => sel.appendChild(new Option(h, String(i))));
      const auto = autoMatch(art, feld.key, headers);
      if (auto !== null) sel.value = String(auto);
      selects[feld.key] = sel;
      tdS.appendChild(sel);
      tr.append(tdL, tdS);
      mtb.appendChild(tr);
    }
    map.appendChild(mtb);
    dlg.appendChild(map);
    dlg._selects = selects; // für den OK-Handler

    // ── Mini-Vorschau der Quelldatei ──
    const vor = document.createElement("div");
    vor.className = "vorschau-klein";
    const vt = document.createElement("table");
    const vh = document.createElement("tr");
    headers.forEach((h) => {
      const th = document.createElement("th"); th.textContent = h; vh.appendChild(th);
    });
    vt.appendChild(vh);
    for (const row of daten.slice(0, 8)) {
      const tr = document.createElement("tr");
      headers.forEach((_, i) => {
        const td = document.createElement("td");
        td.textContent = i < row.length ? row[i] : "";
        tr.appendChild(td);
      });
      vt.appendChild(tr);
    }
    vor.appendChild(vt);
    dlg.appendChild(vor);

    const info = document.createElement("p");
    info.className = "hinweis";
    info.textContent = `${daten.length} Datenzeile(n) erkannt.`;
    dlg.appendChild(info);

    // ── Anhängen/Ersetzen ──
    const az = document.createElement("div");
    az.className = "formzeile";
    const cbAppend = document.createElement("input");
    cbAppend.type = "checkbox";
    cbAppend.id = "imp-append";
    const lblA = document.createElement("label");
    lblA.htmlFor = "imp-append";
    lblA.textContent = "Bestehende Daten behalten (anhängen statt ersetzen)";
    lblA.style.minWidth = "0";
    az.append(cbAppend, lblA);
    dlg.appendChild(az);
    dlg._appendCb = cbAppend;

    // ── Buttons ──
    const btns = document.createElement("div");
    btns.className = "dialog-buttons";
    const bAbbr = document.createElement("button");
    bAbbr.className = "sekundaer";
    bAbbr.textContent = "Abbrechen";
    bAbbr.addEventListener("click", () => dlg.close());
    const bOk = document.createElement("button");
    bOk.id = "imp-ok";
    bOk.textContent = "Importieren";
    bOk.addEventListener("click", () => {
      const anzahl = fuehreImportAus(art, geparst().daten, selects, cbAppend.checked);
      dlg.close();
      onFertig(anzahl);
    });
    btns.append(bAbbr, bOk);
    dlg.appendChild(btns);
  }

  render();
  dlg.showModal();
}

function wert(row, selects, key) {
  const idx = selects[key]?.value;
  if (idx === "" || idx === undefined) return null; // nicht zugeordnet
  const i = parseInt(idx, 10);
  return i < row.length ? String(row[i]).trim() : "";
}

function fuehreImportAus(art, daten, selects, anhaengen) {
  if (art === "teilnehmer") return importiereTeilnehmer(daten, selects, anhaengen);
  return importiereProjekte(daten, selects, anhaengen);
}

function importiereTeilnehmer(daten, selects, anhaengen) {
  if (!anhaengen) db.clearTeilnehmer();
  const konfig = db.getFeldkonfig();
  let anzahl = 0;
  for (const row of daten) {
    const rec = {
      nachname: "-", vorname: "-", stufe: "-", stufenzusatz: "-",
      geschlecht: "-", wunsch_1: 0, wunsch_2: 0, wunsch_3: 0,
      wunsch_4: 0, wunsch_5: 0,
    };
    for (const f of ["nachname", "vorname", "stufenzusatz", "geschlecht"]) {
      const v = wert(row, selects, f);
      if (v) rec[f] = v;
    }
    const stufe = wert(row, selects, "stufe");
    if (stufe) rec.stufe = normStufe(stufe);
    // Kombinierter Name überschreibt Nachname/Vorname, falls belegt
    const ganz = wert(row, selects, "ganzer_name");
    if (ganz) {
      const [nn, vn] = splitGanzerName(ganz);
      if (nn) rec.nachname = nn;
      if (vn) rec.vorname = vn;
    }
    // Kombinierte Klasse überschreibt Stufe/Zusatz, falls belegt
    const kombi = wert(row, selects, "klasse_kombi");
    if (kombi) {
      const [st, zu] = splitKlasse(kombi);
      if (st) rec.stufe = normStufe(st);
      if (zu) rec.stufenzusatz = zu;
    }
    for (let i = 1; i <= konfig.max_wuensche; i++) {
      const v = wert(row, selects, `wunsch_${i}`);
      if (v !== null) rec[`wunsch_${i}`] = zahl(v, 0);
    }
    // Nur importieren, wenn mindestens ein Nachname vorhanden (wie Desktop)
    if (rec.nachname && rec.nachname !== "-") {
      db.insertTeilnehmerVoll(rec);
      anzahl++;
    }
  }
  return anzahl;
}

function importiereProjekte(daten, selects, anhaengen) {
  if (!anhaengen) db.clearProjekte();
  // Kollidierende oder fehlende Nummern automatisch weiterzählen
  // (Spiegel des Desktop-Fixes in importexport.import_projekte).
  const vorhandene = new Set(db.getAlleProjekte().map((p) => p.nummer));
  let naechste = Math.max(0, ...vorhandene) + 1;
  let anzahl = 0;
  for (const row of daten) {
    const name = wert(row, selects, "projektname");
    if (!name || name === "-") continue; // leere/Titelzeile
    let nummer = zahl(wert(row, selects, "nummer"), 0);
    if (nummer === 0 || vorhandene.has(nummer)) nummer = naechste;
    vorhandene.add(nummer);
    naechste = Math.max(naechste, nummer + 1);
    db.insertProjektVoll({
      nummer,
      projektname: name,
      leitung: wert(row, selects, "leitung") || "",
      stufenmin: zahl(wert(row, selects, "stufenmin"), 0),
      stufenmax: zahl(wert(row, selects, "stufenmax"), 0),
      tnmin: zahl(wert(row, selects, "tnmin"), 0),
      tnmax: zahl(wert(row, selects, "tnmax"), 0),
    });
    anzahl++;
  }
  return anzahl;
}
