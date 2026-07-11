#!/bin/bash
# Startskript für Mitmach-Lotse
# Stellt sicher, dass PyQt6 und openpyxl installiert sind

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Mitmach-Lotse ==="

# Python prüfen
if ! command -v python3 &>/dev/null; then
    echo "FEHLER: Python 3 ist nicht installiert."
    echo "Bitte installieren: sudo apt install python3"
    exit 1
fi

# pip prüfen und Abhängigkeiten installieren
echo "Prüfe Abhängigkeiten..."
python3 -m pip install --quiet --user PyQt6 openpyxl 2>/dev/null || \
python3 -m pip install --quiet PyQt6 openpyxl 2>/dev/null

# App starten
echo "Starte App..."
python3 mitmachlotse.py
