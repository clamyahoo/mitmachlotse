/**
 * Raumplan-Tab: Raumliste (CRUD) + Raumzuordnung je Option mit
 * Konfliktprüfung — Web-Gegenstück zu RaumplanTable/RaeumeTable der
 * Desktop-App inklusive der aktuellen Desktop-Regeln:
 *
 *  - Ein Raum darf zwei Optionen nur dann konfliktfrei zugeordnet werden,
 *    wenn BEIDE eine Zeit eingetragen haben UND sich diese unterscheiden.
 *  - Andernfalls Rückfrage "Möchten Sie eine Mehrfachbelegung erzwingen?" —
 *    Nein verwirft die Änderung, Ja speichert; die Hinweisspalte markiert
 *    erzwungene Doppelbelegungen rot (Kapazitätsprobleme orange).
 *  - "Fix" schützt eine Zuordnung vor der Automatik; die automatische
 *    Raumzuteilung führt das UNVERÄNDERTE Desktop-Modul raumzuteilung.py
 *    über Pyodide aus (solver.raumzuteilung).
 */

import * as db from "./db.js";
import * as solver from "./solver.js";
import * as druck from "./druck.js";
import { Kontext } from "./kontext.js";
import { alsCsv, downloadText } from "./csv.js";
import { waehleSpalten, filterGruppen } from "./spaltenwahl.js";
import { zeigeExportDialog } from "./exportdialog.js";

const $ = (id) => document.getElementById(id);

let cb = { setzeDirty: () => {}, status: () => {} };
const raumMarkiert = new Set();

// ── Konfliktlogik (Spiegel von validierung.pruefe_raumkonflikte + UI-Regel) ──

function zeitVon(row) { return (row.zeit || "").trim(); }

/** Kollidierende andere Option für (nummer, raumId, zeit) — oder null. */
function findeKonflikt(plan, nummer, raumId, zeit) {
  if (!raumId) return null;
  for (const row of plan) {
    if (row.nummer === nummer) continue;
    if ((row.raum_id || 0) !== raumId) continue;
    const andere = zeitVon(row);
    if (zeit && andere && zeit !== andere) continue; // verschiedene Zeiten -> ok
    return row;
  }
  return null;
}

/** nummer → {doppel, kap, text} für die Hinweisspalte/Färbung. */
function pruefeKonflikte(plan) {
  const ergebnis = {};
  const eintrag = (nr) => (ergebnis[nr] ??= { doppel: false, kap: false, texte: [] });
  // Doppelbelegung (gleiche Regel wie findeKonflikt, paarweise)
  for (const row of plan) {
    if (!row.raum_id) continue;
    const andere = plan.filter((o) =>
      o.nummer !== row.nummer && (o.raum_id || 0) === row.raum_id &&
      !(zeitVon(row) && zeitVon(o) && zeitVon(row) !== zeitVon(o)));
    if (andere.length) {
      const e = eintrag(row.nummer);
      e.doppel = true;
      e.texte.push(`Doppelbelegung: Raum „${row.raum_name || "?"}“ auch bei ` +
        `Option ${andere.map((o) => o.nummer).join(", ")}`);
    }
  }
  // Kapazität
  for (const row of plan) {
    const kap = row.raum_kapazitaet || 0;
    if (!row.raum_id || kap <= 0) continue;
    const belegt = row.belegt || 0;
    if (belegt > kap) {
      const e = eintrag(row.nummer);
      e.kap = true;
      e.texte.push(`Kapazität überschritten: ${belegt} zugeteilt, ` +
        `Raum fasst nur ${kap}`);
    } else if (row.tnmax && row.tnmax > kap) {
      const e = eintrag(row.nummer);
      e.kap = true;
      e.texte.push(`Kapazität knapp: Raum fasst ${kap}, geplant bis zu ${row.tnmax}`);
    }
  }
  return ergebnis;
}

function frageErzwingen(raumName, zeit, konflikt) {
  const zeitTeil = zeit && zeitVon(konflikt)
    ? `zur Zeit „${zeit}“ ` : "(Zeit ist nicht bei beiden Optionen eingetragen) ";
  return confirm(
    `Der Raum „${raumName}“, den Sie zuteilen möchten, ist ${zeitTeil}` +
    `bereits Option ${konflikt.nummer} (${konflikt.projektname || ""}) ` +
    `zugeordnet.\n\nMöchten Sie eine Mehrfachbelegung erzwingen?`);
}

