"""
Validierung von Schülerwünschen gegen die Zulassungsbeschränkungen
(Jahrgangsstufen-Grenzen) der Projekte.
"""

import database as db


def jgst_int(jgst_str) -> int:
    """
    Versucht Jahrgangsstufe als int zu lesen, sonst 0.

    Robust gegenüber typischen Importformaten:
    - "5"      -> 5
    - "5a"     -> 5
    - "5.0"    -> 5   (Excel liefert Zahlen oft als Float)
    - "5,0"    -> 5   (deutsches Dezimaltrennzeichen)
    - "Jgst 5" -> 5
    - "-"      -> 0
    """
    s = str(jgst_str).strip()
    if not s or s == "-":
        return 0
    try:
        return int(float(s.replace(",", ".")))
    except ValueError:
        pass
    digits = ""
    for ch in s:
        if ch.isdigit():
            digits += ch
        elif digits:
            break
    try:
        return int(digits) if digits else 0
    except ValueError:
        return 0


def projekt_erlaubt_fuer_jgst(projekt: dict, jgst_str) -> bool:
    """
    Prüft, ob ein Projekt für eine gegebene Jahrgangsstufe zulässig ist.
    Teilnehmer/innen ohne erkennbare Jahrgangsstufe (jgst_int == 0) gelten
    als zu jedem Projekt passend (keine Einschränkung anwendbar).
    """
    jgst = jgst_int(jgst_str)
    if jgst == 0:
        return True
    return projekt["stufenmin"] <= jgst <= projekt["stufenmax"]


def hat_klassenstufenbegrenzungen() -> bool:
    """
    Prüft, ob in der aktuellen Projektliste überhaupt
    Zulassungsbeschränkungen nach Jahrgangsstufen vorhanden sind (d. h.
    mindestens ein Projekt hat nicht den vollen Bereich 0-99 als
    stufenmin/stufenmax). Wenn alle Projekte für alle Jahrgangsstufen offen
    sind, erübrigt sich jede Validierung.
    """
    projekte = db.get_all_projekte()
    return any(p["stufenmin"] > 0 or p["stufenmax"] < 99 for p in projekte)


def pruefe_wunsch(jgst_str, wunsch_projekt_nr: int, projekte_dict: dict = None):
    """
    Prüft einen einzelnen Wunsch (Projektnummer) gegen die Jahrgangsstufe.

    Gibt (zulaessig: bool, grund: str|None) zurück.
    - zulaessig=True, wenn der Wunsch 0 (kein Wunsch) ist, das Projekt
      nicht existiert (wird an anderer Stelle behandelt) oder die
      Jahrgangsstufe in den erlaubten Bereich fällt.
    - zulaessig=False mit erklärendem Grund, wenn die Jahrgangsstufe
      außerhalb des erlaubten Bereichs liegt.
    """
    if wunsch_projekt_nr == 0:
        return True, None

    if projekte_dict is None:
        projekte_dict = {p["nummer"]: p for p in db.get_all_projekte()}

    projekt = projekte_dict.get(wunsch_projekt_nr)
    if projekt is None:
        return True, None  # Unbekanntes Projekt -- andere Stelle prüft das

    if projekt_erlaubt_fuer_jgst(projekt, jgst_str):
        return True, None

    jgst = jgst_int(jgst_str)
    grund = (
        f"Projekt {wunsch_projekt_nr} ist nur für Jgst. "
        f"{projekt['stufenmin']}–{projekt['stufenmax']} zugelassen "
        f"(Schüler/in: Jgst. {jgst})"
    )
    return False, grund


def pruefe_alle_wuensche(jgst_str, wuensche: list, projekte_dict: dict = None):
    """
    Prüft eine Liste von bis zu 5 Wunsch-Projektnummern gegen die
    Jahrgangsstufe.

    Gibt eine Liste von (wunsch_rang, projekt_nr, grund) für jeden
    UNZULÄSSIGEN Wunsch zurück (leere Liste, wenn alles passt).
    wunsch_rang ist 1-basiert (1 = Wunsch 1).
    """
    if projekte_dict is None:
        projekte_dict = {p["nummer"]: p for p in db.get_all_projekte()}

    verstoesse = []
    for rang, p_nr in enumerate(wuensche, start=1):
        zulaessig, grund = pruefe_wunsch(jgst_str, p_nr, projekte_dict)
        if not zulaessig:
            verstoesse.append((rang, p_nr, grund))
    return verstoesse


