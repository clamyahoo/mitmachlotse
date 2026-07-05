"""
Import-Dialoge: CSV, Excel, Spaltenzuordnung.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QFileDialog, QTableWidget, QTableWidgetItem,
    QGroupBox, QRadioButton, QButtonGroup, QCheckBox,
    QDialogButtonBox, QMessageBox, QScrollArea, QWidget, QSizePolicy,
    QHeaderView, QAbstractItemView, QLineEdit, QFormLayout, QStackedWidget,
    QListWidget, QListWidgetItem, QSpinBox, QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPalette, QColor
import os
import re
import importexport as ie
import database as db


class FixedComboBox(QComboBox):
    """
    QComboBox mit zuverlässiger schwarz/weiß-Selektion im Dropdown.
    Setzt die Palette direkt beim Öffnen des Popups – nach dem
    Fusion-Theme-Rendering – damit GTK/Fusion die Farben nicht
    mehr überschreiben können.
    """
    def showPopup(self):
        view = self.view()
        pal = view.palette()
        for grp in (QPalette.ColorGroup.Active,
                    QPalette.ColorGroup.Inactive,
                    QPalette.ColorGroup.Normal):
            pal.setColor(grp, QPalette.ColorRole.Base,
                         QColor("#ffffff"))
            pal.setColor(grp, QPalette.ColorRole.Text,
                         QColor("#000000"))
            pal.setColor(grp, QPalette.ColorRole.Highlight,
                         QColor("#000000"))
            pal.setColor(grp, QPalette.ColorRole.HighlightedText,
                         QColor("#ffffff"))
        view.setPalette(pal)
        view.setAutoFillBackground(True)
        super().showPopup()


class TrennzeichenWidget(QGroupBox):
    _OPTIONEN = [
        ("Semikolon  ( ; )", ";"),
        ("Komma  ( , )",     ","),
        ("Tabulator",        "\t"),
    ]

    def __init__(self, parent=None):
        super().__init__("Trennzeichen", parent)
        layout = QHBoxLayout(self)
        layout.addWidget(QLabel("Feldtrennzeichen:"))
        self.combo = FixedComboBox()
        for label, val in self._OPTIONEN:
            self.combo.addItem(label, val)
        self.combo.setCurrentIndex(0)   # Standard: Semikolon
        layout.addWidget(self.combo)
        layout.addStretch()

    def get_delimiter(self) -> str:
        return self.combo.currentData()

    def set_delimiter(self, delim: str):
        for i, (_, val) in enumerate(self._OPTIONEN):
            if val == delim:
                self.combo.setCurrentIndex(i)
                return


class PlanungsmappeEinrichtenDialog(QDialog):
    """
    Erscheint beim Erstellen einer neuen leeren Planungsmappe.
    Erlaubt die Konfiguration aller Feldbezeichnungen und optionalen Felder.
    Kann auch als reiner Bearbeitungsdialog (ohne 'Vorlage laden') verwendet werden.
    """

    STUFE_VORSCHLAEGE        = ["Gruppenbereich", "Jgst.", "Jahrgang", "Klasse",
                                 "Alter", "Semester", "Kurs", "Benutzerdefiniert"]
    STUFENZUSATZ_VORSCHLAEGE = ["Gruppenzusatz", "Klassenzusatz", "Untergruppe",
                                 "Abteilung", "Benutzerdefiniert"]
    PROJEKT_VORSCHLAEGE      = ["Projekt", "Option", "Kurs", "Workshop",
                                 "Veranstaltung", "Angebot", "Aktion",
                                 "Benutzerdefiniert"]

    def __init__(self, parent=None, vorlage_laden: bool = True,
                 aktuell: dict = None):
        """
        vorlage_laden: True = zeigt 'Vorlage laden …'-Button (Neuanlage)
        aktuell:       Vorausfüllung mit bestehender Konfig (None = Defaults)
        """
        super().__init__(parent)
        self.setWindowTitle(
            "Neue Planungsmappe einrichten"
            if vorlage_laden else "Spaltenbezeichnungen anpassen"
        )
        self.setMinimumWidth(460)
        konfig = aktuell or dict(db.FELDKONFIG_DEFAULTS)
        # Ursprünglicher Wert vor dieser Bearbeitung — wird beim Speichern
        # mit dem neuen Wert verglichen, um eine Deaktivierung der
        # Leitungsspalte zu erkennen (siehe _on_ok).
        self._leitung_urspruenglich = (aktuell or {}).get("leitung_label", "").strip()
        self._leitung_wird_geloescht = False

        layout = QVBoxLayout(self)

        if vorlage_laden:
            hinweis = QLabel(
                "<b>Neue Planungsmappe</b><br>"
                "Passen Sie die Bezeichnungen an Ihren Anwendungsfall an.<br>"
                "Sie können alles auch später unter "
                "<i>Datei → Spaltenbezeichnungen anpassen …</i> ändern."
            )
            hinweis.setWordWrap(True)
            layout.addWidget(hinweis)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # ── Hauptbezeichnung (Projekt / Kurs /) ──
        self._cb_projekt = self._make_combo(
            self.PROJEKT_VORSCHLAEGE, konfig.get("projekt_label", "Projekt")
        )
        self._edit_projekt = QLineEdit()
        self._edit_projekt.setPlaceholderText("Benutzerdefinierte Bezeichnung")
        self._edit_projekt.hide()
        self._cb_projekt.currentTextChanged.connect(
            lambda t: self._edit_projekt.show()
            if t == "Benutzerdefiniert" else self._edit_projekt.hide()
        )
        p_col = QVBoxLayout()
        p_col.addWidget(self._cb_projekt)
        p_col.addWidget(self._edit_projekt)
        form.addRow("Bezeichnung für eine Option:", p_col)

        # ── Stufe ──
        self._cb_stufe = self._make_combo(
            self.STUFE_VORSCHLAEGE, konfig.get("stufe_label", "Stufe")
        )
        self._edit_stufe = QLineEdit()
        self._edit_stufe.setPlaceholderText("Benutzerdefinierte Bezeichnung")
        self._edit_stufe.hide()
        self._cb_stufe.currentTextChanged.connect(
            lambda t: self._edit_stufe.show()
            if t == "Benutzerdefiniert" else self._edit_stufe.hide()
        )
        s_col = QVBoxLayout()
        s_col.addWidget(self._cb_stufe)
        s_col.addWidget(self._edit_stufe)
        form.addRow("Gruppenbereich-Bezeichnung:", s_col)

        # ── Stufenzusatz ──
        self._cb_zusatz = self._make_combo(
            self.STUFENZUSATZ_VORSCHLAEGE, konfig.get("stufenzusatz_label", "Stufenzusatz")
        )
        self._edit_zusatz = QLineEdit()
        self._edit_zusatz.setPlaceholderText("Benutzerdefinierte Bezeichnung")
        self._edit_zusatz.hide()
        self._cb_zusatz.currentTextChanged.connect(
            lambda t: self._edit_zusatz.show()
            if t == "Benutzerdefiniert" else self._edit_zusatz.hide()
        )
        z_col = QVBoxLayout()
        z_col.addWidget(self._cb_zusatz)
        z_col.addWidget(self._edit_zusatz)
        form.addRow("Gruppenzusatz-Bezeichnung:", z_col)

        layout.addLayout(form)

        # ── Optionale Zusatzfelder Teilnehmer/innen ──
        tn_group = QGroupBox(
            "Optionale Zusatzfelder – Teilnehmer/innen "
            "(leer lassen = ausgeblendet)"
        )
        tn_layout = QFormLayout(tn_group)
        tn_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._extras = []
        for i in range(1, 4):
            edit = QLineEdit()
            edit.setPlaceholderText("(kein Feld)")
            edit.setText(konfig.get(f"extra_{i}_label", ""))
            tn_layout.addRow(f"Zusatzfeld TN {i}:", edit)
            self._extras.append(edit)
        layout.addWidget(tn_group)

        # ── Veranstaltungsleitung + Zusatzfelder Optionen ──
        opt_group = QGroupBox(
            "Optionale Felder – Optionen / Angebote "
            "(leer lassen = ausgeblendet)"
        )
        opt_layout = QFormLayout(opt_group)
        opt_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._leitung_edit = QLineEdit()
        self._leitung_edit.setText(
            konfig.get("leitung_label", "Veranstaltungsleitung"))
        self._leitung_edit.setPlaceholderText("(leer = Spalte ausblenden)")
        opt_layout.addRow("Bezeichnung Leitung / Ansprechperson:", self._leitung_edit)
        self._projekt_extras = []
        for i in range(1, 4):
            edit = QLineEdit()
            edit.setPlaceholderText("(kein Feld)")
            edit.setText(konfig.get(f"projekt_extra_{i}_label", ""))
            opt_layout.addRow(f"Zusatzfeld Option {i}:", edit)
            self._projekt_extras.append(edit)
        layout.addWidget(opt_group)

        layout.addWidget(opt_group)

        # ── Anzahl Wunschränge ──
        wunsch_group = QGroupBox("Wunschränge")
        wunsch_layout = QFormLayout(wunsch_group)
        wunsch_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._spin_max_wuensche = QSpinBox()
        self._spin_max_wuensche.setRange(1, 5)
        self._spin_max_wuensche.setValue(int(konfig.get("max_wuensche", 5)))
        self._spin_max_wuensche.setToolTip(
            "Wie viele Wunschränge sollen Teilnehmer/innen angeben?\n"
            "Nur die angegebene Anzahl wird in der Tabelle angezeigt\n"
            "und vom Algorithmus berücksichtigt.\n"
            "Die Qualitätsprüfung bewertet Einträge entsprechend."
        )
        wunsch_layout.addRow("Anzahl Wunschränge (1–5):",
                             self._spin_max_wuensche)
        layout.addWidget(wunsch_group)

        # ── Buttons ──
        btn_row = QHBoxLayout()
        btn_neutral = QPushButton("Neutrale Bezeichnungen")
        btn_neutral.setToolTip(
            "Setzt alle Felder auf die neutralen Standardbezeichnungen\n"
            "(Stufe, Stufenzusatz, Projekt) – keine optionalen Felder."
        )
        btn_neutral.clicked.connect(self._set_neutral)
        btn_row.addWidget(btn_neutral)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(self._on_ok)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    # ── Hilfsmethoden ────────────────────────────────────────────────────────

    @staticmethod
    def _make_combo(optionen: list, aktuell: str) -> FixedComboBox:
        cb = FixedComboBox()
        cb.addItems(optionen)
        idx = next((i for i, o in enumerate(optionen)
                    if o != "Benutzerdefiniert" and o == aktuell), None)
        if idx is not None:
            cb.setCurrentIndex(idx)
        else:
            cb.addItem(aktuell)
            cb.setCurrentIndex(cb.count() - 1)
        return cb

    def _get_combo_wert(self, combo: QComboBox, edit: QLineEdit) -> str:
        if combo.currentText() == "Benutzerdefiniert":
            return edit.text().strip() or combo.currentText()
        return combo.currentText()

    def _set_neutral(self):
        defaults = db.FELDKONFIG_DEFAULTS
        self._cb_stufe.setCurrentText("Benutzerdefiniert")
        self._edit_stufe.setText(defaults["stufe_label"])
        self._cb_stufe.setCurrentText(defaults["stufe_label"])
        self._cb_zusatz.setCurrentText(defaults["stufenzusatz_label"])
        self._cb_projekt.setCurrentText(defaults["projekt_label"])
        for edit in self._extras:
            edit.clear()

    def _on_ok(self):
        projekt = self._get_combo_wert(self._cb_projekt, self._edit_projekt)
        stufe   = self._get_combo_wert(self._cb_stufe,   self._edit_stufe)
        zusatz  = self._get_combo_wert(self._cb_zusatz,  self._edit_zusatz)
        if not projekt or not stufe or not zusatz:
            QMessageBox.warning(
                self, "Pflichtfelder fehlen",
                "Bitte alle drei Hauptbezeichnungen ausfüllen."
            )
            return

        neue_leitung = self._leitung_edit.text().strip()
        if self._leitung_urspruenglich and not neue_leitung:
            antwort = QMessageBox.question(
                self, "Leitungsfeld entfernen?",
                "Sind Sie sicher, dass Sie das Feld für die Leitungsperson "
                "entfernen wollen? Eingetragene Inhalte gehen verloren. "
                "Wenn Sie es reaktivieren, müssen Sie die Inhalte neu "
                "eingeben.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if antwort != QMessageBox.StandardButton.Yes:
                return  # Dialog bleibt offen, nichts wird verworfen
            self._leitung_wird_geloescht = True

        self.accept()

    def soll_leitung_geloescht_werden(self) -> bool:
        """True, wenn die Leitungsspalte in diesem Durchgang deaktiviert
        wurde und ihre Inhalte in der Datenbank gelöscht werden sollen."""
        return self._leitung_wird_geloescht

    def get_konfig(self) -> dict:
        return {
            "projekt_label":        self._get_combo_wert(self._cb_projekt, self._edit_projekt),
            "stufe_label":          self._get_combo_wert(self._cb_stufe,   self._edit_stufe),
            "stufenzusatz_label":   self._get_combo_wert(self._cb_zusatz,  self._edit_zusatz),
            "extra_1_label":        self._extras[0].text().strip(),
            "extra_2_label":        self._extras[1].text().strip(),
            "extra_3_label":        self._extras[2].text().strip(),
            "max_wuensche":         str(self._spin_max_wuensche.value()),
            "leitung_label":        self._leitung_edit.text().strip(),
            "projekt_extra_1_label": self._projekt_extras[0].text().strip(),
            "projekt_extra_2_label": self._projekt_extras[1].text().strip(),
            "projekt_extra_3_label": self._projekt_extras[2].text().strip(),
        }


class SpaltenzuordnungDialog(QDialog):
    """
    Dialog zum Zuordnen von Quell-Spalten zu App-Feldern.
    Flaches, stabiles Layout: kein Widget wird nach dem ersten Aufbau
    verschoben. Nur Vorschau-Tabelle und Combo-Optionen werden bei
    Header-/Trennzeichen-Änderung aktualisiert.
    """

    def __init__(self, headers: list, preview_rows: list,
                 app_felder: list, parent=None,
                 csv_filepath: str = None, csv_has_header: bool = True,
                 excel_filepath: str = None):
        super().__init__(parent)
        self.setWindowTitle("Spalten zuordnen")
        self.setMinimumSize(960, 640)
        self.app_felder      = app_felder
        self._csv_filepath   = csv_filepath
        self._excel_filepath = excel_filepath
        self.combos: dict[str, QComboBox] = {}
        self._current_headers: list = []
        self._current_rows:    list = []

        outer = QVBoxLayout(self)
        outer.setSpacing(6)

        # ── Trennzeichen (nur CSV) ────────────────────────────────────────────
        if csv_filepath:
            self.trenn = TrennzeichenWidget()
            detected   = ie.detect_csv_separator(csv_filepath)
            self.trenn.set_delimiter(detected)
            btn_sep = QPushButton("Vorschau aktualisieren")
            btn_sep.clicked.connect(self._reload_full)
            trenn_row = QHBoxLayout()
            trenn_row.addWidget(self.trenn, 1)
            trenn_row.addWidget(btn_sep)
            outer.addLayout(trenn_row)
        else:
            self.trenn = None

        # ── Header-Checkbox ───────────────────────────────────────────────────
        self._cb_has_header = QCheckBox(
            "Erste Zeile enthält Spaltenüberschriften (Header)"
        )
        self._cb_has_header.setChecked(True)
        # Nur Vorschau + Combo-Optionen aktualisieren – KEIN Layout-Umbau
        self._cb_has_header.toggled.connect(self._reload_preview_only)
        outer.addWidget(self._cb_has_header)

        # ── Datei initial einlesen ────────────────────────────────────────────
        init_headers, init_rows = self._lese_datei(has_header=True)
        self._current_headers = list(init_headers)
        self._current_rows    = list(init_rows)

        # ── Zuordnungs-Grid (einmalig gebaut, Optionen werden aktualisiert) ───
        k = db.get_feldkonfig()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        grid_w = QWidget()
        grid_l = QVBoxLayout(grid_w)
        grid_l.setSpacing(3)

        hdr_row = QHBoxLayout()
        hdr_lbl = QLabel("<b>App-Feld</b>")
        hdr_lbl.setMinimumWidth(300)
        hdr_row.addWidget(hdr_lbl, 2)
        hdr_row.addWidget(QLabel("<b>Quell-Spalte</b>"), 3)
        grid_l.addLayout(hdr_row)

        quell_opt = ["(nicht importieren)"] + list(init_headers)
        for feld_key, feld_label in app_felder:
            row_l = QHBoxLayout()
            lbl = QLabel(feld_label)
            lbl.setWordWrap(True)
            lbl.setMinimumWidth(300)
            lbl.setMaximumWidth(420)
            combo = FixedComboBox()
            combo.setMinimumWidth(240)
            combo.setSizePolicy(QSizePolicy.Policy.Expanding,
                                QSizePolicy.Policy.Fixed)
            combo.addItems(quell_opt)
            m = self._auto_match(feld_key, feld_label, init_headers, k)
            if m is not None:
                combo.setCurrentIndex(m + 1)
            combo.currentIndexChanged.connect(self._render_preview)
            self.combos[feld_key] = combo
            row_l.addWidget(lbl, 2)
            row_l.addWidget(combo, 3)
            grid_l.addLayout(row_l)

        grid_l.addStretch()
        scroll.setWidget(grid_w)
        outer.addWidget(scroll, 2)

        # ── Vorschau-Bereich: zwei Tabs (Widgets bleiben, nur Inhalt wechselt) ─
        preview_tabs = QTabWidget()

        self._quelle_table = QTableWidget(0, max(1, len(init_headers)))
        self._quelle_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        preview_tabs.addTab(self._quelle_table, "Einblick Quelldatei")
        preview_tabs.setTabToolTip(0, "Ungefilterte Rohdatei, alle Spalten, bis zu 50 Zeilen")

        self._preview_table = QTableWidget(0, max(1, len(init_headers)))
        self._preview_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        preview_tabs.addTab(self._preview_table, "Vorschau Zieldatei")
        preview_tabs.setTabToolTip(1, "Wie die ersten 5 Zeilen nach dem Import aussehen würden")

        preview_tabs.setMaximumHeight(220)
        self._fill_preview(init_headers, init_rows)
        outer.addWidget(preview_tabs)

        # ── Immer sichtbar: Append-Checkbox ──────────────────────────────────
        self._cb_append = QCheckBox(
            "Bestehende Daten behalten (anh\u00e4ngen statt ersetzen)"
        )
        outer.addWidget(self._cb_append)

        # ── Hinweistext (immer unten, einmalig) ───────────────────────────────
        hinweis_label = QLabel(self._build_hinweis(app_felder, k))
        hinweis_label.setWordWrap(True)
        outer.addWidget(hinweis_label)

        # ── Buttons ───────────────────────────────────────────────────────────
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        outer.addWidget(bb)

    # ── Hilfsmethoden ────────────────────────────────────────────────────────

    def _lese_datei(self, has_header: bool) -> tuple[list, list]:
        """Liest die Quelldatei mit aktuellem Trennzeichen und Header-Flag."""
        if self._csv_filepath and self.trenn:
            try:
                headers, rows = ie.read_csv(
                    self._csv_filepath, self.trenn.get_delimiter(), has_header
                )
            except Exception as e:
                QMessageBox.critical(self, "Fehler beim Lesen", str(e))
                return [], []
        elif self._excel_filepath:
            try:
                headers, rows = ie.read_excel(self._excel_filepath, has_header)
            except Exception as e:
                QMessageBox.critical(self, "Fehler beim Lesen", str(e))
                return [], []
        else:
            return [], []

        if has_header:
            # Zier-/Titelzeilen überspringen (z. B. aus dem Listenexport),
            # damit auch damit erzeugte Dateien direkt reimportierbar sind.
            headers, rows = ie.bereinige_titelzeilen(headers, rows)
        return headers, rows

    def _reload_full(self):
        """Vollneu-Einlesen bei Trennzeichen-Änderung: Combos + Vorschau."""
        has_header = self._cb_has_header.isChecked()
        headers, rows = self._lese_datei(has_header)
        self._current_headers = list(headers)
        self._current_rows    = list(rows)
        self._update_combos(headers)
        self._fill_preview(headers, rows)

    def _reload_preview_only(self):
        """Nur Vorschau + Combo-Optionen – kein Layout-Umbau."""
        has_header = self._cb_has_header.isChecked()
        headers, rows = self._lese_datei(has_header)
        self._current_headers = list(headers)
        self._current_rows    = list(rows)
        self._update_combos(headers)
        self._fill_preview(headers, rows)

    def _update_combos(self, headers: list):
        """Aktualisiert Dropdown-Optionen, bewahrt vorhandene Auswahl."""
        quell_opt = ["(nicht importieren)"] + list(headers)
        for combo in self.combos.values():
            current = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(quell_opt)
            idx = combo.findText(current)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.blockSignals(False)

    def _fill_preview(self, headers: list, rows: list):
        """Speichert Rohdaten und rendert beide Vorschau-Tabs neu."""
        self._preview_headers_raw = headers
        self._preview_rows_raw = rows
        self._render_quelle_ansicht()
        self._render_preview()

    def _render_quelle_ansicht(self):
        """
        Tab "Einblick Quelldatei": ungefilterte Rohdatei, alle Spalten,
        mehr Zeilen als die Ziel-Vorschau — damit man sich unabhängig von
        der aktuellen Zuordnung einen Überblick verschaffen kann, was in
        der Quelldatei überhaupt enthalten ist.
        """
        headers = getattr(self, "_preview_headers_raw", [])
        rows = getattr(self, "_preview_rows_raw", [])
        self._quelle_table.clear()
        cols = len(headers) if headers else 1
        self._quelle_table.setColumnCount(cols)
        anzeige_rows = rows[:50]
        self._quelle_table.setRowCount(len(anzeige_rows))
        if headers:
            self._quelle_table.setHorizontalHeaderLabels(headers)
        for r, row in enumerate(anzeige_rows):
            for c in range(cols):
                val = row[c] if c < len(row) else ""
                self._quelle_table.setItem(r, c, QTableWidgetItem(str(val)))
        self._quelle_table.resizeColumnsToContents()

    def _kurzlabel(self, feld_key: str, feld_label: str) -> str:
        """Kurzer, eindeutiger Spaltentitel für die Vorschau (ohne
        Klammer-Erläuterungen wie "(nur ganze Zahlen, z. B. 5, 6, 10)")."""
        sonderfaelle = {
            "ganzer_name_kombiniert": "Name",
            "klasse_kombiniert": "Gruppe",
        }
        if feld_key in sonderfaelle:
            return sonderfaelle[feld_key]
        return re.split(r"\s*\(", feld_label)[0].strip()

    # Pflichtfelder, die im Datenmodell immer existieren und beim Import
    # einen festen Standardwert erhalten, auch wenn keine Quellspalte
    # zugeordnet ist (siehe _default_projekt in importexport.py). Diese
    # sollen in der Zieldatei-Vorschau nicht einfach verschwinden, sondern
    # mit ihrem tatsächlichen Standardwert auftauchen. "projekt" (Option)
    # und "fixiert" haben eigene Sonderregelungen und bleiben unverändert
    # (nicht Teil dieser Liste).
    _PFLICHTFELDER_STANDARDWERT = {
        "nummer": "0", "projektname": "-",
        "stufenmin": "0", "stufenmax": "0", "tnmin": "0", "tnmax": "0",
    }

    def _render_preview(self, *_args):
        """
        Baut die Vorschau als Ergebnis-Simulation auf: Es werden die
        Spalten gezeigt, die tatsächlich einem App-Feld zugeordnet sind
        (nicht zugeordnete, optionale Quellspalten werden ausgeblendet),
        mit dem kurzen Zielfeld-Namen als Titel (kein Zuordnungspfeil) und
        den passenden Werten aus der aktuell zugeordneten Quellspalte.

        Pflichtfelder mit festem Standardwert bleiben auch ohne Zuordnung
        sichtbar und zeigen den Wert, der beim Import tatsächlich
        eingetragen würde:
        - Optionen: Nummer, Titel, Gruppenbereich/Plätze min+max.
        - Teilnehmer/innen: Name, Gruppenbereich, Gruppenzusatz (jeweils
          nur, wenn KEINE ihrer Alternativ-Spalten zugeordnet ist — z. B.
          kein Platzhalter für Gruppenbereich, wenn stattdessen die
          kombinierte Spalte "Gruppenbereich + Gruppenzusatz" zugeordnet
          wurde) sowie alle unter "Spaltenbezeichnungen anpassen"
          konfigurierten Wunschränge.
        "Option" (Projekt-Zuteilung) und "Fixiert" haben eigene
        Sonderregelungen und werden hier nicht angefasst.

        So ist auch sofort sichtbar, wenn Zuordnungen vertauscht wurden —
        die Vorschau-Inhalte wechseln dann automatisch mit.
        """
        headers = getattr(self, "_preview_headers_raw", [])
        rows = getattr(self, "_preview_rows_raw", [])
        if not hasattr(self, "combos"):
            return

        feld_labels = dict(self.app_felder)
        feld_reihenfolge = {fk: i for i, (fk, _) in enumerate(self.app_felder)}
        vorhandene = set(self.combos.keys())

        def ist_zugeordnet(fk):
            c = self.combos.get(fk)
            return c is not None and c.currentIndex() > 0

        # spalten: Liste von (sortier_index, anzeige_label, wert_funktion)
        spalten = []

        # 1) Alle tatsächlich zugeordneten Felder
        for feld_key, combo in self.combos.items():
            idx = combo.currentIndex()
            if idx > 0 and (idx - 1) < len(headers):
                quell_idx = idx - 1
                spalten.append((
                    feld_reihenfolge.get(feld_key, 999),
                    self._kurzlabel(feld_key, feld_labels.get(feld_key, feld_key)),
                    (lambda row, qi=quell_idx: row[qi] if qi < len(row) else "")
                ))

        # 2) Einzel-Pflichtfelder ohne eigene Zuordnung: fester Platzhalter
        #    (Optionen-Felder sowie alle konfigurierten Wunschränge)
        for feld_key in self.combos.keys():
            if ist_zugeordnet(feld_key):
                continue
            platzhalter = self._PFLICHTFELDER_STANDARDWERT.get(feld_key)
            if platzhalter is None and feld_key.startswith("wunsch_"):
                platzhalter = "0"
            if platzhalter is not None:
                spalten.append((
                    feld_reihenfolge.get(feld_key, 999),
                    self._kurzlabel(feld_key, feld_labels.get(feld_key, feld_key)),
                    (lambda row, ph=platzhalter: ph)
                ))

        # 3) Gruppen-Pflichtfelder mit Alternativen (Name / Gruppenbereich /
        #    Gruppenzusatz): Platzhalter nur, wenn WIRKLICH KEINE der
        #    jeweiligen Alternativ-Spalten zugeordnet ist.
        if "nachname" in vorhandene and not any(
            ist_zugeordnet(k) for k in ("nachname", "vorname", "ganzer_name_kombiniert")
        ):
            spalten.append((feld_reihenfolge.get("nachname", 999), "Name",
                            (lambda row: "-")))

        if "stufe" in vorhandene and not any(
            ist_zugeordnet(k) for k in ("stufe", "klasse_kombiniert")
        ):
            sl_label = self._kurzlabel("stufe", feld_labels.get("stufe", "Gruppenbereich"))
            spalten.append((feld_reihenfolge.get("stufe", 999), sl_label,
                            (lambda row: "0")))

        if "stufenzusatz" in vorhandene and not any(
            ist_zugeordnet(k) for k in ("stufenzusatz", "klasse_kombiniert")
        ):
            zl_label = self._kurzlabel("stufenzusatz", feld_labels.get("stufenzusatz", "Gruppenzusatz"))
            spalten.append((feld_reihenfolge.get("stufenzusatz", 999), zl_label,
                            (lambda row: "-")))

        spalten.sort(key=lambda t: t[0])

        self._preview_table.clear()
        if not spalten:
            self._preview_table.setColumnCount(1)
            self._preview_table.setRowCount(0)
            self._preview_table.setHorizontalHeaderLabels(
                ["(keine Spalte zugeordnet)"]
            )
            return

        display_headers = [lbl for _, lbl, _ in spalten]
        self._preview_table.setColumnCount(len(spalten))
        self._preview_table.setRowCount(min(5, len(rows)))
        self._preview_table.setHorizontalHeaderLabels(display_headers)
        for r, row in enumerate(rows[:5]):
            for c, (_, _, wert_fn) in enumerate(spalten):
                self._preview_table.setItem(r, c, QTableWidgetItem(str(wert_fn(row))))
        self._preview_table.resizeColumnsToContents()

    @staticmethod
    def _build_hinweis(app_felder: list, k: dict) -> str:
        sl = k.get("stufe_label",        "Gruppenbereich")
        zl = k.get("stufenzusatz_label", "Gruppenzusatz")
        h  = ("Ordnen Sie den App-Feldern die entsprechenden Quell-Spalten zu.\n"
              "Felder ohne Zuordnung werden mit Standardwerten \u00fcbernommen.")
        if any(fk == "ganzer_name_kombiniert" for fk, _ in app_felder):
            h += (f"\n\nName: Ordnen Sie ENTWEDER \u201eNachname\u201c + "
                  f"\u201eVorname\u201c als getrennte Spalten zu, ODER eine "
                  f"einzige Namensspalte dem Feld \u201eGanzer Name\u201c.")
        if any(fk == "klasse_kombiniert" for fk, _ in app_felder):
            h += (f"\n\n{sl} / {zl}: Getrennte Spalten ODER eine kombinierte "
                  f"Spalte (z.\u202fB. \u201e5a\u201c) \u2013 wird beim Import "
                  f"automatisch aufgetrennt. Im {sl}-Anteil nur ganze Zahlen.")
        return h

    @staticmethod
    def _auto_match(feld_key: str, feld_label: str,
                    headers: list, konfig: dict) -> int | None:
        sl = konfig.get("stufe_label", "Gruppenbereich").lower()
        zl = konfig.get("stufenzusatz_label", "Gruppenzusatz").lower()
        pl_orig = konfig.get("projekt_label", "Projekt")
        pl = pl_orig.lower()
        # Grammatisch abgeleitete Form (z. B. "Optionsname" mit Fugen-s)
        # zusätzlich als Alias aufnehmen, damit re-importierte, selbst
        # exportierte Dateien auch bei solchen Bezeichnungen automatisch
        # zugeordnet werden.
        try:
            pl_name_form = db.get_label_formen(pl_orig)["name"].lower()
        except Exception:
            pl_name_form = pl + "name"
        aliases = {
            "nachname":  ["nachname", "last name", "familienname"],
            "vorname":   ["vorname", "first name", "given name"],
            "stufe":     ["stufe", "jahrgangsstufe", "jahrgang",
                          sl, "jg", "jgst."],
            "stufenzusatz": ["klassenzusatz", "stufenzusatz", "zusatz", zl],
            "wunsch_1":  ["wunsch 1", "wunsch1", "w1"],
            "wunsch_2":  ["wunsch 2", "wunsch2", "w2"],
            "wunsch_3":  ["wunsch 3", "wunsch3", "w3"],
            "wunsch_4":  ["wunsch 4", "wunsch4", "w4"],
            "wunsch_5":  ["wunsch 5", "wunsch5", "w5"],
            "projekt":   ["projekt", "project", pl, "zuteilung"],
            "nummer":    ["nr", "nr.", "nummer", "number"],
            "projektname": ["projektname", "name", "titel",
                            pl + "name", pl_name_form],
            "stufenmin": ["stufenmin", "min", "jgst. min", "mindest",
                          f"{sl} min"],
            "stufenmax": ["stufenmax", "max", "jgst. max", f"{sl} max"],
            "tnmin":     ["tnmin", "plätze min"],
            "tnmax":     ["tnmax", "plätze max"],
            "ganzer_name_kombiniert": [
                "name", "ganzer name", "ganzer_name", "vollname"
            ],
            "klasse_kombiniert": [
                "klasse", "class", "klassenbezeichnung"
            ],
        }
        candidates = aliases.get(feld_key, [feld_label.lower()])
        for i, h in enumerate(headers):
            h_norm = h.lower().strip().rstrip(".")
            if h_norm in candidates or h_norm == feld_key.lower():
                return i
        return None

    # ── Getter ────────────────────────────────────────────────────────────────

    def get_headers(self) -> list:
        return self._current_headers

    def get_rows(self) -> list:
        return self._current_rows

    def get_mapping(self) -> dict:
        mapping = {}
        for feld_key, combo in self.combos.items():
            idx = combo.currentIndex()
            mapping[feld_key] = (idx - 1) if idx > 0 else None
        return mapping

    def get_append(self) -> bool:
        return self._cb_append.isChecked() if self._cb_append else False


class ImportDialog(QDialog):
    """Haupt-Importdialog: Datei wählen + Trennzeichen + Zuordnung."""

    def __init__(self, modus: str, parent=None):
        """modus: 'schueler' oder 'projekte'"""
        super().__init__(parent)
        self.modus = modus
        self.setWindowTitle(
            "Teilnehmer/innen importieren" if modus == "schueler"
            else "Optionen / Angebote importieren"
        )
        self.setMinimumWidth(500)
        self._headers = []
        self._rows = []
        self._filepath = ""
        self._merge_temp_path = None  # temporäre Datei bei Mehrfach-Import

        layout = QVBoxLayout(self)
        # Passt die Fenstergröße automatisch an den Inhalt an, z. B. wenn
        # der Hinweistext beim Ankreuzen von "Mehrfach zusammenführen"
        # ein-/ausgeblendet wird.
        layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)

        # Mehrere Dateien zusammenführen (nur bei Teilnehmer/innen sinnvoll —
        # eine Optionsliste gibt es immer nur als eine einzige Datei)
        self._cb_mehrfach = QCheckBox(
            "Mehrere Dateien zusammenführen (z. B. je eine Datei pro Gruppe)"
        )
        self._cb_mehrfach.toggled.connect(self._on_mehrfach_toggled)
        if modus == "schueler":
            layout.addWidget(self._cb_mehrfach)

        # Dateiauswahl
        file_group = QGroupBox(
            "Quelldatei(en)" if modus == "schueler" else "Quelldatei"
        )
        file_layout = QHBoxLayout(file_group)
        self.lbl_file = QLabel("Keine Datei gewählt")
        self.lbl_file.setWordWrap(True)
        self.btn_browse = QPushButton("Durchsuchen")
        self.btn_browse.clicked.connect(self._browse)
        file_layout.addWidget(self.lbl_file, 1)
        file_layout.addWidget(self.btn_browse)
        layout.addWidget(file_group)

        hinweis = QLabel(
            "Bei mehreren Dateien werden Spalten anhand ihres Namens "
            "zusammengeführt (z. B. mehrere Gruppen-Exporte, die ausgefüllt "
            "zurückgekommen sind). Format je Datei: .xlsx, .ods oder .csv — "
            "auch gemischt möglich. Die Spaltenzuordnung erfolgt anschließend "
            "wie gewohnt in einem Schritt für alle Dateien zusammen."
        )
        hinweis.setWordWrap(True)
        hinweis.setStyleSheet("color: #555;")
        hinweis.setVisible(False)
        self._lbl_mehrfach_hinweis = hinweis
        if modus == "schueler":
            layout.addWidget(hinweis)

        # Buttons
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._on_ok)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

        # Temporäre Merge-Datei in jedem Fall aufräumen (OK, Abbrechen, X)
        self.finished.connect(self._cleanup_temp)

    def _cleanup_temp(self, *_args):
        if self._merge_temp_path and os.path.exists(self._merge_temp_path):
            try:
                os.unlink(self._merge_temp_path)
            except OSError:
                pass
            self._merge_temp_path = None

    def _on_mehrfach_toggled(self, checked: bool):
        self._filepath = ""
        self.lbl_file.setText("Keine Datei gewählt")
        self._lbl_mehrfach_hinweis.setVisible(checked)

    def _browse(self):
        if self._cb_mehrfach.isChecked():
            paths, _ = QFileDialog.getOpenFileNames(
                self, "Dateien öffnen", "",
                "Tabellen (*.csv *.xlsx *.ods);;Alle Dateien (*)"
            )
            if not paths:
                return
            self._filepath = list(paths)
            if len(paths) == 1:
                self.lbl_file.setText(paths[0])
            else:
                namen = "\n".join(f"• {os.path.basename(p)}" for p in paths)
                self.lbl_file.setText(f"{len(paths)} Dateien gewählt:\n{namen}")
        else:
            path, _ = QFileDialog.getOpenFileName(
                self, "Datei öffnen", "",
                "Tabellen (*.csv *.xlsx *.ods *.txt);;Alle Dateien (*)"
            )
            if not path:
                return
            self._filepath = path
            self.lbl_file.setText(path)

    def _bereite_mehrfach_merge_vor(self) -> bool:
        """
        Führt die gewählten Dateien zusammen, bietet optional die
        Bereinigung von Klammerzusätzen in Gruppenbereich/Gruppenzusatz
        an, und schreibt das Ergebnis in eine temporäre .xlsx-Datei, die
        anschließend wie ein normaler Einzel-Import behandelt wird.
        Gibt True zurück, wenn erfolgreich (self._filepath zeigt danach
        auf die temporäre Datei), sonst False (Abbruch).
        """
        headers, rows = ie.merge_import_dateien(self._filepath)
        if not headers or not rows:
            QMessageBox.warning(
                self, "Keine Daten",
                "In den gewählten Dateien wurden keine Daten gefunden."
            )
            return False

        k = db.get_feldkonfig()
        for spaltenname in (k.get("stufe_label", "Gruppenbereich"),
                            k.get("stufenzusatz_label", "Gruppenzusatz")):
            varianten = ie.detect_wert_varianten(headers, rows, spaltenname)
            if not varianten:
                continue
            beispiele = "\n".join(
                f"  \u201e{alt}\u201c \u2192 \u201e{neu}\u201c"
                for alt, neu in list(varianten.items())[:10]
            )
            antwort = QMessageBox.question(
                self, "Abweichende Werte gefunden",
                f"In der Spalte \u201e{spaltenname}\u201c weichen einzelne Werte "
                f"von den übrigen Zeilen ab (vermutlich ein Zusatz wie ein "
                f"Kürzel in Klammern):\n\n{beispiele}\n\n"
                f"Sollen diese auf die ursprüngliche Form zurückgekürzt werden?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if antwort == QMessageBox.StandardButton.Yes:
                ie.wende_wert_bereinigung_an(headers, rows, spaltenname, varianten)

        self._merge_temp_path = ie.schreibe_merge_temp_xlsx(headers, rows)
        self._filepath = self._merge_temp_path
        return True

    def _on_ok(self):
        mehrfach = self._cb_mehrfach.isChecked()

        if not self._filepath:
            QMessageBox.warning(self, "Fehler", "Bitte eine Datei wählen.")
            return

        if mehrfach and isinstance(self._filepath, list):
            if not self._bereite_mehrfach_merge_vor():
                return

        is_csv = not self._filepath.lower().endswith((".xlsx", ".ods"))

        # ── Auto-Erkennung Wunschanzahl ───────────────────────────────────────
        # Nur für Teilnehmer-Import relevant
        if self.modus == "schueler":
            try:
                if is_csv:
                    detected_h, detected_r = ie.read_csv(self._filepath, ";", True)
                else:
                    detected_h, detected_r = ie.read_excel(self._filepath, True)
                detected_h, _ = ie.bereinige_titelzeilen(detected_h, detected_r)
                datei_wuensche = ie.detect_wunsch_anzahl(detected_h)
                konfig_wuensche = db.get_feldkonfig().get("max_wuensche", 5)
                if datei_wuensche > 0 and datei_wuensche != konfig_wuensche:
                    if datei_wuensche > konfig_wuensche:
                        erklaerung = (
                            f"Die Datei enthält {datei_wuensche} Wunschspalten – "
                            f"mehr als die konfigurierten {konfig_wuensche}.\n"
                            f"Bei 'Beibehalten' werden nur die ersten "
                            f"{konfig_wuensche} Wünsche importiert."
                        )
                    else:
                        erklaerung = (
                            f"Die Datei enthält nur {datei_wuensche} Wunschspalten – "
                            f"weniger als die konfigurierten {konfig_wuensche}.\n"
                            f"Bei 'Beibehalten' werden die fehlenden Wunschränge "
                            f"mit 0 (kein Wunsch) aufgefüllt."
                        )
                    msg = (
                        f"In der Datei wurden {datei_wuensche} Wunschspalte(n) erkannt.\n"
                        f"In dieser Planungsmappe sind {konfig_wuensche} Wunschränge "
                        f"konfiguriert.\n\n"
                        f"{erklaerung}\n\n"
                        f"Was soll gelten?"
                    )
                    box = QMessageBox(self)
                    box.setWindowTitle("Unterschiedliche Wunschanzahl")
                    box.setText(msg)
                    btn_beibehalten = box.addButton(
                        f"Planungsmappe beibehalten ({konfig_wuensche} Wunschränge)",
                        QMessageBox.ButtonRole.AcceptRole
                    )
                    btn_anpassen = box.addButton(
                        f"Planungsmappe anpassen ({datei_wuensche} Wunschränge übernehmen)",
                        QMessageBox.ButtonRole.ActionRole
                    )
                    box.addButton("Abbrechen", QMessageBox.ButtonRole.RejectRole)
                    box.exec()
                    clicked = box.clickedButton()
                    if clicked is None or clicked.text().startswith("Abbrechen"):
                        return
                    if clicked == btn_anpassen:
                        neue_wuensche = max(1, min(5, datei_wuensche))
                        neue_konfig = db.get_feldkonfig()
                        neue_konfig["max_wuensche"] = str(neue_wuensche)
                        db.set_feldkonfig(neue_konfig)
                        # Hauptfenster über Änderung informieren
                        if hasattr(self.parent(), '_sync_labels'):
                            self.parent()._sync_labels()
                            self.parent()._refresh_teilnehmer()
            except Exception:
                pass  # Fehler beim Vorab-Lesen → ignorieren, normal weitermachen

        app_felder = (ie.get_schueler_felder() if self.modus == "schueler"
                      else ie.get_projekt_felder())

        # Header-Checkbox und Vorschau befinden sich jetzt im SpaltenzuordnungDialog
        if is_csv:
            dlg = SpaltenzuordnungDialog(
                [], [], app_felder, self,
                csv_filepath=self._filepath
            )
        else:
            dlg = SpaltenzuordnungDialog(
                [], [], app_felder, self,
                excel_filepath=self._filepath
            )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        mapping = dlg.get_mapping()
        append  = dlg.get_append()
        headers = dlg.get_headers()
        rows    = dlg.get_rows()

        try:
            if self.modus == "schueler":
                importierte_ids = ie.import_teilnehmer(headers, rows, mapping, append)
                QMessageBox.information(
                    self, "Import erfolgreich",
                    f"{len(rows)} Datensätze wurden importiert."
                )
                antwort = QMessageBox.question(
                    self, "Wunscheingaben prüfen?",
                    "Sollen die importierten Wunscheingaben geprüft werden "
                    "(Qualitätsprüfung: Zulässigkeit, Vollständigkeit, "
                    "Mehrfachnennungen)?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if antwort == QMessageBox.StandardButton.Yes:
                    self._qualitaetspruefung_nach_import(importierte_ids)
            else:
                self._pruefe_leitungsspalte(headers, mapping)
                ie.import_projekte(headers, rows, mapping, append)
                QMessageBox.information(
                    self, "Import erfolgreich",
                    f"{len(rows)} Datensätze wurden importiert."
                )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Fehler beim Import", str(e))

    def _pruefe_leitungsspalte(self, headers: list, mapping: dict) -> None:
        """
        "Leitung" wird im Spaltenzuordnungsfenster immer als App-Feld
        angeboten, auch wenn die Spalte über Datei → Spaltenbezeichnungen
        anpassen noch nicht aktiviert wurde (siehe get_projekt_felder).
        Hat der Nutzer ihr dennoch eine Quellspalte zugeordnet, während
        die Spalte in der aktuellen Planungsmappe noch nicht aktiv ist,
        wird nachgefragt, ob sie jetzt eingerichtet werden soll — unter
        Übernahme der Spaltenbezeichnung aus der Quelldatei. Bei "Nein"
        oder wenn ohnehin "nicht importieren" gewählt wurde, bleibt die
        Leitung einfach weg (mapping wird entsprechend bereinigt).
        """
        konfig = db.get_feldkonfig()
        if konfig.get("leitung_label", "").strip():
            return  # Leitungsspalte bereits aktiv -> nichts zu tun

        leitung_idx = mapping.get("leitung")
        if leitung_idx is None:
            return  # "nicht importieren" gewählt -> Feld bleibt weg

        spalten_name = (
            headers[leitung_idx] if leitung_idx < len(headers) else "Leitung"
        )
        pl  = konfig.get("projekt_label", "Option")
        plP = db.pluralisiere_label(pl)

        antwort = QMessageBox.question(
            self, "Leitungsspalte aktivieren?",
            f"Die zu importierenden {plP} sollen laut Ihrer Zuordnung eine "
            f"Spalte für die Leitungspersonen erhalten, Ihre aktuelle "
            f"{plP}-Tabelle enthält momentan aber noch keine Spalte dafür. "
            f"Soll diese Spalte (\u201e{spalten_name}\u201c) in Ihrer "
            f"Tabelle jetzt eingefügt werden?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if antwort != QMessageBox.StandardButton.Yes:
            mapping["leitung"] = None  # keine Spalte aktiv -> nicht importieren
            return

        neue_konfig = db.get_feldkonfig()
        neue_konfig["leitung_label"] = spalten_name
        db.set_feldkonfig(neue_konfig)
        # mapping["leitung"] bleibt wie vom Nutzer gewählt

        hauptfenster = self.parent()
        if hauptfenster is not None:
            if hasattr(hauptfenster, "_sync_labels"):
                hauptfenster._sync_labels()
            if hasattr(hauptfenster, "_refresh_all"):
                hauptfenster._refresh_all()

    def _qualitaetspruefung_nach_import(self, importierte_ids: list):
        """
        Führt nach dem Import dieselbe Qualitätsprüfung durch, die auch
        über Auswertung/Export → Qualitätsprüfung Wunscheingaben verfügbar
        ist (Zulässigkeit, Vollständigkeit, Null-Wünsche, Mehrfachnennungen)
        — beschränkt auf die gerade importierten Datensätze — und zeigt das
        Ergebnis im selben Fenster/Layout an.
        """
        import listenabfragen as la
        konfig = db.get_feldkonfig()
        max_w  = konfig.get("max_wuensche", 5)
        daten  = la.get_qualitaetspruefung(max_w, nur_ids=importierte_ids)
        gesamt = sum(len(v) for v in daten.values())
        if gesamt == 0:
            QMessageBox.information(
                self, "Keine Auffälligkeiten",
                "Die importierten Wunscheingaben zeigen keine "
                "Auffälligkeiten (Zulässigkeit, Vollständigkeit, "
                "Mehrfachnennungen)."
            )
            return

        from dialoge import QualitaetspruefungDialog
        hauptfenster = self.parent()
        qdlg = QualitaetspruefungDialog(hauptfenster, nur_ids=importierte_ids)
        if hauptfenster is not None:
            # Referenz am Hauptfenster halten, damit das (nicht-modale)
            # Fenster nicht vorzeitig durch Garbage Collection verschwindet,
            # sobald dieser Import-Dialog geschlossen wird.
            hauptfenster._qualitaet_fenster_nach_import = qdlg
            if hasattr(hauptfenster, "_markiere_teilnehmer_in_hauptfenster"):
                qdlg.person_angefordert.connect(
                    hauptfenster._markiere_teilnehmer_in_hauptfenster
                )
        qdlg.show()
        qdlg.raise_()
        qdlg.activateWindow()


class ExportDialog(QDialog):
    """Exportdialog: Sortierung, Format, Optionen."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Daten sortieren und exportieren")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)

        k  = db.get_feldkonfig()
        pl = k.get("projekt_label", "Projekt")
        sl = k.get("stufe_label",   "Gruppenbereich")

        # ── Sortierung ────────────────────────────────────────────────────────
        sort_group = QGroupBox("Sortierung")
        sort_layout = QVBoxLayout(sort_group)
        self.sort_bg = QButtonGroup(self)
        self.rb_sort = {}
        optionen = [
            ("klasse_name_projekt",
             f"Zuerst nach {sl}, dann Name, dann {pl}-Nr."),
            ("klasse_projekt",
             f"Zuerst nach {sl}, dann {pl}"),
            ("projekt_klasse_name",
             f"Zuerst nach {pl}, dann {sl}, dann Name"),
        ]
        for key, label in optionen:
            rb = QRadioButton(label)
            self.sort_bg.addButton(rb)
            sort_layout.addWidget(rb)
            self.rb_sort[key] = rb
        self.rb_sort["klasse_name_projekt"].setChecked(True)
        layout.addWidget(sort_group)

        # ── Exportformat ──────────────────────────────────────────────────────
        fmt_group = QGroupBox("Exportformat")
        fmt_layout = QVBoxLayout(fmt_group)
        self.cb_xlsx = QCheckBox("Excel-Datei (.xlsx)  \u2013 empfohlen")
        self.cb_ods  = QCheckBox("OpenDocument-Tabelle (.ods)")
        self.cb_txt  = QCheckBox("CSV/TXT-Datei")
        self.cb_html = QCheckBox("HTML-Datei")
        self.cb_xlsx.setChecked(True)   # Standard: xlsx
        for cb in (self.cb_xlsx, self.cb_ods, self.cb_txt, self.cb_html):
            fmt_layout.addWidget(cb)
        layout.addWidget(fmt_group)

        # ── Trennzeichen (nur bei CSV/TXT sichtbar) ───────────────────────────
        self.trenn = TrennzeichenWidget()
        self.trenn.setVisible(False)
        self.cb_txt.toggled.connect(self.trenn.setVisible)
        layout.addWidget(self.trenn)

        # ── Wünsche mitexportieren ────────────────────────────────────────────
        self.cb_wuensche = QCheckBox("W\u00fcnsche mit exportieren")
        layout.addWidget(self.cb_wuensche)

        # ── Buttons ───────────────────────────────────────────────────────────
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._on_ok)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def _on_ok(self):
        if not any(cb.isChecked()
                   for cb in (self.cb_xlsx, self.cb_ods,
                               self.cb_txt, self.cb_html)):
            QMessageBox.warning(self, "Kein Format gew\u00e4hlt",
                                "Bitte mindestens ein Exportformat ausw\u00e4hlen.")
            return
        self.accept()

    def get_sort_mode(self) -> str:
        for key, rb in self.rb_sort.items():
            if rb.isChecked():
                return key
        return "klasse_name_projekt"

    def get_formate(self) -> list:
        formate = []
        if self.cb_xlsx.isChecked():
            formate.append("xlsx")
        if self.cb_ods.isChecked():
            formate.append("ods")
        if self.cb_txt.isChecked():
            formate.append("txt")
        if self.cb_html.isChecked():
            formate.append("html")
        return formate

    def get_mit_wuenschen(self) -> bool:
        return self.cb_wuensche.isChecked()

    def get_delimiter(self) -> str:
        return self.trenn.get_delimiter()


