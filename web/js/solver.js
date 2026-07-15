/**
 * Solver-Schicht: führt die UNVERÄNDERTEN Desktop-Algorithmen im Browser aus.
 *
 * Pyodide (Python als WebAssembly, ~10 MB) wird bewusst LAZY geladen — erst
 * beim ersten Klick auf "Automatisch zuweisen", nicht beim Seitenaufruf.
 * Danach bleibt die Umgebung für weitere Läufe im Speicher.
 *
 * Ablauf je Lauf:
 *   1. Python-Module aus dem Repo-Root holen (eine Quelle der Wahrheit —
 *      exakt die Dateien, die auch die Desktop-App nutzt).
 *   2. Aktuelle DB-Bytes aus sql.js ins Pyodide-Dateisystem schreiben.
 *   3. db.DB_PATH darauf setzen und algorithmus_a/b/c + apply_ergebnis
 *      unverändert laufen lassen (schreibt direkt in die SQLite-Datei).
 *   4. Geänderte DB-Bytes zurückgeben → sql.js lädt sie neu.
 */

const PYODIDE_CDN = "https://cdn.jsdelivr.net/pyodide/v0.25.1/full/";
const PY_MODULE = ["database.py", "algorithmen.py", "_zuteilungsplaner.py",
                   "_mcmf.py", "raumzuteilung.py"];

let pyodidePromise = null;  // lazy, einmalig
let moduleGeladen = false;

function ladeScript(src) {
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = src;
    s.onload = resolve;
    s.onerror = () => reject(new Error(`Konnte ${src} nicht laden.`));
    document.head.appendChild(s);
  });
}

async function getPyodide(statusCb) {
  if (!pyodidePromise) {
    pyodidePromise = (async () => {
      statusCb("Lade Python-Umgebung (einmalig, ~10 MB) …");
      await ladeScript(PYODIDE_CDN + "pyodide.js");
      const py = await globalThis.loadPyodide({ indexURL: PYODIDE_CDN });
      // sqlite3 ist in Pyodide "unvendored" und muss explizit geladen werden
      statusCb("Lade SQLite-Modul …");
      await py.loadPackage("sqlite3");
      return py;
    })().catch((e) => {
      pyodidePromise = null; // nächster Versuch darf neu starten
      throw e;
    });
  }
  return pyodidePromise;
}

/** Die vier Kern-Module aus dem Repo-Root holen und ins Pyodide-FS legen. */
async function ladeModule(py, statusCb) {
  if (moduleGeladen) return;
  statusCb("Lade Zuteilungs-Algorithmen (Desktop-Module) …");
  for (const name of PY_MODULE) {
    const resp = await fetch("../" + name, { cache: "no-cache" });
    if (!resp.ok) {
      throw new Error(
        `Konnte ../${name} nicht laden (HTTP ${resp.status}). ` +
        `Die Seite muss aus dem Repository-Wurzelverzeichnis ausgeliefert ` +
        `werden (z. B. "python3 -m http.server" im Repo-Root, dann /web/ öffnen).`
      );
    }
    py.FS.writeFile("/" + name, await resp.text());
  }
  await py.runPythonAsync(`import sys\nsys.path.insert(0, "/")`);
  moduleGeladen = true;
}

/**
 * Führt Algorithmus "a" | "b" | "c" auf den übergebenen DB-Bytes aus.
 * Rückgabe: { dbBytes: Uint8Array, statistik: {gesamt, wunsch_treffer} }
 */
export async function zuteilen(variante, dbBytes, statusCb = () => {}) {
  if (!["a", "b", "c"].includes(variante)) {
    throw new Error(`Unbekannte Algorithmus-Variante: ${variante}`);
  }
  const py = await getPyodide(statusCb);
  await ladeModule(py, statusCb);

  statusCb("Berechne Zuteilung …");
  py.FS.writeFile("/mappe.plf", dbBytes);
  const resultJson = await py.runPythonAsync(`
import json
from pathlib import Path
import database as db
db.DB_PATH = Path("/mappe.plf")
import algorithmen

_mw = db.get_feldkonfig()["max_wuensche"]
_erg = algorithmen.algorithmus_${variante}(max_wuensche=_mw)
algorithmen.apply_ergebnis(_erg)
_stat = algorithmen.get_statistik(_erg)
json.dumps(_stat)
`);
  const neueBytes = py.FS.readFile("/mappe.plf");
  return { dbBytes: neueBytes, statistik: JSON.parse(resultJson) };
}

/**
 * Automatische Raumzuteilung — führt das UNVERÄNDERTE Desktop-Modul
 * raumzuteilung.py aus (Greedy First-Fit-Decreasing je Zeitgruppe,
 * respektiert raum_fixiert) und wendet das Ergebnis direkt über
 * database.set_raum_for_projekt an.
 * Rückgabe: { dbBytes, ergebnis: {anzahl, hinweise} }
 */
export async function raumzuteilung(dbBytes, statusCb = () => {}) {
  const py = await getPyodide(statusCb);
  await ladeModule(py, statusCb);

  statusCb("Berechne Raumzuteilung …");
  py.FS.writeFile("/mappe.plf", dbBytes);
  const resultJson = await py.runPythonAsync(`
import json
from pathlib import Path
import database as db
db.DB_PATH = Path("/mappe.plf")
import raumzuteilung

_erg = raumzuteilung.automatische_raumzuteilung()
for _nr, _rid in _erg["zuordnungen"].items():
    db.set_raum_for_projekt(_nr, _rid)
json.dumps({"anzahl": _erg["anzahl"], "hinweise": _erg["hinweise"]})
`);
  const neueBytes = py.FS.readFile("/mappe.plf");
  return { dbBytes: neueBytes, ergebnis: JSON.parse(resultJson) };
}

/** Ist die Python-Umgebung schon geladen? (für UI-Hinweise) */
export function istBereit() {
  return moduleGeladen;
}
