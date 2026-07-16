/**
 * Mehrstufige Assistenten — Web-Gegenstücke zu EinrichtungsassistentDialog
 * und TabellenAssistentDialog der Desktop-App (dialoge.py):
 *
 *  - Einrichtungsassistent: erscheint nach „Neue Planungsmappe". Führt Schritt
 *    für Schritt durch Bezeichnungen → Optionen-Import → Teilnehmer-Import;
 *    alternativ „mit Standardwerten sofort beginnen" oder „bestehende Mappe
 *    öffnen".
 *  - Tabellen-Assistent: erklärt den Weg „Tabellen extern ausfüllen lassen"
 *    (einrichten → exportieren → extern ausfüllen → reimportieren) und öffnet
 *    an den passenden Stellen die bestehenden Dialoge.
 *
 * Beide teilen sich denselben Seiten-Stack-Aufbau (baueAssistent). Untergeordnete
 * Dialoge (Bezeichnungen, Import) werden per <dialog>.showModal() ÜBER dem
 * Assistenten gestapelt — der Assistent bleibt offen und aktualisiert danach
 * seine Statuszeile.
 */

import * as db from "./db.js";

const $ = (id) => document.getElementById(id);

let api = null;

/**
 * @param {object} a  Schnittstelle zur App:
 *   status(text), renderAlles(),
 *   zeigeLabelsDialog(onClose), starteImport(art, onDone),
 *   ladeBeispieldaten(), oeffneDateiPicker(), exportWunschlisten(proGruppe)
 */
export function initAssistenten(a) {
  api = a;
}

// ── Gemeinsamer Aufbau: gestapelte Seiten mit Zurück/Weiter/Fertig ───────────

function baueAssistent(dlg, seiten, { schrittZeigen = true } = {}) {
  let i = 0;

  function render() {
    dlg.innerHTML = "";

    if (schrittZeigen) {
      const s = document.createElement("div");
      s.className = "assi-schritt";
      // Willkommensseite (Index 0) ohne „Schritt x von y"
      s.textContent = i === 0 ? "" : `Schritt ${i} von ${seiten.length - 1}`;
      dlg.appendChild(s);
    }

    const body = document.createElement("div");
    body.className = "assi-body";
    seiten[i].bauen(body, steuerung);
    dlg.appendChild(body);

    const nav = document.createElement("div");
    nav.className = "assi-nav";
    const links = document.createElement("div");
    const rechts = document.createElement("div");
    links.className = "assi-nav-links";
    rechts.className = "assi-nav-rechts";

    if (i > 0) {
      const b = knopf("◀ Zurück", () => { i--; render(); }, "sekundaer");
      links.appendChild(b);
    }
    // „Überspringen" auf optionalen Zwischenschritten
    if (seiten[i].optional && i < seiten.length - 1) {
      links.appendChild(knopf("Schritt überspringen", () => { i++; render(); }, "sekundaer"));
    }

    if (i < seiten.length - 1) {
      // Seite darf „Weiter" verbieten/umleiten (z. B. Willkommensseite)
      const weiter = knopf("Weiter ▶", () => {
        const ziel = seiten[i].weiter ? seiten[i].weiter() : i + 1;
        if (ziel === "schliessen") { dlg.close(); return; }
        if (typeof ziel === "number") i = ziel;
        else i = i + 1;
        render();
      });
      rechts.appendChild(weiter);
    } else {
      rechts.appendChild(knopf("✓ Fertig", () => dlg.close()));
    }

    nav.append(links, rechts);
    dlg.appendChild(nav);
  }

  const steuerung = {
    aktualisieren: render,
    weiterZu: (n) => { i = n; render(); },
  };

  render();
  if (!dlg.open) dlg.showModal();
}

function knopf(text, onClick, klasse = "") {
  const b = document.createElement("button");
  b.textContent = text;
  if (klasse) b.className = klasse;
  b.addEventListener("click", onClick);
  return b;
}

