# -*- mode: python ; coding: utf-8 -*-
"""Especificación de PyInstaller para Control Horario.

Genera dos cosas según la variable de entorno ``CH_MODO``:

* ``carpeta`` (por defecto) — una carpeta con el .exe y sus dependencias.  Es
  lo que empaqueta el instalador: arranca más rápido que un único fichero,
  porque no tiene que descomprimirse en cada ejecución, y da menos falsos
  positivos con los antivirus.
* ``portable`` — un único .exe que se ejecuta sin instalar nada.  Cómodo para
  probar el programa o llevarlo en un pendrive.
"""

import os
import sys
from pathlib import Path

RAIZ = Path(os.environ.get("CH_RAIZ", Path.cwd())).resolve()
MODO = os.environ.get("CH_MODO", "carpeta")
PORTABLE = MODO == "portable"

sys.path.insert(0, str(RAIZ))
from controlhorario.version import __version__  # noqa: E402

NOMBRE = "ControlHorarioPortable" if PORTABLE else "ControlHorario"

analisis = Analysis(
    [str(RAIZ / "construir" / "lanzador.py")],
    pathex=[str(RAIZ)],
    binaries=[],
    datas=[(str(RAIZ / "recursos"), "recursos")],
    hiddenimports=[
        # openpyxl carga estos por su cuenta y PyInstaller no siempre los ve.
        "openpyxl.cell._writer",
        # Sin tkinter no hay interfaz; se declara explícitamente por si acaso.
        "tkinter",
        "tkinter.filedialog",
        "tkinter.messagebox",
        "tkinter.simpledialog",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Se excluyen bibliotecas pesadas que no usamos: sin esto PyInstaller las
    # arrastra si están instaladas en el entorno y el ejecutable engorda.
    excludes=[
        "numpy", "pandas", "matplotlib", "scipy", "PIL", "pytest",
        "setuptools", "pip", "IPython", "notebook",
    ],
    noarchive=False,
)

pyz = PYZ(analisis.pure)

if PORTABLE:
    exe = EXE(
        pyz,
        analisis.scripts,
        analisis.binaries,
        analisis.datas,
        [],
        name=NOMBRE,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        runtime_tmpdir=None,
        console=False,          # sin ventana negra de consola
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=str(RAIZ / "recursos" / "icono.ico"),
        version_info=None,
    )
else:
    exe = EXE(
        pyz,
        analisis.scripts,
        [],
        exclude_binaries=True,
        name=NOMBRE,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=str(RAIZ / "recursos" / "icono.ico"),
    )
    coll = COLLECT(
        exe,
        analisis.binaries,
        analisis.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name=NOMBRE,
    )
