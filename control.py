#!/usr/bin/env python3
"""Punto de entrada antiguo, conservado por costumbre.

Hasta la versión de 2025 todo el programa vivía en este fichero. Ahora está
repartido en el paquete ``controlhorario/``, y esto sólo redirige allí para que
quien tenga el hábito de ejecutar «control.py» siga entrando en el programa.

La forma recomendada de arrancarlo es el acceso directo que crea el instalador,
o bien:

    python -m controlhorario
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    try:
        from controlhorario.__main__ import main
    except ImportError as exc:
        print(
            "No se encuentra el paquete 'controlhorario'.\n"
            f"Detalle: {exc}\n\n"
            "Ejecuta el instalador de la carpeta 'instalar' o, si trabajas "
            "sobre el código fuente, instala las dependencias con:\n"
            "    pip install -r requirements.txt",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    raise SystemExit(main())