// ── Rendering ────────────────────────────────────────────────────────────────

function kopf(theadEl, spalten) {
  theadEl.innerHTML = "";
  const tr = document.createElement("tr");
  for (const s of spalten) {
    const th = document.createElement("th");
    th.textContent = s;
    tr.appendChild(th);
  }
  theadEl.appendChild(tr);
}

function inputZelle(typ, wert, onChange, disabled) {
  const td = document.createElement("td");
  const input = document.createElement("input");
  input.type = typ;
  input.value = wert ?? "";
  if (typ === "number") { input.min = 0; td.className = "zahl"; }
  input.disabled = !!disabled;
  input.addEventListener("change", () => onChange(input));
  td.appendChild(input);
  return td;
}

function roZelle(text, zentriert) {
  const td = document.createElement("td");
  td.textContent = text ?? "";
  td.className = "readonly" + (zentriert ? "" : "");
  return td;
}

function renderRaumliste() {
  kopf($("raum-tabelle").querySelector("thead"),
    ["✓", "Raumname", "Kapazität (0 = unbegrenzt)", "Beschreibung"]);
  const tbody = $("raum-tabelle").querySelector("tbody");
  tbody.innerHTML = "";
  const darf = Kontext.darfOptionenBearbeiten();
  const raeume = db.getAlleRaeume();
  for (const r of raeume) {
    const tr = document.createElement("tr");
    const tdCb = document.createElement("td");
    tdCb.className = "zahl";
    const cbEl = document.createElement("input");
    cbEl.type = "checkbox";
    cbEl.checked = raumMarkiert.has(r.id);
    cbEl.addEventListener("change", () => {
      if (cbEl.checked) raumMarkiert.add(r.id); else raumMarkiert.delete(r.id);
    });
    tdCb.appendChild(cbEl);
    tr.appendChild(tdCb);
    tr.appendChild(inputZelle("text", r.name, (inp) => {
      db.updateRaumFeld(r.id, "name", inp.value);
      cb.setzeDirty(true);
      renderZuordnung(); // Raumnamen in den Dropdowns nachziehen
    }, !darf));
    tr.appendChild(inputZelle("number", r.kapazitaet, (inp) => {
      db.updateRaumFeld(r.id, "kapazitaet", parseInt(inp.value, 10) || 0);
      cb.setzeDirty(true);
      renderZuordnung();
    }, !darf));
    tr.appendChild(inputZelle("text", r.beschreibung, (inp) => {
      db.updateRaumFeld(r.id, "beschreibung", inp.value);
      cb.setzeDirty(true);
    }, !darf));
    tbody.appendChild(tr);
  }
  $("raum-anzahl").textContent = `${raeume.length} Räume`;
}

