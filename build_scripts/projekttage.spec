# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path
block_cipher = None
APP_DIR = Path(SPEC).parent.parent

# UPX aus: UPX-komprimierte DLLs sind ein häufiger Auslöser für
# Virenscanner-Fehlalarme und "DLL"-Ladefehler, besonders auf verwalteten
# Firmenrechnern. Etwas größere Dateien, dafür deutlich robuster.
_UPX = False

a = Analysis(
    [str(APP_DIR / 'mitmachlotse.py')],
    pathex=[str(APP_DIR)],
    binaries=[],
    datas=[(str(APP_DIR / f), '.') for f in [
        'hauptfenster.py','database.py','algorithmen.py','dialoge.py',
        'importexport.py','listenabfragen.py','listenfenster.py',
        'validierung.py','_mcmf.py','_zuteilungsplaner.py',
    ]] + [
        (str(f), 'beispieldaten') for f in (APP_DIR / 'beispieldaten').glob('*')
    ] + [
        (str(f), 'img') for f in (APP_DIR / 'img').glob('*')
    ],
    hiddenimports=['PyQt6.QtCore','PyQt6.QtGui','PyQt6.QtWidgets',
                   'PyQt6.QtPrintSupport','openpyxl','odf','odf.opendocument',
                   'sqlite3','csv','_mcmf','_zuteilungsplaner'],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['tkinter','matplotlib','numpy'],
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if sys.platform == 'win32':
    # Windows: ONEDIR -- ein Ordner mit der .exe und den DLLs direkt daneben
    # (Unterordner _internal), KEIN Entpacken nach %TEMP% bei jedem Start.
    # Das behebt "läuft privat, aber auf dem Arbeitsplatzrechner DLL-Fehler":
    # verwaltete Firmenrechner sperren oft die Programmausführung aus dem
    # Temp-Ordner (AppLocker o. ä.), was den Onefile-Start scheitern lässt.
    # Verteilt wird der Ordner als ZIP (siehe build_windows.bat / Workflow).
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True,
        name='Mitmach-Lotse', debug=False, bootloader_ignore_signals=False,
        strip=False, upx=_UPX, console=False, argv_emulation=False)
    coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas,
        strip=False, upx=_UPX, name='Mitmach-Lotse')
else:
    # Linux/macOS: ONEFILE (eine einzelne ausführbare Datei). Das
    # Linux-AppImage-Skript erwartet genau eine Datei unter
    # dist/linux/Mitmach-Lotse; unter macOS wird sie in ein .app gebündelt.
    exe = EXE(pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
        name='Mitmach-Lotse', debug=False, bootloader_ignore_signals=False,
        strip=False, upx=_UPX, runtime_tmpdir=None, console=False, argv_emulation=False)
    if sys.platform == 'darwin':
        app = BUNDLE(exe, name='Mitmach-Lotse.app',
            bundle_identifier='de.gymnasium-sasbach.projekttage',
            info_plist={'CFBundleName':'Mitmach-Lotse',
                'CFBundleVersion':'1.0.0','NSHighResolutionCapable':True,
                'CFBundleDocumentTypes':[{'CFBundleTypeName':'Planungsmappe',
                    'CFBundleTypeExtensions':['plf'],'CFBundleTypeRole':'Editor'}]})
