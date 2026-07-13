/**
 * Kontext-Schicht: Wer benutzt die App gerade, in welcher Rolle, für welche
 * Gruppen?
 *
 * Heute gibt es genau eine Betriebsart: "lokal" — kein Login, keine Rollen,
 * alle Daten bleiben auf dem Gerät, volle Rechte. Die UI fragt aber bereits
 * überall diese Schicht (statt Rechte fest zu verdrahten), damit später
 * andere Quellen den Kontext befüllen können, ohne die App umzubauen:
 *
 *   1. "lokal"  — heutiger Zustand (dieses Objekt, unverändert).
 *   2. "server" — eigener Server mit eigener Nutzerverwaltung
 *                 (Login-Antwort setzt nutzer/rolle/gruppen).
 *   3. "lti"    — Start aus Moodle via LTI 1.3: Moodle liefert Nutzer,
 *                 Rolle (Student/Teacher) und Gruppenzugehörigkeit im
 *                 signierten Launch mit.
 *
 * Rollenmodell (für später):
 *   "admin"       — alles (heutige lokale Betriebsart)
 *   "tutor"       — sieht/bearbeitet nur Teilnehmer/innen der eigenen
 *                   Gruppen (stufe+stufenzusatz), keine Zuteilung
 *   "teilnehmer"  — sieht/bearbeitet nur die eigenen Wünsche
 */

export const Kontext = {
  quelle: "lokal",   // "lokal" | "server" | "lti"
  nutzer: null,      // z. B. { id, anzeigename } — lokal: niemand
  rolle: "admin",    // lokal: volle Rechte
  gruppen: null,     // null = alle Gruppen; sonst [{stufe, stufenzusatz}, …]

  /** Kurzbeschreibung für die Kopfzeile. */
  beschreibung() {
    if (this.quelle === "lokal") return "lokal · ohne Anmeldung";
    const wer = this.nutzer ? this.nutzer.anzeigename : "unbekannt";
    return `${wer} · ${this.rolle} · ${this.quelle}`;
  },

  /** Darf der aktuelle Nutzer diese/n Teilnehmer/in sehen? */
  darfTeilnehmerSehen(t) {
    if (this.rolle === "admin") return true;
    if (this.gruppen === null) return true;
    return this.gruppen.some(
      (g) => g.stufe === t.stufe && g.stufenzusatz === t.stufenzusatz
    );
  },

  /** Darf der aktuelle Nutzer diese/n Teilnehmer/in bearbeiten? */
  darfTeilnehmerBearbeiten(t) {
    if (this.rolle === "admin") return true;
    if (this.rolle === "tutor") return this.darfTeilnehmerSehen(t);
    return false; // "teilnehmer": nur eigener Datensatz — kommt mit Quelle 2/3
  },

  /** Darf der aktuelle Nutzer Optionen anlegen/ändern? */
  darfOptionenBearbeiten() {
    return this.rolle === "admin";
  },

  /** Darf der aktuelle Nutzer die automatische Zuteilung starten? */
  darfZuteilen() {
    return this.rolle === "admin";
  },
};
