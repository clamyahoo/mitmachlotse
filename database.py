"""
Datenbankmodul für die Projekttage-App.
Verwendet SQLite (in Python eingebaut).
"""

import sqlite3
import os
from pathlib import Path


DB_PATH = Path(__file__).parent / "planungsmappe.plf"

# Standard-Bezeichnungen für konfigurierbare Felder
FELDKONFIG_DEFAULTS = {
    "stufe_label":          "Gruppenbereich",
    "stufenzusatz_label":   "Gruppenzusatz",
    "projekt_label":        "Option",
    "extra_1_label":        "",    # Optionale Zusatzfelder Teilnehmer/innen
    "extra_2_label":        "",
    "extra_3_label":        "",
    "max_wuensche":         "5",
    "leitung_label":        "",   # Leitungsspalte Optionen (leer = ausgeblendet)
    "projekt_extra_1_label": "",   # Optionale Zusatzfelder Optionen
    "projekt_extra_2_label": "",
    "projekt_extra_3_label": "",
}

_PLURALE = {
    "Option":        "Optionen",
    "Workshop":      "Workshops",
    "Kurs":          "Kurse",
    "Veranstaltung": "Veranstaltungen",
    "Angebot":       "Angebote",
    "Aktion":        "Aktionen",
    "Einheit":       "Einheiten",
    "Gruppe":        "Gruppen",
    "Projekt":       "Projekte",
}


def pluralisiere_label(label: str) -> str:
    """Gibt die Pluralform eines Angebots-Labels zurück."""
    return _PLURALE.get(label, label + "e")


# Grammatikalische Formen je Label:
# fugen_s  = True  → Fugen-s im Kompositum  (Options-name, Aktions-name)
# dativ    = "er"  → feminine Dativform      (zu markierter Option)
#          = "em"  → mask./neutr. Dativform  (zu markiertem Projekt)
_LABEL_FORMEN: dict[str, dict] = {
    "Projekt":       {"fugen_s": False, "dativ": "em", "genus": "n"},
    "Option":        {"fugen_s": True,  "dativ": "er", "genus": "f"},
    "Kurs":          {"fugen_s": False, "dativ": "em", "genus": "m"},
    "Workshop":      {"fugen_s": False, "dativ": "em", "genus": "m"},
    "Veranstaltung": {"fugen_s": True,  "dativ": "er", "genus": "f"},
    "Angebot":       {"fugen_s": True,  "dativ": "em", "genus": "n"},
    "Aktion":        {"fugen_s": True,  "dativ": "er", "genus": "f"},
    "Einheit":       {"fugen_s": False, "dativ": "er", "genus": "f"},
    "Gruppe":        {"fugen_s": False, "dativ": "er", "genus": "f"},
}

# Adjektivendungen je Genus für Navigation (Vorherige/r/s, Nächste/r/s)
_NAV_ENDUNG = {
    "f": ("Vorherige",  "Nächste"),
    "m": ("Vorheriger", "Nächster"),
    "n": ("Vorheriges", "Nächstes"),
}

# Demonstrativpronomen im Nominativ ("diese/dieser/dieses Veranstaltung")
_NOM_DEM  = {"f": "diese",  "m": "dieser", "n": "dieses"}
_DAT_DEM  = {"f": "dieser", "m": "diesem", "n": "diesem"}  # "zu dieser/m Option/Projekt"