class WunschauswertungDialog(QDialog):
    """Auswahl: Welches Projekt / welcher Wunschrang für die Wunschauswertung."""

    def __init__(self, projekte: list, parent=None):
        super().__init__(parent)
        import database as _db
        _k   = _db.get_feldkonfig()
        _pl  = _k.get("projekt_label", "Projekt")
        _plP = _db.pluralisiere_label(_pl)
        self.setWindowTitle("Wunschauswertung")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            f"Zeigt, welche Teilnehmer/innen welche {_pl} gewählt haben."
        ))

        # Projektfilter
        proj_group = QGroupBox(_pl)
        proj_layout = QVBoxLayout(proj_group)
        self.combo_projekt = FixedComboBox()
        self.combo_projekt.addItem(f"(alle {_plP})", None)
        self.combo_projekt.addItem("0 – Wunschrang nicht ausgefüllt", 0)
        for p in projekte:
            self.combo_projekt.addItem(f"{p['nummer']}: {p['projektname']}", p["nummer"])
        proj_layout.addWidget(self.combo_projekt)
        layout.addWidget(proj_group)

        # Wunschrang-Filter
        rang_group = QGroupBox("Wunschrang")
        rang_layout = QVBoxLayout(rang_group)
        self.combo_rang = FixedComboBox()
        self.combo_rang.addItem("(alle Wunschränge)", None)
        for r in range(1, 6):
            self.combo_rang.addItem(f"Wunsch {r}", r)
        self.combo_rang.addItem("0 – Kein Wunsch abgegeben", 0)
        self.combo_rang.currentIndexChanged.connect(self._on_rang_changed)
        rang_layout.addWidget(self.combo_rang)
        layout.addWidget(rang_group)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def _on_rang_changed(self):
        # Bei "Kein Wunsch abgegeben" ist eine Projektauswahl sinnlos,
        # da es ja gerade um Schüler ohne Wunsch geht
        ist_kein_wunsch = (self.combo_rang.currentData() == 0)
        self.combo_projekt.setEnabled(not ist_kein_wunsch)
        if ist_kein_wunsch:
            self.combo_projekt.setCurrentIndex(0)

    def get_projekt_nummer(self):
        if self.combo_rang.currentData() == 0:
            return None
        return self.combo_projekt.currentData()

    def get_wunsch_rang(self):
        return self.combo_rang.currentData()


