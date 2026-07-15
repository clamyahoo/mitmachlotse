/**
 * Feldauswahl vor Druck/Export — Web-Gegenstück zum SpaltenauswahlDialog
 * der Desktop-App: alle Spalten standardmäßig angehakt, "Alle"/"Keine" als
 * Schnellschalter.
 *
 * waehleSpalten(headers) → Promise<number[] | null>
 *   Array der behaltenen Spaltenindizes, oder null bei Abbruch.
 */

export function waehleSpalten(headers, titel = "Felder / Spalten für die Ausgabe wählen") {
  return new Promise((resolve) => {
    const dlg = document.getElementById("dlg-spalten");
    dlg.innerHTML = "";

    const h2 = document.createElement("h2");
    h2.textContent = titel;
    dlg.appendChild(h2);

    const schnell = document.createElement("div");
    schnell.className = "aktionszeile";
    const bAlle = document.createElement("button");
    bAlle.className = "sekundaer";
    bAlle.textContent = "Alle";
    const bKeine = document.createElement("button");
    bKeine.className = "sekundaer";
    bKeine.textContent = "Keine";
    schnell.append(bAlle, bKeine);
    dlg.appendChild(schnell);

    const liste = document.createElement("div");
    liste.className = "spalten-liste";
    const checks = headers.map((h) => {
      const label = document.createElement("label");
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = true;
      label.append(cb, document.createTextNode(h));
      liste.appendChild(label);
      return cb;
    });
    dlg.appendChild(liste);

    bAlle.addEventListener("click", () => checks.forEach((c) => { c.checked = true; }));
    bKeine.addEventListener("click", () => checks.forEach((c) => { c.checked = false; }));

    const btns = document.createElement("div");
    btns.className = "dialog-buttons";
    const bAbbr = document.createElement("button");
    bAbbr.className = "sekundaer";
    bAbbr.textContent = "Abbrechen";
    const bOk = document.createElement("button");
    bOk.id = "spalten-ok";
    bOk.textContent = "OK";
    btns.append(bAbbr, bOk);
    dlg.appendChild(btns);

    let beantwortet = false;
    const fertig = (wert) => {
      if (beantwortet) return;
      beantwortet = true;
      dlg.close();
      resolve(wert);
    };
    bAbbr.addEventListener("click", () => fertig(null));
    bOk.addEventListener("click", () => {
      const kept = checks.map((c, i) => (c.checked ? i : -1)).filter((i) => i >= 0);
      if (!kept.length) { alert("Bitte mindestens eine Spalte auswählen."); beantwortet = false; return; }
      fertig(kept);
    });
    // Esc / Schließen ohne Antwort = Abbruch
    dlg.addEventListener("close", () => fertig(null), { once: true });

    dlg.showModal();
  });
}

/** Gruppen (aus druck.js) auf die behaltenen Spaltenindizes filtern. */
export function filterGruppen(gruppen, kept) {
  const nimm = (arr) => kept.map((i) => arr[i]);
  return gruppen.map((g) => ({
    titel: g.titel,
    headers: nimm(g.headers),
    rows: g.rows.map((row) => Array.isArray(row)
      ? nimm(row)
      : { klasse: row.klasse, zellen: nimm(row.zellen) }),
  }));
}