def get_label_formen(label: str) -> dict:
    """
    Gibt grammatikalische Formen des konfigurierten Labels zurück.

    Rückgabe-Dict:
      'name'      → Kompositum-Form  (z. B. "Optionsname", "Kursname")
      'dativ'     → Dativ-Phrase     (z. B. "markierter Option")
      'nr'        → Spaltenheader   (z. B. "Options-Nr.")
      'nav_vor'   → Navigationslabel rückwärts (z. B. "Vorherige Option")
      'nav_naech' → Navigationslabel vorwärts  (z. B. "Nächste Option")
    """
    formen = _LABEL_FORMEN.get(label, {"fugen_s": False, "dativ": "em", "genus": "n"})
    stamm  = label + ("s" if formen["fugen_s"] else "")
    nav_vor, nav_naech = _NAV_ENDUNG.get(formen["genus"], ("Vorheriges", "Nächstes"))
    dativ_suffix = formen["dativ"]          # "er" → feminin, "em" → mask./neutr.
    dativ_art    = "zur" if dativ_suffix == "er" else "zum"
    return {
        "name":       f"{stamm}name",
        "details":    f"{stamm}details",
        "dativ":      f"markiert{dativ_suffix} {label}",
        "dativ_art":  dativ_art,            # "zur Option", "zum Projekt" …
        "nr":         f"{label}-Nr.",
        "nav_vor":    f"{nav_vor} {label}",
        "nav_naech":  f"{nav_naech} {label}",
        "nom":        f"{_NOM_DEM.get(formen['genus'], 'dieses')} {label}",
        "dat_dem":    f"zu {_DAT_DEM.get(formen['genus'], 'diesem')} {label}",
        "kein":       "Keine" if formen["genus"] == "f" else "Kein",
    }