function renderZuordnung() {
  const k = db.getFeldkonfig();
  const rzl = (k.raumzuordnung_extra_label || "").trim();  // leer = Spalte aus
  const spalten = ["Nr.", db.labelFormen(k.projekt_label).name, "Plätze max",
                   "belegt", "Raum", "Kapazität", "Zeit"];
  if (rzl) spalten.push(rzl);
  spalten.push("Fix", "Hinweis");
  kopf($("raumplan-tabelle").querySelector("thead"), spalten);
  const tbody = $("raumplan-tabelle").querySelector("tbody");
  tbody.innerHTML = "";
  const darf = Kontext.darfOptionenBearbeiten();
  const plan = db.getRaumplan();
  const raeume = db.getAlleRaeume();
  const konflikte = pruefeKonflikte(plan);

  for (const row of plan) {
    const tr = document.createElement("tr");
    const info = konflikte[row.nummer];
    if (info) tr.className = info.doppel ? "konflikt-doppel" : "konflikt-kap";

    tr.appendChild(roZelle(String(row.nummer), true));
    tr.appendChild(roZelle(row.projektname || ""));
    tr.appendChild(roZelle(String(row.tnmax ?? "")));
    tr.appendChild(roZelle(String(row.belegt || 0)));

    // Raum-Auswahl
    const tdRaum = document.createElement("td");
    const sel = document.createElement("select");
    sel.disabled = !darf;
    sel.appendChild(new Option("— kein Raum —", 0, false, !row.raum_id));
    for (const r of raeume) {
      sel.appendChild(new Option(r.name, r.id, false, row.raum_id === r.id));
    }
    sel.addEventListener("change", () => {
      const neuId = parseInt(sel.value, 10) || 0;
      const konflikt = findeKonflikt(plan, row.nummer, neuId, zeitVon(row));
      if (konflikt) {
        const raumName = raeume.find((r) => r.id === neuId)?.name || "";
        if (!frageErzwingen(raumName, zeitVon(row), konflikt)) {
          renderZuordnung(); // zurücksetzen
          return;
        }
      }
      db.setRaumZeit(row.nummer, neuId, row.zeit || "");
      cb.setzeDirty(true);
      renderZuordnung();
    });
    tdRaum.appendChild(sel);
    tr.appendChild(tdRaum);

    const kap = row.raum_id ? (row.raum_kapazitaet || 0) : "";
    tr.appendChild(roZelle(kap === 0 && row.raum_id ? "∞" : String(kap)));

    // Zeit
    tr.appendChild(inputZelle("text", row.zeit || "", (inp) => {
      const neueZeit = inp.value.trim();
      const konflikt = findeKonflikt(plan, row.nummer, row.raum_id || 0, neueZeit);
      if (konflikt) {
        const raumName = row.raum_name || "";
        if (!frageErzwingen(raumName, neueZeit, konflikt)) {
          renderZuordnung();
          return;
        }
      }
      db.setRaumZeit(row.nummer, row.raum_id || 0, inp.value);
      cb.setzeDirty(true);
      renderZuordnung();
    }, !darf));

    // Optionales Raumzuordnungs-Zusatzfeld (nur wenn benannt)
    if (rzl) {
      tr.appendChild(inputZelle("text", row.raumzuordnung_extra || "", (inp) => {
        db.setRaumzuordnungExtra(row.nummer, inp.value);
        cb.setzeDirty(true);
      }, !darf));
    }

    // Fix
    const tdFix = document.createElement("td");
    tdFix.className = "zahl";
    const fix = document.createElement("input");
    fix.type = "checkbox";
    fix.checked = !!row.raum_fixiert;
    fix.disabled = !darf;
    fix.addEventListener("change", () => {
      db.setRaumFixiert(row.nummer, fix.checked);
      cb.setzeDirty(true);
    });
    tdFix.appendChild(fix);
    tr.appendChild(tdFix);

    tr.appendChild(roZelle(info ? info.texte.join("  •  ") : ""));
    tbody.appendChild(tr);
  }
}

export function renderRaumplan() {
  renderRaumliste();
  renderZuordnung();
}

// ── Aktionen ─────────────────────────────────────────────────────────────────

async function autoZuteilen() {
  if (!confirm("Räume automatisch zuweisen?\n\nNicht fixierte Raumzuordnungen "
      + "werden dabei neu vergeben. Zeiten werden vorausgesetzt und nicht "
      + "automatisch verteilt.")) return;
  const statusEl = $("raum-solver-status");
  statusEl.hidden = false;
  statusEl.classList.remove("fehler");
  $("btn-raum-auto").disabled = true;
  $("btn-raum-reset").disabled = true;
  try {
    const { dbBytes, ergebnis } = await solver.raumzuteilung(
      db.exportiereBytes(), (t) => { statusEl.textContent = t; });
    await db.ersetzeAusBytes(dbBytes);
    cb.setzeDirty(true);
    renderRaumplan();
    let text = `Raumzuteilung abgeschlossen — ${ergebnis.anzahl} Räume zugewiesen.`;
    if (ergebnis.hinweise.length) {
      text += `\nNicht zuweisbar:\n` + ergebnis.hinweise.join("\n");
    }
    statusEl.textContent = text;
  } catch (e) {
    statusEl.classList.add("fehler");
    statusEl.textContent = "Fehler bei der Raumzuteilung: " + e.message;
  } finally {
    $("btn-raum-auto").disabled = false;
    $("btn-raum-reset").disabled = false;
  }
}

