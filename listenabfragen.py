"""
Abfragefunktionen für die Listenfenster:
Wunschauswertung, Projektteilnehmerlisten, Klassenlisten mit Zuteilung.
"""

import database as db


def _basis_headers() -> list:
    """Gibt die dynamischen Spaltenüberschriften für Teilnehmerlisten zurück."""
    k = db.get_feldkonfig()
    return [
        "Name",
        k.get("stufe_label", "Gruppenbereich"),
        k.get("stufenzusatz_label", "Gruppenzusatz"),
        "Geschlecht",
        "Wunsch 1", "Wunsch 2", "Wunsch 3", "Wunsch 4", "Wunsch 5",
        k.get("projekt_label", "Projekt"),
    ]

def _jgst_sortkey(jgst_val) -> int:
    s = str(jgst_val)
    digits = ""
    for ch in s:
        if ch.isdigit():
            digits += ch
        else:
            break
    try:
        return int(digits) if digits else 0
    except ValueError:
        return 0


def _projekte_dict() -> dict:
    return {p["nummer"]: p for p in db.get_all_projekte()}


# ── Wunschauswertung ─────────────────────────────────────────────────────────

def _wunsch_spalten(s: dict) -> list:
    """
    Gibt die 5 Wunschwerte als Liste zurück (reine Zahlen, inkl. "0" für
    'kein Wunsch eingetragen' -- konsistent mit der Anzeige in der
    Schülertabelle im Hauptfenster, die ebenfalls den tatsächlichen
    Datenwert "0" statt eines Platzhalters wie "-" zeigt).
    """
    return [str(w) for w in
            [s["wunsch_1"], s["wunsch_2"], s["wunsch_3"], s["wunsch_4"], s["wunsch_5"]]]


