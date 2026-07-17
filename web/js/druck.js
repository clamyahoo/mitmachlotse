/**
 * Druck-Listen: baut Gruppenlisten in den #druckbereich und öffnet die
 * Druckansicht des Browsers (dort ist auch "Als PDF speichern" verfügbar).
 * Gegenstück zu den Gesamtlisten-Exporten der Desktop-App — als Web-Version
 * über den nativen Browser-Druck statt eigener PDF-Erzeugung.
 */

import * as db from "./db.js";

function gruppeText(t) {
  const zusatz = t.stufenzusatz && t.stufenzusatz !== "-" ? t.stufenzusatz : "";
  return `${t.stufe}${zusatz}`;
}

function rangText(t, nummer, mw) {
  if (!nummer) return "–";
  const wuensche = [t.wunsch_1, t.wunsch_2, t.wunsch_3, t.wunsch_4, t.wunsch_5]
    .slice(0, mw).filter((w) => w !== 0);
  const idx = wuensche.indexOf(nummer);
  return idx >= 0 ? `Wunsch ${idx + 1}` : "kein Wunsch";
}

/** [{titel, headers, rows}] — je zugewiesener Option eine Gruppe.
 *  Bei aktivem Nachbearbeitungsmodus wird jede Umverteilung von beiden
 *  Seiten sichtbar (wie am Desktop): Neuzugänge als gelbe Zeilen mit
 *  "… · neu (vorher: N)", Abgänge als durchgestrichene Zeilen am
 *  Gruppenende ("umverteilt (jetzt: M)"). */
export function gesamtNachOptionen() {
  const k = db.getFeldkonfig();
  const tn = db.getAlleTeilnehmer();
  const modus = db.istBearbeitungsmodus();
  const gruppen = [];
  for (const p of db.getAlleProjekte()) {
    const mitglieder = tn.filter((t) => t.projekt === p.nummer);
    const leitung = p.leitung && k.leitung_label ? ` — ${p.leitung}` : "";
    const rows = mitglieder.map((t) => {
      const rang = rangText(t, p.nummer, k.max_wuensche);
      const neu = modus && t.projekt_baseline !== null
        && t.projekt_baseline !== p.nummer;
      if (neu) {
        const vorher = t.projekt_baseline || "–";
        return { klasse: "neu", zellen: [
          `${t.nachname}, ${t.vorname}`, gruppeText(t),
          `${rang} · neu (vorher: ${vorher})`,
        ]};
      }
      return [`${t.nachname}, ${t.vorname}`, gruppeText(t), rang];
    });
    if (modus) {
      // Abgänge: waren zur Basis-Zeit hier, sind jetzt woanders
      const geister = tn.filter((t) =>
        t.projekt_baseline === p.nummer && t.projekt !== p.nummer);
      for (const t of geister) {
        rows.push({ klasse: "geist", zellen: [
          `${t.nachname}, ${t.vorname}`, gruppeText(t),
          `umverteilt (jetzt: ${t.projekt || "–"})`,
        ]});
      }
    }
    gruppen.push({
      titel: `${p.nummer}: ${p.projektname}${leitung} (${mitglieder.length} von max. ${p.tnmax})`,
      headers: ["Name", k.stufe_label, "Wunschrang erhalten"],
      rows,
    });
  }
  const ohne = tn.filter((t) => !t.projekt);
  if (ohne.length) {
    gruppen.push({
      titel: `(noch nicht zugeteilt) — ${ohne.length}`,
      headers: ["Name", k.stufe_label, "Wunschrang erhalten"],
      rows: ohne.map((t) => [`${t.nachname}, ${t.vorname}`, gruppeText(t), "–"]),
    });
  }
  return gruppen;
}

/** [{titel, gruppe, headers, rows}] — je Gruppe (Stufe+Zusatz) eine Liste.
 *  Bei aktivem Nachbearbeitungsmodus werden umverteilte Personen gelb
 *  hervorgehoben; die Options-Zelle nennt zusätzlich die vorherige Option
 *  ("… · vorher: N"). */