def get_schueler_mit_unzulaessigen_wuenschen(nur_ids: list = None):
    """
    Durchsucht Teilnehmer/innen in der Datenbank nach Wünschen, die
    außerhalb der Jahrgangsstufen-Zulassung des jeweiligen Projekts
    liegen.

    nur_ids: falls angegeben, werden nur Teilnehmer/innen mit diesen IDs
             geprüft (z. B. gerade importierte Datensätze). Ohne Angabe
             wird die gesamte Datenbank durchsucht.

    Gibt (headers, rows, ids) für ein Listenfenster zurück. Felder mit
    unzulässigen Wünschen werden zusätzlich zur Wunschnummer mit einem
    ⚠-Symbol markiert (z. B. "9 ⚠").
    """
    alle = db.get_all_teilnehmer()
    if nur_ids is not None:
        ids_set = set(nur_ids)
        alle = [s for s in alle if s["id"] in ids_set]

    projekte_dict = {p["nummer"]: p for p in db.get_all_projekte()}

    headers = ["Name", "Jgst.", "Klassenzusatz", "Geschlecht",
               "Wunsch 1", "Wunsch 2", "Wunsch 3", "Wunsch 4", "Wunsch 5",
               "Projekt", "Unzulässige Wünsche"]
    rows = []
    ids = []

    for s in alle:
        wuensche = [s["wunsch_1"], s["wunsch_2"], s["wunsch_3"],
                    s["wunsch_4"], s["wunsch_5"]]
        verstoesse = pruefe_alle_wuensche(s["stufe"], wuensche, projekte_dict)
        if not verstoesse:
            continue

        wunsch_spalten = []
        verstoss_raenge = {v[0] for v in verstoesse}
        for rang, w in enumerate(wuensche, start=1):
            text = str(w)
            if rang in verstoss_raenge:
                text += " ⚠"
            wunsch_spalten.append(text)

        beschreibung = "; ".join(
            f"Wunsch {rang}: {grund}" for rang, p_nr, grund in verstoesse
        )

        rows.append([
            f"{s['nachname']}, {s['vorname']}",
            s["stufe"],
            s["stufenzusatz"],
            s["geschlecht"],
            *wunsch_spalten,
            s["projekt"] if s["projekt"] != 0 else "0",
            beschreibung,
        ])
        ids.append(s["id"])

    return headers, rows, ids


def setze_unzulaessige_wuensche_auf_null(nur_ids: list = None) -> int:
    """
    Setzt bei allen betroffenen Teilnehmer/innen jeden Wunsch, der nicht zur
    Jahrgangsstufen-Zulassung des jeweiligen Projekts passt, auf 0 ("kein
    Wunsch") zurück. Nur dieses Vorgehen garantiert, dass eine spätere
    automatische Einteilung die Zulassungsbeschränkungen wirklich
    einhält (ein unzulässiger, aber stehen gelassener Wunsch würde vom
    Algorithmus ohnehin nie berücksichtigt, könnte aber in Übersichten
    irreführend wirken).

    nur_ids: falls angegeben, werden nur Teilnehmer/innen mit diesen IDs
             bereinigt (z. B. gerade importierte Datensätze).

    Gibt die Anzahl der bereinigten Wunschfelder zurück (nicht die
    Anzahl der betroffenen Teilnehmer/innen).
    """
    alle = db.get_all_teilnehmer()
    if nur_ids is not None:
        ids_set = set(nur_ids)
        alle = [s for s in alle if s["id"] in ids_set]

    projekte_dict = {p["nummer"]: p for p in db.get_all_projekte()}
    wunsch_felder = ["wunsch_1", "wunsch_2", "wunsch_3", "wunsch_4", "wunsch_5"]
    anzahl_bereinigt = 0

    for s in alle:
        wuensche = [s["wunsch_1"], s["wunsch_2"], s["wunsch_3"],
                    s["wunsch_4"], s["wunsch_5"]]
        verstoesse = pruefe_alle_wuensche(s["stufe"], wuensche, projekte_dict)
        if not verstoesse:
            continue

        data = {k: s[k] for k in
               ["nachname", "vorname", "stufe", "stufenzusatz", "geschlecht",
                "wunsch_1", "wunsch_2", "wunsch_3", "wunsch_4", "wunsch_5",
                "projekt"]}
        for rang, p_nr, grund in verstoesse:
            data[wunsch_felder[rang - 1]] = 0
            anzahl_bereinigt += 1
        db.update_teilnehmer(s["id"], data)

    return anzahl_bereinigt


