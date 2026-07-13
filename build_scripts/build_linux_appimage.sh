#!/bin/bash
set -e
cd "$(dirname "$0")/.."

VENV=build_scripts/build/appimage_venv
python3 -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet PyQt6 openpyxl odfpy pyinstaller

"$VENV/bin/pyinstaller" build_scripts/projekttage.spec \
    --distpath build_scripts/dist/linux \
    --workpath build_scripts/build/linux \
    --noconfirm

APPDIR=build_scripts/dist/linux/AppDir
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
cp "build_scripts/dist/linux/Mitmach-Lotse" "$APPDIR/usr/bin/Mitmach-Lotse"
cp img/mitmachlotse.png "$APPDIR/mitmachlotse.png"

cat > "$APPDIR/mitmachlotse.desktop" << DESK
[Desktop Entry]
Type=Application
Name=Mitmach-Lotse
Exec=Mitmach-Lotse %f
Icon=mitmachlotse
Categories=Education;
MimeType=application/x-planungsmappe;
DESK

cat > "$APPDIR/AppRun" << RUN
#!/bin/bash
HERE="\$(dirname "\$(readlink -f "\${0}")")"
exec "\$HERE/usr/bin/Mitmach-Lotse" "\$@"
RUN
chmod 755 "$APPDIR/AppRun"

APPIMAGETOOL=build_scripts/dist/appimagetool.AppImage
if [ ! -f "$APPIMAGETOOL" ]; then
    curl -L -o "$APPIMAGETOOL" \
        https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x "$APPIMAGETOOL"
fi

ARCH=x86_64 "$APPIMAGETOOL" "$APPDIR" build_scripts/dist/Mitmach-Lotse-x86_64.AppImage

echo "Fertig: build_scripts/dist/Mitmach-Lotse-x86_64.AppImage"
