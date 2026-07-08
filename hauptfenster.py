"""
Hauptfenster der Projekttage-App.
"""

import os
import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QLabel, QLineEdit, QMenuBar, QMenu, QStatusBar, QFileDialog,
    QMessageBox, QDialog, QDialogButtonBox, QComboBox, QSpinBox,
    QInputDialog, QToolBar, QSizePolicy, QAbstractItemView,
    QApplication, QGroupBox, QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QUrl
from PyQt6.QtGui import QAction, QKeySequence, QColor, QFont, QIcon, QPalette

import database as db
import algorithmen as alg
import importexport as ie
import listenabfragen as la
import validierung as val_mod
from dialoge import (
    ImportDialog, ExportDialog,
    WunschauswertungDialog, ProjektAuswahlDialog, KlassenAuswahlDialog,
    ProjektZuweisungDialog, ProjektDetailsDialog, AnzahlWuenscheDialog,
    PlanungsmappeEinrichtenDialog, EinrichtungsassistentDialog,
)
from listenfenster import ListenFenster


# ── Editierbare Tabellen-Widgets ─────────────────────────────────────────────

def _erzwinge_lesbare_selektion(table: QTableWidget):
    """
    Erzwingt einen lesbaren Kontrast bei markierten Zeilen, unabhängig vom
    Betriebssystem-Theme. Stylesheet allein reicht auf manchen Plattformen
    nicht aus (z. B. wenn das System-Theme eine sehr helle/weiße
    Selektionsfarbe mit hellem Text vorgibt) -- daher zusätzlich die
    QPalette direkt setzen, die Vorrang vor Theme-Defaults hat.
    """
    palette = table.palette()
    # Aktiver Zustand (Tabelle hat den Fokus): kräftiges Blau, weißer Text
    palette.setColor(QPalette.ColorGroup.Active,
                     QPalette.ColorRole.Highlight, QColor("#2980b9"))
    palette.setColor(QPalette.ColorGroup.Active,
                     QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    # Inaktiver Zustand (Tabelle hat NICHT den Fokus, z. B. weil ein Dialog
    # offen ist): immer noch deutlich sichtbares Blau-Grau, weißer Text --
    # NICHT das helle/weiße Standard-Grau, das den Text unsichtbar macht
    palette.setColor(QPalette.ColorGroup.Inactive,
                     QPalette.ColorRole.Highlight, QColor("#6b95b5"))
    palette.setColor(QPalette.ColorGroup.Inactive,
                     QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    table.setPalette(palette)


def _build_angebots_headers_keys():
    """Gibt (headers, keys) für die Optionstabelle dynamisch zurück."""
    k   = db.get_feldkonfig()
    pl  = k.get("projekt_label",  "Option")
    sl  = k.get("stufe_label",    "Gruppenbereich")
    ll  = k.get("leitung_label",  "").strip()   # leer = Spalte ausblenden
    headers = ["Nr."]
    keys    = ["nummer"]
    if ll:
        headers.append(ll)
        keys.append("leitung")
    headers.append(db.get_label_formen(pl)["name"])
    keys.append("projektname")
    for i in range(1, 4):
        lbl = k.get(f"projekt_extra_{i}_label", "")
        if lbl:
            headers.append(lbl)
            keys.append(f"extra_{i}")
    headers += [f"{sl} min", f"{sl} max", "Plätze min", "Plätze max"]
    keys    += ["stufenmin", "stufenmax", "tnmin", "tnmax"]
    return headers, keys


def _build_raumplan_spalten() -> list:
    """Gibt die Spaltenstruktur der Raumzuordnungstabelle als Liste von
    (key, label) zurück. Leitung und das Zusatzfeld sind optional: nur
    enthalten, wenn ihre Bezeichnung in der Feldkonfiguration gesetzt ist
    (leer = ausgeblendet, analog zu Optionen/Teilnehmer/innen)."""
    k   = db.get_feldkonfig()
    pl  = k.get("projekt_label", "Option")
    ll  = k.get("leitung_label", "").strip()
    rzl = k.get("raumzuordnung_extra_label", "").strip()
    name_h = db.get_label_formen(pl)["name"]

    spalten = [("nummer", "Nr.")]
    if ll:
        spalten.append(("leitung", ll))
    spalten.append(("projektname", name_h))
    spalten += [
        ("tnmax", "Plätze max"),
        ("belegt", "belegt"),
        ("raum", "Raum"),
        ("kapazitaet", "Kapazität"),
        ("zeit", "Zeit"),
    ]
    if rzl:
        spalten.append(("raumzuordnung_extra", rzl))
    spalten.append(("hinweis", "Hinweis"))
    return spalten


class AngebotsTable(QTableWidget):
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(0, 6, parent)  # Spaltenanzahl wird in _rebuild gesetzt
        self._headers = []
        self._keys    = []
        self._loading = False
        self._rebuild_columns()
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)
        _erzwinge_lesbare_selektion(self)

    def _rebuild_columns(self):
        self._headers, self._keys = _build_angebots_headers_keys()
        self.setColumnCount(len(self._keys))
        self.setHorizontalHeaderLabels(self._headers)
        # Optionsname-Spalte dehnt sich (Index nach "Nr." und ggf. "Leitung")
        name_idx = self._keys.index("projektname")
        self.horizontalHeader().setSectionResizeMode(
            name_idx, QHeaderView.ResizeMode.Stretch)

    def _refresh_headers(self):
        """Spaltenüberschriften aktualisieren (bei Konfig-Änderung)."""
        self._rebuild_columns()

    def load(self):
        self._rebuild_columns()
        self._loading = True
        projekte = db.get_all_projekte()
        projekte.sort(key=lambda p: p["nummer"])
        self.setRowCount(len(projekte))
        for r, p in enumerate(projekte):
            for c, key in enumerate(self._keys):
                val = str(p.get(key, "") or "")
                item = QTableWidgetItem(val)
                if key not in ("projektname", "leitung") and not key.startswith("extra"):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.setItem(r, c, item)
        self._loading = False

    def get_selected_nummern(self) -> list[int]:
        selected_rows = sorted(set(idx.row() for idx in self.selectedIndexes()))
        nummern = []
        for row in selected_rows:
            nr_item = self.item(row, 0)
            if nr_item:
                nummern.append(int(nr_item.text()))
        return nummern

    def save_row(self, row: int):
        if self._loading:
            return
        try:
            data = {}
            for c, key in enumerate(self._keys):
                item = self.item(row, c)
                val  = item.text() if item else ""
                if key in ("stufenmin", "stufenmax", "tnmin", "tnmax", "nummer"):
                    data[key] = int(val) if val.strip() else 0
                else:
                    data[key] = val
            if data.get("nummer", 0) > 0 and data.get("projektname"):
                db.upsert_projekt(data)
                self.changed.emit()
        except Exception as e:
            import traceback
            print(f"[AngebotsTable.save_row] {e}\n{traceback.format_exc()}")


class RaeumeTable(QTableWidget):
    """Editierbare Raumliste (Name, Kapazität, Beschreibung) mit Autosave."""

    changed = pyqtSignal()

    HEADERS = ["Raumname", "Kapazität", "Beschreibung"]

    def __init__(self, parent=None):
        super().__init__(0, 3, parent)
        self._loading = False
        self.setHorizontalHeaderLabels(self.HEADERS)
        self.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)
        _erzwinge_lesbare_selektion(self)
        self.cellChanged.connect(self.save_row)

    def load(self):
        self._loading = True
        raeume = db.get_all_raeume()
        self.setRowCount(len(raeume))
        for r, raum in enumerate(raeume):
            self._set_row(r, raum)
        self._loading = False

    def _set_row(self, r: int, raum: dict):
        name_item = QTableWidgetItem(str(raum.get("name", "") or ""))
        # Raum-id an der Namenszelle mitführen (0/None = noch nicht gespeichert)
        name_item.setData(Qt.ItemDataRole.UserRole, raum.get("id") or 0)
        self.setItem(r, 0, name_item)
        kap = raum.get("kapazitaet", 0) or 0
        kap_item = QTableWidgetItem("" if kap == 0 else str(kap))
        kap_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(r, 1, kap_item)
        self.setItem(r, 2, QTableWidgetItem(str(raum.get("beschreibung", "") or "")))

    def add_empty_row(self):
        self._loading = True
        r = self.rowCount()
        self.insertRow(r)
        self._set_row(r, {"id": 0, "name": "", "kapazitaet": 0, "beschreibung": ""})
        self._loading = False
        self.setCurrentCell(r, 0)
        self.editItem(self.item(r, 0))

    def save_row(self, row: int, _col: int = 0):
        if self._loading:
            return
        try:
            name_item = self.item(row, 0)
            if name_item is None:
                return
            name = name_item.text().strip()
            if not name:
                return  # ohne Namen nicht speichern
            kap_txt = (self.item(row, 1).text().strip() if self.item(row, 1) else "")
            try:
                kap = int(kap_txt) if kap_txt else 0
            except ValueError:
                kap = 0
            besch = (self.item(row, 2).text() if self.item(row, 2) else "")
            raum_id = name_item.data(Qt.ItemDataRole.UserRole) or 0
            neue_id = db.upsert_raum({
                "id": raum_id, "name": name,
                "kapazitaet": kap, "beschreibung": besch,
            })
            if not raum_id:
                # frisch angelegt -> id an der Zelle vermerken
                self._loading = True
                name_item.setData(Qt.ItemDataRole.UserRole, neue_id)
                self._loading = False
            self.changed.emit()
        except Exception as e:
            import traceback
            print(f"[RaeumeTable.save_row] {e}\n{traceback.format_exc()}")

    def get_selected_ids(self) -> list:
        ids = []
        for row in sorted(set(idx.row() for idx in self.selectedIndexes())):
            item = self.item(row, 0)
            if item:
                rid = item.data(Qt.ItemDataRole.UserRole) or 0
                if rid:
                    ids.append(rid)
        return ids


class RaumplanTable(QTableWidget):
    """Je Option eine Zeile: Raum (Auswahl) + Zeit zuordnen, mit Konfliktfarben."""

    changed = pyqtSignal()

    # Spalten (key, label) -- dynamisch, siehe _build_raumplan_spalten().
    # Leitung und Zusatzfeld sind optional und daher nicht Teil einer festen
    # Indexliste; self._idx bildet key -> aktuelle Spaltennummer ab.

    # Hintergrundfarben für Konflikthinweise
    FARBE_DOPPEL = QColor("#f8d0d0")   # rot -> Doppelbelegung
    FARBE_KAP    = QColor("#ffe3b3")   # orange -> Kapazität

    def __init__(self, parent=None):
        super().__init__(0, 0, parent)
        self._loading = False
        self._raeume = []
        self._spalten = []   # [(key, label), ...]
        self._idx = {}       # key -> Spaltenindex
        self._rebuild_columns()
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)
        _erzwinge_lesbare_selektion(self)
        self.cellChanged.connect(self._on_cell_changed)

    def _rebuild_columns(self):
        """Baut die Spaltenstruktur neu auf (z. B. wenn Leitung oder das
        Zusatzfeld aktiviert/deaktiviert wurden)."""
        self._spalten = _build_raumplan_spalten()
        self._idx = {key: i for i, (key, _label) in enumerate(self._spalten)}
        self.setColumnCount(len(self._spalten))
        self.setHorizontalHeaderLabels([label for _key, label in self._spalten])
        header = self.horizontalHeader()
        if "projektname" in self._idx:
            header.setSectionResizeMode(
                self._idx["projektname"], QHeaderView.ResizeMode.Stretch)
        if "hinweis" in self._idx:
            header.setSectionResizeMode(
                self._idx["hinweis"], QHeaderView.ResizeMode.Stretch)

    def _ro_item(self, text: str, center: bool = False) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        if center:
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item

    def load(self):
        self._loading = True
        self._rebuild_columns()
        self._raeume = db.get_all_raeume()
        plan = db.get_raumplan()
        # Zeilen zuerst vollständig entfernen und neu anlegen: Ändert sich die
        # Spaltenstruktur (z. B. Leitung/Zusatzfeld aktiviert oder
        # deaktiviert), bleiben sonst verwaiste Zellwidgets (Raum-Comboboxen)
        # an ihrer alten Spaltenposition hängen -- setItem() entfernt ein
        # bereits gesetztes setCellWidget() nicht automatisch. Reine Zeilen
        # neu anzulegen räumt auch deren Widgets zuverlässig ab.
        self.setRowCount(0)
        self.setRowCount(len(plan))
        for r, row in enumerate(plan):
            self.setItem(r, self._idx["nummer"], self._ro_item(str(row["nummer"]), True))
            if "leitung" in self._idx:
                self.setItem(r, self._idx["leitung"],
                             self._ro_item(str(row.get("leitung", "") or "")))
            self.setItem(r, self._idx["projektname"],
                         self._ro_item(str(row.get("projektname", "") or "")))
            self.setItem(r, self._idx["tnmax"], self._ro_item(str(row.get("tnmax", "") or ""), True))
            self.setItem(r, self._idx["belegt"], self._ro_item(str(row.get("belegt", 0) or 0), True))
            # Raum-Auswahl als ComboBox
            combo = QComboBox()
            combo.addItem("— kein Raum —", 0)
            for raum in self._raeume:
                combo.addItem(raum["name"], raum["id"])
            aktuelle_id = row.get("raum_id") or 0
            idx = combo.findData(aktuelle_id)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.currentIndexChanged.connect(
                lambda _i, rr=r: self._on_raum_changed(rr))
            self.setCellWidget(r, self._idx["raum"], combo)
            # Kapazität des gewählten Raums (abgeleitet, read-only)
            self.setItem(r, self._idx["kapazitaet"],
                         self._ro_item(self._kap_text(aktuelle_id), True))
            # Zeit editierbar
            self.setItem(r, self._idx["zeit"], QTableWidgetItem(str(row.get("zeit", "") or "")))
            if "raumzuordnung_extra" in self._idx:
                self.setItem(r, self._idx["raumzuordnung_extra"],
                             QTableWidgetItem(str(row.get("raumzuordnung_extra", "") or "")))
            self.setItem(r, self._idx["hinweis"], self._ro_item(""))
        self._loading = False
        self._aktualisiere_konflikte()

    def _kap_text(self, raum_id: int) -> str:
        if not raum_id:
            return ""
        for raum in self._raeume:
            if raum["id"] == raum_id:
                k = raum.get("kapazitaet", 0) or 0
                return "" if k == 0 else str(k)
        return ""

    def _nummer(self, row: int) -> int:
        item = self.item(row, self._idx["nummer"])
        return int(item.text()) if item and item.text().strip() else 0

    def _raum_id(self, row: int) -> int:
        combo = self.cellWidget(row, self._idx["raum"])
        return combo.currentData() if combo else 0

    def _zeit(self, row: int) -> str:
        item = self.item(row, self._idx["zeit"])
        return item.text() if item else ""

    def _raumzuordnung_extra_wert(self, row: int) -> str:
        if "raumzuordnung_extra" not in self._idx:
            return ""
        item = self.item(row, self._idx["raumzuordnung_extra"])
        return item.text() if item else ""

    def _on_raum_changed(self, row: int):
        if self._loading:
            return
        raum_id = self._raum_id(row)
        db.set_raum_zeit_for_projekt(self._nummer(row), raum_id, self._zeit(row))
        # Kapazitätsspalte nachziehen
        self._loading = True
        self.setItem(row, self._idx["kapazitaet"], self._ro_item(self._kap_text(raum_id), True))
        self._loading = False
        self._aktualisiere_konflikte()
        self.changed.emit()

    def _on_cell_changed(self, row: int, col: int):
        if self._loading:
            return
        if col == self._idx.get("zeit"):
            db.set_raum_zeit_for_projekt(self._nummer(row), self._raum_id(row), self._zeit(row))
            self._aktualisiere_konflikte()
            self.changed.emit()
        elif col == self._idx.get("raumzuordnung_extra"):
            db.set_raumzuordnung_extra(self._nummer(row), self._raumzuordnung_extra_wert(row))
            self.changed.emit()

    def _aktualisiere_konflikte(self):
        """Färbt Zellen und füllt die Hinweisspalte anhand pruefe_raumkonflikte()."""
        konf = val_mod.pruefe_raumkonflikte()
        farb_spalten = [self._idx[k] for k in ("raum", "zeit", "hinweis") if k in self._idx]
        self._loading = True
        try:
            for row in range(self.rowCount()):
                nummer = self._nummer(row)
                info = konf.get(nummer)
                hinweis_item = self.item(row, self._idx["hinweis"])
                if hinweis_item is None:
                    hinweis_item = self._ro_item("")
                    self.setItem(row, self._idx["hinweis"], hinweis_item)
                if info:
                    farbe = self.FARBE_DOPPEL if info["doppelbelegung"] else self.FARBE_KAP
                    hinweis_item.setText(info["text"].replace("\n", "  •  "))
                    hinweis_item.setToolTip(info["text"])
                    for col in farb_spalten:
                        zell = self.item(row, col)
                        if zell is not None:
                            zell.setBackground(farbe)
                    # Combobox-Zelle hat kein Item -> Zeit/Hinweis reichen als Signal
                else:
                    hinweis_item.setText("")
                    hinweis_item.setToolTip("")
                    for col in farb_spalten:
                        zell = self.item(row, col)
                        if zell is not None:
                            zell.setBackground(QColor(Qt.GlobalColor.transparent))
        finally:
            self._loading = False

    def refresh_aus_optionen(self):
        """Aktualisiert die aus der Optionsliste gespiegelten, schreibgeschützten
        Felder (Leitung, Optionsname, Plätze max, belegt) sowie die
        Konfliktfärbung -- ohne die Raum-Dropdowns neu aufzubauen. Wird nach
        jeder Änderung im Optionen-Tab sowie nach jeder Zuteilung aufgerufen."""
        if self.rowCount() == 0:
            return
        plan = {row["nummer"]: row for row in db.get_raumplan()}
        self._loading = True
        for r in range(self.rowCount()):
            row = plan.get(self._nummer(r))
            if row is None:
                continue
            if "leitung" in self._idx:
                item = self.item(r, self._idx["leitung"])
                if item is not None:
                    item.setText(str(row.get("leitung", "") or ""))
            item = self.item(r, self._idx["projektname"])
            if item is not None:
                item.setText(str(row.get("projektname", "") or ""))
            item = self.item(r, self._idx["tnmax"])
            if item is not None:
                item.setText(str(row.get("tnmax", "") or ""))
            item = self.item(r, self._idx["belegt"])
            if item is not None:
                item.setText(str(row.get("belegt", 0) or 0))
        self._loading = False
        self._aktualisiere_konflikte()

    def export_daten(self) -> tuple:
        """Gibt (headers, rows) des aktuellen Raumplans für Export/Druck zurück
        -- in derselben Reihenfolge wie in der Tabelle angezeigt."""
        headers = [label for _key, label in self._spalten]
        rows = []
        for r in range(self.rowCount()):
            zeile = []
            for key, _label in self._spalten:
                if key == "raum":
                    combo = self.cellWidget(r, self._idx["raum"])
                    txt = combo.currentText() if combo else ""
                    if txt.startswith("—"):
                        txt = ""
                    zeile.append(txt)
                else:
                    item = self.item(r, self._idx[key])
                    zeile.append(item.text() if item else "")
            rows.append(zeile)
        return headers, rows