# ── Raumkonflikte ────────────────────────────────────────────────────────────

def pruefe_raumkonflikte() -> dict:
    """
    Prüft die Raum-/Zeitzuordnung der Optionen und gibt je betroffener Option
    einen Hinweis zurück (nur Hinweise, keine Sperre).

    Rückgabe: dict  option_nummer -> {
        "doppelbelegung": bool,   # gleicher Raum + gleiche Zeit wie andere Option(en)
        "kapazitaet":     bool,   # Raumkapazität kleiner als Belegung/geplante Plätze
        "text":           str,    # zusammengefasster Hinweistext für Tooltip/Spalte
    }
    Optionen ohne Auffälligkeit tauchen nicht im dict auf.
    """
    plan = db.get_raumplan()
    ergebnis: dict = {}

    # ── Doppelbelegung: gleiche (raum_id, zeit) bei mehr als einer Option ──
    belegung: dict = {}
    for row in plan:
        raum_id = row.get("raum_id") or 0
        zeit = (row.get("zeit") or "").strip()
        if raum_id and zeit:
            belegung.setdefault((raum_id, zeit), []).append(row)

    for (_raum_id, zeit), optionen in belegung.items():
        if len(optionen) > 1:
            raum_name = optionen[0].get("raum_name") or "?"
            for row in optionen:
                andere = [str(o["nummer"]) for o in optionen
                          if o["nummer"] != row["nummer"]]
                eintrag = ergebnis.setdefault(
                    row["nummer"],
                    {"doppelbelegung": False, "kapazitaet": False, "text": ""}
                )
                eintrag["doppelbelegung"] = True
                eintrag["_dopp"] = (
                    f"Doppelbelegung: Raum „{raum_name}“ zur Zeit "
                    f"„{zeit}“ auch bei Option {', '.join(andere)}"
                )

    # ── Kapazität: Raumkapazität < Belegung bzw. geplante Plätze (tnmax) ──
    for row in plan:
        kap = row.get("raum_kapazitaet")
        if not kap or kap <= 0:
            continue  # kein Raum zugeordnet oder Kapazität unbekannt/unbegrenzt
        belegt = row.get("belegt") or 0
        tnmax = row.get("tnmax") or 0
        raum_name = row.get("raum_name") or "?"
        meldung = None
        if belegt > kap:
            meldung = (f"Kapazität überschritten: {belegt} zugeteilt, "
                       f"Raum „{raum_name}“ fasst nur {kap}")
        elif tnmax and tnmax > kap:
            meldung = (f"Kapazität knapp: Raum „{raum_name}“ fasst {kap}, "
                       f"geplant sind bis zu {tnmax} Plätze")
        if meldung:
            eintrag = ergebnis.setdefault(
                row["nummer"],
                {"doppelbelegung": False, "kapazitaet": False, "text": ""}
            )
            eintrag["kapazitaet"] = True
            eintrag["_kap"] = meldung

    # ── Hinweistexte aus den temporären Einzelmeldungen zusammensetzen ──
    for eintrag in ergebnis.values():
        teile = []
        dopp = eintrag.pop("_dopp", None)
        kap = eintrag.pop("_kap", None)
        if dopp:
            teile.append("⚠ " + dopp)
        if kap:
            teile.append("⚠ " + kap)
        eintrag["text"] = "\n".join(teile)

    return ergebnis