def get_wunschauswertung(projekt_nummer: int = None, wunsch_rang=None):
    """
    Zeigt, welche Schüler welches Projekt auf welchem Wunschrang gewählt haben.

    projekt_nummer: falls gesetzt, nur Wünsche für dieses Projekt
    wunsch_rang:    falls gesetzt (1-5), nur dieser Wunschrang.
                    Sonderfall 0: zeigt Teilnehmer/innen, die GAR KEINEN Wunsch
                    abgegeben haben (alle 5 Wunschfelder = 0). projekt_nummer
                    wird in diesem Fall ignoriert.

    Gibt (headers, rows, ids) zurück.
    """
    schueler = db.get_all_teilnehmer()
    projekte = _projekte_dict()

    basis_headers = _basis_headers()

    # Sonderfall: Schüler ohne jeglichen Wunsch anzeigen
    if wunsch_rang == 0:
        headers = basis_headers + ["Fixiert"]
        rows = []
        ids = []
        for s in schueler:
            wuensche = [s["wunsch_1"], s["wunsch_2"], s["wunsch_3"],
                        s["wunsch_4"], s["wunsch_5"]]
            anzahl = sum(1 for w in wuensche if w != 0)
            if anzahl == 0:
                rows.append([
                    f"{s['nachname']}, {s['vorname']}",
                    s["stufe"],
                    s["stufenzusatz"],
                    s["geschlecht"],
                    *_wunsch_spalten(s),
                    s["projekt"] if s["projekt"] != 0 else "0",
                    "✓" if s.get("fest_zugewiesen") else "",
                ])
                ids.append(s["id"])
        kombiniert = sorted(zip(rows, ids), key=lambda x: (_jgst_sortkey(x[0][1]), str(x[0][2]), x[0][0]))
        rows = [r for r, _ in kombiniert]
        ids = [i for _, i in kombiniert]
        return headers, rows, ids

    headers = basis_headers + ["Wunschrang", "Fixiert"]
    rows = []
    ids = []

    wunsch_felder = {
        1: "wunsch_1", 2: "wunsch_2", 3: "wunsch_3",
        4: "wunsch_4", 5: "wunsch_5",
    }
    raenge = [wunsch_rang] if wunsch_rang else [1, 2, 3, 4, 5]

    # Sonderfall "Projekt 0" (= Wunschrang nicht ausgefüllt)
    if projekt_nummer == 0 and wunsch_rang is None:
        for s in schueler:
            leere_raenge = [
                rang for rang in raenge
                if s[wunsch_felder[rang]] == 0
            ]
            if not leere_raenge:
                continue
            rang_text = ", ".join(f"Wunsch {r}" for r in leere_raenge)
            rows.append([
                f"{s['nachname']}, {s['vorname']}",
                s["stufe"],
                s["stufenzusatz"],
                s["geschlecht"],
                *_wunsch_spalten(s),
                s["projekt"] if s["projekt"] != 0 else "0",
                rang_text,
                "✓" if s.get("fest_zugewiesen") else "",
            ])
            ids.append(s["id"])

        kombiniert = sorted(zip(rows, ids), key=lambda x: (_jgst_sortkey(x[0][1]), str(x[0][2]), x[0][0]))
        rows = [r for r, _ in kombiniert]
        ids = [i for _, i in kombiniert]
        return headers, rows, ids

    # (alle Projekte) ohne Projekt-Filter: eine Zeile pro Person,
    # Wunschrang bezieht sich auf das ZUGETEILTE Projekt
    if projekt_nummer is None and wunsch_rang is None:
        for s in schueler:
            wuensche = [s[wunsch_felder[r]] for r in range(1, 6)]
            p = s["projekt"]
            if p != 0 and p in wuensche:
                rang = wuensche.index(p) + 1
                rang_text = f"Wunsch {rang}"
            elif p == 0:
                rang_text = "–"
            else:
                rang_text = "kein Wunsch"
            rows.append([
                f"{s['nachname']}, {s['vorname']}",
                s["stufe"],
                s["stufenzusatz"],
                s["geschlecht"],
                *_wunsch_spalten(s),
                p if p != 0 else "0",
                rang_text,
                "✓" if s.get("fest_zugewiesen") else "",
            ])
            ids.append(s["id"])
        kombiniert = sorted(zip(rows, ids), key=lambda x: (_jgst_sortkey(x[0][1]), str(x[0][2]), x[0][0]))
        rows = [r for r, _ in kombiniert]
        ids = [i for _, i in kombiniert]
        return headers, rows, ids

    # Spezifischer Projekt- oder Wunschrang-Filter:
    # eine Zeile pro Wunsch, der dem Filter entspricht
    for s in schueler:
        for rang in raenge:
            feld = wunsch_felder[rang]
            p_nr = s[feld]

            if projekt_nummer is not None:
                if p_nr != projekt_nummer:
                    continue
            else:
                if p_nr == 0:
                    continue

            rows.append([
                f"{s['nachname']}, {s['vorname']}",
                s["stufe"],
                s["stufenzusatz"],
                s["geschlecht"],
                *_wunsch_spalten(s),
                s["projekt"] if s["projekt"] != 0 else "0",
                f"Wunsch {rang}",
                "✓" if s.get("fest_zugewiesen") else "",
            ])
            ids.append(s["id"])

    kombiniert = sorted(zip(rows, ids), key=lambda x: (_jgst_sortkey(x[0][1]), str(x[0][2]), x[0][0]))
    rows = [r for r, _ in kombiniert]
    ids = [i for _, i in kombiniert]
    return headers, rows, ids


def get_schueler_ohne_ausreichend_wuensche(mindest_anzahl: int = 1):
    """
    Gibt Teilnehmer/innen zurück, die weniger als mindest_anzahl Wünsche
    abgegeben haben (z. B. mindest_anzahl=1 -> komplett ohne Wunsch,
    mindest_anzahl=5 -> nicht alle 5 Wünsche ausgefüllt).
    """
    schueler = db.get_all_teilnehmer()
    headers = _basis_headers() + ["Anzahl Wünsche", "Fixiert"]
    rows = []
    for s in schueler:
        wuensche = [s["wunsch_1"], s["wunsch_2"], s["wunsch_3"],
                    s["wunsch_4"], s["wunsch_5"]]
        anzahl = sum(1 for w in wuensche if w != 0)
        if anzahl < mindest_anzahl:
            fixiert = "✓" if s.get("fest_zugewiesen") else ""
            rows.append([
                f"{s['nachname']}, {s['vorname']}",
                s["stufe"],
                s["stufenzusatz"],
                s["geschlecht"],
                *_wunsch_spalten(s),
                s["projekt"] if s["projekt"] != 0 else "0",
                anzahl,
                fixiert,
            ])
    rows.sort(key=lambda r: (_jgst_sortkey(r[1]), str(r[2]), r[0]))
    return headers, rows