class ProjektAuswahlDialog(QDialog):
    """Auswahl eines einzelnen Projekts für die Teilnehmerliste."""

    def __init__(self, projekte: list, parent=None):
        super().__init__(parent)
        import database as _db
        _k  = _db.get_feldkonfig()
        _pl = _k.get("projekt_label", "Projekt")
        self.setWindowTitle(f"Teilnehmerliste nach {_pl}")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f"Für welche/n {_pl} soll die Teilnehmerliste angezeigt werden?"))

        self.combo_projekt = FixedComboBox()
        self.combo_projekt.addItem(f"0 – Kein {_pl} (noch nicht zugeteilt)", 0)
        for p in projekte:
            self.combo_projekt.addItem(f"{p['nummer']}: {p['projektname']}", p["nummer"])
        layout.addWidget(self.combo_projekt)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def get_projekt_nummer(self):
        return self.combo_projekt.currentData()


class KlassenAuswahlDialog(QDialog):
    """Auswahl einer Gruppe für die Gruppenliste mit Zuteilung."""

    def __init__(self, klassen: list, parent=None):
        """klassen: Liste von (stufe, stufenzusatz)-Tupeln"""
        super().__init__(parent)
        self.setWindowTitle("Gruppenliste mit Zuteilung")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Für welche Gruppe soll die Liste angezeigt werden?"))

        self.combo_klasse = FixedComboBox()
        k = db.get_feldkonfig()
        sl = k.get("stufe_label", "Gruppenbereich")
        for stufe, stufenzusatz in klassen:
            label = (f"{stufe}{stufenzusatz}" if stufenzusatz and stufenzusatz != "-"
                     else f"{sl} {stufe}")
            self.combo_klasse.addItem(label, (stufe, stufenzusatz))
        layout.addWidget(self.combo_klasse)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def get_klasse(self):
        return self.combo_klasse.currentData()


