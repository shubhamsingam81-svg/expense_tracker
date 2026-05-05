# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for JDAP Orchestrator Tool.
Bundles app.py + index.html into a single executable.

Build command:
    pyinstaller jdap_orchestrator.spec
"""

import os

block_cipher = None
spec_dir = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    [os.path.join(spec_dir, 'app.py')],
    pathex=[spec_dir],
    binaries=[],
    datas=[
        (os.path.join(spec_dir, 'index.html'), '.'),
    ],
    hiddenimports=['flask'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='jdap_orchestrator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