# ── Projektteilnehmerliste ───────────────────────────────────────────────────

def get_projektteilnehmerliste(projekt_nummer: int):
    """
    Alle Schüler, die einem bestimmten Projekt zugeteilt sind.
    Sonderfall projekt_nummer=0: alle Teilnehmer/innen, die noch KEINEM
    Projekt zugeteilt sind.
    Gibt (headers, rows, ids, projekt_info, anzahl_aktuell) zurück.
    projekt_info ist bei projekt_nummer=0 None, da es kein echtes Projekt ist.
    anzahl_aktuell = Zahl der aktuell zugeteilten Personen OHNE die
    Geister-Einträge (siehe unten), für Titel/Zähler.
    """
    alle = db.get_all_teilnehmer()
    schueler = [s for s in alle if s["projekt"] == projekt_nummer]
    projekte = _projekte_dict()
    p = projekte.get(projekt_nummer) if projekt_nummer != 0 else None

    headers = _basis_headers() + ["Wunschrang erhalten", "Fixiert"]

    def _rang_text(s):
        if projekt_nummer == 0:
            return "–"
        wuensche = [s["wunsch_1"], s["wunsch_2"], s["wunsch_3"], s["wunsch_4"], s["wunsch_5"]]
        if projekt_nummer in wuensche:
            return f"Wunsch {wuensche.index(projekt_nummer) + 1}"
        return "kein Wunsch"

    rows = []
    ids = []
    for s in schueler:
        fixiert = "✓" if s.get("fest_zugewiesen") else ""
        rows.append([
            f"{s['nachname']}, {s['vorname']}",
            s["stufe"],
            s["stufenzusatz"],
            s["geschlecht"],
            *_wunsch_spalten(s),
            s["projekt"] if s["projekt"] != 0 else "0",
            _rang_text(s),
            fixiert,
        ])
        ids.append(s["id"])

    kombiniert = sorted(zip(rows, ids), key=lambda x: (_jgst_sortkey(x[0][1]), str(x[0][2]), x[0][0]))
    rows = [r for r, _ in kombiniert]
    ids = [i for _, i in kombiniert]
    anzahl_aktuell = len(rows)

    # Geister-Einträge (Nachbearbeitungsmodus): Personen, die zur Basis-Zeit
    # dieser Option zugeteilt waren, jetzt aber woanders sind. Rein informativ
    # (durchgestrichen, ans Ende der Liste), zählen NICHT zu anzahl_aktuell.
    if projekt_nummer != 0 and db.ist_bearbeitungsmodus_aktiv():
        geister = [s for s in alle
                   if s.get("projekt_baseline") == projekt_nummer
                   and s["projekt"] != projekt_nummer]
        geister.sort(key=lambda s: (_jgst_sortkey(s["stufe"]),
                                     str(s["stufenzusatz"]), str(s["nachname"])))
        for s in geister:
            g = lambda v: db.Geist(db._durchstreichen(str(v)))
            aktuell = s["projekt"] if s["projekt"] != 0 else 0
            rows.append([
                g(f"{s['nachname']}, {s['vorname']}"),
                g(s["stufe"]),
                g(s["stufenzusatz"]),
                g(s["geschlecht"]),
                *[g(w) for w in _wunsch_spalten(s)],
                g(f"jetzt: {aktuell}" if aktuell else "jetzt: –"),
                g("umverteilt"),
                g(""),
            ])
            ids.append(s["id"])

    return headers, rows, ids, p, anzahl_aktuell


# ── Klassenliste mit Zuteilung ───────────────────────────────────────────────