function absatz(html, klasse = "") {
  const p = document.createElement("p");
  p.innerHTML = html;
  if (klasse) p.className = klasse;
  return p;
}

function statusZeile(text, ok = false) {
  const el = document.createElement("div");
  el.className = "assi-status" + (ok ? " ok" : "");
  el.textContent = text;
  return el;
}

// ── Einrichtungsassistent ────────────────────────────────────────────────────

export function zeigeEinrichtungsassistent() {
  const dlg = $("dlg-start");
  // Merker für die Statuszeilen der Import-/Bezeichnungsschritte
  const zustand = { bezeichnungen: false, optionen: null, teilnehmer: null };

  const seiten = [
    { // Seite 0: Willkommen
      bauen(body) {
        const logo = document.createElement("img");
        logo.src = "../img/mitmachlotse.png";
        logo.alt = "Mitmach-Lotse";
        logo.className = "assi-logo";
        logo.onerror = () => logo.remove();
        body.appendChild(logo);

        body.appendChild(absatz(
          "<span class='assi-titel'>Mitmach-Lotse</span>", "assi-zentriert"));
        body.appendChild(absatz(
          "Schön, dass Sie da sind! Richten Sie in wenigen Schritten Ihre " +
          "erste Planungsmappe ein.", "assi-zentriert hinweis"));
        body.appendChild(absatz(
          "<b>Diese Planungsmappe ist noch leer. Wie möchten Sie beginnen?</b>"));

        const wahl = document.createElement("div");
        wahl.className = "assi-wahl";
        for (const [wert, titel, text] of [
          ["assistent", "Mit dem Assistenten einrichten",
           "Schritt für Schritt: Bezeichnungen anpassen, Optionen und " +
           "Teilnehmer/innen importieren."],
          ["standard", "Mit Standardbezeichnungen sofort beginnen",
           'Alles lässt sich später über „Bezeichnungen anpassen" ändern.'],
          ["laden", "Bestehende Planungsmappe öffnen",
           "Eine vorhandene .plf-/.db-Datei laden und damit weiterarbeiten."],
        ]) {
          const lab = document.createElement("label");
          lab.className = "assi-radio";
          const rb = document.createElement("input");
          rb.type = "radio"; rb.name = "assi-start"; rb.value = wert;
          if (wert === "assistent") rb.checked = true;
          const inhalt = document.createElement("div");
          inhalt.innerHTML = `<b>${titel}</b><br><span class="hinweis">${text}</span>`;
          lab.append(rb, inhalt);
          wahl.appendChild(lab);
        }
        body.appendChild(wahl);
      },
      weiter() {
        const wert = dlg.querySelector('input[name="assi-start"]:checked')?.value;
        if (wert === "standard") return "schliessen";
        if (wert === "laden") { dlg.close(); api.oeffneDateiPicker(); return "schliessen"; }
        return 1; // Assistent: zu Schritt 1
      },
    },
    { // Seite 1: Bezeichnungen
      optional: true,
      bauen(body, steuerung) {
        body.appendChild(absatz("<b>Schritt 1 von 3 – Bezeichnungen</b>"));
        body.appendChild(absatz(
          'Passen Sie Begriffe wie „Option", „Gruppenbereich" oder die Anzahl ' +
          "der Wunschränge an Ihren Anwendungsfall an. Später jederzeit über " +
          '„Bezeichnungen anpassen" änderbar.', "hinweis"));
        body.appendChild(knopf("Bezeichnungen konfigurieren …", () => {
          api.zeigeLabelsDialog(() => {
            zustand.bezeichnungen = true;
            steuerung.aktualisieren();
          });
        }));
        const k = db.getFeldkonfig();
        body.appendChild(zustand.bezeichnungen
          ? statusZeile(
              `✓ Gespeichert: ${k.projekt_label} · ${k.stufe_label} · ` +
              `${k.max_wuensche} Wunschränge`, true)
          : statusZeile("Noch nicht angepasst – Standardwerte werden verwendet."));
      },
    },
    { // Seite 2: Optionen importieren
      optional: true,
      bauen(body, steuerung) {
        const k = db.getFeldkonfig();
        const plP = db.labelFormen(k.projekt_label).pluralNom;
        body.appendChild(absatz(`<b>Schritt 2 von 3 – ${plP} importieren</b>`));
        body.appendChild(absatz(
          `Möchten Sie jetzt eine ${plP}-Liste importieren? Unterstützt werden ` +
          "<b>.csv, .xlsx, .xls, .ods</b>. Dieser Schritt ist optional.", "hinweis"));
        body.appendChild(knopf(`${plP} importieren …`, () => {
          api.starteImport("optionen", (anzahl) => {
            zustand.optionen = anzahl;
            steuerung.aktualisieren();
          });
        }));
        body.appendChild(zustand.optionen !== null
          ? statusZeile(`✓ ${zustand.optionen} ${plP} importiert.`, true)
          : statusZeile("Noch nicht importiert."));
      },
    },
    { // Seite 3: Teilnehmer importieren
      bauen(body, steuerung) {
        body.appendChild(absatz("<b>Schritt 3 von 3 – Teilnehmer/innen importieren</b>"));
        body.appendChild(absatz(
          "Importieren Sie jetzt eine Teilnehmerliste (auch mehrere Dateien auf " +
          "einmal, die anhand der Spaltennamen zusammengeführt werden). " +
          "Optional.", "hinweis"));
        body.appendChild(knopf("Teilnehmer/innen importieren …", () => {
          api.starteImport("teilnehmer", (anzahl) => {
            zustand.teilnehmer = anzahl;
            steuerung.aktualisieren();
          });
        }));
        body.appendChild(zustand.teilnehmer !== null
          ? statusZeile(`✓ ${zustand.teilnehmer} Teilnehmer/innen importiert.`, true)
          : statusZeile("Noch nicht importiert."));
      },
    },
  ];

  baueAssistent(dlg, seiten);
}

