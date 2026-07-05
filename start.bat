@echo off
REM Startskript für Windows
cd /d "%~dp0"

echo === Projekttage-Einteilungsprogramm ===

REM Python prüfen
python --version >nul 2>&1
if errorlevel 1 (
    echo FEHLER: Python ist nicht installiert.
    echo Bitte herunterladen von https://www.python.org
    pause
    exit /b 1
)

echo Prüfe Abhängigkeiten...
python -m pip install --quiet PyQt6 openpyxl

echo Starte App...
python mitmachlotse.py
