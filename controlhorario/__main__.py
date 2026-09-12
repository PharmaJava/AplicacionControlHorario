"""Punto de entrada: python -m controlhorario"""

from __future__ import annotations

import sys


def main() -> int:
    try:
        import tkinter  # noqa: F401
    except ImportError:
        print(
            "No se encuentra tkinter, la biblioteca gráfica de Python.\n"
            "  · Windows/macOS: reinstala Python marcando «tcl/tk and IDLE».\n"
            "  · Debian/Ubuntu: sudo apt install python3-tk\n"
            "  · Fedora:        sudo dnf install python3-tkinter",
            file=sys.stderr,
        )
        return 1

    from .ui.app import ejecutar

    ejecutar()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
