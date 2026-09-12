"""Versión de la aplicación."""

__version__ = "2026.1.0"

NOMBRE_APP = "Control Horario"
NOMBRE_LARGO = "Control Horario · Registro de jornada"

# Autor del programa. Es una persona, no una empresa: nada de razones sociales.
AUTOR = "PharmaJava"


def anio() -> str:
    """Año de la versión, para el aviso de autoría."""
    return __version__.split(".", 1)[0]


def credito() -> str:
    return f"{AUTOR} © {anio()}"
