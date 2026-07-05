"""
Einteilungsalgorithmen für die Projekttage-App.

Alle drei Algorithmen nutzen denselben Min-Cost-Flow-Solver
(_zuteilungsplaner.loese_zuteilung) und unterscheiden sich nur in der
Gewichtung der Ziele. Das garantiert für alle drei Algorithmen
gleichermaßen:

  - Kapazitätsgrenzen (tnmax) werden NIE überschritten (harte Grenze).
  - Niemals wird ein nicht gewähltes Projekt zugewiesen.
  - Die Anzahl unversorgter Teilnehmer/innen wird mathematisch minimiert
    (nicht nur heuristisch reduziert) -- "alle versorgen" ist bei A und
    B niedriger priorisiert als der jeweilige Hauptfokus, aber niemals
    komplett übergangen.

Algorithmus A: Wunsch-Priorisierung
  → Möglichst hohe Wünsche erfüllen, mit leichter Mindest-TN-Stütze.
    Sinnvoll v. a. bei vielen Teilnehmer/innen im Verhältnis zu den
    Plätzen, wenn der Wunschfaktor besonders im Vordergrund stehen soll.

Algorithmus B: Mindest-Teilnehmerzahl-Priorisierung
  → Stärkere Priorität auf das zuverlässige Erreichen der
    Mindestteilnehmerzahl jedes Projekts, Wünsche bleiben zweitrangig,
    aber weiterhin maßgeblich für die Reihenfolge innerhalb der
    verfügbaren Plätze.

Algorithmus C: Alle-Versorgen-Priorität
  → Höchste Priorität darauf, dass wirklich jede(r) ein gewünschtes
    Projekt bekommt (auch außerhalb des eigentlich zulässigen
    Stufenbereichs, falls nötig) -- bei gleichbleibend strikter
    Kapazitätsgrenze.
"""

import random
import database as db
from _zuteilungsplaner import loese_zuteilung as _loese_zuteilung


def _wuensche(s: dict, max_anzahl: int = 5) -> list:
    """
    Gibt die Wunschliste eines Schülers ohne Nullen zurück.
    max_anzahl begrenzt, wie viele der 5 Wünsche (ab Wunsch 1)
    überhaupt berücksichtigt werden.
    """
    alle = [s["wunsch_1"], s["wunsch_2"], s["wunsch_3"],
            s["wunsch_4"], s["wunsch_5"]][:max_anzahl]
    return [w for w in alle if w != 0]


def _jgst_int(jgst_str) -> int:
    """Versucht Jahrgangsstufe als int zu lesen, sonst 0."""
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


def _schueler_passt_zu_projekt(schueler: dict, projekt: dict) -> bool:
    """Prüft ob Jahrgangsstufe im erlaubten Bereich liegt."""
    jgst = _jgst_int(schueler["stufe"])
    if jgst == 0:
        return True
    return projekt["stufenmin"] <= jgst <= projekt["stufenmax"]


def _run(seed, max_wuensche, mindest_bonus, cohesion_gewicht,
         jgst_relaxiert_erlaubt) -> dict:
    """Gemeinsame Ausführung für A/B/C über den MCMF-Solver."""
    if seed is not None:
        random.seed(seed)
    max_wuensche = max(1, min(5, max_wuensche))

    alle_tn = db.get_all_teilnehmer()
    proj_liste = db.get_all_projekte()

    if not proj_liste:
        return {t["id"]: 0 for t in alle_tn if not t.get("fest_zugewiesen")}

    return _loese_zuteilung(
        alle_tn, proj_liste, max_wuensche=max_wuensche,
        mindest_bonus=mindest_bonus, cohesion_gewicht=cohesion_gewicht,
        jgst_relaxiert_erlaubt=jgst_relaxiert_erlaubt
    )


def algorithmus_a(seed: int = None, max_wuensche: int = 5) -> dict:
    """
    Wunsch-Priorisierung mit leichter Mindest-TN-Stütze.
    "Alle versorgen" bleibt aktiv, ist aber niedriger priorisiert als
    Wunscherfüllung und Mindest-TN-Absicherung.
    """
    return _run(seed, max_wuensche,
               mindest_bonus=0.3, cohesion_gewicht=0.02,
               jgst_relaxiert_erlaubt=True)


def algorithmus_b(seed: int = None, max_wuensche: int = 5) -> dict:
    """
    Starke Mindest-Teilnehmerzahl-Priorisierung.
    "Alle versorgen" bleibt aktiv, ist aber niedriger priorisiert als
    das zuverlässige Erreichen der Mindestteilnehmerzahl.
    """
    return _run(seed, max_wuensche,
               mindest_bonus=0.6, cohesion_gewicht=0.02,
               jgst_relaxiert_erlaubt=True)


def algorithmus_c(seed: int = None, max_wuensche: int = 5) -> dict:
    """
    Alle-Versorgen-Priorität: maximiert die Anzahl versorgter
    Teilnehmer/innen (mathematisch, nicht nur heuristisch), bei
    weiterhin strikt eingehaltener Kapazitätsgrenze und ausschließlicher
    Zuteilung auf tatsächlich gewünschte Projekte.
    """
    return _run(seed, max_wuensche,
               mindest_bonus=0.0, cohesion_gewicht=0.05,
               jgst_relaxiert_erlaubt=True)


def apply_ergebnis(ergebnis: dict):
    """
    Schreibt die Ergebnisse in die Datenbank.
    Diese Zuteilungen sind automatisch (nicht manuell).
    """
    for schueler_id, projekt_nr in ergebnis.items():
        db.set_angebot_for_teilnehmer(schueler_id, projekt_nr, manuell=False)


def get_statistik(ergebnis: dict) -> dict:
    """Gibt Statistiken zur Einteilung zurück."""
    schueler_liste = db.get_all_teilnehmer()
    teilnehmer_dict = {s["id"]: s for s in schueler_liste}

    wunsch_treffer = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 0: 0}
    gesamt = len(ergebnis)

    for s_id, p_nr in ergebnis.items():
        s = teilnehmer_dict.get(s_id)
        if not s:
            continue
        wuensche = _wuensche(s)
        if p_nr == 0:
            wunsch_treffer[0] += 1
        elif p_nr in wuensche:
            rang = wuensche.index(p_nr) + 1
            wunsch_treffer[rang] = wunsch_treffer.get(rang, 0) + 1
        else:
            wunsch_treffer[0] += 1

    return {
        "gesamt": gesamt,
        "wunsch_treffer": wunsch_treffer,
    }
