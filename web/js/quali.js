/**
 * Qualitätsprüfung der Wunscheingaben — Web-Gegenstück zu
 * listenabfragen.get_qualitaetspruefung (dieselben vier Kategorien und
 * Symbole wie in der Desktop-App):
 *
 *   ⚠ Unzulässig      — Wunsch außerhalb des erlaubten Bereichs / unbekannt
 *   ✎ Unvollständig   — weniger als die konfigurierte Wunschanzahl
 *   ○ Keine Wünsche   — alle Wunschfelder leer
 *   ↻ Mehrfach        — dieselbe Option mehrmals gewählt (nur Hinweis)
 */

import * as db from "./db.js";

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
      eintraege.push({ icon: "○", kategorie: "Keine Wünsche", name, gruppe,
        details: "alle Wunschfelder leer — bleibt bei der Zuteilung unversorgt" });
      continue;
    }
    if (aktive.length < mw) {
      eintraege.push({ icon: "✎", kategorie: "Unvollständig", name, gruppe,
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
      eintraege.push({ icon: "↻", kategorie: "Mehrfach", name, gruppe, details });
    }

    // Unzulässige Wünsche (Bereich / unbekannte Nummer)
    const jgstRoh = parseInt(String(t.stufe), 10);
    const jgst = Number.isNaN(jgstRoh) ? 0 : jgstRoh;
    const probleme = [];
    wuensche.forEach((w, i) => {
      if (!w) return;
      const p = projekte[w];
      if (!p) {
        probleme.push(`Wunsch ${i + 1}: ${k.projekt_label} ${w} existiert nicht`);
      } else if (jgst !== 0 && (jgst < p.stufenmin || jgst > p.stufenmax)) {
        probleme.push(
          `Wunsch ${i + 1} (${w}: ${p.projektname}): Bereich ` +
          `${p.stufenmin}–${p.stufenmax}, aber ${k.stufe_label} ${jgst}`);
      }
    });
    if (probleme.length) {
      eintraege.push({ icon: "⚠", kategorie: "Unzulässig", name, gruppe,
        details: probleme.join("; ") });
    }
  }
  return eintraege;
}