def get_klassenliste(jgst: str, abteilung: str = None):
    """
    Alle Schüler einer Jahrgangsstufe (optional + Klassenzusatz) mit
    zugeteiltem Projekt.
    Gibt (headers, rows, ids) zurück.
    """
    alle = db.get_all_teilnehmer()

    schueler = [s for s in alle if str(s["stufe"]) == str(jgst)]
    if abteilung:
        schueler = [s for s in schueler if s["stufenzusatz"] == abteilung]

    headers = _basis_headers() + ["Fixiert"]
    rows = []
    ids = []

    for s in schueler:
        fixiert = "✓" if s.get("fest_zugewiesen") else ""
        rows.append([
            f"{s['nachname']}, {s['vorname']}",
            s["stufe"],
            s["stufenzusatz"],
            s["geschlecht"],
            *_wunsch_spalten(s),
            db.zuteilung_anzeige(s),
            fixiert,
        ])
        ids.append(s["id"])

    kombiniert = sorted(zip(rows, ids), key=lambda x: x[0][0])
    rows = [r for r, _ in kombiniert]
    ids = [i for _, i in kombiniert]
    return headers, rows, ids


def get_verfuegbare_klassen() -> list:
    """Gibt eine sortierte Liste eindeutiger (stufe, stufenzusatz)-Kombinationen zurück."""
    alle = db.get_all_teilnehmer()
    klassen = set()
    for s in alle:
        klassen.add((s["stufe"], s["stufenzusatz"]))
    result = sorted(klassen, key=lambda k: (_jgst_sortkey(k[0]), str(k[1])))
    return result


# ── Projektdetails ───────────────────────────────────────────────────────────

def get_projektdetails(projekt_nummer: int) -> dict:
    """
    Liefert detaillierte Statistiken zu einem einzelnen Projekt:
    - Projekt-Stammdaten (Name, TN min/max)
    - Wie oft das Projekt insgesamt gewünscht wurde (über alle Ränge)
    - Aufschlüsselung der Wünsche nach Rang (Wunsch 1: n, Wunsch 2: n, ...)
    - Für jede zugeteilte Person, mit welchem Wunschrang sie das Projekt
      bekommen hat (rein statistisch, OHNE Namen)
    - Anzahl der Zuteilungen, die nicht auf einem eigenen Wunsch beruhten
      (z. B. manuelle Ausweich-Zuteilung)

    Gibt None zurück, falls das Projekt nicht existiert.
    """
    projekte = _projekte_dict()
    p = projekte.get(projekt_nummer)
    if p is None:
        return None

    alle = db.get_all_teilnehmer()

    wunsch_anzahl_nach_rang = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    gesamt_gewuenscht = 0

    for s in alle:
        wuensche = [s["wunsch_1"], s["wunsch_2"], s["wunsch_3"], s["wunsch_4"], s["wunsch_5"]]
        if projekt_nummer in wuensche:
            rang = wuensche.index(projekt_nummer) + 1
            wunsch_anzahl_nach_rang[rang] += 1
            gesamt_gewuenscht += 1

    zugeteilte = [s for s in alle if s["projekt"] == projekt_nummer]
    zuteilung_nach_rang = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    zuteilung_ohne_wunsch = 0

    for s in zugeteilte:
        wuensche = [s["wunsch_1"], s["wunsch_2"], s["wunsch_3"], s["wunsch_4"], s["wunsch_5"]]
        if projekt_nummer in wuensche:
            rang = wuensche.index(projekt_nummer) + 1
            zuteilung_nach_rang[rang] += 1
        else:
            zuteilung_ohne_wunsch += 1

    return {
        "projekt": p,
        "gesamt_gewuenscht": gesamt_gewuenscht,
        "wunsch_anzahl_nach_rang": wunsch_anzahl_nach_rang,
        "anzahl_zugeteilt": len(zugeteilte),
        "zuteilung_nach_rang": zuteilung_nach_rang,
        "zuteilung_ohne_wunsch": zuteilung_ohne_wunsch,
    }


# ── Qualitätsprüfung Wunscheingaben ──────────────────────────────────────────