/** Raumzuordnung als eine Druck-/Export-Gruppe ({titel, headers, rows}).
 *  Das Raumzuordnungs-Zusatzfeld erscheint als Spalte, wenn es benannt ist. */
function raumplanGruppe() {
  const k = db.getFeldkonfig();
  const rzl = (k.raumzuordnung_extra_label || "").trim();
  const plan = db.getRaumplan();
  const headers = ["Nr.", db.labelFormen(k.projekt_label).name, "Raum", "Zeit",
                   "Plätze max", "belegt"];
  if (rzl) headers.push(rzl);
  const rows = plan.map((row) => {
    const r = [row.nummer, row.projektname || "", row.raum_name || "—",
               row.zeit || "", row.tnmax ?? "", row.belegt || 0];
    if (rzl) r.push(row.raumzuordnung_extra || "");
    return r;
  });
  return {
    titel: `Raumzuordnung (${plan.length} ${db.labelFormen(k.projekt_label).pluralNom})`,
    headers, rows,
  };
}

async function druckeRaumplan() {
  const g = raumplanGruppe();
  const kept = await waehleSpalten(g.headers);
  if (!kept) return;
  druck.drucke("Raumplan", filterGruppen([g], kept));
}

function exportiereRaumplan() {
  const g = raumplanGruppe();
  if (!g.rows.length) { alert("Keine Optionen vorhanden."); return; }
  zeigeExportDialog({
    titel: "Raumzuordnung",
    dateiBasis: "raumzuordnung",
    gruppen: [g],
    status: cb.status,
  });
}

/** Raumliste als CSV-Text — Spalten wie der Desktop-Export, damit die Datei
 *  beim Reimport automatisch zugeordnet wird. (Exportiert für Tests.) */
export function raumlisteAlsCsv() {
  return alsCsv(
    ["Raumname", "Kapazität", "Beschreibung"],
    db.getAlleRaeume().map((r) => [r.name, r.kapazitaet, r.beschreibung])
  );
}

export function initRaumplan(callbacks) {
  cb = callbacks;
  $("btn-raum-neu").addEventListener("click", () => {
    db.insertRaum();
    cb.setzeDirty(true);
    renderRaumplan();
  });
  $("btn-raum-loeschen").addEventListener("click", () => {
    if (!raumMarkiert.size) { alert("Bitte zuerst Räume ankreuzen."); return; }
    if (!confirm(`${raumMarkiert.size} Raum/Räume löschen? Zuordnungen zu ` +
                 `Optionen werden dabei entfernt.`)) return;
    db.deleteRaeume([...raumMarkiert]);
    raumMarkiert.clear();
    cb.setzeDirty(true);
    renderRaumplan();
  });
  $("btn-raum-auto").addEventListener("click", autoZuteilen);
  $("btn-raum-reset").addEventListener("click", () => {
    if (!confirm("Alle nicht fixierten Raumzuordnungen entfernen?")) return;
    const n = db.raumzuteilungAufheben();
    cb.setzeDirty(true);
    renderRaumplan();
    cb.status(`Raumzuteilung aufgehoben (${n} Zuordnungen entfernt, fixierte bleiben).`);
  });
  $("btn-raum-druck").addEventListener("click", druckeRaumplan);
  $("btn-raum-plan-export").addEventListener("click", exportiereRaumplan);
  $("btn-raum-export").addEventListener("click", () => {
    const raeume = db.getAlleRaeume();
    if (!raeume.length) { alert("Keine Räume vorhanden."); return; }
    // Kopfzeile/Datum standardmäßig aus, damit ein CSV-Export ohne Zusatz-
    // zeilen bleibt und sich sauber wieder importieren lässt (Round-Trip).
    zeigeExportDialog({
      titel: "Raumliste",
      dateiBasis: "raumliste",
      kopfzeileVorgabe: "",
      datumVorgabe: false,
      gruppen: [{
        titel: "Raumliste",
        headers: ["Raumname", "Kapazität", "Beschreibung"],
        rows: raeume.map((r) => [r.name, r.kapazitaet, r.beschreibung]),
      }],
      status: cb.status,
    });
  });
  // btn-raum-import wird in app.js verdrahtet (dort lebt der Datei-Input).
}
