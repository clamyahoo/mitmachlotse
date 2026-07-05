#!/bin/bash
set -e
cd "$(dirname "$0")/.."
pip3 install PyQt6 openpyxl odfpy pyinstaller --quiet
pyinstaller build_scripts/projekttage.spec --distpath build_scripts/dist/macos --workpath build_scripts/build/macos --noconfirm
if command -v create-dmg &>/dev/null; then
    create-dmg --volname "Mitmach-Lotse" \
        "build_scripts/dist/Mitmach-Lotse.dmg" \
        "build_scripts/dist/macos/Mitmach-Lotse.app"
else
    hdiutil create -volname "Mitmach-Lotse" \
        -srcfolder "build_scripts/dist/macos/Mitmach-Lotse.app" \
        -ov -format UDZO "build_scripts/dist/Mitmach-Lotse.dmg"
fi
echo "Fertig: build_scripts/dist/Mitmach-Lotse.dmg"