def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Erstellt alle Tabellen beim ersten Start und migriert ältere Datenbanken."""
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS projekte (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            nummer      INTEGER UNIQUE NOT NULL,
            projektname TEXT NOT NULL,
            stufenmin    INTEGER DEFAULT 0,
            stufenmax    INTEGER DEFAULT 99,
            tnmin       INTEGER DEFAULT 0,
            tnmax       INTEGER DEFAULT 30
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS teilnehmer (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            nachname          TEXT NOT NULL DEFAULT '-',
            vorname           TEXT NOT NULL DEFAULT '-',
            ganzer_name       TEXT GENERATED ALWAYS AS (nachname || ', ' || vorname) STORED,
            stufe             TEXT DEFAULT '-',
            stufenzusatz      TEXT DEFAULT '-',
            geschlecht        TEXT DEFAULT '-',
            wunsch_1          INTEGER DEFAULT 0,
            wunsch_2          INTEGER DEFAULT 0,
            wunsch_3          INTEGER DEFAULT 0,
            wunsch_4          INTEGER DEFAULT 0,
            wunsch_5          INTEGER DEFAULT 0,
            projekt           INTEGER DEFAULT 0,
            fest_zugewiesen   INTEGER DEFAULT 0
        )
    """)

    # ── Migration: schueler → teilnehmer (Tabellenname) ──────────────────────
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schueler'")
    if c.fetchone():
        c.execute("ALTER TABLE schueler RENAME TO teilnehmer")

    # ── Migration: Spalten in teilnehmer umbenennen ───────────────────────────
    c.execute("PRAGMA table_info(teilnehmer)")
    spalten_t = [row[1] for row in c.fetchall()]
    col_renames = [
        ("jgst",            "stufe"),
        ("abteilung",       "stufenzusatz"),
        ("manuell_zugeteilt","fest_zugewiesen"),
    ]
    for old_col, new_col in col_renames:
        if old_col in spalten_t and new_col not in spalten_t:
            c.execute(f"ALTER TABLE teilnehmer RENAME COLUMN {old_col} TO {new_col}")

    # ── Migration: fehlende Spalten ergänzen ──────────────────────────────────
    c.execute("PRAGMA table_info(teilnehmer)")
    spalten_t = [row[1] for row in c.fetchall()]
    if "fest_zugewiesen" not in spalten_t:
        c.execute("ALTER TABLE teilnehmer ADD COLUMN fest_zugewiesen INTEGER DEFAULT 0")
    for col in ("extra_1", "extra_2", "extra_3"):
        if col not in spalten_t:
            c.execute(f"ALTER TABLE teilnehmer ADD COLUMN {col} TEXT DEFAULT ''")

    # ── Migration: Projekte-Spalten (jgstmin/jgstmax → stufenmin/stufenmax) ──
    c.execute("PRAGMA table_info(projekte)")
    spalten_p = [row[1] for row in c.fetchall()]
    for old_col, new_col in [("jgstmin", "stufenmin"), ("jgstmax", "stufenmax")]:
        if old_col in spalten_p and new_col not in spalten_p:
            c.execute(f"ALTER TABLE projekte RENAME COLUMN {old_col} TO {new_col}")

    # ── Migration: neue Spalten in projekte ──────────────────────────────────
    c.execute("PRAGMA table_info(projekte)")
    spalten_p2 = [row[1] for row in c.fetchall()]
    for col, default in [
        ("leitung",  "''"),
        ("extra_1",  "''"),
        ("extra_2",  "''"),
        ("extra_3",  "''"),
    ]:
        if col not in spalten_p2:
            c.execute(f"ALTER TABLE projekte ADD COLUMN {col} TEXT DEFAULT {default}")

    # ── Feldkonfiguration ─────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS feldkonfiguration (
            schluessel TEXT PRIMARY KEY,
            wert       TEXT NOT NULL DEFAULT ''
        )
    """)
    for key, val in FELDKONFIG_DEFAULTS.items():
        c.execute(
            "INSERT OR IGNORE INTO feldkonfiguration (schluessel, wert) VALUES (?, ?)",
            (key, val)
        )

    conn.commit()
    conn.close()


# ── Projekte ────────────────────────────────────────────────────────────────

def get_all_projekte():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM projekte ORDER BY nummer"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def upsert_projekt(data: dict):
    """Fügt ein Projekt ein oder aktualisiert es (via nummer)."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO projekte
            (nummer, projektname, stufenmin, stufenmax, tnmin, tnmax,
             leitung, extra_1, extra_2, extra_3)
        VALUES
            (:nummer, :projektname, :stufenmin, :stufenmax, :tnmin, :tnmax,
             :leitung, :extra_1, :extra_2, :extra_3)
        ON CONFLICT(nummer) DO UPDATE SET
            projektname = excluded.projektname,
            stufenmin   = excluded.stufenmin,
            stufenmax   = excluded.stufenmax,
            tnmin       = excluded.tnmin,
            tnmax       = excluded.tnmax,
            leitung     = excluded.leitung,
            extra_1     = excluded.extra_1,
            extra_2     = excluded.extra_2,
            extra_3     = excluded.extra_3
    """, {
        "nummer":      data.get("nummer", 0),
        "projektname": data.get("projektname", ""),
        "stufenmin":   data.get("stufenmin", 0),
        "stufenmax":   data.get("stufenmax", 99),
        "tnmin":       data.get("tnmin", 0),
        "tnmax":       data.get("tnmax", 30),
        "leitung":     data.get("leitung", ""),
        "extra_1":     data.get("extra_1", ""),
        "extra_2":     data.get("extra_2", ""),
        "extra_3":     data.get("extra_3", ""),
    })
    conn.commit()
    conn.close()


def renumber_projekte_und_insert(new_data: dict) -> int:
    """
    Fügt ein neues Projekt ein, sortiert alle Projekte nach
    stufenmin → stufenmax → projektname und vergibt die Nummern neu (1, 2, 3, …).
    Aktualisiert dabei alle Wunsch- und Zuteilungsreferenzen in der Teilnehmer-Tabelle.
    Gibt die neue Nummer des eingefügten Projekts zurück.
    """
    conn = get_connection()
    try:
        # Temporäre Nummer weit außerhalb des normalen Bereichs
        TEMP_NR = 99999
        conn.execute("""
            INSERT INTO projekte (nummer, projektname, stufenmin, stufenmax, tnmin, tnmax)
            VALUES (:nummer, :projektname, :stufenmin, :stufenmax, :tnmin, :tnmax)
        """, {**new_data, "nummer": TEMP_NR})

        # Alle Projekte sortiert laden (inkl. neues)
        rows = conn.execute("""
            SELECT nummer FROM projekte
            ORDER BY stufenmin ASC, stufenmax ASC, projektname ASC
        """).fetchall()

        # Mapping: alte Nummer → neue Nummer
        mapping = {r[0]: i + 1 for i, r in enumerate(rows)}
        neue_nr_fuer_neues = mapping[TEMP_NR]

        # Zuerst alle auf Offset verschieben (verhindert Konflikte bei Umbenennung)
        OFFSET = 100000
        for old_nr in mapping:
            conn.execute("UPDATE projekte SET nummer = ? WHERE nummer = ?",
                         (old_nr + OFFSET, old_nr))
        # Wunsch- und Projekt-Felder ebenfalls auf Offset
        for old_nr in mapping:
            for feld in ("wunsch_1", "wunsch_2", "wunsch_3", "wunsch_4", "wunsch_5"):
                conn.execute(f"UPDATE teilnehmer SET {feld} = ? WHERE {feld} = ?",
                             (old_nr + OFFSET, old_nr))
            conn.execute("UPDATE teilnehmer SET projekt = ? WHERE projekt = ?",
                         (old_nr + OFFSET, old_nr))

        # Dann auf finale Nummern umbenennen
        for old_nr, new_nr in mapping.items():
            conn.execute("UPDATE projekte SET nummer = ? WHERE nummer = ?",
                         (new_nr, old_nr + OFFSET))
            for feld in ("wunsch_1", "wunsch_2", "wunsch_3", "wunsch_4", "wunsch_5"):
                conn.execute(f"UPDATE teilnehmer SET {feld} = ? WHERE {feld} = ?",
                             (new_nr, old_nr + OFFSET))
            conn.execute("UPDATE teilnehmer SET projekt = ? WHERE projekt = ?",
                         (new_nr, old_nr + OFFSET))

        conn.commit()
        return neue_nr_fuer_neues
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def hat_zuteilungen_oder_wuensche() -> bool:
    """True wenn irgendein Teilnehmer Wünsche oder eine Zuteilung hat."""
    conn = get_connection()
    row = conn.execute("""
        SELECT COUNT(*) FROM teilnehmer
        WHERE projekt != 0
           OR wunsch_1 != 0 OR wunsch_2 != 0 OR wunsch_3 != 0
           OR wunsch_4 != 0 OR wunsch_5 != 0
    """).fetchone()
    conn.close()
    return row[0] > 0


def delete_projekt(nummer: int):
    conn = get_connection()
    conn.execute("DELETE FROM projekte WHERE nummer = ?", (nummer,))
    conn.commit()
    conn.close()


def clear_projekte():
    conn = get_connection()
    conn.execute("DELETE FROM projekte")
    conn.commit()
    conn.close()


def loesche_leitung_daten():
    """
    Löscht die Inhalte der Leitungsspalte bei allen Optionen/Projekten
    vollständig (nicht nur ausblenden). Wird aufgerufen, wenn die
    Leitungsspalte über "Spaltenbezeichnungen anpassen" deaktiviert wird —
    aus Datenschutzgründen dürfen personenbezogene Daten (Namen von
    Leitungspersonen) nicht einfach unsichtbar in der Datenbank verbleiben.
    """
    conn = get_connection()
    conn.execute("UPDATE projekte SET leitung = ''")
    conn.commit()
    conn.close()


# ── Schüler ─────────────────────────────────────────────────────────────────

def get_all_teilnehmer(order="nachname, vorname"):
    conn = get_connection()
    rows = conn.execute(f"SELECT * FROM teilnehmer ORDER BY {order}").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_teilnehmer_by_id(schueler_id: int):
    """Gibt einen einzelnen Schüler-Datensatz zurück, oder None."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM teilnehmer WHERE id = ?", (schueler_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def insert_teilnehmer(data: dict) -> int:
    """Fügt einen Schüler ein und gibt die neu erzeugte ID zurück."""
    conn = get_connection()
    data = {**data, "fest_zugewiesen": data.get("fest_zugewiesen", 0),
            "extra_1": data.get("extra_1", ""),
            "extra_2": data.get("extra_2", ""),
            "extra_3": data.get("extra_3", "")}
    cur = conn.execute("""
        INSERT INTO teilnehmer
            (nachname, vorname, stufe, stufenzusatz, geschlecht,
             wunsch_1, wunsch_2, wunsch_3, wunsch_4, wunsch_5, projekt,
             fest_zugewiesen, extra_1, extra_2, extra_3)
        VALUES
            (:nachname, :vorname, :stufe, :stufenzusatz, :geschlecht,
             :wunsch_1, :wunsch_2, :wunsch_3, :wunsch_4, :wunsch_5, :projekt,
             :fest_zugewiesen, :extra_1, :extra_2, :extra_3)
    """, data)
    neue_id = cur.lastrowid
    conn.commit()
    conn.close()
    return neue_id


def update_teilnehmer(schueler_id: int, data: dict):
    """
    Aktualisiert einen Schüler-Datensatz. Das Feld fest_zugewiesen wird
    NICHT verändert, außer es ist explizit in data enthalten – normale
    Tabellenbearbeitung (Name, Wünsche etc.) soll den Status nicht antasten.
    """
    conn = get_connection()
    if "fest_zugewiesen" in data:
        conn.execute("""
            UPDATE teilnehmer SET
                nachname  = :nachname,
                vorname   = :vorname,
                stufe      = :stufe,
                stufenzusatz = :stufenzusatz,
                geschlecht= :geschlecht,
                wunsch_1  = :wunsch_1,
                wunsch_2  = :wunsch_2,
                wunsch_3  = :wunsch_3,
                wunsch_4  = :wunsch_4,
                wunsch_5  = :wunsch_5,
                projekt   = :projekt,
                fest_zugewiesen = :fest_zugewiesen
            WHERE id = :id
        """, {**data, "id": schueler_id})
    else:
        conn.execute("""
            UPDATE teilnehmer SET
                nachname  = :nachname,
                vorname   = :vorname,
                stufe      = :stufe,
                stufenzusatz = :stufenzusatz,
                geschlecht= :geschlecht,
                wunsch_1  = :wunsch_1,
                wunsch_2  = :wunsch_2,
                wunsch_3  = :wunsch_3,
                wunsch_4  = :wunsch_4,
                wunsch_5  = :wunsch_5,
                projekt   = :projekt
            WHERE id = :id
        """, {**data, "id": schueler_id})
    conn.commit()
    conn.close()


def delete_teilnehmer(schueler_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM teilnehmer WHERE id = ?", (schueler_id,))
    conn.commit()
    conn.close()


def clear_teilnehmer():
    conn = get_connection()
    conn.execute("DELETE FROM teilnehmer")
    conn.commit()
    conn.close()


def set_angebot_for_teilnehmer(schueler_id: int, projekt_nummer: int, manuell: bool = False):
    """
    Weist einem Schüler ein Projekt zu.
    manuell=True markiert die Zuteilung als manuell -- sie bleibt dann bei
    künftigen automatischen Einteilungsdurchläufen erhalten.
    manuell=False (z. B. durch den Algorithmus) setzt das Flag zurück auf 0.
    """
    conn = get_connection()
    conn.execute(
        "UPDATE teilnehmer SET projekt = ?, fest_zugewiesen = ? WHERE id = ?",
        (projekt_nummer, 1 if manuell else 0, schueler_id)
    )
    conn.commit()
    conn.close()


def reset_all_zuteilungen(nur_automatische: bool = True):
    """
    Setzt Projektzuteilungen zurück.
    nur_automatische=True (Standard): manuell zugeteilte Schüler bleiben
      unangetastet -- das ist der Fall bei einem neuen automatischen
      Einteilungsdurchlauf.
    nur_automatische=False: wirklich ALLE Zuteilungen werden zurückgesetzt,
      auch manuelle (für den expliziten Menüpunkt "Einteilung komplett
      aufheben").
    """
    conn = get_connection()
    if nur_automatische:
        conn.execute("UPDATE teilnehmer SET projekt = 0 WHERE fest_zugewiesen = 0")
    else:
        conn.execute("UPDATE teilnehmer SET projekt = 0, fest_zugewiesen = 0")
    conn.commit()
    conn.close()


def get_schueler_search(term: str):
    conn = get_connection()
    like = f"%{term}%"
    rows = conn.execute("""
        SELECT * FROM teilnehmer
        WHERE nachname LIKE ? OR vorname LIKE ? OR jgst LIKE ? OR abteilung LIKE ?
        ORDER BY nachname, vorname
    """, (like, like, like, like)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_projektteilnahme():
    """Gibt für jedes Projekt die Anzahl zugeteilter Schüler zurück."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT p.nummer, p.projektname, p.tnmin, p.tnmax,
               COUNT(s.id) as teilnehmer
        FROM projekte p
        LEFT JOIN teilnehmer s ON s.projekt = p.nummer
        GROUP BY p.nummer
        ORDER BY p.nummer
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def repariere_stufen_werte() -> int:
    """
    Bereinigt fehlerhafte Jahrgangsstufen-Werte in bestehenden Daten,
    die z. B. durch einen früheren Excel-Import als "5.0" statt "5"
    gespeichert wurden (führte zu fehlerhaften Jgst-Vergleichen im
    Einteilungsalgorithmus). Gibt die Anzahl der korrigierten Datensätze
    zurück.

    Sicher mehrfach ausführbar -- bereits korrekte Werte werden nicht
    verändert.
    """
    conn = get_connection()
    rows = conn.execute("SELECT id, jgst FROM teilnehmer").fetchall()
    korrigiert = 0
    for row in rows:
        alt = row["stufe"]
        s = str(alt).strip()
        if not s or s == "-":
            continue
        bereinigt = s.replace(",", ".")
        try:
            zahl = float(bereinigt)
            if zahl == int(zahl):
                neu = str(int(zahl))
                if neu != alt:
                    conn.execute(
                        "UPDATE teilnehmer SET jgst = ? WHERE id = ?",
                        (neu, row["id"])
                    )
                    korrigiert += 1
        except ValueError:
            continue
    conn.commit()
    conn.close()
    return korrigiert


def get_feldkonfig() -> dict:
    """Gibt die gespeicherten Feldbezeichnungen zurück (mit Defaults als Fallback).
    max_wuensche wird als int zurückgegeben."""
    try:
        conn = get_connection()
        rows = conn.execute(
            "SELECT schluessel, wert FROM feldkonfiguration"
        ).fetchall()
        conn.close()
        konfig = dict(FELDKONFIG_DEFAULTS)
        for row in rows:
            if row["schluessel"] in konfig:
                konfig[row["schluessel"]] = row["wert"]
        # max_wuensche immer als int zurückgeben
        try:
            konfig["max_wuensche"] = max(1, min(5, int(konfig["max_wuensche"])))
        except (ValueError, TypeError):
            konfig["max_wuensche"] = 5
        return konfig
    except Exception:
        d = dict(FELDKONFIG_DEFAULTS)
        d["max_wuensche"] = 5
        return d


def set_feldkonfig(konfig: dict):
    """Speichert Feldbezeichnungen in der Planungsmappe."""
    conn = get_connection()
    for key, val in konfig.items():
        conn.execute("""
            INSERT INTO feldkonfiguration (schluessel, wert) VALUES (?, ?)
            ON CONFLICT(schluessel) DO UPDATE SET wert = excluded.wert
        """, (key, val))
    conn.commit()
    conn.close()