export function gesamtNachGruppen() {
  const k = db.getFeldkonfig();
  const projekte = Object.fromEntries(db.getAlleProjekte().map((p) => [p.nummer, p]));
  const modus = db.istBearbeitungsmodus();
  const nameVon = (nr) => nr ? (projekte[nr]?.projektname ?? "?") : "";
  const nachGruppe = new Map();
  for (const t of db.getAlleTeilnehmer()) {
    const schluessel = gruppeText(t);
    if (!nachGruppe.has(schluessel)) nachGruppe.set(schluessel, []);
    nachGruppe.get(schluessel).push(t);
  }
  const gruppen = [];
  for (const [name, mitglieder] of [...nachGruppe.entries()].sort(
    (a, b) => a[0].localeCompare(b[0], "de", { numeric: true }))) {
    gruppen.push({
      titel: `${k.stufe_label} ${name} (${mitglieder.length})`,
      gruppe: name,
      headers: ["Name", `${k.projekt_label}-Nr.`, k.projekt_label],
      rows: mitglieder.map((t) => {
        const optName = t.projekt ? nameVon(t.projekt) : "⚠ (keine)";
        const geaendert = modus && t.projekt_baseline !== null
          && t.projekt_baseline !== t.projekt;
        if (geaendert) {
          const vorher = t.projekt_baseline
            ? `${t.projekt_baseline}: ${nameVon(t.projekt_baseline)}` : "keine";
          return { klasse: "neu", zellen: [
            `${t.nachname}, ${t.vorname}`, t.projekt || "0",
            `${optName} · vorher: ${vorher}`,
          ]};
        }
        return [`${t.nachname}, ${t.vorname}`, t.projekt || "0", optName];
      }),
    });
  }
  return gruppen;
}

/** Einzelliste für eine konkrete Optionsnummer. */
export function einzelOption(nummer) {
  return gesamtNachOptionen().filter((g) => g.titel.startsWith(`${nummer}:`));
}

/** Einzelliste für eine konkrete Gruppe (Stufe+Zusatz, z. B. „5a"). */
export function einzelGruppe(name) {
  return gesamtNachGruppen().filter((g) => g.gruppe === name);
}

/** Vorhandene Gruppen (Stufe+Zusatz) in sortierter Reihenfolge. */
export function gruppenNamen() {
  return gesamtNachGruppen().map((g) => g.gruppe);
}

/** Baut die Gruppen in den #druckbereich (ohne zu drucken — testbar). */
export function baueDruckbereich(titel, gruppen) {
  const el = document.getElementById("druckbereich");
  el.innerHTML = "";
  const h1 = document.createElement("h1");
  h1.textContent = titel;
  el.appendChild(h1);
  const datum = document.createElement("div");
  datum.className = "druckdatum";
  datum.textContent = new Date().toLocaleDateString("de-DE",
    { year: "numeric", month: "long", day: "numeric" });
  el.appendChild(datum);
  for (const g of gruppen) {
    const sec = document.createElement("section");
    const h2 = document.createElement("h2");
    h2.textContent = g.titel;
    sec.appendChild(h2);
    const tbl = document.createElement("table");
    const thead = document.createElement("thead");
    const trh = document.createElement("tr");
    for (const h of g.headers) {
      const th = document.createElement("th"); th.textContent = h; trh.appendChild(th);
    }
    thead.appendChild(trh);
    tbl.appendChild(thead);
    const tbody = document.createElement("tbody");
    for (const row of g.rows) {
      // Zeilen sind Arrays oder {klasse, zellen} (Nachbearbeitungs-Marker)
      const zellen = Array.isArray(row) ? row : row.zellen;
      const tr = document.createElement("tr");
      if (!Array.isArray(row) && row.klasse) tr.className = row.klasse;
      for (const zelle of zellen) {
        const td = document.createElement("td"); td.textContent = zelle; tr.appendChild(td);
      }
      tbody.appendChild(tr);
    }
    tbl.appendChild(tbody);
    sec.appendChild(tbl);
    el.appendChild(sec);
  }
  return el;
}

/** Druckansicht öffnen (Browser-Dialog, inkl. "Als PDF speichern"). */
export function drucke(titel, gruppen) {
  baueDruckbereich(titel, gruppen);
  window.print();
}