def _build_teilnehmer_headers_keys():
    """Gibt (headers, keys) basierend auf der aktuellen Feldkonfiguration zurück."""
    konfig = db.get_feldkonfig()
    stufe   = konfig.get("stufe_label",        "Gruppenbereich")
    zusatz  = konfig.get("stufenzusatz_label",  "Gruppenzusatz")
    projekt = konfig.get("projekt_label",       "Option")
    mw      = konfig.get("max_wuensche",        5)

    headers = ["ID", "Name", stufe, zusatz]
    keys    = ["id", "name", "stufe", "stufenzusatz"]

    # Optionale Zusatzfelder zwischen Gruppenzusatz und Wünsche
    for i in range(1, 4):
        lbl = konfig.get(f"extra_{i}_label", "")
        if lbl:
            headers.append(lbl)
            keys.append(f"extra_{i}")

    wunsch_headers = [f"W{i}" for i in range(1, mw + 1)]
    wunsch_keys    = [f"wunsch_{i}" for i in range(1, mw + 1)]
    headers += wunsch_headers + [projekt, "Fixiert"]
    keys    += wunsch_keys    + ["projekt", "fest_zugewiesen"]
    return headers, keys


class TeilnehmerTable(QTableWidget):
    # "name" ist ein Anzeige-Feld (Nachname, Vorname kombiniert), kein DB-Feld

    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(0, 11, parent)
        self._headers = []
        self._keys = []
        self._loading = False
        self._all_data = []
        self._rebuild_columns()
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)
        _erzwinge_lesbare_selektion(self)
        self.cellDoubleClicked.connect(self._on_doppelklick)

    def _rebuild_columns(self):
        """Spaltenstruktur neu aufbauen (nach Konfig-Änderung)."""
        headers, keys = _build_teilnehmer_headers_keys()
        self._headers = headers
        self._keys = keys
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)
        name_idx = keys.index("name") if "name" in keys else 1
        self.horizontalHeader().setSectionResizeMode(
            name_idx, QHeaderView.ResizeMode.Stretch
        )
        self.setColumnHidden(0, True)  # ID ausblenden

    def _on_doppelklick(self, row: int, col: int):
        """
        Doppelklick auf die Projekt-Spalte öffnet den Dialog zur manuellen
        Zuteilung, statt die Zellen direkt (und damit ohne den
        'Manuell'-Status zu setzen) bearbeitbar zu machen. Es werden nur
        die Wunschprojekte angeboten, konsistent mit der manuellen
        Zuteilung aus den Listenfenstern heraus.
        """
        projekt_col = self._keys.index("projekt")
        if col != projekt_col:
            return
        id_item = self.item(row, 0)
        if not id_item:
            return
        schueler_id = int(id_item.text())
        main_window = self.window()
        if hasattr(main_window, "_feste_zuweisung"):
            main_window._feste_zuweisung(schueler_id, nur_wunschprojekte=True)

    @staticmethod
    def _jgst_sortkey(jgst_val) -> int:
        """Wandelt Jgst. in eine Sortierzahl um (führende Ziffern, sonst 0)."""
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

    def _sort_rows(self, rows: list) -> list:
        """Feste Sortierung: Jahrgangsstufe -> Klassenzusatz -> Name."""
        return sorted(
            rows,
            key=lambda s: (
                self._jgst_sortkey(s["stufe"]),
                str(s["stufenzusatz"]).lower(),
                str(s["nachname"]).lower(),
                str(s["vorname"]).lower(),
            )
        )

    def load(self, data=None):
        self._loading = True
        # Spalten bei jeder Ladung neu aufbauen (Konfig könnte sich geändert haben)
        self._rebuild_columns()
        rows = data if data is not None else db.get_all_teilnehmer()
        self._all_data = db.get_all_teilnehmer()
        rows = self._sort_rows(rows)
        self.setRowCount(len(rows))
        for r, s in enumerate(rows):
            for c, key in enumerate(self._keys):
                if key == "id":
                    val = str(s["id"])
                elif key == "name":
                    val = f"{s['nachname']}, {s['vorname']}"
                elif key == "fest_zugewiesen":
                    val = "✓" if (s["fest_zugewiesen"] and s["projekt"] != 0) else ""
                elif key == "projekt":
                    val = f"0 ⚠ Kein {db.get_feldkonfig().get('projekt_label', 'Option')}" if s["projekt"] == 0 else str(s["projekt"])
                elif key in ("extra_1", "extra_2", "extra_3"):
                    val = str(s.get(key, "") or "")
                else:
                    val = str(s[key]) if key in s else ""
                item = QTableWidgetItem(val)
                if key != "name":
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if key == "fest_zugewiesen":
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if key == "projekt":
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    if s["projekt"] == 0:
                        font = item.font()
                        font.setBold(True)
                        item.setFont(font)
                self.setItem(r, c, item)
        self._loading = False

    def save_row(self, row: int):
        if self._loading:
            return
        try:
            id_item = self.item(row, 0)
            if not id_item:
                return
            schueler_id = int(id_item.text())

            # Felder aus der DB vorholen (enthält Felder die nicht in _keys sind)
            aktueller = db.get_teilnehmer_by_id(schueler_id)
            if not aktueller:
                return

            # Sichtbare Spalten einlesen
            data = {}
            for c, key in enumerate(self._keys):
                if key in ("id", "name", "fest_zugewiesen", "projekt"):
                    continue
                item = self.item(row, c)
                val  = item.text() if item else ""
                if key in ("wunsch_1", "wunsch_2", "wunsch_3",
                           "wunsch_4", "wunsch_5"):
                    try:
                        data[key] = int(val) if val.strip() else 0
                    except ValueError:
                        data[key] = 0
                else:
                    data[key] = val

            # Name-Spalte (kombiniert) → nachname / vorname
            name_col = self._keys.index("name") if "name" in self._keys else -1
            if name_col >= 0:
                name_item = self.item(row, name_col)
                name_val  = name_item.text() if name_item else ""
                nachname, vorname = ie.split_ganzer_name(name_val)
                data["nachname"] = nachname
                data["vorname"]  = vorname
            else:
                data["nachname"] = aktueller["nachname"]
                data["vorname"]  = aktueller["vorname"]

            # Felder die nicht sichtbar sind aus dem aktuellen DB-Stand übernehmen
            data.setdefault("geschlecht",  aktueller.get("geschlecht", "-"))
            data.setdefault("extra_1",     aktueller.get("extra_1", ""))
            data.setdefault("extra_2",     aktueller.get("extra_2", ""))
            data.setdefault("extra_3",     aktueller.get("extra_3", ""))
            data["projekt"] = aktueller["projekt"]

            # Wünsche gegen Jahrgangsstufen-Zulassung prüfen
            wuensche = [data.get(f"wunsch_{i}", 0) for i in range(1, 6)]
            verstoesse = val_mod.pruefe_alle_wuensche(data.get("stufe", 0),
                                                      wuensche)
            if verstoesse:
                meldung = "\n".join(
                    f"  Wunsch {rang}: {grund}"
                    for rang, p_nr, grund in verstoesse
                )
                QMessageBox.warning(
                    self.window(), "Unzulässiger Wunsch",
                    f"Folgende(r) Wunsch/Wünsche passen nicht zur "
                    f"Jahrgangsstufe und wurden auf \"kein Wunsch\" (0) "
                    f"zurückgesetzt:\n\n{meldung}\n\n"
                    f"Alle übrigen Eingaben wurden gespeichert."
                )
                self._loading = True
                wunsch_felder = [f"wunsch_{i}" for i in range(1, 6)]
                for rang, p_nr, grund in verstoesse:
                    feld = wunsch_felder[rang - 1]
                    data[feld] = 0
                    spalte = self._keys.index(feld) if feld in self._keys else -1
                    if spalte >= 0:
                        item = self.item(row, spalte)
                        if item:
                            item.setText("0")
                self._loading = False

            db.update_teilnehmer(schueler_id, data)
            # Signal auslösen → Hauptfenster kann neu sortieren
            self.changed.emit()

        except Exception as e:
            import traceback
            print(f"[save_row] Fehler: {e}\n{traceback.format_exc()}")

    def keyPressEvent(self, event):
        """Tab in Wunschspalten springt zur nächsten Wunschspalte (nicht zurück zum Anfang)."""
        from PyQt6.QtCore import Qt as _Qt
        from PyQt6.QtGui import QKeySequence as _QKS
        if event.key() == _Qt.Key.Key_Tab and self._keys:
            col = self.currentColumn()
            row = self.currentRow()
            try:
                key = self._keys[col]
            except IndexError:
                key = ""
            wunsch_keys = ["wunsch_1", "wunsch_2", "wunsch_3", "wunsch_4", "wunsch_5"]
            if key in wunsch_keys:
                idx = wunsch_keys.index(key)
                if idx < 4:
                    # Nächste Wunschspalte in derselben Zeile
                    next_col = self._keys.index(wunsch_keys[idx + 1])
                    self.setCurrentCell(row, next_col)
                    self.editItem(self.item(row, next_col))
                else:
                    # Letzte Wunschspalte → erste Wunschspalte der nächsten Zeile
                    next_row = (row + 1) % self.rowCount()
                    first_wunsch_col = self._keys.index("wunsch_1")
                    self.setCurrentCell(next_row, first_wunsch_col)
                    self.editItem(self.item(next_row, first_wunsch_col))
                return
        super().keyPressEvent(event)

    def get_selected_id(self) -> int | None:
        rows = self.selectedItems()
        if not rows:
            return None
        row = self.currentRow()
        id_item = self.item(row, 0)
        return int(id_item.text()) if id_item else None

    def get_selected_ids(self) -> list[int]:
        """Gibt die IDs aller markierten Zeilen zurück (Mehrfachauswahl)."""
        selected_rows = sorted(set(idx.row() for idx in self.selectedIndexes()))
        ids = []
        for row in selected_rows:
            id_item = self.item(row, 0)
            if id_item:
                ids.append(int(id_item.text()))
        return ids


# ── Statistik-Widget ─────────────────────────────────────────────────────────

