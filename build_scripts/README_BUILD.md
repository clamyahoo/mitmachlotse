# Mitmach-Lotse – Pakete erstellen

| Plattform | Skript | Ergebnis |
|---|---|---|
| Linux (Debian/Ubuntu) | `build_linux_deb.sh` | `.deb`-Paket |
| Linux (distributionsunabhängig) | `build_linux_appimage.sh` | `.AppImage` |
| Windows | `build_windows.bat` | Ordner `Mitmach-Lotse\` mit `.exe` (als ZIP verteilen) |
| macOS | `build_macos.sh` | `.dmg` |
| Flatpak | `flatpak/` | Flatpak-Manifest |

## Linux .deb
```bash
bash build_scripts/build_linux_deb.sh
sudo dpkg -i projekttage-verwaltung_1.0.0_all.deb
```

## Linux AppImage
```bash
bash build_scripts/build_linux_appimage.sh
chmod +x build_scripts/dist/Mitmach-Lotse-x86_64.AppImage
./build_scripts/dist/Mitmach-Lotse-x86_64.AppImage

## Windows
Doppelklick auf `build_scripts/build_windows.bat` (Python muss installiert sein).

Ergebnis ist der **Ordner** `build_scripts\dist\windows\Mitmach-Lotse\` mit
`Mitmach-Lotse.exe` und dem Unterordner `_internal`. Zum Weitergeben den
**ganzen Ordner** als ZIP packen — die `.exe` läuft nur mit dem daneben
liegenden `_internal`.

Bewusst **Onedir** (Ordner) statt einer einzelnen `.exe`: Die Einzeldatei
(Onefile) entpackt sich bei jedem Start in den `%TEMP%`-Ordner und lädt die
DLLs von dort. Verwaltete Firmenrechner sperren die Ausführung aus `%TEMP%`
oft (AppLocker o. ä.), was zu „DLL"-Ladefehlern führt. Beim Onedir-Build
liegen die DLLs direkt neben der `.exe`, ohne Temp-Entpacken.

Der Build läuft auch automatisch in der Cloud: GitHub Actions
(`.github/workflows/build.yml`) baut bei jedem Push auf `main` und lädt das
Ergebnis als ZIP-Artefakt hoch — kein eigener Windows-Rechner nötig.

Falls beim manuellen Build in cmd „`pyinstaller` wird nicht als Befehl
erkannt" erscheint: Das ist ein PATH-Problem (der Scripts-Ordner von Python
fehlt im PATH). Die `.bat` umgeht das bereits, indem sie PyInstaller als
Modul aufruft (`python -m PyInstaller …`).

## macOS
```bash
bash build_scripts/build_macos.sh
# Optional für .dmg: brew install create-dmg
```

## Dateiendung .plf
Die App verwendet `.plf` als primäres Format (technisch identisch mit `.db` = SQLite).
Das .deb-Paket registriert `.plf` automatisch im System.