class ProjektZuweisungDialog(QDialog):
    """
    Dialog zur manuellen Projektzuweisung eines einzelnen Schülers.
    Verwendet QListWidget statt QComboBox für zuverlässige Darstellung
    auch auf GTK-basierten Linux-Themes.
    """

    def __init__(self, schueler_name: str, optionen: list, parent=None):
        super().__init__(parent)
        import database as _db
        _k  = _db.get_feldkonfig()
        _pl = _k.get("projekt_label", "Projekt")
        self.setWindowTitle(f"{_pl} zuweisen")
        self.setMinimumSize(520, 420)
        self._optionen = optionen

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"{_pl} für <b>{schueler_name}</b> auswählen:"))

        self.liste = QListWidget()
        self.liste.setStyleSheet("""
            QListWidget {
                background-color: white;
                color: black;
                border: 1px solid #aaa;
            }
            QListWidget::item {
                padding: 4px 8px;
                color: black;
                background-color: white;
            }
            QListWidget::item:selected {
                background-color: #000000;
                color: #ffffff;
            }
            QListWidget::item:hover:!selected {
                background-color: #e8e8e8;
                color: black;
            }
        """)

        for label, p_nr in optionen:
            item = QListWidgetItem(label)
            if p_nr is None:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled
                              & ~Qt.ItemFlag.ItemIsSelectable)
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self.liste.addItem(item)

        # Ersten wählbaren Eintrag vorauswählen
        for i in range(self.liste.count()):
            if self.liste.item(i).flags() & Qt.ItemFlag.ItemIsEnabled:
                self.liste.setCurrentRow(i)
                break

        # Doppelklick bestätigt sofort
        self.liste.itemDoubleClicked.connect(
            lambda item: self.accept()
            if item.flags() & Qt.ItemFlag.ItemIsEnabled else None
        )
        layout.addWidget(self.liste)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def get_projekt_nummer(self):
        row = self.liste.currentRow()
        if 0 <= row < len(self._optionen):
            return self._optionen[row][1]
        return None

    def exec(self):
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        return super().exec()