class StatistikWidget(QWidget):
    projekt_doppelklick          = pyqtSignal(int)
    wunschauswertung_angefordert = pyqtSignal(int)
    projektdetails_angefordert   = pyqtSignal(int)
    teilnehmerliste_angefordert  = pyqtSignal(int)
    qualitaetspruefung_angefordert = pyqtSignal()
    klassenliste_angefordert     = pyqtSignal()

    export_nach_gruppen_angefordert  = pyqtSignal()
    export_nach_optionen_angefordert = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # ── Wunschstatistik + rechte Spalte (Qualitätsprüfung + Export) ─────
        stat_row = QHBoxLayout()
        self.lbl = QLabel("Noch keine Einteilung vorgenommen.")
        self.lbl.setWordWrap(True)
        self.lbl.setAlignment(Qt.AlignmentFlag.AlignTop)
        stat_row.addWidget(self.lbl, stretch=1)

        # Rechte Spalte: Qualitätsprüfung oben, darunter die zwei Export-Buttons
        rechts = QVBoxLayout()
        rechts.setSpacing(4)
        self.btn_qualitaet = QPushButton("Qualitätsprüfung Wunscheingaben")
        self.btn_qualitaet.clicked.connect(self.qualitaetspruefung_angefordert)
        self.btn_exp_gruppen  = QPushButton("Gesamtliste nach Gruppen exportieren")
        self.btn_exp_optionen = QPushButton("")   # Text → _update_statistik_headers
        self.btn_exp_gruppen.clicked.connect(self.export_nach_gruppen_angefordert)
        self.btn_exp_optionen.clicked.connect(self.export_nach_optionen_angefordert)
        rechts.addWidget(self.btn_qualitaet)
        rechts.addWidget(self.btn_exp_gruppen)
        rechts.addWidget(self.btn_exp_optionen)
        stat_row.addLayout(rechts, stretch=0)
        layout.addLayout(stat_row)

        # ── Buttons für markierte Option ──────────────────────────────────────
        btn_row = QHBoxLayout()
        self.btn_wunschliste   = QPushButton("")   # Text → _update_statistik_headers
        self.btn_tnliste       = QPushButton("")
        self.btn_gruppenliste  = QPushButton("Gruppenliste mit Zuteilung")
        self.btn_details       = QPushButton("")
        for btn in (self.btn_wunschliste, self.btn_tnliste,
                    self.btn_details):
            btn.setEnabled(False)
        self.btn_wunschliste.clicked.connect(self._on_wunschauswertung_klick)
        self.btn_tnliste.clicked.connect(self._on_tnliste_klick)
        self.btn_gruppenliste.clicked.connect(self.klassenliste_angefordert)
        self.btn_details.clicked.connect(self._on_details_klick)
        btn_row.addWidget(self.btn_wunschliste)
        btn_row.addWidget(self.btn_tnliste)
        btn_row.addWidget(self.btn_gruppenliste)
        btn_row.addWidget(self.btn_details)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # ── Optionstabelle ────────────────────────────────────────────────────
        self.table = QTableWidget(0, 5)
        self._update_statistik_headers()
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.cellDoubleClicked.connect(self._on_doppelklick)
        self.table.itemSelectionChanged.connect(self._on_selektion_geaendert)
        layout.addWidget(self.table)

    def _update_statistik_headers(self):
        konfig   = db.get_feldkonfig()
        pl       = konfig.get("projekt_label", "Option")
        formen   = db.get_label_formen(pl)
        pl_plural = db.pluralisiere_label(pl)
        self.btn_exp_optionen.setText(
            f"Gesamtliste nach {pl_plural} exportieren")
        self.btn_wunschliste.setText(
            f"Wunschauswertungsliste zu {formen['dativ']}")
        self.btn_tnliste.setText(
            f"Teilnehmerliste {formen['dativ_art']} {formen['dativ'].split()[-1]}")
        self.btn_details.setText(f"Wunschdetails zu {formen['dativ']}")
        self.table.setHorizontalHeaderLabels(
            [formen["nr"], formen["name"], "Plätze min", "Plätze max", "Zugeteilt"]
        )

    def _aktuelle_projekt_nr(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        nr_item = self.table.item(row, 0)
        return int(nr_item.text()) if nr_item else None

    def _on_selektion_geaendert(self):
        nr = self._aktuelle_projekt_nr()
        aktiv = nr is not None
        self.btn_wunschliste.setEnabled(aktiv)
        self.btn_tnliste.setEnabled(aktiv)
        self.btn_details.setEnabled(aktiv)

    def _on_wunschauswertung_klick(self):
        nr = self._aktuelle_projekt_nr()
        if nr is not None:
            self.wunschauswertung_angefordert.emit(nr)

    def _on_tnliste_klick(self):
        nr = self._aktuelle_projekt_nr()
        if nr is not None:
            self.teilnehmerliste_angefordert.emit(nr)

    def _on_details_klick(self):
        nr = self._aktuelle_projekt_nr()
        if nr is not None:
            self.projektdetails_angefordert.emit(nr)

    def _on_doppelklick(self, row: int, col: int):
        nr_item = self.table.item(row, 0)
        if nr_item:
            self.projektdetails_angefordert.emit(int(nr_item.text()))

    def _berechne_wunschrang(self) -> tuple[int, dict, int]:
        """Berechnet Wunschrang-Verteilung aus aktuellem DB-Stand.
        Gibt zurück: (gesamt, {rang: anzahl}, nicht_zugeteilt)
        rang 0 = zugeteilt, aber Projekt war kein Wunsch."""
        tn = db.get_all_teilnehmer()
        zaehler = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 0: 0}
        nicht_zugeteilt = 0
        for t in tn:
            p = t["projekt"]
            if not p:
                nicht_zugeteilt += 1
                continue
            wuensche = [t["wunsch_1"], t["wunsch_2"], t["wunsch_3"],
                        t["wunsch_4"], t["wunsch_5"]]
            if p in wuensche:
                zaehler[wuensche.index(p) + 1] += 1
            else:
                zaehler[0] += 1
        return len(tn), zaehler, nicht_zugeteilt

    def refresh(self, wunsch_stats: dict = None):
        self._update_statistik_headers()

        # Wunschrang-Statistik immer aus aktuellem DB-Stand berechnen
        gesamt, zaehler, nicht_zugeteilt = self._berechne_wunschrang()
        zugeteilt = gesamt - nicht_zugeteilt
        basis = zugeteilt or 1

        lines = [f"<b>Wunschrang-Übersicht ({gesamt} Teilnehmer/innen, "
                 f"{zugeteilt} zugeteilt):</b>"]
        for rang in range(1, 6):
            n = zaehler[rang]
            lines.append(
                f"&nbsp;&nbsp;Wunsch {rang} erhalten: <b>{n}</b> "
                f"({n / basis * 100:.1f}\u202f%)"
            )
        n0 = zaehler[0]
        lines.append(
            f"&nbsp;&nbsp;Kein Wunsch erfüllt: <b>{n0}</b> "
            f"({n0 / basis * 100:.1f}\u202f%) &nbsp;|&nbsp; "
            f"Nicht zugeteilt: <b>{nicht_zugeteilt}</b>"
        )
        self.lbl.setText("<br>".join(lines))

        teilnahme = db.get_projektteilnahme()
        self.table.setRowCount(len(teilnahme))
        for r, p in enumerate(teilnahme):
            self.table.setItem(r, 0, QTableWidgetItem(str(p["nummer"])))
            self.table.setItem(r, 1, QTableWidgetItem(p["projektname"]))
            self.table.setItem(r, 2, QTableWidgetItem(str(p["tnmin"])))
            self.table.setItem(r, 3, QTableWidgetItem(str(p["tnmax"])))

            unterbesetzt = p["teilnehmer"] < p["tnmin"]
            ueberbesetzt = p["teilnehmer"] > p["tnmax"]

            # Auffälligkeit wird über ein Textsymbol markiert, NICHT über
            # Hintergrundfarbe: Qt's Standard-Selektionsfarbe überdeckt
            # individuell gesetzte Zellhintergründe beim Anklicken
            # zuverlässig, was Farbmarkierungen in anklickbaren Tabellen
            # unzuverlässig macht. Ein Textsymbol bleibt davon unberührt.
            if unterbesetzt:
                differenz = p["teilnehmer"] - p["tnmin"]
                text = f"⚠ {p['teilnehmer']} ({differenz})"
            elif ueberbesetzt:
                differenz = p["teilnehmer"] - p["tnmax"]
                text = f"⚠ {p['teilnehmer']} (+{differenz})"
            else:
                text = str(p["teilnehmer"])

            item_tn = QTableWidgetItem(text)
            item_tn.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if unterbesetzt or ueberbesetzt:
                font = item_tn.font()
                font.setBold(True)
                item_tn.setFont(font)
            self.table.setItem(r, 4, item_tn)


