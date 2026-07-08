"""
Automatische Raumzuteilung für die Mitmach-Lotse-App.

Einfaches Greedy-Verfahren (First-Fit-Decreasing Bin-Packing), bewusst ohne
MCMF -- die Aufgabe ist deutlich simpler als die Teilnehmer-Zuteilung:

  - Optionen werden nach ihrer eingetragenen Zeit gruppiert. Zwei Optionen
    kollidieren nur bei gleichem Raum UND gleicher Zeit; verschiedene Zeiten
    dürfen denselben Raum nutzen.
  - Innerhalb einer Zeit-Gruppe bekommt jede Option einen eigenen Raum.
  - Bedarf je Option = tatsächlich zugeteilte Teilnehmerzahl (belegt), falls
    vorhanden, sonst die geplanten Plätze (tnmax).
  - Manuell fixierte Raumzuordnungen (raum_fixiert) bleiben unangetastet und
    belegen ihren Raum in der jeweiligen Zeit-Gruppe.
  - Engpässe (zu wenige/zu kleine Räume) werden als Hinweise gemeldet, nie hart
    blockiert -- konsistent mit pruefe_raumkonflikte und der Teilnehmer-
    Zuteilung.

Die Zeit wird vorausgesetzt (nur Räume werden verteilt, keine Zeiten). Optionen
mit leerer Zeit bilden eine eigene Gruppe, in der ebenfalls verschiedene Räume
vergeben werden (sichere Annahme "alles gleichzeitig").
"""

import database as db


def _bedarf(row: dict) -> int:
    """Platzbedarf einer Option: belegt, falls schon zugeteilt, sonst tnmax."""
    belegt = row.get("belegt") or 0
    if belegt > 0:
        return belegt
    return row.get("tnmax") or 0


def automatische_raumzuteilung() -> dict:
    """
    Verteilt Räume automatisch auf die Optionen.

    Rückgabe: {
        "zuordnungen": {option_nummer: raum_id},  # nur nicht-fixierte Optionen
        "hinweise":    [str, ...],                 # nicht zuweisbare Optionen
        "anzahl":      int,                        # erfolgreich zugewiesene Räume
    }
    """
    plan = db.get_raumplan()
    raeume = db.get_all_raeume()

    zuordnungen: dict = {}
    hinweise: list = []
    anzahl = 0

    # Optionen nach Zeit gruppieren (exakter Textabgleich, leere Zeit = "")
    gruppen: dict = {}
    for row in plan:
        zeit = (row.get("zeit") or "").strip()
        gruppen.setdefault(zeit, []).append(row)

    for zeit, optionen in gruppen.items():
        zeit_label = zeit if zeit else "(ohne Zeit)"

        # Räume, die in dieser Zeit-Gruppe durch fixierte Optionen belegt sind
        belegte_raeume = set()
        for row in optionen:
            if row.get("raum_fixiert") and (row.get("raum_id") or 0):
                belegte_raeume.add(row["raum_id"])

        # Nicht-fixierte Optionen nach Bedarf absteigend (First-Fit-Decreasing)
        offen = [row for row in optionen
                 if not (row.get("raum_fixiert") and (row.get("raum_id") or 0))]
        offen.sort(key=lambda r: _bedarf(r), reverse=True)

        for row in offen:
            bedarf = _bedarf(row)
            frei = [r for r in raeume if r["id"] not in belegte_raeume]

            # Bevorzugt kleinster Raum mit ausreichender BEKANNTER Kapazität
            passend = sorted(
                (r for r in frei if (r.get("kapazitaet") or 0) >= bedarf
                 and (r.get("kapazitaet") or 0) > 0),
                key=lambda r: r["kapazitaet"]
            )
            gewaehlt = passend[0] if passend else None

            # Rückfall: Raum mit unbekannter/unbegrenzter Kapazität (0)
            if gewaehlt is None:
                unbegrenzt = [r for r in frei if (r.get("kapazitaet") or 0) == 0]
                gewaehlt = unbegrenzt[0] if unbegrenzt else None

            if gewaehlt is None:
                zuordnungen[row["nummer"]] = 0  # keine passende Zuordnung
                hinweise.append(
                    f"Option {row['nummer']} ({row.get('projektname', '')}, "
                    f"Bedarf {bedarf}): kein freier Raum in Zeit „{zeit_label}“ "
                    f"groß genug."
                )
            else:
                zuordnungen[row["nummer"]] = gewaehlt["id"]
                belegte_raeume.add(gewaehlt["id"])
                anzahl += 1

    return {"zuordnungen": zuordnungen, "hinweise": hinweise, "anzahl": anzahl}


def raumzuteilung_aufheben() -> int:
    """Entfernt bei allen NICHT fixierten Optionen die Raumzuordnung.
    Gibt die Anzahl der geleerten Zuordnungen zurück."""
    plan = db.get_raumplan()
    anzahl = 0
    for row in plan:
        if row.get("raum_fixiert"):
            continue
        if row.get("raum_id") or 0:
            db.set_raum_for_projekt(row["nummer"], 0)
            anzahl += 1
    return anzahl
