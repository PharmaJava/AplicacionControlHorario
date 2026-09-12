"""Saber si el programa corre empaquetado como .exe y localizar sus recursos.

PyInstaller descomprime el programa en una carpeta temporal distinta en cada
ejecución y apunta ``sys._MEIPASS`` a ella.  Eso rompe dos cosas si no se tiene
en cuenta:

* los ficheros de ``recursos/`` no están donde estaría el código fuente, y
* un acceso directo de arranque que apuntara a esa carpeta dejaría de
  funcionar en cuanto Windows la borre.

Este módulo centraliza las dos preguntas para que el resto del código no tenga
que enterarse de si va empaquetado o no.
"""

from __future__ import annotations

import sys
from pathlib import Path


def esta_empaquetado() -> bool:
    """¿Estamos dentro de un ejecutable creado con PyInstaller?"""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def directorio_base() -> Path:
    """Carpeta desde la que se leen los recursos incluidos en el programa."""
    if esta_empaquetado():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]  # noqa: SLF001
    return Path(__file__).resolve().parent.parent


def ruta_recurso(*partes: str) -> Path:
    """Ruta de un fichero de ``recursos/``, empaquetado o no."""
    return directorio_base().joinpath("recursos", *partes)


def ejecutable() -> Path:
    """El fichero con el que se relanza el programa.

    Empaquetado es el propio ``.exe``; en código fuente, el intérprete de
    Python (``pythonw.exe`` en Windows, para no arrastrar una consola).
    """
    actual = Path(sys.executable)
    if esta_empaquetado():
        return actual
    if sys.platform.startswith("win"):
        sin_consola = actual.with_name("pythonw.exe")
        if sin_consola.exists():
            return sin_consola
    return actual


def directorio_ejecutable() -> Path:
    """Carpeta estable donde vive el programa instalado.

    A diferencia de ``directorio_base()``, ésta sobrevive entre ejecuciones,
    así que es la que debe usarse en accesos directos.
    """
    if esta_empaquetado():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


__all__ = [
    "directorio_base",
    "directorio_ejecutable",
    "ejecutable",
    "esta_empaquetado",
    "ruta_recurso",
]