class ProjektDetailsDialog(QDialog):
    """
    Zeigt detaillierte Statistiken zu einem einzelnen Projekt: wie oft
    es gewünscht wurde (gesamt und nach Wunschrang aufgeschlüsselt), und
    mit welchem Wunschrang die aktuell zugeteilten Personen das Projekt
    bekommen haben -- rein statistisch, ohne Namen.

    Bietet zusätzlich:
    - Doppelklick auf eine Wunschrang-Zeile in der "Wie oft gewünscht"-
      Tabelle öffnet die gefilterte Wunschauswertung für diesen Rang.
    - Vorheriges-/Nächstes-Projekt-Navigation (sofern eine Liste aller
      Projekt-Nummern übergeben wird).
    """

    wunschauswertung_angefordert = pyqtSignal(int)
    teilnehmerliste_angefordert  = pyqtSignal(int)
    # Signal: (projekt_nummer, wunsch_rang_oder_None) -- für die gefilterte
    # Wunschauswertung nach Doppelklick auf eine Wunschrang-Zeile
    wunschauswertung_rang_angefordert = pyqtSignal(int, int)
    # Signal: neue Projekt-Nummer, wenn Vor/Zurück geklickt wird
    projekt_wechsel_angefordert = pyqtSignal(int)

    def __init__(self, details: dict, parent=None):
        super().__init__(parent)
        p = details["projekt"]
        import database as _db
        _k      = _db.get_feldkonfig()
        _pl     = _k.get("projekt_label", "Projekt")
        _formen = _db.get_label_formen(_pl)
        self.setWindowTitle(
            f"Wunschdetails – {p['nummer']}: {p['projektname']}"
        )
        self.setMinimumSize(520, 520)
        self.setModal(False)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self._projekt_nr = p["nummer"]

        layout = QVBoxLayout(self)

        # ── Kopfzeile ──
        titel_label = QLabel(f"<b>{p['nummer']}: {p['projektname']}</b>")
        titel_label.setStyleSheet("font-size: 15px;")
        titel_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(titel_label)

        info_label = QLabel(
            f"Plätze: {p['tnmin']}–{p['tnmax']}   |   "
            f"Aktuell zugeteilt: {details['anzahl_zugeteilt']}"
        )
        layout.addWidget(info_label)

        # ── Wunsch-Statistik ──
        wunsch_gruppe = QGroupBox(
            f"Wie oft wurde {_formen['nom']} gewünscht? "
            "(Doppelklick auf eine Zeile zeigt die Personen)"
        )
        wunsch_layout = QVBoxLayout(wunsch_gruppe)
        gesamt = details["gesamt_gewuenscht"]
        wunsch_layout.addWidget(QLabel(f"<b>Insgesamt gewünscht: {gesamt}×</b>"))

        self.wunsch_table = QTableWidget(5, 2)
        self.wunsch_table.setHorizontalHeaderLabels(["Wunschrang", "Anzahl"])
        self.wunsch_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.wunsch_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.wunsch_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.wunsch_table.verticalHeader().setVisible(False)
        self.wunsch_table.cellDoubleClicked.connect(self._on_wunsch_doppelklick)
        for i, rang in enumerate(range(1, 6)):
            n = details["wunsch_anzahl_nach_rang"].get(rang, 0)
            item_rang = QTableWidgetItem(f"Wunsch {rang}")
            item_rang.setData(Qt.ItemDataRole.UserRole, rang)
            self.wunsch_table.setItem(i, 0, item_rang)
            item_n = QTableWidgetItem(str(n))
            item_n.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_n.setData(Qt.ItemDataRole.UserRole, rang)
            self.wunsch_table.setItem(i, 1, item_n)
        self.wunsch_table.setMaximumHeight(180)
        wunsch_layout.addWidget(self.wunsch_table)
        layout.addWidget(wunsch_gruppe)

        # ── Zuteilungs-Statistik ──
        zuteil_gruppe = QGroupBox("Zugeteilte Personen – mit welchem Wunschrang?")
        zuteil_layout = QVBoxLayout(zuteil_gruppe)

        zuteil_table = QTableWidget(0, 2)
        zuteil_table.setHorizontalHeaderLabels(["Wunschrang", "Anzahl Personen"])
        zuteil_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        zuteil_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        zuteil_table.verticalHeader().setVisible(False)

        zeilen = []
        for rang in range(1, 6):
            n = details["zuteilung_nach_rang"].get(rang, 0)
            if n > 0:
                zeilen.append((f"Wunsch {rang}", n))
        if details["zuteilung_ohne_wunsch"] > 0:
            zeilen.append(("Ohne eigenen Wunsch (Ausweich-/Sonderzuteilung)",
                          details["zuteilung_ohne_wunsch"]))

        zuteil_table.setRowCount(len(zeilen))
        for i, (label, n) in enumerate(zeilen):
            zuteil_table.setItem(i, 0, QTableWidgetItem(label))
            item_n = QTableWidgetItem(str(n))
            item_n.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            zuteil_table.setItem(i, 1, item_n)
        if not zeilen:
            zuteil_table.setRowCount(1)
            zuteil_table.setItem(0, 0, QTableWidgetItem("Noch niemand zugeteilt"))
            zuteil_table.setItem(0, 1, QTableWidgetItem("–"))

        zuteil_layout.addWidget(zuteil_table)
        layout.addWidget(zuteil_gruppe)

        # ── Buttons ──
        btn_layout = QHBoxLayout()
        btn_wunschauswertung = QPushButton(
            f"Wunschauswertungsliste {_formen['dativ_art']} {_pl}"
        )
        btn_wunschauswertung.clicked.connect(self._on_wunschauswertung)
        btn_teilnehmerliste = QPushButton(
            f"Teilnehmerliste {_formen['dativ_art']} {_pl}"
        )
        btn_teilnehmerliste.clicked.connect(self._on_teilnehmerliste)
        btn_schliessen = QPushButton("Schließen")
        btn_schliessen.clicked.connect(self.accept)
        btn_layout.addWidget(btn_wunschauswertung)
        btn_layout.addWidget(btn_teilnehmerliste)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_schliessen)
        layout.addLayout(btn_layout)

    def _on_wunsch_doppelklick(self, row: int, col: int):
        item = self.wunsch_table.item(row, 0)
        if item is None:
            return
        rang = item.data(Qt.ItemDataRole.UserRole)
        self.wunschauswertung_rang_angefordert.emit(self._projekt_nr, rang)
        self.hide()

    def _on_wunschauswertung(self):
        self.wunschauswertung_angefordert.emit(self._projekt_nr)
        self.hide()

    def _on_teilnehmerliste(self):
        self.teilnehmerliste_angefordert.emit(self._projekt_nr)
        self.hide()