# ── Haupt-Fenster ────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mitmach-Lotse")
        self.setMinimumSize(1100, 700)
        self._last_export_dir = str(Path.home())
        self._search_term = ""
        self._search_results = []
        self._search_idx = 0
        self._offene_listenfenster = []  # Referenzen halten, sonst GC schließt sie

        db.init_db()
        self._build_ui()
        self._build_menu()
        self._build_shortcuts()
        self._refresh_all()
        self._update_title()
        # Assistent beim Start anzeigen, wenn DB leer ist
        if self._db_ist_leer():
            self._zeige_assistenten()

    def _db_ist_leer(self) -> bool:
        """Gibt True zurück, wenn weder Projekte noch Teilnehmer/innen vorhanden sind."""
        try:
            conn = db.get_connection()
            n_p = conn.execute("SELECT COUNT(*) FROM projekte").fetchone()[0]
            n_s = conn.execute("SELECT COUNT(*) FROM teilnehmer").fetchone()[0]
            conn.close()
            return n_p == 0 and n_s == 0
        except Exception:
            return False

    def _zeige_assistenten(self):
        """Öffnet den Einrichtungsassistenten und aktualisiert danach die Anzeige."""
        dlg = EinrichtungsassistentDialog(self)
        dlg.exec()
        self._refresh_all()
        self._update_title()
        self._update_search_placeholder()
        self._sync_labels()

    # ── Konfigurations-Helfer ─────────────────────────────────────────────────

    def _get_pl(self) -> tuple:
        """Gibt (label, formen, plural) für den konfigurierten Projektbegriff zurück.
        Zentrale Anlaufstelle statt 44× get_feldkonfig().get(...) im Code."""
        lbl = db.get_feldkonfig().get("projekt_label", "Option")
        return lbl, db.get_label_formen(lbl), db.pluralisiere_label(lbl)

    def _sync_labels(self):
        """Synchronisiert alle dynamischen UI-Texte mit der aktuellen Konfiguration.
        Wird beim Öffnen einer Planungsmappe und nach Spaltenbezeichnungs-Änderungen
        aufgerufen. Nur eine einzige Stelle statt zwei identischer Blöcke."""
        lbl, formen, plP = self._get_pl()
        self.tabs.setTabText(1, plP)
        self.btn_add_p.setText(f"+ {lbl} hinzufügen")
        self.btn_zuteilen_s.setText(f"{lbl} fix zuweisen")
        self.a_manuell.setText(f"{lbl} fix zuweisen")
        self.a14_teilnehmerliste.setText(f"Teilnehmerliste nach {lbl}")
        self.a_exp_pr.setText(f"Gesamtliste nach {plP} exportieren")
        if hasattr(self, "raumplan_table"):
            self.raumplan_table.load()
        self.statistik_widget.refresh()

    # ── Spaltenbezeichnungen ──────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(6, 6, 6, 6)

        # Such-Leiste oben
        search_bar = QHBoxLayout()
        search_bar.addWidget(QLabel("Suche (Strg+F):"))
        self.search_edit = QLineEdit()
        self._update_search_placeholder()
        self.search_edit.returnPressed.connect(self._search_forward)
        self.search_edit.textChanged.connect(self._on_search_changed)
        search_bar.addWidget(self.search_edit)
        btn_up = QPushButton("▲ Zurück")
        btn_up.clicked.connect(self._search_backward)
        btn_dn = QPushButton("▼ Weiter")
        btn_dn.clicked.connect(self._search_forward)
        self.lbl_search_info = QLabel("")
        search_bar.addWidget(btn_up)
        search_bar.addWidget(btn_dn)
        search_bar.addWidget(self.lbl_search_info)
        main_layout.addLayout(search_bar)

        # Tab-Widget
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self._on_tab_changed)
        main_layout.addWidget(self.tabs)

        # Tab 1: Schüler
        teilnehmer_tab = QWidget()
        sl = QVBoxLayout(teilnehmer_tab)
        btn_row_s = QHBoxLayout()
        btn_add_s = QPushButton("+ Teilnehmer/in hinzufügen")
        btn_del_s = QPushButton("✗ Zeile löschen")
        _lbl_z, _, _ = self._get_pl()
        self.btn_zuteilen_s = QPushButton(f"{_lbl_z} fix zuweisen")
        btn_zuteilen_aufheben_s = QPushButton("✗ Fixierung aufheben")
        btn_add_s.clicked.connect(self._add_teilnehmer)
        btn_del_s.clicked.connect(self._delete_teilnehmer)
        self.btn_zuteilen_s.clicked.connect(lambda: self._feste_zuweisung(nur_wunschprojekte=True))
        btn_zuteilen_aufheben_s.clicked.connect(self._feste_zuweisung_aufheben)
        btn_row_s.addWidget(btn_add_s)
        btn_row_s.addWidget(btn_del_s)
        btn_row_s.addWidget(self.btn_zuteilen_s)
        btn_row_s.addWidget(btn_zuteilen_aufheben_s)
        btn_row_s.addStretch()
        sl.addLayout(btn_row_s)
        self.teilnehmer_table = TeilnehmerTable()
        self.teilnehmer_table.cellChanged.connect(self.teilnehmer_table.save_row)
        self.teilnehmer_table.changed.connect(self._refresh_and_reselect)
        self.teilnehmer_table.changed.connect(self._signal_gespeichert)
        sl.addWidget(self.teilnehmer_table)
        self.tabs.addTab(teilnehmer_tab, "Teilnehmer/innen")
        self.tabs.setTabIcon(0, QIcon.fromTheme("system-users",
            QIcon.fromTheme("people", QIcon.fromTheme("contact-new"))))

        # Tab 2: Projekte
        projekte_tab = QWidget()
        pl = QVBoxLayout(projekte_tab)
        btn_row_p = QHBoxLayout()
        _lbl_p, _, _ = self._get_pl()
        self.btn_add_p = QPushButton(f"+ {_lbl_p} hinzufügen")
        self.btn_add_p.clicked.connect(self._add_angebot)
        btn_del_p = QPushButton("✗ Zeile löschen")
        btn_del_p.clicked.connect(self._delete_angebot)
        btn_exp_p = QPushButton("Exportieren")
        btn_exp_p.clicked.connect(self._export_angebote)
        btn_druck_p = QPushButton("Drucken")
        btn_druck_p.clicked.connect(self._drucken_angebote)
        btn_vor_p = QPushButton("Druckvorschau")
        btn_vor_p.clicked.connect(self._druckvorschau_angebote)
        btn_row_p.addWidget(self.btn_add_p)
        btn_row_p.addWidget(btn_del_p)
        btn_row_p.addStretch()
        btn_row_p.addWidget(btn_exp_p)
        btn_row_p.addWidget(btn_druck_p)
        btn_row_p.addWidget(btn_vor_p)
        pl.addLayout(btn_row_p)
        self.angebots_table = AngebotsTable()
        self.angebots_table.cellChanged.connect(self.angebots_table.save_row)
        pl.addWidget(self.angebots_table)
        _, _, _pl_label = self._get_pl()
        self.tabs.addTab(projekte_tab, _pl_label)
        self.tabs.setTabIcon(1, QIcon.fromTheme("folder",
            QIcon.fromTheme("folder-open")))

        # Tab 3: Raumplan (Räume + Zeitzuordnung)
        raumplan_tab = QWidget()
        rl = QVBoxLayout(raumplan_tab)

        raum_group = QGroupBox("Raumliste")
        rg_layout = QVBoxLayout(raum_group)
        rg_btns = QHBoxLayout()
        btn_add_raum = QPushButton("+ Raum hinzufügen")
        btn_add_raum.clicked.connect(self._add_raum)
        btn_del_raum = QPushButton("✗ Raum löschen")
        btn_del_raum.clicked.connect(self._delete_raum)
        btn_import_raum = QPushButton("Raumliste importieren")
        btn_import_raum.clicked.connect(self._importiere_raeume)
        btn_export_raum = QPushButton("Raumliste exportieren")
        btn_export_raum.clicked.connect(self._export_raumliste)
        rg_btns.addWidget(btn_add_raum)
        rg_btns.addWidget(btn_del_raum)
        rg_btns.addWidget(btn_import_raum)
        rg_btns.addWidget(btn_export_raum)
        rg_btns.addStretch()
        rg_layout.addLayout(rg_btns)
        self.raeume_table = RaeumeTable()
        rg_layout.addWidget(self.raeume_table)
        rl.addWidget(raum_group)

        plan_group = QGroupBox(
            "Raumzuordnung – je Option ein Raum und eine Zeit "
            "(Doppelbelegungen und Kapazitätsprobleme werden farbig markiert)"
        )
        pg_layout = QVBoxLayout(plan_group)
        pg_btns = QHBoxLayout()
        pg_btns.addStretch()
        btn_exp_raum = QPushButton("Exportieren")
        btn_exp_raum.clicked.connect(self._export_raumplan)
        btn_druck_raum = QPushButton("Drucken")
        btn_druck_raum.clicked.connect(self._drucken_raumplan)
        btn_vor_raum = QPushButton("Druckvorschau")
        btn_vor_raum.clicked.connect(self._druckvorschau_raumplan)
        pg_btns.addWidget(btn_exp_raum)
        pg_btns.addWidget(btn_druck_raum)
        pg_btns.addWidget(btn_vor_raum)
        pg_layout.addLayout(pg_btns)
        self.raumplan_table = RaumplanTable()
        pg_layout.addWidget(self.raumplan_table)
        rl.addWidget(plan_group)

        # Räume-Änderung -> Raumplan-Dropdowns/Kapazitäten neu laden
        self.raeume_table.changed.connect(self._refresh_raumplan)
        # Optionen-Änderung (u. a. Leitung, Optionsname, Plätze max) live
        # in der Raumzuordnung spiegeln
        self.angebots_table.changed.connect(self.raumplan_table.refresh_aus_optionen)
        self.tabs.addTab(raumplan_tab, "Raumplan")
        self.tabs.setTabIcon(2, QIcon.fromTheme("view-calendar",
            QIcon.fromTheme("office-calendar", QIcon.fromTheme("map"))))

        # Tab 4: Statistik
        self.statistik_widget = StatistikWidget()
        self.statistik_widget.wunschauswertung_angefordert.connect(self._oeffne_wunschauswertung_fuer_projekt)
        self.statistik_widget.projektdetails_angefordert.connect(self._zeige_projektdetails)
        self.statistik_widget.teilnehmerliste_angefordert.connect(
            self._oeffne_projektteilnehmerliste)
        self.statistik_widget.qualitaetspruefung_angefordert.connect(
            self._zeige_qualitaetspruefung)
        self.statistik_widget.klassenliste_angefordert.connect(
            self._zeige_klassenliste)
        self.statistik_widget.export_nach_gruppen_angefordert.connect(
            self._export_gesamtliste_nach_klassen)
        self.statistik_widget.export_nach_optionen_angefordert.connect(
            self._export_gesamtliste_nach_projekten)
        self.angebots_table.changed.connect(self.statistik_widget.refresh)
        self.tabs.addTab(self.statistik_widget, "Auswertung, Nachbearbeitung, Export")
        self.tabs.setTabIcon(3, QIcon.fromTheme("x-office-spreadsheet",
            QIcon.fromTheme("office-chart-bar", QIcon.fromTheme("applications-other"))))

        # Status-Bar
        self.statusBar().showMessage("Bereit.")

        # Speicher-Indikator (Diskette): blass = gespeichert, kräftig = soeben geändert
        self._save_icon_label = QLabel()
        self._save_icon_label.setToolTip(
            "Alle Änderungen werden automatisch sofort gespeichert."
        )
        self._save_icon_dim   = self._make_disk_icon(dim=True)
        self._save_icon_bright = self._make_disk_icon(dim=False)
        self._save_icon_label.setPixmap(self._save_icon_dim)
        self.statusBar().addPermanentWidget(self._save_icon_label)

        self._save_blink_timer = QTimer(self)
        self._save_blink_timer.setSingleShot(True)
        self._save_blink_timer.timeout.connect(
            lambda: self._save_icon_label.setPixmap(self._save_icon_dim)
        )

    @staticmethod
    def _make_disk_icon(dim: bool) -> "QPixmap":
        """Zeichnet ein einfaches Disketten-Icon, blass oder kräftig."""
        from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen
        size = 16
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor("#b0b0b0") if dim else QColor("#2563eb")
        painter.setBrush(color)
        painter.setPen(QPen(color.darker(120), 1))
        painter.drawRoundedRect(1, 1, size - 2, size - 2, 2, 2)
        # Kleines "Etikett" oben
        label_color = QColor("#ffffff") if not dim else QColor("#e8e8e8")
        painter.setBrush(label_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(4, 2, size - 8, 5)
        painter.end()
        return pm

    def _signal_gespeichert(self):
        """Lässt das Disketten-Icon kurz aufblitzen (kräftig → blass)."""
        if not hasattr(self, "_save_icon_label"):
            return
        self._save_icon_label.setPixmap(self._save_icon_bright)
        self._save_blink_timer.start(900)

    # ── Menü aufbauen ────────────────────────────────────────────────────────

    def _build_menu(self):
        mb = self.menuBar()

        # ── Datei ──
        m_datei = mb.addMenu("Datei")
        a = QAction("Planungsmappe öffnen", self)
        a.setShortcut(QKeySequence("Ctrl+O"))
        a.triggered.connect(self._open_db)
        m_datei.addAction(a)

        a_neu = QAction("Neue leere Planungsmappe erstellen", self)
        a_neu.setShortcut(QKeySequence("Ctrl+Shift+N"))
        a_neu.triggered.connect(self._new_db)
        m_datei.addAction(a_neu)

        a_schliessen = QAction("Planungsmappe schließen", self)
        a_schliessen.setShortcut(QKeySequence("Ctrl+W"))
        a_schliessen.triggered.connect(self._close_db)
        m_datei.addAction(a_schliessen)

        m_datei.addSeparator()

        # "Planungsmappe speichern" (Strg+S) bleibt als reiner Shortcut aktiv
        # ohne Menüeintrag, da automatisches Speichern (SQLite) ohnehin
        # nach jeder Aktion erfolgt -- der Shortcut dient nur als
        # beruhigende Bestätigung (vgl. Microsoft Access).
        a3 = QAction("Planungsmappe speichern", self)
        a3.setShortcut(QKeySequence("Ctrl+S"))
        a3.triggered.connect(self._save_db)
        self.addAction(a3)  # Shortcut aktiv, aber kein Menüeintrag

        a3x = QAction("Planungsmappe speichern als", self)
        a3x.setShortcut(QKeySequence("Ctrl+Shift+S"))
        a3x.triggered.connect(self._save_db_as)
        m_datei.addAction(a3x)

        m_datei.addSeparator()

        a3b = QAction("Gruppenbereich-Werte bereinigen (z. B. \"5.0\" → \"5\")", self)
        a3b.triggered.connect(self._repariere_jgst)
        m_datei.addAction(a3b)

        a3c = QAction("Spaltenbezeichnungen anpassen", self)
        a3c.setShortcut(QKeySequence("Ctrl+B"))
        a3c.triggered.connect(self._spaltenbezeichnungen_anpassen)
        m_datei.addAction(a3c)

        a3d = QAction("Tabellen-Export- und Importassistenten starten", self)
        a3d.triggered.connect(self._tabellen_assistent_starten)
        m_datei.addAction(a3d)

        a3e = QAction("Speicherorte verwalten (für Export, z. B. Nextcloud/WebDAV)", self)
        a3e.triggered.connect(self._speicherorte_verwalten)
        m_datei.addAction(a3e)

        m_datei.addSeparator()

        a4 = QAction("App schließen", self)
        a4.setShortcut(QKeySequence("Ctrl+Q"))
        a4.triggered.connect(self.close)
        m_datei.addAction(a4)

        # ── Importieren ──
        m_import = mb.addMenu("Importieren")

        a5 = QAction("Teilnehmer/innen importieren", self)
        a5.setShortcut(QKeySequence("Ctrl+I"))
        a5.triggered.connect(lambda: self._import("schueler"))
        m_import.addAction(a5)

        a6 = QAction("Optionen / Angebote importieren", self)
        a6.setShortcut(QKeySequence("Ctrl+Shift+I"))
        a6.triggered.connect(lambda: self._import("projekte"))
        m_import.addAction(a6)

        # ── Einteilung ──
        m_einteilen = mb.addMenu("Einteilung")

        a7 = QAction("Automatisch zuweisen – Algorithmus A (Wunsch-Priorität)", self)
        a7.setShortcut(QKeySequence("Ctrl+Shift+A"))
        a7.triggered.connect(lambda: self._auto_einteilen("A"))
        m_einteilen.addAction(a7)

        a8 = QAction("Automatisch zuweisen – Algorithmus B (Mindest-TN-Priorität)", self)
        a8.setShortcut(QKeySequence("Ctrl+Shift+B"))
        a8.triggered.connect(lambda: self._auto_einteilen("B"))
        m_einteilen.addAction(a8)

        a8c = QAction("Automatisch zuweisen – Algorithmus C (Alle-Versorgen-Priorität)", self)
        a8c.setShortcut(QKeySequence("Ctrl+Shift+C"))
        a8c.triggered.connect(lambda: self._auto_einteilen("C"))
        m_einteilen.addAction(a8c)

        m_einteilen.addSeparator()

        _lbl2, _, _ = self._get_pl()
        self.a_manuell = QAction(f"{_lbl2} fix zuweisen", self)
        self.a_manuell.setShortcut(QKeySequence("Ctrl+Shift+F"))
        self.a_manuell.triggered.connect(lambda: self._feste_zuweisung(nur_wunschprojekte=True))
        m_einteilen.addAction(self.a_manuell)

        m_einteilen.addSeparator()

        a9 = QAction("Automatische Zuweisung aufheben", self)
        a9.setShortcut(QKeySequence("Ctrl+Shift+R"))
        a9.triggered.connect(self._reset_einteilung)
        m_einteilen.addAction(a9)

        a_fix_loeschen = QAction("Alle fixen Zuweisungen löschen", self)
        a_fix_loeschen.triggered.connect(self._alle_fixierungen_aufheben)
        m_einteilen.addAction(a_fix_loeschen)

        # Hinweis: Die feste Zuweisung einzelner Teilnehmer/innen erfolgt
        # über die Schaltflächen "Projekt zuteilen" und
        # "✗ Fixierung aufheben" direkt über der Schülertabelle
        # im Tab "Teilnehmer/innen" -- dort, wo die Auswahl auch stattfindet.

        # ── Exportieren ──
        # ── Suche / Listen ──
        m_listen = mb.addMenu("Auswertung/Export")

        _pl_wa, _, _ = self._get_pl()
        a13 = QAction(f"Wunschauswertungsliste nach {_pl_wa}", self)
        a13.setShortcut(QKeySequence("Ctrl+Shift+W"))
        a13.triggered.connect(self._zeige_wunschauswertung)
        m_listen.addAction(a13)

        _lbl14, _, _ = self._get_pl()
        self.a14_teilnehmerliste = QAction(f"Teilnehmerliste nach {_lbl14}", self)
        a14 = self.a14_teilnehmerliste
        a14.setShortcut(QKeySequence("Ctrl+Shift+P"))
        a14.triggered.connect(self._zeige_projektteilnehmerliste)
        m_listen.addAction(a14)

        a15 = QAction("Gruppenliste mit Zuteilung", self)
        a15.setShortcut(QKeySequence("Ctrl+Shift+K"))
        a15.triggered.connect(self._zeige_klassenliste)
        m_listen.addAction(a15)

        m_listen.addSeparator()

        a16 = QAction("Qualitätsprüfung Wunscheingaben", self)
        a16.setShortcut(QKeySequence("Ctrl+Shift+Q"))
        a16.triggered.connect(self._zeige_qualitaetspruefung)
        m_listen.addAction(a16)

        m_listen.addSeparator()

        a_exp_kl = QAction("Gesamtliste nach Gruppen exportieren", self)
        a_exp_kl.triggered.connect(self._export_gesamtliste_nach_klassen)
        m_listen.addAction(a_exp_kl)

        _, _, _plP_exp = self._get_pl()
        self.a_exp_pr = QAction(f"Gesamtliste nach {_plP_exp} exportieren", self)
        a_exp_pr = self.a_exp_pr
        a_exp_pr.triggered.connect(self._export_gesamtliste_nach_projekten)
        m_listen.addAction(a_exp_pr)

        # ── Hilfe ──
        m_hilfe = mb.addMenu("Hilfe")

        a_hilfe = QAction("Tastaturkürzel-Übersicht", self)
        a_hilfe.setShortcut(QKeySequence("F1"))
        a_hilfe.triggered.connect(self._zeige_tastenkuerzel)
        m_hilfe.addAction(a_hilfe)

        m_hilfe.addSeparator()

        m_beispiel = m_hilfe.addMenu("Beispieldaten ausprobieren")

        a_bsp_mappe = QAction(
            "Beispiel-Planungsmappe öffnen (ausgefüllt, bereit zum Zuteilen)", self
        )
        a_bsp_mappe.triggered.connect(self._oeffne_beispiel_planungsmappe)
        m_beispiel.addAction(a_bsp_mappe)

        m_beispiel.addSeparator()

        a_bsp_tn = QAction("Beispiel-Teilnehmerliste importieren", self)
        a_bsp_tn.triggered.connect(self._importiere_beispiel_teilnehmer)
        m_beispiel.addAction(a_bsp_tn)

        a_bsp_pr = QAction("Beispiel-Optionsliste importieren", self)
        a_bsp_pr.triggered.connect(self._importiere_beispiel_projekte)
        m_beispiel.addAction(a_bsp_pr)

        m_hilfe.addSeparator()

        a_ueber = QAction("Über Mitmach-Lotse", self)
        a_ueber.triggered.connect(self._zeige_ueber)
        m_hilfe.addAction(a_ueber)

    # ── Tastenkürzel ─────────────────────────────────────────────────────────

    def _build_shortcuts(self):
        def sc(key, slot):
            a = QAction(self)
            a.setShortcut(QKeySequence(key))
            a.triggered.connect(slot)
            self.addAction(a)
            return a

        # Navigation: Suche
        sc("Ctrl+F",   self._focus_search)
        sc("Escape",   self._escape_search)

        # Navigation: Tabs (Ctrl+1/2/3 und Alt+1/2/3 als Alternative)
        sc("Ctrl+1",   lambda: self.tabs.setCurrentIndex(0))
        sc("Ctrl+2",   lambda: self.tabs.setCurrentIndex(1))
        sc("Ctrl+3",   lambda: self.tabs.setCurrentIndex(2))
        sc("Ctrl+4",   lambda: self.tabs.setCurrentIndex(3))
        sc("Alt+1",    lambda: self.tabs.setCurrentIndex(0))
        sc("Alt+2",    lambda: self.tabs.setCurrentIndex(1))
        sc("Alt+3",    lambda: self.tabs.setCurrentIndex(2))
        sc("Alt+4",    lambda: self.tabs.setCurrentIndex(3))

        # Tabellen: Neu / Löschen / Neu laden – kontextabhängig
        sc("Ctrl+N",    self._shortcut_neu)
        sc("Delete",    self._shortcut_loeschen)
        sc("F5",        self._shortcut_neu_laden)


    # ── Daten laden/speichern ────────────────────────────────────────────────

    def _refresh_all(self):
        self._refresh_teilnehmer()
        self._refresh_angebote()
        self._refresh_raumplan()
        self.statistik_widget.refresh()

    def _refresh_raumplan(self):
        """Lädt Raumliste und Raumzuordnung neu (falls Tab bereits gebaut)."""
        if hasattr(self, "raeume_table"):
            self.raeume_table.load()
        if hasattr(self, "raumplan_table"):
            self.raumplan_table.load()

    def _on_tab_changed(self, idx: int):
        """Beim Wechsel auf den Raumplan-Tab die gespiegelten Felder (u. a.
        „belegt", Leitung) auffrischen, damit sie eine zwischenzeitliche
        (Um-)Zuteilung bzw. Bearbeitung im Optionen-Tab widerspiegeln."""
        if idx == 2 and hasattr(self, "raumplan_table"):
            self.raumplan_table.refresh_aus_optionen()

    def _refresh_and_reselect(self):
        """Nach save_row: Tabelle neu sortieren, zuletzt bearbeiteten TN wiederfinden."""
        # Aktuelle ID merken
        aktuell_id = self.teilnehmer_table.get_selected_id()
        self._refresh_teilnehmer()
        if aktuell_id is None:
            return
        for row in range(self.teilnehmer_table.rowCount()):
            id_item = self.teilnehmer_table.item(row, 0)
            if id_item and int(id_item.text()) == aktuell_id:
                self.teilnehmer_table.selectRow(row)
                self.teilnehmer_table.scrollToItem(
                    self.teilnehmer_table.item(row, 1),
                    QAbstractItemView.ScrollHint.PositionAtCenter
                )
                break

    def _refresh_teilnehmer(self):
        self.teilnehmer_table.load()
        n = self.teilnehmer_table.rowCount()
        self.statusBar().showMessage(f"{n} Teilnehmer/innen geladen.")
        self._signal_gespeichert()

    def _refresh_angebote(self):
        self.angebots_table.load()
        n = self.angebots_table.rowCount()
        self.statusBar().showMessage(f"{n} {self._get_pl()[2]} geladen.")
        self._signal_gespeichert()

    def _update_title(self):
        """Zeigt den Namen der aktuellen DB-Datei im Fenstertitel."""
        name = db.DB_PATH.name
        self.setWindowTitle(f"Mitmach-Lotse – {name}")

    def _update_search_placeholder(self):
        """Setzt den Platzhaltertext des Suchfelds dynamisch."""
        k = db.get_feldkonfig()
        self.search_edit.setPlaceholderText(
            f"Name, {k.get('stufe_label', 'Gruppenbereich')}, "
            f"{k.get('stufenzusatz_label', 'Gruppenzusatz')}"
        )

    # ── Datenbank schließen / neu ────────────────────────────────────────────

    def _close_db(self):
        """Schließt die aktuelle Datenbank und legt eine neue leere an."""
        antwort = QMessageBox.question(
            self, "Planungsmappe schließen",
            f"Aktuelle Planungsmappe schließen?\n\n"
            f"Datei: {db.DB_PATH.name}\n\n"
            f"Die Daten bleiben in der Datei erhalten. "
            f"Die Anzeige wird geleert, bis eine neue Planungsmappe geöffnet "
            f"oder Daten importiert werden.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if antwort != QMessageBox.StandardButton.Yes:
            return
        self._erstelle_leere_db()

    def _new_db(self):
        """Erstellt direkt eine neue leere Datenbank (mit Bestätigung)."""
        antwort = QMessageBox.question(
            self, "Neue Planungsmappe",
            "Eine neue leere Planungsmappe erstellen?\n\n"
            "Die bisherige Planungsmappe bleibt als Datei erhalten,\n"
            "wird aber nicht mehr angezeigt.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if antwort != QMessageBox.StandardButton.Yes:
            return
        self._erstelle_leere_db()

    def _erstelle_leere_db(self):
        """Gemeinsame Logik: neue leere DB in einem Temp-Verzeichnis."""
        import tempfile
        tmp_path = Path(tempfile.gettempdir()) / "projekttage_neu.db"
        if tmp_path.exists():
            tmp_path.unlink()
        db.DB_PATH = tmp_path
        db.init_db()
        self._zeige_assistenten()

    def _spaltenbezeichnungen_anpassen(self):
        """Datei → Spaltenbezeichnungen anpassen"""
        konfig = db.get_feldkonfig()
        dlg = PlanungsmappeEinrichtenDialog(
            self, vorlage_laden=False, aktuell=konfig
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            db.set_feldkonfig(dlg.get_konfig())
            if dlg.soll_leitung_geloescht_werden():
                db.loesche_leitung_daten()
            self._refresh_all()
            self._sync_labels()
            self._update_search_placeholder()
            self.statusBar().showMessage("Spaltenbezeichnungen gespeichert.")

    def _tabellen_assistent_starten(self):
        """Datei → Tabellen-Export- und Importassistenten starten"""
        from dialoge import TabellenAssistentDialog
        # show() statt exec(): Der Assistent ist bewusst nicht-modal, damit
        # das von ihm geöffnete Qualitätsprüfungsfenster nicht dahinter
        # verschwindet (siehe Kommentar in TabellenAssistentDialog).
        if not hasattr(self, '_tabellen_assistent_fenster') or \
           not self._tabellen_assistent_fenster.isVisible():
            self._tabellen_assistent_fenster = TabellenAssistentDialog(self)
            self._tabellen_assistent_fenster.finished.connect(
                lambda *_: self._refresh_all()
            )
        self._tabellen_assistent_fenster.show()
        self._tabellen_assistent_fenster.raise_()
        self._tabellen_assistent_fenster.activateWindow()

    # ── Beispieldaten (Hilfe-Menü) ───────────────────────────────────────────

    BEISPIEL_ORDNER = Path(__file__).parent / "beispieldaten"

    def _oeffne_beispiel_planungsmappe(self):
        """
        Hilfe → Beispieldaten ausprobieren → Beispiel-Planungsmappe öffnen.
        Lädt direkt eine Arbeitskopie der mitgelieferten Beispieldatei, ohne
        Speicherort-Abfrage -- die Kopie liegt im Temp-Verzeichnis, analog zu
        "Neue leere Planungsmappe erstellen" (_erstelle_leere_db). Wer die
        Beispieldaten dauerhaft behalten möchte, nutzt anschließend ganz
        normal "Planungsmappe speichern als".
        """
        quelle = self.BEISPIEL_ORDNER / "planungsmappe_beispiel.plf"
        if not quelle.exists():
            QMessageBox.warning(self, "Beispieldaten", "Beispieldatei wurde nicht gefunden.")
            return
        import shutil
        import tempfile
        tmp_path = Path(tempfile.gettempdir()) / "beispiel_planungsmappe.plf"
        if tmp_path.exists():
            tmp_path.unlink()
        shutil.copy2(str(quelle), tmp_path)

        db.DB_PATH = tmp_path
        db.init_db()
        self._refresh_all()
        self._sync_labels()
        self._update_search_placeholder()
        self._update_title()

        konfig = db.get_feldkonfig()
        projekt_pl = db.pluralisiere_label(konfig.get("projekt_label", "Option"))
        n_tn = len(db.get_all_teilnehmer())
        n_pr = len(db.get_all_projekte())
        QMessageBox.information(
            self, "Beispiel-Planungsmappe geöffnet",
            f"Eine Beispiel-Planungsmappe mit {n_tn} Teilnehmer/innen und "
            f"{n_pr} {projekt_pl} wurde geladen – bereits mit Wünschen befüllt, "
            f"aber noch ohne Zuteilung.\n\n"
            "Zum Ausprobieren z. B.:\n"
            "• Einteilung → Automatisch zuweisen (Algorithmus A/B/C)\n"
            "• Auswertung/Export → Wunschstatistik und Listen ansehen\n\n"
            "Ihre bisherige Planungsmappe bleibt davon unberührt auf der Festplatte "
            "erhalten. Möchten Sie das Beispiel dauerhaft behalten, nutzen Sie "
            "anschließend \"Planungsmappe speichern als\"."
        )

    def _importiere_beispiel_teilnehmer(self):
        """
        Hilfe → Beispieldaten ausprobieren → Beispiel-Teilnehmerliste importieren.
        Öffnet den normalen Importdialog mit bereits gewählter Beispieldatei --
        Datei muss also nicht erst manuell gesucht werden, kann aber über
        "Durchsuchen" weiterhin geändert werden.
        """
        quelle = self.BEISPIEL_ORDNER / "teilnehmerliste_beispiel.xlsx"
        if not quelle.exists():
            QMessageBox.warning(self, "Beispieldaten", "Beispieldatei wurde nicht gefunden.")
            return
        dlg = ImportDialog("schueler", self, vorbelegter_pfad=str(quelle))
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._refresh_all()

    def _importiere_beispiel_projekte(self):
        """Hilfe → Beispieldaten ausprobieren → Beispiel-Optionsliste importieren."""
        quelle = self.BEISPIEL_ORDNER / "projektvorschlagsliste_beispiel.ods"
        if not quelle.exists():
            QMessageBox.warning(self, "Beispieldaten", "Beispieldatei wurde nicht gefunden.")
            return
        dlg = ImportDialog("projekte", self, vorbelegter_pfad=str(quelle))
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._refresh_all()

    # ── Kontextabhängige Shortcut-Aktionen ───────────────────────────────────

    def _shortcut_neu(self):
        """Strg+N: Neuer Eintrag, je nach aktivem Tab."""
        idx = self.tabs.currentIndex()
        if idx == 0:
            self._add_teilnehmer()
        elif idx == 1:
            self._add_angebot()
        elif idx == 2:
            self._add_raum()

    def _shortcut_loeschen(self):
        """Entf: Zeile löschen, je nach aktivem Tab.
        Wird nur ausgelöst, wenn die Tabelle (nicht ein Editor) den Fokus hat.
        """
        idx = self.tabs.currentIndex()
        if idx == 0:
            focused = QApplication.focusWidget()
            # Nur löschen, wenn die Tabelle selbst fokussiert ist,
            # nicht wenn eine Zelle gerade bearbeitet wird
            if focused is self.teilnehmer_table or focused is self.teilnehmer_table.viewport():
                self._delete_teilnehmer()
        elif idx == 1:
            focused = QApplication.focusWidget()
            if focused is self.angebots_table or focused is self.angebots_table.viewport():
                self._delete_angebot()
        elif idx == 2:
            # Im Raumplan-Tab nur die Raumliste löschbar (die Zuordnungstabelle
            # spiegelt die Optionen und darf nicht per Entf verändert werden).
            focused = QApplication.focusWidget()
            if focused is self.raeume_table or focused is self.raeume_table.viewport():
                self._delete_raum()

    def _shortcut_neu_laden(self):
        """F5: Neu laden, je nach aktivem Tab."""
        idx = self.tabs.currentIndex()
        if idx == 0:
            self._refresh_teilnehmer()
        elif idx == 1:
            self._refresh_angebote()
        else:
            self._refresh_all()

    def _escape_search(self):
        """Escape: Suchfeld leeren und Fokus zurück zur Tabelle."""
        if self.search_edit.text():
            self.search_edit.clear()
        self.teilnehmer_table.setFocus()

    def _zeige_ueber(self):
        """Hilfe → Über Mitmach-Lotse."""
        from dialoge import UeberDialog
        dlg = UeberDialog(self)
        dlg.exec()

    # ── Tastaturkürzel-Übersicht ────────────────────────────────────────────────

    def _zeige_tastenkuerzel(self):
        """F1: Zeigt eine übersichtliche Liste aller Tastenkürzel."""
        text = (
            "<h3>Tastenkürzel – Mitmach-Lotse</h3>"
            "<table cellpadding='4' cellspacing='0'>"
            "<tr><th align='left' colspan='2'><u>Datei / Planungsmappe</u></th></tr>"
            "<tr><td><b>Strg+O</b></td><td>Planungsmappe öffnen</td></tr>"
            "<tr><td><b>Strg+Shift+N</b></td><td>Neue leere Planungsmappe erstellen</td></tr>"
            "<tr><td><b>Strg+W</b></td><td>Planungsmappe schließen</td></tr>"
            "<tr><td><b>Strg+Shift+S</b></td><td>Planungsmappe speichern als …</td></tr>"
            "<tr><td><b>Strg+B</b></td><td>Spaltenbezeichnungen anpassen</td></tr>"
            "<tr><td><b>Strg+Q</b></td><td>App beenden</td></tr>"
            "<tr><th align='left' colspan='2'><u>&nbsp;<br>Navigation</u></th></tr>"
            "<tr><td><b>Strg+1</b></td><td>Tab &#8222;Teilnehmer/innen&#8220;</td></tr>"
            f"<tr><td><b>Strg+2</b></td><td>Tab &#8222;{self._get_pl()[2]}&#8220;</td></tr>"
            "<tr><td><b>Strg+3</b></td><td>Tab &#8222;Raumplan&#8220;</td></tr>"
            "<tr><td><b>Strg+4</b></td><td>Tab &#8222;Auswertung, Nachbearbeitung, Export&#8220;</td></tr>"
            "<tr><td><b>Strg+F</b></td><td>Suchfeld fokussieren</td></tr>"
            "<tr><td><b>Escape</b></td><td>Suche leeren / zurück zur Tabelle</td></tr>"
            "<tr><th align='left' colspan='2'><u>&nbsp;<br>Tabellen-Aktionen</u></th></tr>"
            f"<tr><td><b>Strg+N</b></td><td>Neuer Eintrag (Teilnehmer/in, {self._get_pl()[0]} oder Raum, je nach Tab)</td></tr>"
            "<tr><td><b>Entf</b></td><td>Markierten Eintrag löschen (Tabellenfokus nötig)</td></tr>"
            "<tr><td><b>F5</b></td><td>Tabelle neu laden</td></tr>"
            "<tr><th align='left' colspan='2'><u>&nbsp;<br>Import / Export</u></th></tr>"
            "<tr><td><b>Strg+I</b></td><td>Teilnehmer/innen importieren</td></tr>"
            f"<tr><td><b>Strg+Shift+I</b></td><td>{self._get_pl()[2]} importieren</td></tr>"
            "<tr><td><b>Strg+E</b></td><td>Daten exportieren</td></tr>"
            "<tr><th align='left' colspan='2'><u>&nbsp;<br>Einteilung</u></th></tr>"
            "<tr><td><b>Strg+Shift+A</b></td><td>Algorithmus A starten (Wunsch-Priorität)</td></tr>"
            "<tr><td><b>Strg+Shift+B</b></td><td>Algorithmus B starten (Mindest-TN-Priorität)</td></tr>"
            f"<tr><td><b>Strg+Shift+F</b></td><td>{self._get_pl()[0]} fix zuweisen</td></tr>"
            "<tr><td><b>Strg+Shift+R</b></td><td>Automatische Zuweisung aufheben</td></tr>"
            "<tr><th align='left' colspan='2'><u>&nbsp;<br>Listen / Suche</u></th></tr>"
            "<tr><td><b>Strg+Shift+W</b></td><td>Wunschauswertung</td></tr>"
            f"<tr><td><b>Strg+Shift+P</b></td><td>Teilnehmerliste nach {self._get_pl()[0]}</td></tr>"
            "<tr><td><b>Strg+Shift+K</b></td><td>Gruppenliste mit Zuteilung</td></tr>"
            "<tr><td><b>F1</b></td><td>Diese Übersicht</td></tr>"
            "</table>"
        )
        dlg = QDialog(self)
        dlg.setWindowTitle("Tastenkürzel-Übersicht")
        dlg.setMinimumWidth(460)
        layout = QVBoxLayout(dlg)
        lbl = QLabel(text)
        lbl.setWordWrap(False)
        layout.addWidget(lbl)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        bb.accepted.connect(dlg.accept)
        layout.addWidget(bb)
        dlg.exec()

    # Dateiendung – an einer Stelle änderbar
    PMAPPE_ENDUNG = ".plf"
    PMAPPE_FILTER = ".plf – Planungsmappe (Planning File) (*.plf)"
    PMAPPE_ALT    = ".db – SQLite-Datenbank (*.db)"
    PMAPPE_ALLE   = "Alle Dateien (*)"

    def _open_db(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Planungsmappe öffnen", "",
            f"{self.PMAPPE_FILTER};;{self.PMAPPE_ALT};;{self.PMAPPE_ALLE}"
        )
        if path:
            db.DB_PATH = Path(path)
            db.init_db()
            self._refresh_all()
            self._update_title()

    def _save_db(self):
        """
        Einfaches Speichern ohne Verzeichnisauswahl.
        Da alle Änderungen direkt in db.DB_PATH (SQLite) geschrieben werden,
        bestätigt dies primär dass alle Daten gesichert sind -- nützlich
        nach mehreren Änderungen, bevor man die App schließt.
        """
        self._refresh_all()
        self._signal_gespeichert()
        self.statusBar().showMessage(
            f"Gespeichert: {db.DB_PATH.name}", 3000
        )

    def _save_db_as(self):
        vorschlag = db.DB_PATH.stem
        path, _ = QFileDialog.getSaveFileName(
            self, "Planungsmappe speichern als",
            vorschlag,
            f"{self.PMAPPE_FILTER};;{self.PMAPPE_ALT}"
        )
        if not path:
            return
        if Path(path).suffix.lower() not in (self.PMAPPE_ENDUNG, ".db"):
            path += self.PMAPPE_ENDUNG
        import shutil
        shutil.copy2(str(db.DB_PATH), path)
        QMessageBox.information(self, "Gespeichert",
                                f"Planungsmappe gesichert:\n{path}")

    def _repariere_jgst(self):
        antwort = QMessageBox.question(
            self, "Jahrgangsstufen-Werte bereinigen",
            "Bereinigt fehlerhafte Jahrgangsstufen-Werte, die z. B. durch\n"
            "einen Excel-Import als \"5.0\" statt \"5\" gespeichert wurden.\n\n"
            "Solche Werte können dazu führen, dass die automatische\n"
            f"Einteilung Teilnehmer/innen fälschlich keinem {self._get_pl()[0]} zuteilt,\n"
            f"weil die Jahrgangsstufe nicht mehr zum {self._get_pl()[0]}-Bereich passt.\n\n"
            "Fortfahren?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if antwort != QMessageBox.StandardButton.Yes:
            return

        anzahl = db.repariere_stufen_werte()
        self._refresh_teilnehmer()

        if anzahl:
            QMessageBox.information(
                self, "Bereinigung abgeschlossen",
                f"{anzahl} Jahrgangsstufen-Werte wurden korrigiert.\n\n"
                "Empfehlung: Führen Sie die automatische Einteilung erneut\n"
                "aus, damit betroffene Teilnehmer/innen korrekt berücksichtigt\n"
                "werden."
            )
        else:
            QMessageBox.information(
                self, "Bereinigung abgeschlossen",
                "Es wurden keine fehlerhaften Werte gefunden."
            )

    # ── Schüler-Aktionen ─────────────────────────────────────────────────────

    def _add_teilnehmer(self):
        from dialoge import TeilnehmerHinzufuegenDialog
        # Vorbelegung aus markierter Zeile (Gruppenbereich + Zusatz)
        vorbelegung = {}
        selected = self.teilnehmer_table.get_selected_ids()
        if selected:
            tn = db.get_teilnehmer_by_id(selected[0])
            if tn:
                vorbelegung = {"stufe": tn["stufe"],
                               "stufenzusatz": tn["stufenzusatz"]}

        dlg = TeilnehmerHinzufuegenDialog(self, vorbelegung=vorbelegung)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        neue_id = db.insert_teilnehmer(dlg.get_data())
        self._refresh_teilnehmer()

        # Zur einsortierten Position springen und markieren
        for row in range(self.teilnehmer_table.rowCount()):
            id_item = self.teilnehmer_table.item(row, 0)
            if id_item and int(id_item.text()) == neue_id:
                self.teilnehmer_table.selectRow(row)
                self.teilnehmer_table.scrollToItem(
                    self.teilnehmer_table.item(row, 1),
                    QAbstractItemView.ScrollHint.PositionAtCenter
                )
                break

    def _delete_teilnehmer(self):
        ids = self.teilnehmer_table.get_selected_ids()
        if not ids:
            QMessageBox.information(self, "Hinweis", "Bitte eine oder mehrere Zeilen auswählen.")
            return
        if len(ids) == 1:
            frage = "Teilnehmer/in wirklich löschen?"
        else:
            frage = f"{len(ids)} Teilnehmer/innen wirklich löschen?"
        antwort = QMessageBox.question(
            self, "Löschen?", frage,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if antwort == QMessageBox.StandardButton.Yes:
            for sid in ids:
                db.delete_teilnehmer(sid)
            self._refresh_teilnehmer()

    # ── Projekt-Aktionen ─────────────────────────────────────────────────────

    def _add_angebot(self):
        from dialoge import ProjektHinzufuegenDialog
        projekte  = db.get_all_projekte()
        max_nr    = max((p["nummer"] for p in projekte), default=0)

        dlg = ProjektHinzufuegenDialog(self, max_nummer=max_nr)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        data = dlg.get_data()

        if dlg.get_einsortieren():
            neue_nr = db.renumber_projekte_und_insert(data)
        else:
            neue_nr = dlg.get_nummer()
            db.upsert_projekt({**data, "nummer": neue_nr})

        self._refresh_angebote()
        self.statistik_widget.refresh()

        # Zur neuen Zeile springen und markieren
        for row in range(self.angebots_table.rowCount()):
            item = self.angebots_table.item(row, 0)
            if item and item.text() == str(neue_nr):
                self.angebots_table.selectRow(row)
                self.angebots_table.scrollToItem(
                    item, QAbstractItemView.ScrollHint.PositionAtCenter
                )
                break

    def _spaltenauswahl(self, headers: list,
                        titel: str = "Felder / Spalten für die Ausgabe wählen"):
        """Zeigt die Feldauswahl vor dem Drucken (ohne Kopfzeile/Datum-Optionen,
        die beim direkten Drucken nicht greifen).
        Rückgabe: Liste der gewählten Spaltenindizes, oder None bei Abbruch."""
        from dialoge import SpaltenauswahlDialog
        dlg = SpaltenauswahlDialog(headers, titel, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        return dlg.get_kept_indices()

    def _spaltenauswahl_export(self, headers: list,
                               titel: str = "Felder / Spalten für die Ausgabe wählen",
                               kopfzeile_vorgabe: str = ""):
        """Wie _spaltenauswahl, aber für echte Datei-Exporte zusätzlich mit
        Kopfzeile- und „Datum in der Fußzeile"-Option (wie beim Gesamtlisten-
        Export). Rückgabe: (kept_indices, kopfzeile, datum_fusszeile), oder
        None bei Abbruch."""
        from dialoge import SpaltenauswahlDialog
        dlg = SpaltenauswahlDialog(
            headers, titel, parent=self,
            mit_kopfzeile=True, kopfzeile_vorgabe=kopfzeile_vorgabe
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        return dlg.get_kept_indices(), dlg.get_kopfzeile(), dlg.get_datum_fusszeile()

    def _angebote_headers_rows(self):
        headers, keys = _build_angebots_headers_keys()
        projekte = sorted(db.get_all_projekte(), key=lambda p: p["nummer"])
        rows = [[str(p.get(k, "") or "") for k in keys] for p in projekte]
        return headers, rows

    # ── Speicherorte (Sidebar im Speichern-Dialog) ────────────────────────────

    def _sidebar_urls(self) -> list:
        """QUrls der konfigurierten Speicherorte (nur existierende Ordner)."""
        urls = []
        for ort in db.get_speicherorte():
            p = Path(ort["pfad"])
            if p.exists():
                urls.append(QUrl.fromLocalFile(str(p)))
        return urls

    def _save_dialog(self, titel: str, vorschlag: str, filter_str: str):
        """Speichern-Dialog mit konfigurierten Speicherorten in der Seitenleiste.
        Rückgabe (pfad, gewählter_filter) oder (None, None) bei Abbruch.
        Fällt ohne konfigurierte Orte auf den Standarddialog zurück."""
        extra = self._sidebar_urls()
        start = os.path.join(self._last_export_dir, vorschlag)
        if not extra:
            pfad, sel = QFileDialog.getSaveFileName(self, titel, start, filter_str)
            if pfad:
                self._last_export_dir = os.path.dirname(pfad)
            return pfad, sel
        dlg = QFileDialog(self, titel, start, filter_str)
        dlg.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        # Qt-Dialog erzwingen, damit die Seitenleisten-Einträge zuverlässig erscheinen
        dlg.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dlg.setSidebarUrls(dlg.sidebarUrls() + extra)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None, None
        files = dlg.selectedFiles()
        if not files:
            return None, None
        pfad = files[0]
        self._last_export_dir = os.path.dirname(pfad)
        return pfad, dlg.selectedNameFilter()

    def _dir_dialog(self, titel: str):
        """Ordnerauswahl mit konfigurierten Speicherorten in der Seitenleiste."""
        extra = self._sidebar_urls()
        if not extra:
            return QFileDialog.getExistingDirectory(self, titel, self._last_export_dir)
        dlg = QFileDialog(self, titel, self._last_export_dir)
        dlg.setFileMode(QFileDialog.FileMode.Directory)
        dlg.setOption(QFileDialog.Option.ShowDirsOnly, True)
        dlg.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dlg.setSidebarUrls(dlg.sidebarUrls() + extra)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return ""
        files = dlg.selectedFiles()
        return files[0] if files else ""

    def _speicherorte_verwalten(self):
        """Datei → Speicherorte verwalten."""
        from dialoge import SpeicherorteDialog
        SpeicherorteDialog(self).exec()

    def _export_angebote(self):
        """Exportiert die aktuelle Optionstabelle."""
        headers, rows = self._angebote_headers_rows()
        auswahl = self._spaltenauswahl_export(headers)
        if auswahl is None:
            return
        kept, kopfzeile, datum_fuss = auswahl
        headers, rows = ie.filter_spalten(headers, rows, kept)
        pl, _, plP = self._get_pl()
        gruppen = [(plP, headers, rows)]
        ext_filter = "PDF (*.pdf);;Excel (*.xlsx);;ODS (*.ods);;CSV (*.csv)"
        pfad, sel = self._save_dialog(f"{plP} exportieren", plP, ext_filter)
        if not pfad:
            return
        fmt = {"PDF": "pdf", "Excel": "xlsx", "ODS": "ods", "CSV": "csv"}.get(
            (sel or "").split(" ")[0], "pdf"
        )
        if not any(pfad.lower().endswith(f".{x}") for x in ("pdf","xlsx","ods","csv")):
            pfad += f".{fmt}"
        try:
            ie.export_gruppen(pfad, fmt, gruppen, kopfzeile=kopfzeile,
                              datum_fusszeile=datum_fuss)
        except Exception as e:
            QMessageBox.critical(self, "Exportfehler", str(e))

    def _drucken_angebote(self):
        from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
        from PyQt6.QtGui import QTextDocument
        headers, rows = self._angebote_headers_rows()
        kept = self._spaltenauswahl(headers)
        if kept is None:
            return
        headers, rows = ie.filter_spalten(headers, rows, kept)
        _, _, plP = self._get_pl()
        printer = QPrinter(QPrinter.PrinterMode.ScreenResolution)
        if QPrintDialog(printer, self).exec() != QPrintDialog.DialogCode.Accepted:
            return
        doc = QTextDocument()
        doc.setHtml(self._html_tabelle(plP, headers, rows))
        getattr(doc, 'print')(printer)

    def _druckvorschau_angebote(self):
        from PyQt6.QtPrintSupport import QPrinter, QPrintPreviewDialog
        from PyQt6.QtGui import QTextDocument
        headers, rows = self._angebote_headers_rows()
        kept = self._spaltenauswahl(headers)
        if kept is None:
            return
        headers, rows = ie.filter_spalten(headers, rows, kept)
        _, _, plP = self._get_pl()
        printer = QPrinter(QPrinter.PrinterMode.ScreenResolution)
        dlg = QPrintPreviewDialog(printer, self)
        def _render(p):
            doc = QTextDocument()
            doc.setHtml(self._html_tabelle(plP, headers, rows))
            getattr(doc, 'print')(p)
        dlg.paintRequested.connect(_render)
        dlg.exec()

    # ── Raumplan ─────────────────────────────────────────────────────────────

    @staticmethod
    def _html_tabelle(titel: str, headers: list, rows: list) -> str:
        """Baut ein einfaches HTML-Dokument (eine Tabelle) für Druck/Vorschau."""
        th = "".join(f"<th>{h}</th>" for h in headers)
        tbody = ""
        for row in rows:
            cells = "".join(f"<td>{c}</td>" for c in row)
            tbody += f"<tr>{cells}</tr>"
        return f"""<!DOCTYPE html><html><head><meta charset='UTF-8'>
<style>body{{font-family:Arial,sans-serif;font-size:9pt}}
table{{border-collapse:collapse;width:100%}}
th{{background:#4472C4;color:#fff;padding:3px 6px;text-align:left;font-size:8.5pt}}
td{{padding:2px 6px;border-bottom:1px solid #ddd;font-size:8.5pt}}
tr:nth-child(even) td{{background:#f0f4f8}}
h2{{font-size:11pt}}</style></head><body>
<h2>{titel}</h2>
<table><thead><tr>{th}</tr></thead><tbody>{tbody}</tbody></table>
</body></html>"""

    def _add_raum(self):
        self.tabs.setCurrentIndex(2)
        self.raeume_table.add_empty_row()

    def _delete_raum(self):
        ids = self.raeume_table.get_selected_ids()
        if not ids:
            QMessageBox.information(self, "Hinweis", "Bitte einen oder mehrere Räume auswählen.")
            return
        antwort = QMessageBox.question(
            self, "Raum löschen?",
            f"{len(ids)} Raum/Räume wirklich löschen?\n\n"
            "Die Zuordnung wird bei betroffenen Optionen entfernt.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if antwort != QMessageBox.StandardButton.Yes:
            return
        for rid in ids:
            db.delete_raum(rid)
        self._refresh_raumplan()
        self._signal_gespeichert()

    def _importiere_raeume(self):
        """Öffnet den Import-Dialog für die Raumliste (CSV/xlsx/ods)."""
        self.tabs.setCurrentIndex(2)
        self._import("raeume")

    def _export_raumliste(self):
        """Exportiert die Raumliste so, dass die Datei beim Wiederimport
        automatisch zum Raum-Spaltenzuordnungsfenster passt (Spaltentitel
        „Raumname", „Kapazität", „Beschreibung"). Kopfzeile bleibt standardmäßig
        leer, damit der Reimport die Spaltenüberschriften direkt in Zeile 1
        findet -- wird sie befüllt, erkennt der Reimport sie wie bei den
        Gesamtlisten automatisch und überspringt sie."""
        # Spaltentitel = exakt die Feldlabels aus dem Raum-Import
        felder = ie.get_raum_felder()  # [(key, label), ...]
        headers = [label for _key, label in felder]
        keys    = [key for key, _label in felder]
        raeume = db.get_all_raeume()
        rows = []
        for raum in raeume:
            zeile = []
            for k in keys:
                v = raum.get(k, "")
                if k == "kapazitaet":
                    v = "" if not v else str(v)
                zeile.append(str(v or ""))
            rows.append(zeile)

        auswahl = self._spaltenauswahl_export(headers)
        if auswahl is None:
            return
        kept, kopfzeile, datum_fuss = auswahl
        headers, rows = ie.filter_spalten(headers, rows, kept)

        ext_filter = "Excel (*.xlsx);;ODS (*.ods);;CSV (*.csv);;PDF (*.pdf)"
        pfad, sel = self._save_dialog("Raumliste exportieren", "Raumliste", ext_filter)
        if not pfad:
            return
        fmt = {"Excel": "xlsx", "ODS": "ods", "CSV": "csv", "PDF": "pdf"}.get(
            (sel or "").split(" ")[0], "xlsx"
        )
        if not any(pfad.lower().endswith(f".{x}") for x in ("xlsx", "ods", "csv", "pdf")):
            pfad += f".{fmt}"
        try:
            ie.export_gruppen(pfad, fmt, [("", headers, rows)],
                              kopfzeile=kopfzeile, datum_fusszeile=datum_fuss)
        except Exception as e:
            QMessageBox.critical(self, "Exportfehler", str(e))

    def _export_raumplan(self):
        headers, rows = self.raumplan_table.export_daten()
        auswahl = self._spaltenauswahl_export(headers)
        if auswahl is None:
            return
        kept, kopfzeile, datum_fuss = auswahl
        headers, rows = ie.filter_spalten(headers, rows, kept)
        gruppen = [("Raumplan", headers, rows)]
        ext_filter = "PDF (*.pdf);;Excel (*.xlsx);;ODS (*.ods);;CSV (*.csv)"
        pfad, sel = self._save_dialog("Raumplan exportieren", "Raumplan", ext_filter)
        if not pfad:
            return
        fmt = {"PDF": "pdf", "Excel": "xlsx", "ODS": "ods", "CSV": "csv"}.get(
            (sel or "").split(" ")[0], "pdf"
        )
        if not any(pfad.lower().endswith(f".{x}") for x in ("pdf", "xlsx", "ods", "csv")):
            pfad += f".{fmt}"
        try:
            ie.export_gruppen(pfad, fmt, gruppen, kopfzeile=kopfzeile,
                              datum_fusszeile=datum_fuss)
        except Exception as e:
            QMessageBox.critical(self, "Exportfehler", str(e))

    def _drucken_raumplan(self):
        from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
        from PyQt6.QtGui import QTextDocument
        headers, rows = self.raumplan_table.export_daten()
        kept = self._spaltenauswahl(headers)
        if kept is None:
            return
        headers, rows = ie.filter_spalten(headers, rows, kept)
        printer = QPrinter(QPrinter.PrinterMode.ScreenResolution)
        if QPrintDialog(printer, self).exec() != QPrintDialog.DialogCode.Accepted:
            return
        doc = QTextDocument()
        doc.setHtml(self._html_tabelle("Raumplan", headers, rows))
        getattr(doc, 'print')(printer)

    def _druckvorschau_raumplan(self):
        from PyQt6.QtPrintSupport import QPrinter, QPrintPreviewDialog
        from PyQt6.QtGui import QTextDocument
        headers, rows = self.raumplan_table.export_daten()
        kept = self._spaltenauswahl(headers)
        if kept is None:
            return
        headers, rows = ie.filter_spalten(headers, rows, kept)
        printer = QPrinter(QPrinter.PrinterMode.ScreenResolution)
        dlg = QPrintPreviewDialog(printer, self)
        def _render(p):
            doc = QTextDocument()
            doc.setHtml(self._html_tabelle("Raumplan", headers, rows))
            getattr(doc, 'print')(p)
        dlg.paintRequested.connect(_render)
        dlg.exec()

    def _delete_angebot(self):
        nummern = self.angebots_table.get_selected_nummern()
        if not nummern:
            QMessageBox.information(self, "Hinweis", "Bitte eine oder mehrere Zeilen auswählen.")
            return
        if len(nummern) == 1:
            _pl_del, _, _plP_del = self._get_pl()
            frage = f"{_pl_del} Nr. {nummern[0]} wirklich löschen?"
        else:
            liste = ", ".join(str(n) for n in nummern)
            frage = f"{len(nummern)} {_plP_del} wirklich löschen? (Nr. {liste})"
        antwort = QMessageBox.question(
            self, "Löschen?", frage,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if antwort == QMessageBox.StandardButton.Yes:
            for nr in nummern:
                db.delete_projekt(nr)
            self._refresh_angebote()

    # ── Import ───────────────────────────────────────────────────────────────

    def _import(self, modus: str):
        dlg = ImportDialog(modus, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._refresh_all()

    # ── Einteilung ───────────────────────────────────────────────────────────

    def _auto_einteilen(self, algo: str):
        schueler = db.get_all_teilnehmer()
        projekte = db.get_all_projekte()
        if not schueler:
            QMessageBox.warning(self, "Fehler", "Keine Teilnehmer/innen vorhanden.")
            return
        if not projekte:
            QMessageBox.warning(self, "Fehler", f"Keine {self._get_pl()[2]} vorhanden.")
            return

        algo_namen = {
            "A": "A (Wunsch-Priorität)",
            "B": "B (Mindest-TN-Priorität)",
            "C": "C (Alle-Versorgen-Priorität)",
        }
        algo_name = algo_namen.get(algo, algo)
        dlg = AnzahlWuenscheDialog(algo_name, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        max_wuensche = dlg.get_max_wuensche()

        anzahl_fest = sum(1 for s in schueler if s["fest_zugewiesen"] and s["projekt"] != 0)
        hinweis_manuell = (
            f"\n\n{anzahl_fest} fest zugewiesene Teilnehmer/innen bleiben "
            f"dabei unverändert erhalten."
            if anzahl_fest else ""
        )
        hinweis_wuensche = (
            f"\n\nEs werden nur die ersten {max_wuensche} Wünsche berücksichtigt."
            if max_wuensche < 5 else ""
        )

        antwort = QMessageBox.question(
            self, "Automatisch zuweisen",
            f"Algorithmus {algo_name} starten?\n"
            "Bestehende automatische Zuteilungen werden überschrieben."
            + hinweis_manuell + hinweis_wuensche,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if antwort != QMessageBox.StandardButton.Yes:
            return

        self.statusBar().showMessage("Einteilung läuft")
        QApplication.processEvents()

        # Nur automatische Zuteilungen zurücksetzen, manuelle bleiben erhalten
        db.reset_all_zuteilungen(nur_automatische=True)

        if algo == "A":
            ergebnis = alg.algorithmus_a(max_wuensche=max_wuensche)
        elif algo == "B":
            ergebnis = alg.algorithmus_b(max_wuensche=max_wuensche)
        else:
            ergebnis = alg.algorithmus_c(max_wuensche=max_wuensche)

        alg.apply_ergebnis(ergebnis)
        statistik = alg.get_statistik(ergebnis)

        self._refresh_teilnehmer()
        self.raumplan_table.refresh_aus_optionen()
        self.statistik_widget.refresh(statistik)
        self.tabs.setCurrentIndex(3)  # Statistik-Tab

        gesamt = statistik["gesamt"]
        wt = statistik["wunsch_treffer"]
        anzahl_nicht_zugeteilt = sum(1 for p_nr in ergebnis.values() if p_nr == 0)
        msg = (
            f"Einteilung abgeschlossen!\n\n"
            f"Teilnehmer/innen gesamt: {gesamt}\n"
            f"Wunsch 1: {wt.get(1,0)}\n"
            f"Wunsch 2: {wt.get(2,0)}\n"
            f"Wunsch 3: {wt.get(3,0)}\n"
            f"Wunsch 4: {wt.get(4,0)}\n"
            f"Wunsch 5: {wt.get(5,0)}\n"
            f"Kein Wunsch erfüllt: {wt.get(0,0)}"
            + (f"\nFest zugewiesen (unverändert): {anzahl_fest}" if anzahl_fest else "")
        )
        if anzahl_nicht_zugeteilt:
            _pl_algo, _, _plP_algo = self._get_pl()
            msg += (
                f"\n\n⚠ {anzahl_nicht_zugeteilt} Teilnehmer/innen konnten keinem "
                f"ihrer Wunsch{_plP_algo} zugeteilt werden (alle Wunsch{_plP_algo} "
                f"waren bereits voll). Diese Teilnehmer/innen wurden NICHT einem "
                f"nicht gewünschten {_pl_algo} zugeteilt, sondern bleiben ohne "
                f"{_pl_algo}, bis manuell nachgesteuert wird."
            )
            msgbox = QMessageBox(self)
            msgbox.setWindowTitle("Einteilung fertig")
            msgbox.setText(msg)
            btn_liste = msgbox.addButton("Liste anzeigen", QMessageBox.ButtonRole.ActionRole)
            msgbox.addButton(QMessageBox.StandardButton.Ok)
            msgbox.exec()
            if msgbox.clickedButton() == btn_liste:
                self._oeffne_projektteilnehmerliste(0)
        else:
            QMessageBox.information(self, "Einteilung fertig", msg)
        self.statusBar().showMessage("Automatische Zuweisung abgeschlossen.")

    def _reset_einteilung(self):
        schueler = db.get_all_teilnehmer()
        anzahl_fest = sum(1 for s in schueler if s["fest_zugewiesen"] and s["projekt"] != 0)

        if anzahl_fest:
            msgbox = QMessageBox(self)
            msgbox.setWindowTitle("Zuweisung aufheben")
            msgbox.setText(
                f"Es gibt {anzahl_fest} fest zugewiesene Teilnehmer/innen.\n\n"
                "Sollen auch diese zurückgesetzt werden?"
            )
            btn_alle = msgbox.addButton("Wirklich alle zurücksetzen", QMessageBox.ButtonRole.DestructiveRole)
            btn_nur_auto = msgbox.addButton("Nur automatische zurücksetzen", QMessageBox.ButtonRole.AcceptRole)
            btn_abbrechen = msgbox.addButton("Abbrechen", QMessageBox.ButtonRole.RejectRole)
            msgbox.exec()

            clicked = msgbox.clickedButton()
            if clicked == btn_abbrechen:
                return
            nur_automatische = (clicked == btn_nur_auto)
        else:
            antwort = QMessageBox.question(
                self, "Zuweisung aufheben",
                f"Alle {self._get_pl()[2]}-Zuteilungen zurücksetzen?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if antwort != QMessageBox.StandardButton.Yes:
                return
            nur_automatische = True

        db.reset_all_zuteilungen(nur_automatische=nur_automatische)
        self._refresh_all()
        self.statusBar().showMessage("Einteilung zurückgesetzt.")

    def _feste_zuweisung(self, schueler_id=None, nur_wunschprojekte: bool = False):
        """
        Weist einen Schüler manuell einem Projekt zu.
        Nur die vom Schüler gewählten Wunschprojekte werden angeboten,
        sortiert nach Wunschreihenfolge.

        nur_wunschprojekte=False (Standard, z. B. im Hauptfenster-Menü):
            zusätzlich steht über eine Trennlinie die komplette restliche
            Projektliste als Ausweichmöglichkeit zur Verfügung.
        nur_wunschprojekte=True (z. B. aus den Listenfenstern heraus):
            es werden ausschließlich die gewählten Wunschprojekte angeboten,
            damit die Auswahlliste kurz und übersichtlich bleibt. Hat der
            Schüler keinen Wunsch abgegeben, wird trotzdem auf die komplette
            Liste zurückgegriffen, da sonst keine Zuteilung möglich wäre.
        """
        # Wichtig: Wenn diese Methode direkt als Slot an ein Qt-Signal wie
        # QAction.triggered oder QPushButton.clicked angehängt wird, übergibt
        # Qt automatisch ein bool-Argument (z. B. False) als ersten
        # Positionsparameter -- das würde sonst fälschlich als
        # schueler_id=False ankommen ("False is not None" ist True!) und die
        # Funktion lautlos abbrechen lassen. Da bool in Python eine
        # Unterklasse von int ist, reicht eine reine "isinstance(..., int)"
        # NICHT aus -- bool muss explizit ausgeschlossen werden.
        if isinstance(schueler_id, bool) or not isinstance(schueler_id, int):
            schueler_id = None

        sid = schueler_id if schueler_id is not None else self.teilnehmer_table.get_selected_id()
        if sid is None:
            QMessageBox.information(
                self, "Hinweis",
                "Bitte zuerst eine/n Teilnehmer/in in der Tabelle auswählen."
            )
            return
        alle_projekte = db.get_all_projekte()
        if not alle_projekte:
            QMessageBox.warning(self, "Fehler", f"Keine {self._get_pl()[2]} vorhanden.")
            return

        schueler = next((s for s in db.get_all_teilnehmer() if s["id"] == sid), None)
        if schueler is None:
            return

        projekte_dict = {p["nummer"]: p for p in alle_projekte}
        wunsch_nrn = [w for w in [schueler["wunsch_1"], schueler["wunsch_2"],
                                   schueler["wunsch_3"], schueler["wunsch_4"],
                                   schueler["wunsch_5"]] if w != 0]

        projekt_optionen = []
        # Zuerst die gewählten Wünsche, in Wunschreihenfolge
        for rang, p_nr in enumerate(wunsch_nrn, start=1):
            p = projekte_dict.get(p_nr)
            name = p["projektname"] if p else f"(unbekannte/r {self._get_pl()[0]})"
            projekt_optionen.append((f"Wunsch {rang}: {p_nr} – {name}", p_nr))

        if not nur_wunschprojekte:
            # Trennlinie + restliche Projekte, falls die Person z. B. einen
            # nicht gewünschten Ausweichplatz braucht
            uebrige = [p for p in alle_projekte if p["nummer"] not in wunsch_nrn]
            if uebrige and wunsch_nrn:
                projekt_optionen.append((f"── Weitere {self._get_pl()[2]} (kein Wunsch) ──", None))
            for p in uebrige:
                projekt_optionen.append((f"{p['nummer']}: {p['projektname']}", p["nummer"]))

        if not wunsch_nrn:
            # Kein Wunsch vorhanden -> in jedem Fall alle Projekte anbieten,
            # da sonst keine Zuteilung möglich wäre
            projekt_optionen = [(f"{p['nummer']}: {p['projektname']}", p["nummer"])
                                for p in alle_projekte]

        # Immer am Ende: Zuteilung aufheben (Projekt 0)
        if projekt_optionen:
            projekt_optionen.append(("── ──", None))  # Trennlinie
        _pl_kein, _f_kein, _ = self._get_pl()
        projekt_optionen.append((f"0 – {_f_kein['kein']} {_pl_kein} (Zuweisung aufheben)", 0))

        dlg = ProjektZuweisungDialog(
            f"{schueler['nachname']}, {schueler['vorname']}",
            projekt_optionen, self
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        gewaehlte_nr = dlg.get_projekt_nummer()
        if gewaehlte_nr is None:
            return  # Trennlinie ausgewählt -- nichts tun

        db.set_angebot_for_teilnehmer(sid, gewaehlte_nr, manuell=(gewaehlte_nr != 0))
        self._refresh_teilnehmer()
        self.statistik_widget.refresh()

    def _feste_zuweisung_aufheben(self):
        ids = self.teilnehmer_table.get_selected_ids()
        if not ids:
            QMessageBox.information(self, "Hinweis", "Bitte eine oder mehrere Zeilen auswählen.")
            return
        for sid in ids:
            db.set_angebot_for_teilnehmer(sid, 0, manuell=False)
        self._refresh_teilnehmer()
        self.statistik_widget.refresh()

    def _alle_fixierungen_aufheben(self):
        alle = db.get_all_teilnehmer()
        fixed = [s for s in alle if s.get("fest_zugewiesen")]
        if not fixed:
            QMessageBox.information(self, "Hinweis",
                                    "Es gibt keine fest zugewiesenen Teilnehmer/innen.")
            return
        antwort = QMessageBox.question(
            self, "Alle fixen Zuweisungen löschen",
            f"Wirklich alle {len(fixed)} fixen Zuweisungen aufheben?\n"
            "Die Teilnehmer/innen werden beim nächsten Algorithmenlauf "
            "neu zugeteilt.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if antwort != QMessageBox.StandardButton.Yes:
            return
        for s in fixed:
            db.set_angebot_for_teilnehmer(s["id"], 0, manuell=False)
        self._refresh_teilnehmer()
        self.statistik_widget.refresh()

    # ── Export ───────────────────────────────────────────────────────────────

    def _export(self):
        dlg = ExportDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        sort_mode = dlg.get_sort_mode()
        formate = dlg.get_formate()
        mit_wuenschen = dlg.get_mit_wuenschen()
        delimiter = dlg.get_delimiter()

        if not formate:
            QMessageBox.warning(self, "Fehler", "Bitte mindestens ein Exportformat wählen.")
            return

        # Jahreszahl abfragen
        jahr, ok = QInputDialog.getText(
            self, "Jahreszahl", "Jahreszahl für die Überschrift (z. B. 2025):"
        )
        if not ok:
            return

        # Titel je nach Sortierung
        titel_map = {
            "klasse_name_projekt": "Einteilung nach Klassen",
            "klasse_projekt":       "Einteilung nach Klassen",
            "projekt_klasse_name":  "Einteilung nach Projekten",
        }
        titel = titel_map.get(sort_mode, "Einteilung")

        export_dir = QFileDialog.getExistingDirectory(
            self, "Exportordner wählen", self._last_export_dir
        )
        if not export_dir:
            return
        self._last_export_dir = export_dir

        errors = []
        for fmt in formate:
            try:
                fname = f"projekttage_{sort_mode}.{fmt}"
                fpath = os.path.join(export_dir, fname)
                if fmt == "txt":
                    headers, rows = ie.get_export_data(sort_mode, mit_wuenschen)
                    ie.export_txt(fpath, rows, headers, delimiter)
                elif fmt == "xlsx":
                    ie.export_excel(fpath, sort_mode, titel, jahr, mit_wuenschen)
                elif fmt == "html":
                    ie.export_html(fpath, sort_mode, titel, jahr, mit_wuenschen)
            except Exception as e:
                errors.append(f"{fmt}: {e}")

        if errors:
            QMessageBox.warning(self, "Exportfehler", "\n".join(errors))
        else:
            QMessageBox.information(
                self, "Export erfolgreich",
                f"Dateien gespeichert in:\n{export_dir}"
            )

    def _export_gesamtliste(self, modus: str):
        from dialoge import GesamtExportDialog
        dlg = GesamtExportDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        fmt          = dlg.get_format()
        kopfzeile    = dlg.get_kopfzeile()
        seitenumbr   = dlg.get_seitenumbrueche()
        datum_fuss   = dlg.get_datum_fusszeile()
        separat      = dlg.get_separat()
        ausgabe_modus = dlg.get_ausgabe_modus()  # 'zip' oder 'ordner'

        # Wünsche werden immer mitgeholt -- ob sie in der Ausgabe erscheinen,
        # entscheidet die anschließende Feldauswahl (granularer als ein
        # pauschaler Ein/Aus-Haken, u. a. einzelne Wunschränge abwählbar).
        if modus == "klassen":
            gruppen = ie.get_gesamtliste_nach_klassen(mit_wuenschen=True)
            vorgabe = "Gesamtliste_nach_Gruppen"
        else:
            gruppen = ie.get_gesamtliste_nach_projekten(mit_wuenschen=True)
            vorgabe = f"Gesamtliste_nach_{self._get_pl()[2]}"

        # Feldauswahl: einheitlich auf alle Gruppen anwenden (gleiche Spalten je Gruppe)
        if gruppen:
            kept = self._spaltenauswahl(gruppen[0][1])
            if kept is None:
                return
            gruppen = [
                (name, *ie.filter_spalten(headers, rows, kept))
                for (name, headers, rows) in gruppen
            ]

        if separat:
            if ausgabe_modus == "zip":
                pfad, _ = self._save_dialog(
                    "Gesamtliste exportieren (ZIP)", vorgabe + ".zip",
                    "ZIP-Archiv (*.zip)"
                )
                if not pfad:
                    return
                if not pfad.lower().endswith(".zip"):
                    pfad += ".zip"
                try:
                    ie.export_gruppen_separat(pfad, fmt, gruppen,
                                              kopfzeile, datum_fuss, als_zip=True)
                    QMessageBox.information(self, "Export erfolgreich",
                                            f"ZIP gespeichert:\n{pfad}")
                except Exception as e:
                    QMessageBox.critical(self, "Fehler beim Export", str(e))
            else:
                ordner = self._dir_dialog("Zielordner für Einzeldateien wählen")
                if not ordner:
                    return
                try:
                    ie.export_gruppen_separat(ordner, fmt, gruppen,
                                              kopfzeile, datum_fuss, als_zip=False)
                    QMessageBox.information(self, "Export erfolgreich",
                                            f"Dateien gespeichert in:\n{ordner}")
                except Exception as e:
                    QMessageBox.critical(self, "Fehler beim Export", str(e))
        else:
            ext = {"xlsx": ".xlsx", "ods": ".ods",
                   "csv": ".csv", "pdf": ".pdf"}[fmt]
            pfad, _ = self._save_dialog(
                "Gesamtliste exportieren", vorgabe + ext,
                f"{fmt.upper()}-Datei (*{ext})"
            )
            if not pfad:
                return
            if not pfad.lower().endswith(ext):
                pfad += ext
            try:
                ie.export_gruppen(pfad, fmt, gruppen, kopfzeile, seitenumbr, datum_fuss)
                QMessageBox.information(self, "Export erfolgreich",
                                        f"Datei gespeichert:\n{pfad}")
            except Exception as e:
                QMessageBox.critical(self, "Fehler beim Export", str(e))

    def _export_gesamtliste_nach_klassen(self):
        self._export_gesamtliste("klassen")

    def _export_gesamtliste_nach_projekten(self):
        self._export_gesamtliste("projekte")

    # ── Suche/Listen-Fenster ─────────────────────────────────────────────────

    def _oeffne_listenfenster(self, titel: str, headers: list, rows: list,
                              row_ids: list = None, zuteilen_callback=None,
                              wunsch_bearbeiten_callback=None, details_callback=None):
        """Öffnet ein neues, nicht-modales Listenfenster und hält die Referenz."""
        fenster = ListenFenster(titel, headers, rows, self,
                                row_ids=row_ids, zuteilen_callback=zuteilen_callback,
                                wunsch_bearbeiten_callback=wunsch_bearbeiten_callback,
                                details_callback=details_callback)
        # Geschlossene Fenster aus der Referenzliste entfernen, sonst wächst sie
        fenster.finished.connect(lambda: self._offene_listenfenster.remove(fenster)
                                  if fenster in self._offene_listenfenster else None)
        self._offene_listenfenster.append(fenster)
        fenster.show()
        fenster.raise_()
        fenster.activateWindow()
        return fenster

    def _zeige_wunschauswertung(self):
        projekte = db.get_all_projekte()
        if not projekte:
            QMessageBox.warning(self, "Fehler", f"Keine {self._get_pl()[2]} vorhanden.")
            return
        dlg = WunschauswertungDialog(projekte, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        projekt_nr = dlg.get_projekt_nummer()
        wunsch_rang = dlg.get_wunsch_rang()
        self._oeffne_wunschauswertung(projekt_nr, wunsch_rang)

    def _oeffne_wunschauswertung_fuer_projekt(self, projekt_nr: int):
        """Öffnet die Wunschauswertung direkt für ein konkretes Projekt,
        ohne vorherigen Auswahldialog (z. B. per Button aus der
        Statistik-Tabelle). Gibt das geöffnete Fenster zurück (oder None,
        falls keine Treffer)."""
        return self._oeffne_wunschauswertung(projekt_nr, None)

    def _oeffne_wunschauswertung(self, projekt_nr, wunsch_rang):
        """Gibt das geöffnete ListenFenster zurück (oder None, falls keine
        Treffer gefunden wurden)."""
        projekte = db.get_all_projekte()
        headers, rows, ids = la.get_wunschauswertung(projekt_nr, wunsch_rang)

        titel_teile = ["Wunschauswertung"]
        if wunsch_rang == 0:
            titel_teile.append("Teilnehmer/innen ohne Wunschabgabe")
        else:
            if projekt_nr == 0:
                titel_teile.append("Wunschrang nicht ausgefüllt")
            elif projekt_nr is not None:
                p = next((p for p in projekte if p["nummer"] == projekt_nr), None)
                if p:
                    titel_teile.append(f"{self._get_pl()[0]} {p['nummer']}: {p['projektname']}")
            if wunsch_rang is not None:
                titel_teile.append(f"Wunsch {wunsch_rang}")
        titel = " – ".join(titel_teile)

        if not rows:
            QMessageBox.information(self, "Keine Treffer", "Keine passenden Einträge gefunden.")
            return None

        fenster_ref = {}

        def zuteilen(schueler_id):
            self._feste_zuweisung(schueler_id, nur_wunschprojekte=True)
            h, r, i = la.get_wunschauswertung(projekt_nr, wunsch_rang)
            fenster_ref["f"].aktualisiere_daten(h, r, i)

        def details(projekt_nr_arg=projekt_nr):
            if projekt_nr_arg and projekt_nr_arg != 0:
                self._zeige_projektdetails(projekt_nr_arg)

        fenster = self._oeffne_listenfenster(
            titel, headers, rows, row_ids=ids,
            zuteilen_callback=zuteilen,
            details_callback=details if (projekt_nr and projekt_nr != 0) else None
        )
        fenster_ref["f"] = fenster
        return fenster

    def _zeige_projektteilnehmerliste(self):
        projekte = db.get_all_projekte()
        if not projekte:
            QMessageBox.warning(self, "Fehler", f"Keine {self._get_pl()[2]} vorhanden.")
            return
        dlg = ProjektAuswahlDialog(projekte, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        projekt_nr = dlg.get_projekt_nummer()
        self._oeffne_projektteilnehmerliste(projekt_nr)

    def _oeffne_projektteilnehmerliste(self, projekt_nr: int):
        """Öffnet die Teilnehmerliste für ein konkretes Projekt direkt,
        ohne vorherigen Auswahldialog (z. B. per Doppelklick aus der
        Statistik-Tabelle). projekt_nr=0 zeigt alle Teilnehmer/innen ohne
        Projektzuteilung."""
        headers, rows, ids, p_info = la.get_projektteilnehmerliste(projekt_nr)

        pl, _, _ = self._get_pl()

        if projekt_nr == 0:
            titel = f"Teilnehmer/innen ohne {pl} ({len(rows)})"
        else:
            titel = f"Teilnehmerliste – {pl} {projekt_nr}"
            if p_info:
                titel += f": {p_info['projektname']}"
                tn_info = f" ({len(rows)} TN, Plätze: {p_info['tnmin']}–{p_info['tnmax']})"
                titel += tn_info

        if not rows:
            _pl_tn, _f_tn, _ = self._get_pl()
            msg = (f"Aktuell sind alle Teilnehmer/innen einem {_pl_tn} zugeteilt."
                  if projekt_nr == 0 else
                  f"{_f_tn['nom'].capitalize()} hat aktuell keine Teilnehmer/innen zugeteilt.")
            QMessageBox.information(self, "Keine Treffer", msg)
            return

        fenster_ref = {}

        def zuteilen(schueler_id):
            self._feste_zuweisung(schueler_id, nur_wunschprojekte=True)
            h, r, i, p = la.get_projektteilnehmerliste(projekt_nr)
            fenster_ref["f"].aktualisiere_daten(h, r, i)

        def details_tl(pnr=projekt_nr):
            if pnr and pnr != 0:
                self._zeige_projektdetails(pnr)

        fenster = self._oeffne_listenfenster(
            titel, headers, rows, row_ids=ids,
            zuteilen_callback=zuteilen,
            details_callback=details_tl if (projekt_nr and projekt_nr != 0) else None
        )
        fenster_ref["f"] = fenster
        return fenster

    def _zeige_projektdetails(self, projekt_nr: int):
        """Zeigt ein Popup mit Detailstatistiken zu einem einzelnen Projekt
        (wie oft gewünscht, mit welchem Wunschrang zugeteilt usw.)."""
        details = la.get_projektdetails(projekt_nr)
        if details is None:
            QMessageBox.warning(self, "Fehler", f"{self._get_pl()[0]} nicht gefunden.")
            return

        dlg = ProjektDetailsDialog(details, self)

        def auf_wunschauswertung(nr):
            dlg.hide()
            fenster = self._oeffne_wunschauswertung_fuer_projekt(nr)
            if fenster is not None:
                fenster.finished.connect(lambda: (dlg.show(), dlg.raise_(),
                                                  dlg.activateWindow()))

        def auf_wunschauswertung_rang(nr, rang):
            dlg.hide()
            fenster = self._oeffne_wunschauswertung(nr, rang)
            if fenster is not None:
                fenster.finished.connect(lambda: (dlg.show(), dlg.raise_(),
                                                  dlg.activateWindow()))

        def auf_teilnehmerliste(nr):
            dlg.hide()
            fenster = self._oeffne_projektteilnehmerliste(nr)
            if fenster is not None:
                fenster.finished.connect(lambda: (dlg.show(), dlg.raise_(),
                                                  dlg.activateWindow()))

        dlg.wunschauswertung_angefordert.connect(auf_wunschauswertung)
        dlg.wunschauswertung_rang_angefordert.connect(auf_wunschauswertung_rang)
        dlg.teilnehmerliste_angefordert.connect(auf_teilnehmerliste)
        dlg.projekt_wechsel_angefordert.connect(self._zeige_projektdetails)
        # Referenz halten, sonst wird der Dialog vom Garbage Collector
        # entfernt, sobald diese Methode endet (show() ist nicht-blockierend)
        self._offene_listenfenster.append(dlg)
        dlg.finished.connect(lambda: self._offene_listenfenster.remove(dlg)
                             if dlg in self._offene_listenfenster else None)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _zeige_klassenliste(self):
        klassen = la.get_verfuegbare_klassen()
        if not klassen:
            QMessageBox.warning(self, "Fehler", "Keine Teilnehmer/innen vorhanden.")
            return
        dlg = KlassenAuswahlDialog(klassen, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        stufe, stufenzusatz = dlg.get_klasse()
        headers, rows, ids = la.get_klassenliste(stufe, stufenzusatz if stufenzusatz != "-" else None)

        konfig = db.get_feldkonfig()
        sl = konfig.get("stufe_label", "Gruppenbereich")
        klassen_label = (f"{stufe}{stufenzusatz}" if stufenzusatz != "-"
                         else f"{sl} {stufe}")
        titel = f"Gruppenliste mit Zuteilung – {klassen_label}"

        if not rows:
            QMessageBox.information(self, "Keine Treffer", "Keine Teilnehmer/innen in dieser Gruppe gefunden.")
            return

        fenster_ref = {}

        def zuteilen(schueler_id):
            self._feste_zuweisung(schueler_id, nur_wunschprojekte=True)
            h, r, i = la.get_klassenliste(stufe, stufenzusatz if stufenzusatz != "-" else None)
            fenster_ref["f"].aktualisiere_daten(h, r, i)

        fenster = self._oeffne_listenfenster(
            titel, headers, rows, row_ids=ids,
            zuteilen_callback=zuteilen
        )
        fenster_ref["f"] = fenster

    def _zeige_qualitaetspruefung(self):
        """Öffnet die Qualitätsprüfung Wunscheingaben (nicht-modal)."""
        from dialoge import QualitaetspruefungDialog
        if not hasattr(self, '_qualitaet_fenster') or \
           not self._qualitaet_fenster.isVisible():
            self._qualitaet_fenster = QualitaetspruefungDialog(self)
            self._qualitaet_fenster.person_angefordert.connect(
                self._markiere_teilnehmer_in_hauptfenster
            )
        self._qualitaet_fenster.show()
        self._qualitaet_fenster.raise_()
        self._qualitaet_fenster.activateWindow()

    def _markiere_teilnehmer_in_hauptfenster(self, tid: int):
        """Springt zu einem Teilnehmer im Hauptfenster (aus Qualitätsprüfung)."""
        self.tabs.setCurrentIndex(0)
        self.raise_()
        self.activateWindow()
        for row in range(self.teilnehmer_table.rowCount()):
            id_item = self.teilnehmer_table.item(row, 0)
            if id_item and int(id_item.text()) == tid:
                self.teilnehmer_table.selectRow(row)
                self.teilnehmer_table.scrollToItem(
                    self.teilnehmer_table.item(row, 1),
                    QAbstractItemView.ScrollHint.PositionAtCenter
                )
                break

    def _zeige_unzulaessige_wuensche(self):
        """Prüft die gesamte Schülerliste auf Wünsche, die nicht zur
        Jahrgangsstufen-Zulassung des jeweiligen Projekts passen."""
        if not val_mod.hat_klassenstufenbegrenzungen():
            QMessageBox.information(
                self, "Keine Beschränkungen",
                f"Keines der vorhandenen {self._get_pl()[2]} hat eine "
                "Jahrgangsstufen-Beschränkung -- eine Prüfung ist daher "
                "nicht erforderlich."
            )
            return

        headers, rows, ids = val_mod.get_schueler_mit_unzulaessigen_wuenschen()
        if not rows:
            QMessageBox.information(
                self, "Keine Treffer",
                f"Alle eingetragenen Wünsche entsprechen den "
                f"Zulassungsvorgaben der {self._get_pl()[2]}."
            )
            return
        self._oeffne_unzulaessige_wuensche_liste(headers, rows, ids)

    def _oeffne_unzulaessige_wuensche_liste(self, headers, rows, ids):
        """Öffnet ein Listenfenster mit Schülern, deren Wünsche nicht zur
        Jahrgangsstufen-Zulassung passen (gemeinsame Anzeige-Logik für
        Menüpunkt und Import-Prüfung). Bietet zusätzlich die Möglichkeit,
        einzelne Wünsche per Doppelklick direkt zu korrigieren."""
        titel = f"Teilnehmer/innen mit unzulässigen Wünschen ({len(rows)})"

        fenster_ref = {}

        def aktualisieren():
            h, r, i = val_mod.get_schueler_mit_unzulaessigen_wuenschen(nur_ids=ids)
            fenster_ref["f"].aktualisiere_daten(h, r, i)
            if not r:
                fenster_ref["f"].close()

        def zuteilen(schueler_id):
            self._feste_zuweisung(schueler_id, nur_wunschprojekte=True)
            aktualisieren()

        def wunsch_bearbeiten(schueler_id, wunsch_rang):
            self._wunsch_bearbeiten(schueler_id, wunsch_rang)
            aktualisieren()

        fenster = self._oeffne_listenfenster(
            titel, headers, rows, row_ids=ids, zuteilen_callback=zuteilen,
            wunsch_bearbeiten_callback=wunsch_bearbeiten
        )
        fenster_ref["f"] = fenster
        return fenster

    def _wunsch_bearbeiten(self, schueler_id: int, wunsch_rang: int):
        """
        Öffnet einen Auswahldialog, um EINEN bestimmten Wunschrang
        (wunsch_1..wunsch_5) eines Schülers direkt zu setzen. Es werden
        nur Projekte angeboten, die für die Jahrgangsstufe der Person
        zulässig sind -- ideal, um nach einer Validierungsprüfung einen
        unzulässigen Wunsch gezielt zu korrigieren.
        """
        schueler = next((s for s in db.get_all_teilnehmer() if s["id"] == schueler_id), None)
        if schueler is None:
            return
        alle_projekte = db.get_all_projekte()
        if not alle_projekte:
            QMessageBox.warning(self, "Fehler", f"Keine {self._get_pl()[2]} vorhanden.")
            return

        zulaessige = [p for p in alle_projekte
                     if val_mod.projekt_erlaubt_fuer_jgst(p, schueler["stufe"])]
        if not zulaessige:
            QMessageBox.warning(
                self, f"Keine zulässigen {self._get_pl()[2]}",
                f"Für die Jahrgangsstufe {schueler['stufe']} ist aktuell "
                f"kein einziges {self._get_pl()[0]} zugelassen."
            )
            return

        projekt_optionen = [(f"{p['nummer']}: {p['projektname']}", p["nummer"])
                            for p in zulaessige]

        dlg = ProjektZuweisungDialog(
            f"{schueler['nachname']}, {schueler['vorname']} – Wunsch {wunsch_rang}",
            projekt_optionen, self
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        gewaehlte_nr = dlg.get_projekt_nummer()
        if gewaehlte_nr is None:
            return

        feld = f"wunsch_{wunsch_rang}"
        data = {k: schueler[k] for k in
               ["nachname", "vorname", "stufe", "stufenzusatz", "geschlecht",
                "wunsch_1", "wunsch_2", "wunsch_3", "wunsch_4", "wunsch_5", "projekt"]}
        data[feld] = gewaehlte_nr
        db.update_teilnehmer(schueler_id, data)
        self._refresh_teilnehmer()

    # ── Suche ────────────────────────────────────────────────────────────────

    def _focus_search(self):
        self.search_edit.setFocus()
        self.search_edit.selectAll()
        self.tabs.setCurrentIndex(0)

    def _on_search_changed(self, text: str):
        self._search_term = text
        self._search_results = []
        self._search_idx = 0
        if not text:
            self.lbl_search_info.setText("")
            self.teilnehmer_table.clearSelection()
            return
        self._do_search()

    def _do_search(self):
        term = self._search_term.lower()
        results = []
        for row in range(self.teilnehmer_table.rowCount()):
            for col in range(1, self.teilnehmer_table.columnCount()):
                item = self.teilnehmer_table.item(row, col)
                if item and term in item.text().lower():
                    results.append(row)
                    break
        self._search_results = results
        if results:
            self._highlight_search(self._search_idx % len(results))
        else:
            self.lbl_search_info.setText("Nicht gefunden.")
            self.teilnehmer_table.clearSelection()

    def _highlight_search(self, idx: int):
        if not self._search_results:
            return
        row = self._search_results[idx]
        self.teilnehmer_table.selectRow(row)
        self.teilnehmer_table.scrollToItem(
            self.teilnehmer_table.item(row, 1),
            QAbstractItemView.ScrollHint.PositionAtCenter
        )
        total = len(self._search_results)
        self.lbl_search_info.setText(f"{idx+1}/{total}")

    def _search_forward(self):
        if not self._search_results:
            self._do_search()
            return
        self._search_idx = (self._search_idx + 1) % len(self._search_results)
        self._highlight_search(self._search_idx)

    def _search_backward(self):
        if not self._search_results:
            self._do_search()
            return
        self._search_idx = (self._search_idx - 1) % len(self._search_results)
        self._highlight_search(self._search_idx)
