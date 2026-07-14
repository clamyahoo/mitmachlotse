@echo off
echo Mitmach-Lotse -- Windows-Build
REM PyInstaller als Python-Modul installieren/aufrufen (python -m ...), damit
REM der Build NICHT vom PATH-Eintrag des Scripts-Ordners abhaengt -- sonst
REM scheitert "pyinstaller" haeufig mit "Befehl nicht gefunden", obwohl es
REM installiert ist.
python -m pip install PyQt6 openpyxl odfpy pyinstaller --quiet
cd /d "%~dp0.."
python -m PyInstaller build_scripts\projekttage.spec --distpath build_scripts\dist\windows --workpath build_scripts\build\windows --noconfirm
echo.
echo Fertig. Ergebnis ist der ORDNER:
echo   build_scripts\dist\windows\Mitmach-Lotse\
echo Darin liegt Mitmach-Lotse.exe -- der GANZE Ordner muss zusammen
echo weitergegeben werden (z. B. als ZIP gepackt). Die .exe laeuft nur
echo mit dem daneben liegenden Unterordner _internal.
pause
