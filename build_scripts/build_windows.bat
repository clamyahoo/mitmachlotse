@echo off
echo Mitmach-Lotse -- Windows-Build
pip install PyQt6 openpyxl odfpy pyinstaller --quiet
cd /d "%~dp0.."
pyinstaller build_scripts\projekttage.spec --distpath build_scripts\dist\windows --workpath build_scripts\build\windows --noconfirm
echo Fertig: build_scripts\dist\windows\Mitmach-Lotse.exe
pause
