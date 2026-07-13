# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
block_cipher = None
APP_DIR = Path(SPEC).parent.parent

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
exe = EXE(pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name='Mitmach-Lotse', debug=False, bootloader_ignore_signals=False,
    strip=False, upx=True, runtime_tmpdir=None, console=False, argv_emulation=False)
if __import__('sys').platform == 'darwin':
    app = BUNDLE(exe, name='Mitmach-Lotse.app',
        bundle_identifier='de.gymnasium-sasbach.projekttage',
        info_plist={'CFBundleName':'Mitmach-Lotse',
            'CFBundleVersion':'1.0.0','NSHighResolutionCapable':True,
            'CFBundleDocumentTypes':[{'CFBundleTypeName':'Planungsmappe',
                'CFBundleTypeExtensions':['plf'],'CFBundleTypeRole':'Editor'}]})
