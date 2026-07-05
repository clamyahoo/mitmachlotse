# Mitmach-Lotse – Pakete erstellen

| Plattform | Skript | Ergebnis |
|---|---|---|
| Linux (Debian/Ubuntu) | `build_linux_deb.sh` | `.deb`-Paket |
| Windows | `build_windows.bat` | `.exe` |
| macOS | `build_macos.sh` | `.dmg` |
| Flatpak | `flatpak/` | Flatpak-Manifest |

## Linux .deb
```bash
bash build_scripts/build_linux_deb.sh
sudo dpkg -i projekttage-verwaltung_1.0.0_all.deb
```

## Windows
Doppelklick auf `build_scripts/build_windows.bat` (Python muss installiert sein).

## macOS
```bash
bash build_scripts/build_macos.sh
# Optional für .dmg: brew install create-dmg
```

## Dateiendung .plf
Die App verwendet `.plf` als primäres Format (technisch identisch mit `.db` = SQLite).
Das .deb-Paket registriert `.plf` automatisch im System.