class AnzahlWuenscheDialog(QDialog):
    """
    Auswahl, wie viele Wünsche bei der automatischen Einteilung
    berücksichtigt werden sollen. Vorausgefüllt mit dem konfigurierten Wert.
    """

    def __init__(self, algo_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Automatisch einteilen")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)

        konfig_mw = db.get_feldkonfig().get("max_wuensche", 5)

        layout.addWidget(QLabel(f"<b>Algorithmus {algo_name} starten</b>"))
        layout.addWidget(QLabel(
            f"Wie viele der {konfig_mw} konfigurierten Wunschränge sollen "
            "berücksichtigt werden?\n"
            "Teilnehmer/innen, deren berücksichtigte Wünsche alle nicht "
            "klappen, bleiben unzugeteilt."
        ))

        self.combo = FixedComboBox()
        for n in range(konfig_mw, 0, -1):
            if n == konfig_mw:
                self.combo.addItem(f"Alle {n} Wünsche (Standard)", n)
            else:
                self.combo.addItem(f"Nur Wunsch 1–{n}", n)
        layout.addWidget(self.combo)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def get_max_wuensche(self) -> int:
        return self.combo.currentData()


class EinrichtungsassistentDialog(QDialog):
    """
    Mehrstufiger Einrichtungsassistent für neue und leere Planungsmappen.
    Erscheint beim App-Start (wenn DB leer) und beim Anlegen einer neuen Mappe.

    Ablauf:
      Seite 0 – Willkommen: Assistent oder Standardwerte?
      Seite 1 – Spaltenbezeichnungen konfigurieren
      Seite 2 – Projekte importieren (optional)
      Seite 3 – Teilnehmer/innen importieren (optional)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Planungsmappe einrichten")
        self.setMinimumWidth(560)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        self._konfig_geaendert = False   # hat der Nutzer Bezeichnungen gespeichert?

        outer = QVBoxLayout(self)

        # ── Schrittanzeige ────────────────────────────────────────────────────
        self.lbl_schritt = QLabel()
        self.lbl_schritt.setAlignment(Qt.AlignmentFlag.AlignRight)
        outer.addWidget(self.lbl_schritt)

        # ── Seiten ────────────────────────────────────────────────────────────
        self.stack = QStackedWidget()
        outer.addWidget(self.stack)
        self._baue_seite_willkommen()
        self._baue_seite_spalten()
        self._baue_seite_import("projekte")
        self._baue_seite_import("teilnehmer")

        # ── Navigation ────────────────────────────────────────────────────────
        nav = QHBoxLayout()
        self.btn_zurueck     = QPushButton("◀ Zurück")
        self.btn_ueberspringen = QPushButton("Schritt überspringen")
        self.btn_weiter      = QPushButton("Weiter ▶")
        self.btn_fertig      = QPushButton("✓ Fertig")
        nav.addWidget(self.btn_zurueck)
        nav.addWidget(self.btn_ueberspringen)
        nav.addStretch()
        nav.addWidget(self.btn_weiter)
        nav.addWidget(self.btn_fertig)
        outer.addLayout(nav)

        self.btn_zurueck.clicked.connect(self._zurueck)
        self.btn_ueberspringen.clicked.connect(self._ueberspringen)
        self.btn_weiter.clicked.connect(self._weiter)
        self.btn_fertig.clicked.connect(self.accept)

        self._update_nav()

    # ── Seitenaufbau ──────────────────────────────────────────────────────────

    def _baue_seite_willkommen(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(16)
        lay.setContentsMargins(32, 24, 32, 24)

        # ── Titel ──
        lbl_app = QLabel("<span style='font-size:22pt;font-weight:bold;color:#1F3864;'>"
                         "Mitmach-Lotse</span>")
        lbl_app.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_app.setTextFormat(Qt.TextFormat.RichText)

        lbl_untertitel = QLabel(
            "<span style='font-size:10pt;color:#555;'>"
            "Verwaltung und Zuteilung von Teilnehmer/innen zu Optionen, "
            "Projekten, Kursen und ähnlichen Gruppenveranstaltungen</span>"
        )
        lbl_untertitel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_untertitel.setWordWrap(True)
        lbl_untertitel.setTextFormat(Qt.TextFormat.RichText)

        lbl_gruss = QLabel(
            "<span style='font-size:10pt;'>Schön, dass Sie da sind! Richten "
            "Sie in wenigen Schritten Ihre erste Planungsmappe ein!</span>"
        )
        lbl_gruss.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_gruss.setWordWrap(True)
        lbl_gruss.setTextFormat(Qt.TextFormat.RichText)

        lbl_features = QLabel(
            "<b>Was Sie mit Mitmach-Lotse erledigen können:</b><br>"
            "&#8226; Teilnehmer/innen anhand ihrer Wünsche fair und "
            "automatisch verteilen &#8211; per mathematisch optimierten "
            "Algorithmen<br>"
            "&#8226; Wunschlisten für externe Bearbeitung exportieren "
            "(Excel, OpenDocument oder CSV) und nahtlos wieder "
            "importieren &#8211; z. B. über Tutoren oder "
            "Klassenlehrkräfte<br>"
            "&#8226; Eingaben per Qualitätsprüfung automatisch auf "
            "Zulässigkeit, Vollständigkeit und Mehrfachnennungen prüfen<br>"
            "&#8226; Ausgabe-, Gruppen- und Auswertungslisten auf "
            "Knopfdruck erstellen, drucken oder als PDF/Excel/ODS "
            "exportieren<br>"
            "&#8226; Begriffe wie &#8222;Option&#8220;, &#8222;Gruppe&#8220; "
            "oder &#8222;Wunsch&#8220; frei an den eigenen Sprachgebrauch "
            "anpassen"
        )
        lbl_features.setWordWrap(True)
        lbl_features.setTextFormat(Qt.TextFormat.RichText)

        # ── Trennlinie ──
        from PyQt6.QtWidgets import QFrame
        linie = QFrame()
        linie.setFrameShape(QFrame.Shape.HLine)
        linie.setFrameShadow(QFrame.Shadow.Sunken)

        lbl_frage = QLabel("<b>Diese Planungsmappe ist noch leer. Wie möchten Sie beginnen?</b>")
        lbl_frage.setWordWrap(True)
        lbl_frage.setTextFormat(Qt.TextFormat.RichText)

        self.rb_assistent = QRadioButton(
            "Mit dem Assistenten einrichten\n"
            "Schritt für Schritt: Bezeichnungen anpassen, "
            "Optionen und Teilnehmer/innen importieren."
        )
        self.rb_standard = QRadioButton(
            "Mit Standardbezeichnungen sofort beginnen\n"
            "Einstellungen lassen sich jederzeit unter Datei → Spaltenbezeichnungen anpassen."
        )
        self.rb_laden = QRadioButton(
            "Bestehende Planungsmappe öffnen\n"
            "Eine vorhandene .plf- oder .db-Datei laden und damit weiterarbeiten."
        )
        self.rb_assistent.setChecked(True)

        lbl_hinweis = QLabel(
            "<small><i>Alle Einstellungen können Sie jederzeit später ändern "
            "und Daten über das Menü Importieren laden.</i></small>"
        )
        lbl_hinweis.setWordWrap(True)
        lbl_hinweis.setTextFormat(Qt.TextFormat.RichText)

        lay.addWidget(lbl_app)
        lay.addWidget(lbl_untertitel)
        lay.addWidget(lbl_gruss)
        lay.addWidget(lbl_features)
        lay.addWidget(linie)
        lay.addSpacing(8)
        lay.addWidget(lbl_frage)
        lay.addSpacing(4)
        lay.addWidget(self.rb_assistent)
        lay.addWidget(self.rb_standard)
        lay.addWidget(self.rb_laden)
        lay.addStretch()
        lay.addWidget(lbl_hinweis)
        self.stack.addWidget(w)

    def _baue_seite_spalten(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        lbl = QLabel(
            "<b>Schritt 1 von 3 &#8211; Spaltenbezeichnungen</b><br>"
            "Klicken Sie auf &#8222;Jetzt konfigurieren&#8220;, um die Bezeichnungen "
            "an Ihren Anwendungsfall anzupassen. "
            "Sie k&#246;nnen diesen Schritt auch &#252;berspringen und "
            "sp&#228;ter unter <i>Datei &#8594; Spaltenbezeichnungen anpassen &#8230;</i> "
            "&#196;nderungen vornehmen."
        )
        lbl.setWordWrap(True)
        lay.addWidget(lbl)
        lay.addSpacing(12)

        self.btn_konfigurieren = QPushButton("Konfigurieren")
        self.btn_konfigurieren.clicked.connect(self._oeffne_spalten_dialog)
        self.lbl_spalten_status = QLabel("(noch nicht konfiguriert – Standardwerte werden verwendet)")
        self.lbl_spalten_status.setStyleSheet("color: gray; font-style: italic;")

        lay.addWidget(self.btn_konfigurieren)
        lay.addWidget(self.lbl_spalten_status)
        lay.addStretch()
        self.stack.addWidget(w)

    def _baue_seite_import(self, modus: str):
        """Baut eine Import-Seite für 'projekte' oder 'teilnehmer'."""
        w = QWidget()
        lay = QVBoxLayout(w)

        ist_projekte = (modus == "projekte")
        schritt = "2" if ist_projekte else "3"
        k = db.get_feldkonfig()
        pl = k.get("projekt_label", "Projekt")
        bezeichnung = (f"{db.pluralisiere_label(pl)}"
                       if ist_projekte else "Teilnehmer/innen")
        lbl = QLabel(
            f"<b>Schritt {schritt} von 3 – {bezeichnung} importieren</b><br>"
            f"Möchten Sie jetzt eine {bezeichnung}-Liste importieren?<br>"
            f"Unterstützte Formate: <b>.xlsx, .ods, .csv</b><br><br>"
            f"Sie können diesen Schritt auch überspringen und "
            f"die Daten später über das Menü <i>Importieren</i> laden."
        )
        lbl.setWordWrap(True)
        lay.addWidget(lbl)
        lay.addSpacing(12)

        btn = QPushButton(f"{bezeichnung} jetzt importieren")
        btn.clicked.connect(lambda: self._import_starten(modus))
        lbl_status = QLabel(f"(noch nicht importiert)")
        lbl_status.setStyleSheet("color: gray; font-style: italic;")
        if ist_projekte:
            self.lbl_projekt_status = lbl_status
        else:
            self.lbl_teilnehmer_status = lbl_status

        lay.addWidget(btn)
        lay.addWidget(lbl_status)
        lay.addStretch()
        self.stack.addWidget(w)

    # ── Navigation ────────────────────────────────────────────────────────────

    def _aktuelle_seite(self) -> int:
        return self.stack.currentIndex()

    def _weiter(self):
        seite = self._aktuelle_seite()
        if seite == 0:
            if self.rb_standard.isChecked():
                self.accept()
                return
            if self.rb_laden.isChecked():
                self._lade_bestehende()
                return
        naechste = seite + 1
        if naechste < self.stack.count():
            self.stack.setCurrentIndex(naechste)
            self._update_nav()

    def _lade_bestehende(self):
        """Öffnet eine bestehende Planungsmappe und schließt den Assistenten."""
        from pathlib import Path
        path, _ = QFileDialog.getOpenFileName(
            self, "Planungsmappe öffnen", "",
            ".plf – Planungsmappe (Planning File) (*.plf);;"
            ".db – SQLite-Datenbank (*.db);;Alle Dateien (*)"
        )
        if path:
            db.DB_PATH = Path(path)
            db.init_db()
            self.accept()

    def _zurueck(self):
        seite = self._aktuelle_seite()
        if seite > 0:
            self.stack.setCurrentIndex(seite - 1)
            self._update_nav()

    def _ueberspringen(self):
        seite = self._aktuelle_seite()
        if seite < self.stack.count() - 1:
            self.stack.setCurrentIndex(seite + 1)
            self._update_nav()
        else:
            self.accept()

    def _update_nav(self):
        seite = self._aktuelle_seite()
        letzte = self.stack.count() - 1

        self.btn_zurueck.setVisible(seite > 0)
        self.btn_ueberspringen.setVisible(0 < seite < letzte)
        self.btn_weiter.setVisible(seite < letzte)
        self.btn_fertig.setVisible(seite == letzte)

        if seite == 0:
            self.lbl_schritt.setText("")
        else:
            self.lbl_schritt.setText(f"Schritt {seite} von {letzte}")

    # ── Aktionen ──────────────────────────────────────────────────────────────

    def _oeffne_spalten_dialog(self):
        konfig = db.get_feldkonfig()
        dlg = PlanungsmappeEinrichtenDialog(
            self, vorlage_laden=True, aktuell=konfig
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            db.set_feldkonfig(dlg.get_konfig())
            self._konfig_geaendert = True
            neue_k = db.get_feldkonfig()
            self.lbl_spalten_status.setText(
                f"\u2713 Gespeichert: "
                f"Gruppenbereich = \u201e{neue_k['stufe_label']}\u201c, "
                f"Gruppenzusatz = \u201e{neue_k['stufenzusatz_label']}\u201c, "
                f"Option/Projekt = \u201e{neue_k['projekt_label']}\u201c"
            )
            self.lbl_spalten_status.setStyleSheet("color: green;")

    def _import_starten(self, modus: str):
        # ImportDialog kennt nur "schueler" und "projekte"
        import_modus = "schueler" if modus == "teilnehmer" else modus
        dlg = ImportDialog(import_modus, self)
        dlg.exec()
        ist_projekte = (modus == "projekte")
        status_lbl = (self.lbl_projekt_status
                      if ist_projekte else self.lbl_teilnehmer_status)
        k = db.get_feldkonfig()
        pl = k.get("projekt_label", "Projekt")
        bezeichnung = (db.pluralisiere_label(pl)
                       if ist_projekte else "Teilnehmer/innen")
        status_lbl.setText(f"✓ Import abgeschlossen")
        status_lbl.setStyleSheet("color: green;")


class FensterExportDialog(QDialog):
    """Export-Dialog für Fensterlisten: Format + mit/ohne Wünsche."""

    FORMATE = [("Excel-Datei (.xlsx)", "xlsx"),
               ("ODS-Tabelle (.ods)",  "ods"),
               ("CSV-Datei (.csv)",    "csv"),
               ("PDF-Datei (.pdf)",    "pdf")]

    def __init__(self, hat_wuensche: bool = True, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Liste exportieren")
        self.setMinimumWidth(340)
        layout = QVBoxLayout(self)

        # Format
        fmt_group = QGroupBox("Format")
        fmt_layout = QVBoxLayout(fmt_group)
        self._fmt_radios = []
        bg = QButtonGroup(self)
        for label, key in self.FORMATE:
            rb = QRadioButton(label)
            bg.addButton(rb)
            fmt_layout.addWidget(rb)
            self._fmt_radios.append((rb, key))
        self._fmt_radios[0][0].setChecked(True)
        layout.addWidget(fmt_group)

        # Optionen
        self._cb_wuensche = QCheckBox("Wünsche mit einbeziehen")
        self._cb_wuensche.setChecked(True)
        self._cb_wuensche.setEnabled(hat_wuensche)
        layout.addWidget(self._cb_wuensche)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def get_format(self) -> str:
        for rb, key in self._fmt_radios:
            if rb.isChecked():
                return key
        return "xlsx"

    def get_mit_wuenschen(self) -> bool:
        return self._cb_wuensche.isChecked()


class GesamtExportDialog(QDialog):
    """Export-Dialog für Gesamtlisten: Format + Optionen + Kopfzeile."""

    FORMATE = [("Excel-Datei (.xlsx)", "xlsx"),
               ("ODS-Tabelle (.ods)",  "ods"),
               ("CSV-Datei (.csv)",    "csv"),
               ("PDF-Datei (.pdf)",    "pdf")]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gesamtliste exportieren")
        self.setMinimumWidth(380)
        layout = QVBoxLayout(self)

        # Kopfzeile
        kz_group = QGroupBox("Kopfzeile (z. B. Veranstaltungsname, Datum)")
        kz_layout = QVBoxLayout(kz_group)
        self._edit_kopfzeile = QLineEdit()
        kz_layout.addWidget(self._edit_kopfzeile)
        layout.addWidget(kz_group)

        # Format
        fmt_group = QGroupBox("Format")
        fmt_layout = QVBoxLayout(fmt_group)
        self._fmt_radios = []
        bg = QButtonGroup(self)
        for label, key in self.FORMATE:
            rb = QRadioButton(label)
            bg.addButton(rb)
            fmt_layout.addWidget(rb)
            self._fmt_radios.append((rb, key))
        self._fmt_radios[0][0].setChecked(True)
        layout.addWidget(fmt_group)

        # Optionen
        opt_group = QGroupBox("Optionen")
        opt_layout = QVBoxLayout(opt_group)
        self._cb_wuensche = QCheckBox("Wünsche mit einbeziehen")
        self._cb_wuensche.setChecked(True)
        self._cb_seitenumbrueche = QCheckBox(
            "Seitenumbruch nach jeder Gruppe")
        self._cb_seitenumbrueche.setChecked(True)
        self._cb_datum = QCheckBox("Datum in der Fußzeile (PDF und xlsx)")
        self._cb_datum.setChecked(False)
        self._cb_datum.setToolTip(
            "PDF: Datum erscheint links unten auf jeder Seite.\n"
            "Excel (.xlsx): Datum als Druckfußzeile (sichtbar beim Drucken\n"
            "  oder beim PDF-Export direkt aus Excel/LibreOffice).\n"
            "ODS: Datum in der Seitenfußzeile derzeit nicht verfügbar.\n"
            "CSV: kein Effekt."
        )
        opt_layout.addWidget(self._cb_wuensche)
        opt_layout.addWidget(self._cb_seitenumbrueche)
        opt_layout.addWidget(self._cb_datum)

        # Einzeldatei-Export
        self._cb_separat = QCheckBox("Jede Gruppe / jede Option als separate Datei")
        self._cb_separat.setChecked(False)
        self._cb_separat.setToolTip(
            "Erstellt pro Gruppe oder Option eine eigene Datei.\n"
            "Praktisch z. B. für Ausgabelisten oder zum Vorab-Befüllen\n"
            "von Wünschen (Export → ausfüllen → Reimport)."
        )
        opt_layout.addWidget(self._cb_separat)

        # ZIP oder Ordner
        self._ausgabe_group = QGroupBox("Ausgabe (bei separaten Dateien)")
        ausgabe_layout = QVBoxLayout(self._ausgabe_group)
        self._rb_zip    = QRadioButton("Als ZIP-Archiv")
        self._rb_ordner = QRadioButton("Direkt in Ordner schreiben")
        self._rb_zip.setChecked(True)
        bg_aus = QButtonGroup(self)
        bg_aus.addButton(self._rb_zip)
        bg_aus.addButton(self._rb_ordner)
        ausgabe_layout.addWidget(self._rb_zip)
        ausgabe_layout.addWidget(self._rb_ordner)
        self._ausgabe_group.setEnabled(False)
        opt_layout.addWidget(self._ausgabe_group)

        self._cb_separat.toggled.connect(self._ausgabe_group.setEnabled)
        layout.addWidget(opt_group)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def get_format(self) -> str:
        for rb, key in self._fmt_radios:
            if rb.isChecked():
                return key
        return "xlsx"

    def get_kopfzeile(self) -> str:
        return self._edit_kopfzeile.text().strip()

    def get_mit_wuenschen(self) -> bool:
        return self._cb_wuensche.isChecked()

    def get_seitenumbrueche(self) -> bool:
        return self._cb_seitenumbrueche.isChecked()

    def get_datum_fusszeile(self) -> bool:
        return self._cb_datum.isChecked()

    def get_separat(self) -> bool:
        return self._cb_separat.isChecked()

    def get_ausgabe_modus(self) -> str:
        """'zip' oder 'ordner'"""
        return "ordner" if self._rb_ordner.isChecked() else "zip"


class TeilnehmerHinzufuegenDialog(QDialog):
    """Popup zum Anlegen eines neuen Teilnehmers / einer neuen Teilnehmerin."""

    def __init__(self, parent=None, vorbelegung: dict = None):
        super().__init__(parent)
        k = db.get_feldkonfig()
        self._sl  = k.get("stufe_label",        "Gruppenbereich")
        self._zl  = k.get("stufenzusatz_label", "Gruppenzusatz")
        self.setWindowTitle("Teilnehmer/in hinzufügen")
        self.setMinimumWidth(380)
        v = vorbelegung or {}

        layout = QVBoxLayout(self)
        form   = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        self._e_nachname    = QLineEdit(v.get("nachname", ""))
        self._e_vorname     = QLineEdit(v.get("vorname",  ""))
        self._e_stufe       = QLineEdit(str(v.get("stufe", "")))
        self._e_stufenzus   = QLineEdit(str(v.get("stufenzusatz", "")))

        form.addRow("Nachname *:",           self._e_nachname)
        form.addRow("Vorname *:",            self._e_vorname)
        form.addRow(f"{self._sl}:",          self._e_stufe)
        form.addRow(f"{self._zl} (Kürzel):", self._e_stufenzus)

        layout.addLayout(form)
        layout.addWidget(QLabel(
            "<small>* Pflichtfelder. Weitere Felder und Wünsche können "
            "danach in der Tabelle eingetragen werden.</small>"
        ))

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._on_ok)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def _on_ok(self):
        if not self._e_nachname.text().strip():
            QMessageBox.warning(self, "Pflichtfeld", "Bitte einen Nachnamen eingeben.")
            self._e_nachname.setFocus()
            return
        if not self._e_vorname.text().strip():
            QMessageBox.warning(self, "Pflichtfeld", "Bitte einen Vornamen eingeben.")
            self._e_vorname.setFocus()
            return
        self.accept()

    def get_data(self) -> dict:
        stufe_text = self._e_stufe.text().strip()
        try:
            stufe_val = int(stufe_text)
        except ValueError:
            stufe_val = 0
        data = {
            "nachname":     self._e_nachname.text().strip(),
            "vorname":      self._e_vorname.text().strip(),
            "stufe":        stufe_val,
            "stufenzusatz": self._e_stufenzus.text().strip(),
            "geschlecht":   "-",
            "wunsch_1": 0, "wunsch_2": 0, "wunsch_3": 0,
            "wunsch_4": 0, "wunsch_5": 0,
            "projekt": 0,
        }
        return data


class ProjektHinzufuegenDialog(QDialog):
    """Popup zum Anlegen eines neuen Projekts / Angebots."""

    def __init__(self, parent=None, max_nummer: int = 0):
        super().__init__(parent)
        k = db.get_feldkonfig()
        pl = k.get("projekt_label", "Projekt")
        sl = k.get("stufe_label",   "Gruppenbereich")
        self.setWindowTitle(f"{pl} hinzufügen")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)

        # ── Grunddaten ──
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self._e_name    = QLineEdit()
        self._e_stmin   = QLineEdit("5")
        self._e_stmax   = QLineEdit("10")
        self._e_tnmin   = QLineEdit("5")
        self._e_tnmax   = QLineEdit("30")
        form.addRow(f"{db.get_label_formen(pl)['name']} *:", self._e_name)
        form.addRow(f"{sl} min:",              self._e_stmin)
        form.addRow(f"{sl} max:",              self._e_stmax)
        form.addRow("Plätze min:",             self._e_tnmin)
        form.addRow("Plätze max:",             self._e_tnmax)
        layout.addLayout(form)

        # ── Nummerierung ──
        nr_group = QGroupBox("Nummerierung")
        nr_layout = QVBoxLayout(nr_group)
        hat_daten = db.hat_zuteilungen_oder_wuensche()

        self._rb_fest = QRadioButton(
            f"Feste Nummer (Vorschlag: {max_nummer + 1} – Ende der Liste)")
        sort_label = (
            f"Einsortieren + alle {db.pluralisiere_label(pl)} neu nummerieren\n"
            f"(nach {sl} min → {sl} max → {pl}name)"
        )
        if hat_daten:
            sort_label += "\n⚠ Nicht möglich: Es gibt bereits Wünsche oder Zuteilungen."
        self._rb_sort = QRadioButton(sort_label)
        self._rb_fest.setChecked(True)
        self._rb_sort.setEnabled(not hat_daten)
        bg = QButtonGroup(self)
        bg.addButton(self._rb_fest)
        bg.addButton(self._rb_sort)
        self._spin_nr = QLineEdit(str(max_nummer + 1))
        self._spin_nr.setFixedWidth(80)

        fest_row = QHBoxLayout()
        fest_row.addWidget(self._rb_fest)
        fest_row.addWidget(self._spin_nr)
        fest_row.addStretch()
        nr_layout.addLayout(fest_row)
        nr_layout.addWidget(self._rb_sort)

        self._rb_fest.toggled.connect(
            lambda checked: self._spin_nr.setEnabled(checked))

        layout.addWidget(nr_group)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._on_ok)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def _on_ok(self):
        if not self._e_name.text().strip():
            QMessageBox.warning(self, "Pflichtfeld", "Bitte einen Namen eingeben.")
            self._e_name.setFocus()
            return
        if self._rb_fest.isChecked():
            try:
                int(self._spin_nr.text())
            except ValueError:
                QMessageBox.warning(self, "Ungültige Nummer",
                                    "Bitte eine gültige Ganzzahl eingeben.")
                self._spin_nr.setFocus()
                return
        self.accept()

    def get_data(self) -> dict:
        def _int(s, default=0):
            try: return int(s.strip())
            except ValueError: return default
        return {
            "projektname": self._e_name.text().strip(),
            "stufenmin":   _int(self._e_stmin.text()),
            "stufenmax":   _int(self._e_stmax.text(), 99),
            "tnmin":       _int(self._e_tnmin.text(), 5),
            "tnmax":       _int(self._e_tnmax.text(), 30),
        }

    def get_nummer(self) -> int | None:
        """None = einsortieren+neu nummerieren, sonst feste Nummer."""
        if self._rb_fest.isChecked():
            try: return int(self._spin_nr.text())
            except ValueError: return None
        return None

    def get_einsortieren(self) -> bool:
        return self._rb_sort.isChecked()


class UeberDialog(QDialog):
    """Hilfe → Über Mitmach-Lotse."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Über Mitmach-Lotse")
        self.setMinimumWidth(480)
        self.setModal(True)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # App-Name und Version
        lbl_name = QLabel("<h2>Mitmach-Lotse</h2>")
        lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_name)

        lbl_version = QLabel("Version 1.0")
        lbl_version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_version)

        layout.addWidget(_trennlinie())

        # Beschreibung
        lbl_desc = QLabel(
            "Mitmach-Lotse ist ein Zuordnungsprogramm, das die Verteilung von "
            "Personen auf Angebote, Kurse, Arbeitsgruppen oder ähnliche Einheiten "
            "automatisiert. Die Software löst dieses logistische Verteilungsproblem "
            "mathematisch über optimierte Matching-Algorithmen, die individuelle "
            "Wünsche berücksichtigen. Mitmach-Lotse ist universell und "
            "branchenübergreifend einsetzbar, um den administrativen Aufwand bei "
            "der Gruppenbildung zu minimieren und eine transparente, "
            "unvoreingenommene Zuteilung zu garantieren."
        )
        lbl_desc.setWordWrap(True)
        layout.addWidget(lbl_desc)

        layout.addWidget(_trennlinie())

        # Autor, Lizenz, Entwicklungshinweis
        AUTOR = "Clemens Arnold"

        meta = QLabel(
            f"<b>Autor:</b> {AUTOR}<br>"
            "<b>Lizenz:</b> GNU General Public License v3.0 (GPL-3.0)<br>"
            "<b>Entwicklung:</b> Entwickelt mit Claude (Anthropic)"
        )
        meta.setWordWrap(True)
        layout.addWidget(meta)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        bb.accepted.connect(self.accept)
        layout.addWidget(bb)


