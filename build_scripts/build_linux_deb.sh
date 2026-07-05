#!/bin/bash
set -e
cd "$(dirname "$0")/.."
VER=1.0.0; APP=projekttage-verwaltung; BUILD=/tmp/deb_build/${APP}_${VER}
rm -rf /tmp/deb_build && mkdir -p $BUILD/{DEBIAN,opt/projekttage,usr/bin,usr/share/{applications,mime/packages}}
cp *.py _mcmf.py _zuteilungsplaner.py requirements.txt $BUILD/opt/projekttage/ 2>/dev/null || true
cat > $BUILD/DEBIAN/control << CTRL
Package: $APP
Version: $VER
Section: education
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-pip, python3-venv
Maintainer: Lender-Gymnasium Sasbach
Description: Mitmach-Lotse
CTRL
cat > $BUILD/DEBIAN/postinst << PINST
#!/bin/bash
python3 -m venv /opt/projekttage/venv --system-site-packages
/opt/projekttage/venv/bin/pip install --quiet PyQt6 openpyxl odfpy
update-mime-database /usr/share/mime 2>/dev/null || true
PINST
chmod 755 $BUILD/DEBIAN/postinst
cat > $BUILD/usr/bin/projekttage << BIN
#!/bin/bash
exec /opt/projekttage/venv/bin/python3 /opt/projekttage/mitmachlotse.py "\$@"
BIN
chmod 755 $BUILD/usr/bin/projekttage
cat > $BUILD/usr/share/applications/projekttage.desktop << DESK
[Desktop Entry]
Type=Application
Name=Mitmach-Lotse
Exec=projekttage %f
Categories=Education;
MimeType=application/x-planungsmappe;
DESK
cat > $BUILD/usr/share/mime/packages/projekttage.xml << MIME
<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="application/x-planungsmappe">
    <comment>Planungsmappe (Mitmach-Lotse)</comment>
    <glob pattern="*.plf"/>
  </mime-type>
</mime-info>
MIME
dpkg-deb --build $BUILD ${APP}_${VER}_all.deb
echo "Fertig: ${APP}_${VER}_all.deb"
