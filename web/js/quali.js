/**
 * Qualitätsprüfung der Wunscheingaben — Web-Gegenstück zu
 * listenabfragen.get_qualitaetspruefung (dieselben vier Kategorien und
 * Symbole wie in der Desktop-App):
 *
 *   ⚠ Unzulässig      — Wunsch außerhalb des erlaubten Bereichs / unbekannt
 *   ✎ Unvollständig   — weniger als die konfigurierte Wunschanzahl
 *   ○ Keine Wünsche   — alle Wunschfelder leer
 *   ↻ Mehrfach        — dieselbe Option mehrmals gewählt (nur Hinweis)
 *
 * Zusätzlich stellt das Modul die fortlaufende Einzelprüfung eines Wunsches
 * bereit (wunschZulaessig), die die Teilnehmertabelle nutzt, um unzulässige
 * Wünsche direkt bei der Eingabe zu markieren.
 */

import * as db from "./db.js";

/** Jahrgangsstufe robust als Zahl lesen (Spiegel von validierung.jgst_int):
 *  "5" → 5, "5a" → 5, "5.0"/"5,0" → 5, "-"/"" → 0. */
export function stufeZahl(stufe) {
  const s = String(stufe ?? "").trim();
  if (!s || s === "-") return 0;
  const f = parseFloat(s.replace(",", "."));
  if (!Number.isNaN(f)) return Math.trunc(f);
  const m = s.match(/^\d+/);
  return m ? parseInt(m[0], 10) : 0;
}

/** Prüft einen einzelnen Wunsch gegen die Stufenzulassung des Projekts.
 *  Rückgabe: { ok:true } oder { ok:false, grund:"…" }. */
export function wunschZulaessig(stufe, wunschNr, projekteDict, k = null) {
  if (!wunschNr) return { ok: true };
  const konfig = k || db.getFeldkonfig();
  const p = projekteDict[wunschNr];
  if (!p) return { ok: false, grund: `${konfig.projekt_label} ${wunschNr} existiert nicht` };
  const jgst = stufeZahl(stufe);
  if (jgst !== 0 && (jgst < p.stufenmin || jgst > p.stufenmax)) {
    return { ok: false, grund:
      `${konfig.projekt_label} ${wunschNr} nur für ${konfig.stufe_label} ` +
      `${p.stufenmin}–${p.stufenmax} (${konfig.stufe_label} ${jgst})` };
  }
  return { ok: true };
}

export function pruefeQualitaet() {
  const k = db.getFeldkonfig();
  const mw = k.max_wuensche;
  const projekte = Object.fromEntries(db.getAlleProjekte().map((p) => [p.nummer, p]));
  const eintraege = [];

  for (const t of db.getAlleTeilnehmer()) {
    const name = `${t.nachname}, ${t.vorname}`;
    const zusatz = t.stufenzusatz && t.stufenzusatz !== "-" ? t.stufenzusatz : "";
    const gruppe = `${t.stufe}${zusatz}`;
    const wuensche = [t.wunsch_1, t.wunsch_2, t.wunsch_3, t.wunsch_4, t.wunsch_5]
      .slice(0, mw);
    const aktive = wuensche.filter((w) => w !== 0);

    if (!aktive.length) {
      eintraege.push({ key: "keine", icon: "○", kategorie: "Keine Wünsche", name, gruppe,
        details: "alle Wunschfelder leer — bleibt bei der Zuteilung unversorgt" });
      continue;
    }
    if (aktive.length < mw) {
      eintraege.push({ key: "unvollstaendig", icon: "✎", kategorie: "Unvollständig", name, gruppe,
        details: `nur ${aktive.length} von ${mw} Wünschen ausgefüllt` });
    }

    // Mehrfachnennungen (kann bewusst sein — nur Hinweis)
    const gesehen = {};
    wuensche.forEach((w, i) => { if (w) (gesehen[w] ??= []).push(i + 1); });
    const mehrfach = Object.entries(gesehen).filter(([, r]) => r.length > 1);
    if (mehrfach.length) {
      const details = mehrfach.map(([nr, raenge]) => {
        const p = projekte[nr];
        return `${nr}${p ? ` (${p.projektname})` : ""} auf Wunsch ${raenge.join(" und ")}`;
      }).join("; ");
      eintraege.push({ key: "mehrfach", icon: "↻", kategorie: "Mehrfach", name, gruppe, details });
    }

    // Unzulässige Wünsche (Bereich / unbekannte Nummer)
    const probleme = [];
    wuensche.forEach((w, i) => {
      if (!w) return;
      const r = wunschZulaessig(t.stufe, w, projekte, k);
      if (!r.ok) probleme.push(`Wunsch ${i + 1}: ${r.grund}`);
    });
    if (probleme.length) {
      eintraege.push({ key: "unzulaessig", icon: "⚠", kategorie: "Unzulässig", name, gruppe,
        details: probleme.join("; ") });
    }
  }
  return eintraege;
}