// ── Tabellen-Export-/Importassistent ─────────────────────────────────────────

export function zeigeTabellenassistent() {
  const dlg = $("dlg-tabellen");
  const k = db.getFeldkonfig();
  const sl = k.stufe_label;
  const pl = k.projekt_label;
  const plP = db.labelFormen(pl).pluralNom;

  const seiten = [
    { // 1: Einführung
      bauen(body) {
        body.appendChild(absatz(
          "<span class='assi-titel'>Tabellen extern ausfüllen lassen</span>",
          "assi-zentriert"));
        body.appendChild(absatz(
          "Dieser Assistent führt durch den Weg, wenn Wünsche nicht direkt in " +
          "der App, sondern extern eingetragen werden — z. B. durch Tutor/innen " +
          "oder Klassenleitungen:"));
        body.appendChild(absatz(
          `<b>1. Tabellen einrichten</b> – Bezeichnungen und ${plP}-Liste stehen fest.<br>` +
          "<b>2. Exportieren</b> – als Tabelle(n) zum externen Bearbeiten.<br>" +
          "<b>3. Extern ausfüllen lassen</b> – z. B. über eine geteilte Cloud.<br>" +
          "<b>4. Reimportieren</b> – die ausgefüllten Dateien fließen zurück in " +
          "die Planungsmappe."));
      },
    },
    { // 2: Tabellen einrichten
      bauen(body) {
        body.appendChild(absatz("<b>Schritt 2 von 5 – Tabellen einrichten</b>"));
        body.appendChild(absatz(
          `&#8226; <b>Bezeichnungen</b> (${sl}, ${pl} …) passen zum Sprachgebrauch.<br>` +
          `&#8226; <b>${plP}-Liste</b> ist mit Nummer, Name und Platzzahl angelegt – ` +
          "nur so ist später prüfbar, ob ein Wunsch zulässig ist.<br>" +
          `&#8226; <b>Grunddaten der Teilnehmer/innen</b> (Name, ${sl}) sind erfasst; ` +
          "die Wunschspalten dürfen noch leer sein.", "hinweis"));
        body.appendChild(knopf("Bezeichnungen anpassen …",
          () => api.zeigeLabelsDialog(() => {})));
      },
    },
    { // 3: Exportieren
      bauen(body) {
        body.appendChild(absatz("<b>Schritt 3 von 5 – Exportieren</b>"));
        body.appendChild(absatz(
          "Exportiert eine Tabelle mit allen Teilnehmer/innen und ihren (noch " +
          "leeren) Wunschspalten zum externen Ausfüllen. Mit der Option " +
          '<b>„Je Gruppe eine eigene Datei"</b> entsteht pro Gruppe eine kompakte ' +
          "Datei — praktisch zum Verteilen.", "hinweis"));
        const proGruppe = document.createElement("label");
        proGruppe.className = "assi-radio";
        const cb = document.createElement("input");
        cb.type = "checkbox"; cb.id = "tabassi-progruppe";
        proGruppe.append(cb, document.createTextNode(" Je Gruppe eine eigene Datei"));
        body.appendChild(proGruppe);
        body.appendChild(knopf("Wunschlisten-Vorlage exportieren …", () => {
          const n = api.exportWunschlisten($("tabassi-progruppe").checked);
          const st = body.querySelector(".assi-status");
          st?.remove();
          body.appendChild(statusZeile(`✓ Export erstellt (${n} Datei(en)).`, true));
        }));
        body.appendChild(absatz(
          "<i>Praxis:</i> Einzeldateien je Gruppe in einem Cloud-Ordner ablegen, " +
          "den die Gruppenverantwortlichen ausfüllen.", "assi-praxis"));
      },
    },
    { // 4: Extern ausfüllen
      bauen(body) {
        body.appendChild(absatz("<b>Schritt 4 von 5 – Extern ausfüllen lassen</b>"));
        body.appendChild(absatz(
          "Dieser Schritt findet außerhalb der App statt:"));
        body.appendChild(absatz(
          "&#8226; Datei(en) an die zuständigen Personen geben (Cloud, E-Mail, Ausdruck).<br>" +
          "&#8226; .xlsx/.ods öffnen sich in Excel, LibreOffice und den meisten Office-Apps.<br>" +
          `&#8226; Spaltenüberschriften und ${sl}-Angabe unverändert lassen, damit der ` +
          "Reimport passt.<br>" +
          "&#8226; Wünsche vollständig und möglichst zulässig eintragen.", "hinweis"));
        body.appendChild(absatz(
          `<i>Hinweis:</i> Soll eine Person fest einer bestimmten ${pl} zugeordnet ` +
          `werden, bei jedem Wunsch die Nummer dieser ${pl} eintragen.`, "assi-praxis"));
      },
    },
    { // 5: Reimportieren
      bauen(body) {
        body.appendChild(absatz("<b>Schritt 5 von 5 – Reimportieren</b>"));
        body.appendChild(absatz(
          'Die ausgefüllten Dateien über „Teilnehmer/innen importieren" wieder ' +
          "einlesen. Kommen mehrere Dateien zurück (z. B. je Gruppe), lassen sie " +
          "sich in einem Schritt zusammenführen — einfach alle auf einmal " +
          "auswählen.", "hinweis"));
        body.appendChild(knopf("Teilnehmer/innen importieren …",
          () => api.starteImport("teilnehmer", () => {})));
        body.appendChild(absatz(
          "Nach dem Import lohnt der Blick in die <b>Qualitätsprüfung</b> " +
          '(Tab „Zuteilung & Auswertung"): sie zeigt unzulässige, unvollständige ' +
          "oder mehrfach genannte Wünsche.", "assi-praxis"));
      },
    },
  ];

  baueAssistent(dlg, seiten, { schrittZeigen: false });
}