def get_qualitaetspruefung(max_wuensche: int = 5, nur_ids: list = None) -> dict:
    """
    Analysiert die Wunscheingaben aller Teilnehmer/innen auf vier Kategorien:

    - 'unzulaessig':    Wünsche außerhalb des erlaubten Stufenbereichs
    - 'unvollstaendig': Weniger als max_wuensche Wünsche eingetragen
                        (aber mindestens 1)
    - 'null':           Gar keine Wünsche (alle = 0)
    - 'mehrfach':       Dieselbe Option mehrmals als Wunsch eingetragen
                        (kann bewusst sein — nur Hinweis)

    nur_ids: falls angegeben, werden nur Teilnehmer/innen mit diesen IDs
             geprüft (z. B. gerade importierte Datensätze). Ohne Angabe
             wird die gesamte Datenbank durchsucht.

    Gibt dict mit je einer Liste von dicts zurück.
    """
    alle = db.get_all_teilnehmer()
    if nur_ids is not None:
        ids_set = set(nur_ids)
        alle = [t for t in alle if t["id"] in ids_set]
    projekte = {p["nummer"]: p for p in db.get_all_projekte()}
    wunsch_felder = [f"wunsch_{i}" for i in range(1, 6)]

    unzulaessig    = []
    unvollstaendig = []
    null_wuensche  = []
    mehrfach       = []

    for t in alle:
        name     = f"{t['nachname']}, {t['vorname']}"
        gruppe   = f"{t['stufe']}{t['stufenzusatz']}"
        wuensche = [t[f] for f in wunsch_felder]  # alle 5, auch wenn max_wuensche < 5
        aktive   = [w for w in wuensche[:max_wuensche] if w != 0]

        # Null-Wünsche
        hat_wuensche = any(w != 0 for w in wuensche)
        if not hat_wuensche:
            null_wuensche.append({
                "id": t["id"], "name": name, "gruppe": gruppe
            })
            continue  # unvollständig wäre hier redundant

        # Unvollständig (innerhalb max_wuensche)
        if len(aktive) < max_wuensche:
            unvollstaendig.append({
                "id": t["id"], "name": name, "gruppe": gruppe,
                "anzahl": len(aktive), "max": max_wuensche
            })

        # Mehrfachnennungen
        aktive_nrn = [w for w in wuensche[:max_wuensche] if w != 0]
        gesehen = {}
        for i, w in enumerate(wuensche[:max_wuensche], 1):
            if w == 0:
                continue
            gesehen.setdefault(w, []).append(i)
        for p_nr, raenge in gesehen.items():
            if len(raenge) > 1:
                p_name = projekte[p_nr]["projektname"] if p_nr in projekte else f"#{p_nr}"
                mehrfach.append({
                    "id": t["id"], "name": name, "gruppe": gruppe,
                    "option_nr": p_nr, "option_name": p_name,
                    "raenge": raenge
                })

        # Unzulässige Wünsche
        import validierung as val_mod
        for rang in range(1, max_wuensche + 1):
            w = t[f"wunsch_{rang}"]
            if w == 0:
                continue
            if w not in projekte:
                unzulaessig.append({
                    "id": t["id"], "name": name, "gruppe": gruppe,
                    "rang": rang, "option_nr": w, "option_name": f"#{w} (unbekannt)",
                    "grund": "Option existiert nicht"
                })
                continue
            p = projekte[w]
            try:
                jgst = int(float(str(t["stufe"]).replace(",", ".")))
            except (ValueError, TypeError):
                jgst = 0
            if jgst != 0 and not (p["stufenmin"] <= jgst <= p["stufenmax"]):
                p_name = p["projektname"]
                unzulaessig.append({
                    "id": t["id"], "name": name, "gruppe": gruppe,
                    "rang": rang, "option_nr": w, "option_name": p_name,
                    "grund": f"Stufenbereich {p['stufenmin']}–{p['stufenmax']}, aber Stufe {jgst}"
                })

    return {
        "unzulaessig":    unzulaessig,
        "unvollstaendig": unvollstaendig,
        "null":           null_wuensche,
        "mehrfach":       mehrfach,
    }