def _trennlinie():
    """Hilfsfunktion: horizontale Trennlinie für Dialoge."""
    from PyQt6.QtWidgets import QFrame
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    return line


class QualitaetspruefungDialog(QDialog):
    """
    Nicht-modales Fenster: Qualitätsprüfung Wunscheingaben.
    Zeigt vier Kategorien von Problemen, die per Checkbox aus-/eingeblendet
    werden können. Doppelklick springt zur Person im Hauptfenster.
    """

    # Signal: Teilnehmer-ID, die im Hauptfenster markiert werden soll
    person_angefordert = pyqtSignal(int)

    def __init__(self, parent=None, nur_ids: list = None):
        super().__init__(parent)
        import database as _db
        _k  = _db.get_feldkonfig()
        self._max_w  = _k.get("max_wuensche", 5)
        self._pl     = _k.get("projekt_label", "Option")
        self._plP_qp = _db.pluralisiere_label(self._pl)
        self._nur_ids = nur_ids
        titel = "Qualitätsprüfung Wunscheingaben"
        if nur_ids is not None:
            titel += " – nur importierte Datensätze"
        self.setWindowTitle(titel)
        self.setMinimumSize(720, 540)
        self.setModal(False)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )

        layout = QVBoxLayout(self)

        # ── Hinweis ──
        hinweis = QLabel(
            f"<b>Hinweis:</b> Mehrfachnennungen derselben {self._pl} können <i>bewusst</i> "
            f"eingesetzt werden, um Teilnehmer/innen gezielt in bestimmte {self._plP_qp} "
            "einzuplanen (z. B. auf Wunsch von Gruppenverantwortlichen). Sie sind daher "
            "möglicherweise nur optionale Hinweise, keine Fehler."
        )
        hinweis.setWordWrap(True)
        hinweis.setStyleSheet("background:#fff8dc;padding:6px;border-radius:4px;")
        layout.addWidget(hinweis)

        # ── Filter-Checkboxen ──
        filter_row = QHBoxLayout()
        self._cb_unzulaessig    = QCheckBox("Unzulässige Wünsche")
        self._cb_unvollstaendig = QCheckBox(f"Weniger als {self._max_w} Wünsche")
        self._cb_null           = QCheckBox("Keine Wünsche (alles 0)")
        self._cb_mehrfach       = QCheckBox(f"{self._pl} mehrmals genannt")
        for cb in (self._cb_unzulaessig, self._cb_unvollstaendig,
                   self._cb_null, self._cb_mehrfach):
            cb.setChecked(True)
            cb.toggled.connect(self._refresh_table)
            filter_row.addWidget(cb)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        # ── Tabelle ──
        self._table = QTableWidget()
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.doubleClicked.connect(self._on_doppelklick)
        layout.addWidget(self._table)

        # ── Buttons ──
        btn_row = QHBoxLayout()
        btn_aktualisieren = QPushButton("Aktualisieren")
        btn_aktualisieren.clicked.connect(self._lade_daten)
        btn_drucken = QPushButton("Drucken")
        btn_drucken.clicked.connect(self._drucken)
        btn_vorschau = QPushButton("Druckvorschau")
        btn_vorschau.clicked.connect(self._druckvorschau)
        btn_export = QPushButton("Exportieren")
        btn_export.clicked.connect(self._exportieren)
        btn_schliessen = QPushButton("Schließen")
        btn_schliessen.clicked.connect(self.close)
        self._lbl_anzahl = QLabel("")
        btn_row.addWidget(btn_aktualisieren)
        btn_row.addWidget(btn_drucken)
        btn_row.addWidget(btn_vorschau)
        btn_row.addWidget(btn_export)
        btn_row.addStretch()
        btn_row.addWidget(self._lbl_anzahl)
        btn_row.addWidget(btn_schliessen)
        layout.addLayout(btn_row)

        self._daten = {}
        self._lade_daten()

    def _lade_daten(self):
        import listenabfragen as la
        self._daten = la.get_qualitaetspruefung(self._max_w, nur_ids=self._nur_ids)
        self._refresh_table()

    def _refresh_table(self):
        from PyQt6.QtGui import QColor, QFont
        # Spalten: Kategorie | Name | Gruppe | W1..Wn | Details
        wunsch_cols = [f"W{i}" for i in range(1, self._max_w + 1)]
        headers = ["Kategorie", "Name", "Gruppe"] + wunsch_cols + ["Details"]
        n_cols = len(headers)
        self._table.setColumnCount(n_cols)
        self._table.setHorizontalHeaderLabels(headers)
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(1, hh.ResizeMode.Stretch)           # Name
        hh.setSectionResizeMode(n_cols - 1, hh.ResizeMode.Stretch)  # Details
        for i in range(3, 3 + self._max_w):
            hh.setSectionResizeMode(i, hh.ResizeMode.ResizeToContents)

        # Teilnehmerdaten für Wunschanzeige vorholen
        import database as _db
        tn_by_id = {t["id"]: t for t in _db.get_all_teilnehmer()}
        projekte  = {p["nummer"]: p["projektname"]
                     for p in _db.get_all_projekte()}

        def wunsch_label(w: int) -> str:
            if w == 0:
                return ""
            return str(w)

        rows = []
        from collections import defaultdict

        if self._cb_unzulaessig.isChecked():
            gruppiert = defaultdict(list)
            for e in self._daten.get("unzulaessig", []):
                gruppiert[e["id"]].append(e)
            for tid, eintraege in gruppiert.items():
                erste = eintraege[0]
                t = tn_by_id.get(tid, {})
                raenge_betroffen = {e["rang"] for e in eintraege}
                wuensche = []
                for i in range(1, self._max_w + 1):
                    text = wunsch_label(t.get(f"wunsch_{i}", 0))
                    if i in raenge_betroffen and text:
                        text += " ⚠"
                    wuensche.append(text)
                details = "; ".join(
                    f"W{e['rang']}: {self._pl} {e['option_nr']} – {e['grund']}"
                    for e in eintraege
                )
                rows.append((tid, "⚠", "⚠ Unzulässig",
                             erste["name"], erste["gruppe"], wuensche, details))

        if self._cb_unvollstaendig.isChecked():
            for e in self._daten.get("unvollstaendig", []):
                t = tn_by_id.get(e["id"], {})
                wuensche = []
                for i in range(1, self._max_w + 1):
                    w = t.get(f"wunsch_{i}", 0)
                    wuensche.append("⚠" if w == 0 else str(w))
                rows.append((e["id"], "✎", "✎ Unvollständig",
                             e["name"], e["gruppe"], wuensche,
                             f"{e['anzahl']} von {e['max']} ausgefüllt"))

        if self._cb_null.isChecked():
            for e in self._daten.get("null", []):
                rows.append((e["id"], "○", "○ Keine Wünsche",
                             e["name"], e["gruppe"],
                             ["⚠"] * self._max_w, "Alle Wünsche = 0"))

        if self._cb_mehrfach.isChecked():
            gruppiert = defaultdict(list)
            for e in self._daten.get("mehrfach", []):
                gruppiert[e["id"]].append(e)
            for tid, alle in gruppiert.items():
                erste = alle[0]
                t = tn_by_id.get(tid, {})
                raenge_betroffen = set()
                for x in alle:
                    raenge_betroffen.update(x["raenge"])
                wuensche = []
                for i in range(1, self._max_w + 1):
                    text = wunsch_label(t.get(f"wunsch_{i}", 0))
                    if i in raenge_betroffen and text:
                        text += " ⚠"
                    wuensche.append(text)
                details = "; ".join(
                    f"{self._pl} {x['option_nr']} ({'/ '.join(f'W{r}' for r in x['raenge'])})"
                    for x in alle
                )
                rows.append((tid, "↻", "↻ Mehrfach",
                             erste["name"], erste["gruppe"], wuensche, details))

        self._table.setRowCount(len(rows))
        self._row_ids = []
        farben = {}  # keine unterschiedlichen Farben mehr
        schrift_farben = {}  # keine unterschiedlichen Schriftfarben

        for r, (tid, symbol, kat, name, gruppe, wuensche, details) in enumerate(rows):
            self._row_ids.append(tid)
            bg  = farben.get(symbol, QColor("#ffffff"))
            sfg = schrift_farben.get(symbol)
            for c, val in enumerate([kat, name, gruppe] + wuensche + [details]):
                item = QTableWidgetItem(val)
                item.setBackground(bg)
                if sfg:
                    item.setForeground(sfg)
                self._table.setItem(r, c, item)
            self._table.setRowHeight(r, 22)

        total = sum(len(v) for v in self._daten.values())
        self._lbl_anzahl.setText(
            f"{len(rows)} Einträge angezeigt (gesamt: {total})"
        )

    def _on_doppelklick(self, index):
        row = index.row()
        if 0 <= row < len(self._row_ids):
            self.person_angefordert.emit(self._row_ids[row])

    def _build_print_html(self) -> str:
        wunsch_headers = "".join(
            f"<th>W{i}</th>" for i in range(1, self._max_w + 1)
        )
        rows_html = ""
        for r in range(self._table.rowCount()):
            items = [self._table.item(r, c) for c in range(self._table.columnCount())]
            vals  = [it.text() if it else "" for it in items]
            kat   = vals[0] if vals else ""
            farbe = "#c0392b" if kat.startswith("⚠") else "#222"
            cells = "".join(f"<td>{v}</td>" for v in vals)
            rows_html += f"<tr style='color:{farbe}'>{cells}</tr>"
        wunsch_th = "".join(f"<th>W{i}</th>" for i in range(1, self._max_w + 1))
        return f"""<!DOCTYPE html><html><head><meta charset='UTF-8'>
<style>body{{font-family:Arial,sans-serif;font-size:8pt}}
table{{border-collapse:collapse;width:100%}}
th{{background:#4472C4;color:#fff;padding:2px 5px;text-align:left;font-size:7.5pt}}
td{{padding:2px 5px;border-bottom:1px solid #ddd;font-size:7.5pt}}
tr:nth-child(even) td{{background:#f8f8f8}}
h2{{font-size:11pt;margin-bottom:3pt}}</style></head><body>
<h2>Qualitätsprüfung Wunscheingaben</h2>
<table><thead><tr>
<th>Kategorie</th><th>Name</th><th>Gruppe</th>{wunsch_th}<th>Details</th>
</tr></thead><tbody>{rows_html}</tbody></table></body></html>"""

    def _drucken(self):
        from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
        from PyQt6.QtGui import QTextDocument
        printer = QPrinter(QPrinter.PrinterMode.ScreenResolution)
        dlg = QPrintDialog(printer, self)
        if dlg.exec() != QPrintDialog.DialogCode.Accepted:
            return
        doc = QTextDocument()
        doc.setHtml(self._build_print_html())
        getattr(doc, 'print')(printer)

    def _druckvorschau(self):
        from PyQt6.QtPrintSupport import QPrinter, QPrintPreviewDialog
        from PyQt6.QtGui import QTextDocument
        printer = QPrinter(QPrinter.PrinterMode.ScreenResolution)
        dlg = QPrintPreviewDialog(printer, self)
        def _render(p):
            doc = QTextDocument()
            doc.setHtml(self._build_print_html())
            getattr(doc, 'print')(p)
        dlg.paintRequested.connect(_render)
        dlg.exec()

    def _exportieren(self):
        from PyQt6.QtWidgets import QFileDialog
        pfad, _ = QFileDialog.getSaveFileName(
            self, "Qualitätsprüfung exportieren",
            "Qualitaetspruefung.pdf",
            "PDF (*.pdf);;Excel (*.xlsx);;CSV (*.csv)"
        )
        if not pfad:
            return
        # Tabelleninhalt als Gruppen aufbereiten
        wunsch_headers = [f"W{i}" for i in range(1, self._max_w + 1)]
        col_headers = ["Kategorie", "Name", "Gruppe"] + wunsch_headers + ["Details"]
        rows = []
        for r in range(self._table.rowCount()):
            row = [self._table.item(r, c).text() if self._table.item(r, c) else ""
                   for c in range(self._table.columnCount())]
            rows.append(row)
        gruppen = [("Qualitätsprüfung Wunscheingaben", col_headers, rows)]
        import importexport as _ie
        ext = pfad.rsplit(".", 1)[-1].lower() if "." in pfad else "pdf"
        if ext not in ("pdf", "xlsx", "ods", "csv"):
            ext = "pdf"
            pfad += ".pdf"
        try:
            _ie.export_gruppen(pfad, ext, gruppen, kopfzeile="", datum_fusszeile=False)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Export erfolgreich",
                                    f"Gespeichert:\n{pfad}")
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Exportfehler", str(e))


