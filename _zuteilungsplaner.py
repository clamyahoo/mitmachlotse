"""
Optimale Zuteilung per Min-Cost-Max-Flow.

Modelliert die Zuteilung von Teilnehmer/innen zu Projekten als
Transportproblem: garantiert die MATHEMATISCH MAXIMALE Anzahl
versorgter Teilnehmer/innen (innerhalb gewünschter Projekte, strikt
innerhalb der Kapazitätsgrenzen) und minimiert dabei zusätzlich die
Summe der Wunschränge -- mit konfigurierbarer Gewichtung für
Mindestteilnehmerzahl-Priorität und Gruppenkohäsion.

Ersetzt die früheren, rein heuristischen Mehr-Pass-Verfahren
(_stabile_zuteilung / _erweiterte_zuteilung), die bei realer Knappheit
unnötig viele Teilnehmer/innen unversorgt ließen, obwohl es
mathematisch möglich gewesen wäre, sie unterzubringen.
"""

from _mcmf import MCMF


def _jgst_int(jgst_str) -> int:
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


def loese_zuteilung(alle_tn: list, projekte_liste: list,
                    max_wuensche: int = 5,
                    mindest_bonus: float = 0.0,
                    cohesion_gewicht: float = 0.0,
                    jgst_relaxiert_erlaubt: bool = True) -> dict:
    """
    Berechnet die optimale Zuteilung.

    mindest_bonus: Kostenabzug für die ersten tnmin-Plätze je Projekt.
        0.0    = keine Mindest-TN-Priorität (reine Wunschpriorität)
        ~0.3   = leichte Priorität (entspricht früherem Algo A)
        ~0.6   = starke Priorität (entspricht früherem Algo B)
        Muss klein genug bleiben, um die Wunschrang-Reihenfolge (Kosten
        1..5) nicht zu invertieren -- max. empfohlen: 0.6.

    cohesion_gewicht: Stärke des Klassenzusammenhalt-Bonus (0 = aus).
        Reduziert die Kosten eines Wunsches leicht, wenn auffällig viele
        Mitschüler/innen (gleiche Stufe + Zusatz) denselben Wunsch auch
        haben -- stärker gewichtet bei jüngeren Gruppenstufen. Bleibt
        immer klein genug, um Wunschrang-Priorität nicht zu invertieren.

    jgst_relaxiert_erlaubt: Falls True, dürfen Wünsche auch außerhalb des
        zulässigen Stufenbereichs erfüllt werden (mit Strafaufschlag),
        falls dadurch sonst unversorgte Teilnehmer/innen versorgt werden
        können. Bei False werden solche Wünsche komplett ignoriert.

    Gibt {schueler_id: projekt_nummer} zurück (0 = nicht zugeteilt).
    Fest zugewiesene Teilnehmer/innen sind NICHT im Ergebnis enthalten
    (bleiben unangetastet), belegen aber Kapazität.
    """
    projekte = {p["nummer"]: p for p in projekte_liste}
    if not projekte:
        return {t["id"]: 0 for t in alle_tn if not t.get("fest_zugewiesen")}

    fest_projekt: dict[int, int] = {}
    for t in alle_tn:
        if t.get("fest_zugewiesen") and t["projekt"]:
            fest_projekt[t["projekt"]] = fest_projekt.get(t["projekt"], 0) + 1

    fest_ids = {t["id"] for t in alle_tn
               if t.get("fest_zugewiesen") and t["projekt"]}
    zu_planen = [t for t in alle_tn if t["id"] not in fest_ids]

    if not zu_planen:
        return {}

    student_ids = [t["id"] for t in zu_planen]
    student_idx = {sid: i for i, sid in enumerate(student_ids)}
    proj_nrs = list(projekte.keys())
    proj_idx = {nr: i for i, nr in enumerate(proj_nrs)}

    N, P = len(student_ids), len(proj_nrs)
    SRC = 0
    STU0 = 1
    PRJ_MIN0 = STU0 + N
    PRJ_REST0 = PRJ_MIN0 + P
    SINK = PRJ_REST0 + P
    total_nodes = SINK + 1

    mcmf = MCMF(total_nodes)
    ESCAPE_COST = 100000  # garantiert günstiger jede echte Zuteilung als "kein Projekt"

    student_escape_eid: dict[int, int] = {}
    for sid in student_ids:
        i = student_idx[sid]
        mcmf.add_edge(SRC, STU0 + i, 1, 0)
        eid = len(mcmf.edges)
        mcmf.add_edge(STU0 + i, SINK, 1, ESCAPE_COST)
        student_escape_eid[sid] = eid

    # Statischer Klassenkohäsions-Bonus (vorab berechnet, unabhängig vom
    # eigentlichen Zuteilungsergebnis -- verhindert Zirkelbezug)
    by_klasse: dict[tuple, list] = {}
    for t in zu_planen:
        by_klasse.setdefault((t["stufe"], t["stufenzusatz"]), []).append(t)

    def _klassen_bonus(t: dict, p_nr: int) -> float:
        if cohesion_gewicht <= 0:
            return 0.0
        klassenkameraden = by_klasse.get((t["stufe"], t["stufenzusatz"]), [])
        n_mit_wunsch = sum(
            1 for k in klassenkameraden
            if k["id"] != t["id"] and p_nr in
               (k["wunsch_1"], k["wunsch_2"], k["wunsch_3"],
                k["wunsch_4"], k["wunsch_5"])
        )
        stufe_int = _jgst_int(t["stufe"])
        junior_gewicht = max(1, 12 - stufe_int)
        return n_mit_wunsch * junior_gewicht * cohesion_gewicht

    # Kanten Student -> Projekt (zweifach: Mindest-Teil + Rest-Teil)
    # Liste statt Dict, da ein/e Teilnehmer/in dasselbe Projekt theoretisch
    # mehrfach (in verschiedenen Wunschrängen) gewählt haben könnte --
    # ein Dict mit Schlüssel (sid, p_nr) würde dabei frühere Kanten
    # überschreiben und deren genutzten Flow beim Auslesen verlieren.
    student_proj_edges: list[tuple] = []  # (sid, p_nr, eid_min, eid_rest)
    for t in zu_planen:
        sid = t["id"]
        i = student_idx[sid]
        wuensche_roh = [t["wunsch_1"], t["wunsch_2"], t["wunsch_3"],
                        t["wunsch_4"], t["wunsch_5"]][:max_wuensche]
        for rang, p_nr in enumerate(wuensche_roh, start=1):
            if p_nr == 0 or p_nr not in projekte:
                continue
            p = projekte[p_nr]
            jgst = _jgst_int(t["stufe"])
            passt = (jgst == 0) or (p["stufenmin"] <= jgst <= p["stufenmax"])
            if not passt and not jgst_relaxiert_erlaubt:
                continue
            stufe_strafe = 0.0 if passt else 50.0
            bonus = _klassen_bonus(t, p_nr)
            cost = rang - bonus + stufe_strafe

            j = proj_idx[p_nr]
            eid_min = len(mcmf.edges)
            mcmf.add_edge(STU0 + i, PRJ_MIN0 + j, 1, cost - mindest_bonus)
            eid_rest = len(mcmf.edges)
            mcmf.add_edge(STU0 + i, PRJ_REST0 + j, 1, cost)
            student_proj_edges.append((sid, p_nr, eid_min, eid_rest))

    for p_nr in proj_nrs:
        p = projekte[p_nr]
        j = proj_idx[p_nr]
        bereits = fest_projekt.get(p_nr, 0)
        frei = max(0, p["tnmax"] - bereits)
        tnmin_frei = max(0, p["tnmin"] - bereits)
        min_slots = min(tnmin_frei, frei)
        rest_slots = frei - min_slots
        mcmf.add_edge(PRJ_MIN0 + j, SINK, min_slots, 0)
        mcmf.add_edge(PRJ_REST0 + j, SINK, rest_slots, 0)

    mcmf.solve(SRC, SINK)

    # Ergebnis aus den genutzten Kanten extrahieren
    ergebnis: dict[int, int] = {}
    for sid, p_nr, eid_min, eid_rest in student_proj_edges:
        used = mcmf.used_flow(eid_min) + mcmf.used_flow(eid_rest)
        if used > 0:
            ergebnis[sid] = p_nr

    for sid in student_ids:
        if sid not in ergebnis:
            ergebnis[sid] = 0

    return ergebnis
