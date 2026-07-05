"""
Mitmach-Lotse-Programm
Startdatei: python mitmachlotse.py
"""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from hauptfenster import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Projekttage")
    app.setOrganizationName("Schule")
    app.setStyle("Fusion")

    # App-Palette NACH setStyle() setzen – Fusion liest diese für
    # alle Dropdown-Selektionen. Stylesheet kann danach für
    # einzelne Widgets (z. B. Tabellen) überschreiben.
    from PyQt6.QtGui import QPalette, QColor
    pal = app.palette()
    for grp in (QPalette.ColorGroup.Active,
                QPalette.ColorGroup.Inactive,
                QPalette.ColorGroup.Normal):
        pal.setColor(grp, QPalette.ColorRole.Highlight,
                     QColor("#000000"))          # Dropdown-Hintergrund: schwarz
        pal.setColor(grp, QPalette.ColorRole.HighlightedText,
                     QColor("#ffffff"))          # Dropdown-Text: weiß
    app.setPalette(pal)

    # Helles, professionelles Stylesheet
    app.setStyleSheet("""
        QMainWindow {
            background-color: #f5f5f5;
        }
        QMenuBar {
            background-color: #2c3e50;
            color: white;
            font-size: 13px;
            padding: 2px;
        }
        QMenuBar::item:selected {
            background-color: #3d5166;
        }
        QMenu {
            background-color: #ffffff;
            border: 1px solid #ccc;
            font-size: 13px;
        }
        QMenu::item:selected {
            background-color: #2980b9;
            color: white;
        }
        QTabWidget::pane {
            border: 1px solid #ccc;
            background: white;
        }
        QTabBar::tab {
            background: #dde3ea;
            padding: 6px 16px;
            margin-right: 2px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            font-size: 13px;
        }
        QTabBar::tab:selected {
            background: white;
            font-weight: bold;
            color: #2c3e50;
        }
        QTableWidget {
            gridline-color: #e0e0e0;
            font-size: 12px;
        }
        QTableWidget::item:alternate {
            background-color: #f0f4f8;
        }
        QTableWidget::item:selected,
        QTableWidget::item:alternate:selected {
            background-color: #2980b9;
            color: #ffffff;
        }
        QTableWidget::item:selected:!active,
        QTableWidget::item:alternate:selected:!active {
            background-color: #5499c7;
            color: #ffffff;
        }
        QHeaderView::section {
            background-color: #2c3e50;
            color: white;
            padding: 5px;
            font-size: 12px;
            font-weight: bold;
            border: none;
        }
        QPushButton {
            background-color: #2980b9;
            color: white;
            border: none;
            padding: 6px 14px;
            border-radius: 4px;
            font-size: 12px;
        }
        QPushButton:hover {
            background-color: #3498db;
        }
        QPushButton:pressed {
            background-color: #1c6ea4;
        }
        QLineEdit {
            border: 1px solid #bbb;
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 13px;
            background: white;
        }
        QLineEdit:focus {
            border: 1px solid #2980b9;
        }
        QStatusBar {
            background-color: #ecf0f1;
            color: #555;
            font-size: 12px;
        }
        QGroupBox {
            font-weight: bold;
            border: 1px solid #ccc;
            border-radius: 4px;
            margin-top: 8px;
            padding-top: 8px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 8px;
            color: #2c3e50;
        }
        QComboBox {
            border: 1px solid #bbb;
            border-radius: 4px;
            padding: 3px 8px;
            background: white;
            font-size: 12px;
        }
        QComboBox:focus {
            border: 1px solid #2980b9;
        }
        QCheckBox {
            font-size: 12px;
        }
        QRadioButton {
            font-size: 12px;
        }
        QLabel {
            font-size: 12px;
        }
        QMessageBox {
            font-size: 13px;
        }
    """)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