class TabellenAssistentDialog(QDialog):
    """
    Mehrstufiger Assistent für den Workflow "Tabellen extern ausfüllen
    lassen": erklärt Schritt für Schritt, wie Tabellen für die Zuteilung
    eingerichtet, für externe Bearbeitung exportiert und die
    ausgefüllten Dateien anschließend wieder importiert werden — und
    öffnet an den passenden Stellen die dafür vorhandenen Dialoge
    (Gesamtliste exportieren, Teilnehmer/innen importieren) direkt aus
    dem Hauptfenster heraus.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hauptfenster = parent
        k = db.get_feldkonfig()
        self._sl  = k.get("stufe_label", "Gruppenbereich")
        self._pl  = k.get("projekt_label", "Option")
        self._plP = db.pluralisiere_label(self._pl)

        self.setWindowTitle("Tabellen-Export- und Importassistent")
        self.setMinimumSize(620, 520)
        # Bewusst NICHT anwendungsmodal: Der Assistent öffnet im letzten
        # Schritt ein eigenständiges, nicht-modales Qualitätsprüfungsfenster.
        # Ein anwendungsmodaler Assistent würde sich danach automatisch
        # wieder davor schieben. Aus demselben Grund wird der Assistent
        # über show() statt exec() geöffnet (siehe hauptfenster.py).
        self.setModal(False)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )

        outer = QVBoxLayout(self)

        self.lbl_schritt = QLabel()
        self.lbl_schritt.setAlignment(Qt.AlignmentFlag.AlignRight)
        outer.addWidget(self.lbl_schritt)

        self.stack = QStackedWidget()
        outer.addWidget(self.stack)
        self._baue_seite_einfuehrung()
        self._baue_seite_tabellen()
        self._baue_seite_export()
        self._baue_seite_extern()
        self._baue_seite_reimport()

        nav = QHBoxLayout()
        self.btn_zurueck = QPushButton("◀ Zurück")
        self.btn_weiter  = QPushButton("Weiter ▶")
        self.btn_fertig  = QPushButton("✓ Fertig")
        nav.addWidget(self.btn_zurueck)
        nav.addStretch()
        nav.addWidget(self.btn_weiter)
        nav.addWidget(self.btn_fertig)
        outer.addLayout(nav)

        self.btn_zurueck.clicked.connect(self._zurueck)
        self.btn_weiter.clicked.connect(self._weiter)
        self.btn_fertig.clicked.connect(self.accept)

        self._update_nav()

    # ── Navigation ────────────────────────────────────────────────────────────

    def _update_nav(self):
        i = self.stack.currentIndex()
        n = self.stack.count()
        self.lbl_schritt.setText(f"Schritt {i + 1} von {n}")
        self.btn_zurueck.setEnabled(i > 0)
        self.btn_weiter.setVisible(i < n - 1)
        self.btn_fertig.setVisible(i == n - 1)
        # Auf den Seiten mit optionaler Aktion (Tabellen einrichten,
        # Exportieren) macht der Button deutlich, dass "Weiter" den
        # Schritt auch ohne Aktion überspringt.
        if i in (1, 2):
            self.btn_weiter.setText("Weiter / Schritt überspringen ▶")
        else:
            self.btn_weiter.setText("Weiter ▶")

    def _weiter(self):
        self.stack.setCurrentIndex(self.stack.currentIndex() + 1)
        self._update_nav()

    def _zurueck(self):
        self.stack.setCurrentIndex(self.stack.currentIndex() - 1)
        self._update_nav()

    # ── Seiten ────────────────────────────────────────────────────────────────

    def _baue_seite_einfuehrung(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(12)
        lay.setContentsMargins(24, 20, 24, 20)

        titel = QLabel(
            "<span style='font-size:16pt;font-weight:bold;color:#1F3864;'>"
            "Tabellen extern ausfüllen lassen</span>"
        )
        titel.setTextFormat(Qt.TextFormat.RichText)
        titel.setWordWrap(True)

        text = QLabel(
            "Dieser Assistent führt durch den kompletten Weg, wenn Wünsche "
            f"nicht direkt in der App, sondern extern eingetragen werden "
            f"sollen &#8211; zum Beispiel durch Tutoren, Klassenlehrkräfte "
            f"oder andere Gruppenverantwortliche:<br><br>"
            "<b>1. Tabellen einrichten</b> &#8211; Spaltenbezeichnungen und "
            f"die {self._plP}-Liste stehen fest.<br>"
            "<b>2. Exportieren</b> &#8211; als Tabelle(n), die extern "
            "bearbeitet werden können.<br>"
            "<b>3. Extern ausfüllen lassen</b> &#8211; z. B. über eine "
            "geteilte Cloud.<br>"
            "<b>4. Reimportieren</b> &#8211; die ausgefüllten Dateien "
            "fließen wieder in die Planungsmappe ein.<br><br>"
            "Ein typisches Szenario: Für jede Teilnehmergruppe wird eine "
            "eigene Datei exportiert und in einem Zielverzeichnis "
            "abgelegt, das über eine Cloud mit den jeweiligen "
            "Gruppenverantwortlichen geteilt wird. Diese übernehmen dann "
            "die organisatorische Aufgabe, die Wünsche ihrer Gruppe "
            "vollständig einzusammeln und dabei bereits ein Auge auf deren "
            "Zulässigkeit zu werfen."
        )
        text.setWordWrap(True)
        text.setTextFormat(Qt.TextFormat.RichText)

        lay.addWidget(titel)
        lay.addWidget(text)
        lay.addStretch()
        self.stack.addWidget(w)

    def _baue_seite_tabellen(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(12)
        lay.setContentsMargins(24, 20, 24, 20)

        lbl = QLabel(
            "<b>Schritt 2 von 5 &#8211; Tabellen einrichten</b><br><br>"
            "Bevor exportiert wird, sollten folgende Punkte feststehen:"
        )
        lbl.setWordWrap(True)
        lbl.setTextFormat(Qt.TextFormat.RichText)

        liste = QLabel(
            f"&#8226; <b>Spaltenbezeichnungen</b>: {self._sl}, "
            f"Gruppenzusatz, {self._pl}-Bezeichnung usw. sind so benannt, "
            "wie sie in der Einrichtung oder für das Veranstaltungsprogramm "
            "gebräuchlich sind.<br>"
            f"&#8226; <b>{self._plP}-Liste</b>: Alle {self._plP} mit "
            "Nummer, Name und Platzzahl/Zulassungsbereich sind bereits "
            "angelegt &#8211; nur so lässt sich später prüfen, ob ein "
            "eingetragener Wunsch zulässig ist.<br>"
            f"&#8226; <b>Teilnehmer/innen-Grunddaten</b>: Name und "
            f"{self._sl} (Gruppenzugehörigkeit) sind erfasst &#8211; die "
            "Wunschspalten können zu diesem Zeitpunkt noch leer sein."
        )
        liste.setWordWrap(True)
        liste.setTextFormat(Qt.TextFormat.RichText)

        btn_spalten = QPushButton("Spaltenbezeichnungen anpassen …")
        btn_spalten.clicked.connect(self._oeffne_spaltenbezeichnungen)

        lay.addWidget(lbl)
        lay.addWidget(liste)
        lay.addSpacing(8)
        lay.addWidget(btn_spalten)
        lay.addStretch()
        self.stack.addWidget(w)

    def _baue_seite_export(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(12)
        lay.setContentsMargins(24, 20, 24, 20)

        lbl = QLabel(
            "<b>Schritt 3 von 5 &#8211; Exportieren</b><br><br>"
            "&#8222;Gesamtliste exportieren&#8220; erstellt eine Tabelle "
            "mit allen Teilnehmer/innen und ihren (noch leeren) "
            "Wunschspalten. Wichtig: Die Option &#8222;Jede Gruppe als "
            "separate Datei&#8220; erzeugt, wenn ausgewählt, für jede "
            "Gruppe eine eigene, kompakte Datei."
        )
        lbl.setWordWrap(True)
        lbl.setTextFormat(Qt.TextFormat.RichText)

        hinweis = QLabel(
            "<i>Praxisbeispiel:</i> Sie als Koordinator/in speichern die "
            "Einzeldateien je Gruppe in einem Zielverzeichnis, das über "
            "eine Cloud mit den Gruppenverantwortlichen geteilt wird. "
            "Diese sammeln dann die Wünsche ihrer Gruppe vollständig ein "
            "und achten dabei bereits auf die Zulässigkeit der Wünsche."
        )
        hinweis.setWordWrap(True)
        hinweis.setTextFormat(Qt.TextFormat.RichText)
        hinweis.setStyleSheet("background:#eaf2fb;padding:6px;border-radius:4px;")

        btn_export = QPushButton("Gesamtliste exportieren …")
        btn_export.clicked.connect(self._oeffne_export)

        lay.addWidget(lbl)
        lay.addWidget(hinweis)
        lay.addSpacing(8)
        lay.addWidget(btn_export)
        lay.addStretch()
        self.stack.addWidget(w)

    def _baue_seite_extern(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(12)
        lay.setContentsMargins(24, 20, 24, 20)

        lbl = QLabel(
            "<b>Schritt 4 von 5 &#8211; Extern ausfüllen lassen</b><br><br>"
            "Dieser Schritt findet außerhalb der App statt und erfordert "
            "hier keine Aktion:"
        )
        lbl.setWordWrap(True)
        lbl.setTextFormat(Qt.TextFormat.RichText)

        liste = QLabel(
            "&#8226; Die Datei(en) an die zuständigen Personen weitergeben "
            "(z. B. per Cloud-Freigabe, E-Mail-Anhang oder Ausdruck).<br>"
            "&#8226; Format .xlsx und .ods lassen sich mit Excel, "
            "LibreOffice Calc und den meisten Office-Apps bearbeiten.<br>"
            f"&#8226; Struktur (Spaltenüberschriften, {self._sl}-Angabe) "
            "bitte unverändert lassen, damit der Reimport funktioniert.<br>"
            "&#8226; Wichtig für die ausfüllende Person: Wünsche "
            f"vollständig eintragen und möglichst nur zulässige "
            f"{self._plP} für die jeweilige {self._sl}-Zugehörigkeit "
            "wählen."
        )
        liste.setWordWrap(True)
        liste.setTextFormat(Qt.TextFormat.RichText)

        hinweis = QLabel(
            f"<i>Hinweis:</i> Wenn eine Person von vornherein einer "
            f"bestimmten {self._pl} zugeordnet werden soll, dann bei jedem "
            f"Wunsch die Nummer dieser {self._pl} eintragen."
        )
        hinweis.setWordWrap(True)
        hinweis.setTextFormat(Qt.TextFormat.RichText)
        hinweis.setStyleSheet("background:#eaf2fb;padding:6px;border-radius:4px;")

        lay.addWidget(lbl)
        lay.addWidget(liste)
        lay.addWidget(hinweis)
        lay.addStretch()
        self.stack.addWidget(w)

    def _baue_seite_reimport(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(12)
        lay.setContentsMargins(24, 20, 24, 20)

        lbl = QLabel(
            "<b>Schritt 5 von 5 &#8211; Reimportieren</b><br><br>"
            "Die ausgefüllten Dateien werden über &#8222;Teilnehmer/innen "
            "importieren&#8220; wieder eingelesen. Kommen mehrere Dateien "
            "zurück (z. B. eine je Gruppe), lässt sich dort die Checkbox "
            "&#8222;Mehrere Dateien zusammenführen&#8220; aktivieren, um "
            "sie in einem Schritt zusammenzuführen."
        )
        lbl.setWordWrap(True)
        lbl.setTextFormat(Qt.TextFormat.RichText)

        hinweis = QLabel(
            "Nach dem Import lohnt sich ein Blick in die "
            "<b>Qualitätsprüfung Wunscheingaben</b> (Auswertungs-Tab): Sie "
            "zeigt unzulässige, unvollständige oder mehrfach genannte "
            f"{self._plP} übersichtlich an."
        )
        hinweis.setWordWrap(True)
        hinweis.setTextFormat(Qt.TextFormat.RichText)
        hinweis.setStyleSheet("background:#eaf2fb;padding:6px;border-radius:4px;")

        btn_import = QPushButton("Teilnehmer/innen importieren …")
        btn_import.clicked.connect(self._oeffne_import)

        lay.addWidget(lbl)
        lay.addWidget(hinweis)
        lay.addSpacing(8)
        lay.addWidget(btn_import)
        lay.addStretch()
        self.stack.addWidget(w)

    # ── Aktionen (delegieren an bestehende Dialoge im Hauptfenster) ────────────

    def _oeffne_spaltenbezeichnungen(self):
        if self._hauptfenster and hasattr(self._hauptfenster,
                                          "_spaltenbezeichnungen_anpassen"):
            self._hauptfenster._spaltenbezeichnungen_anpassen()

    def _oeffne_export(self):
        if self._hauptfenster and hasattr(self._hauptfenster,
                                          "_export_gesamtliste"):
            self._hauptfenster._export_gesamtliste("klassen")

    def _oeffne_import(self):
        if self._hauptfenster and hasattr(self._hauptfenster, "_import"):
            # Vorherige Referenz zurücksetzen, damit unten nicht versehentlich
            # ein Fenster aus einem früheren Durchlauf angehoben wird.
            self._hauptfenster._qualitaet_fenster_nach_import = None
            self._hauptfenster._import("schueler")
            # Der Assistent ist als anwendungsmodaler Dialog geöffnet und
            # würde nach dem Schließen von ImportDialog sonst automatisch
            # wieder in den Vordergrund rücken und das (nicht-modale)
            # Qualitätsprüfungsfenster verdecken -- daher hier explizit
            # erneut anheben.
            qdlg = getattr(self._hauptfenster, "_qualitaet_fenster_nach_import", None)
            if qdlg is not None and qdlg.isVisible():
                qdlg.raise_()
                qdlg.activateWindow()
