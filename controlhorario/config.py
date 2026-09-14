"""Rutas de la aplicación y ajustes persistentes.

La versión de 2024 usaba ``os.getenv('APPDATA')``, que sólo existe en Windows y
devuelve ``None`` en Linux y macOS (rompiendo ``os.path.join``).  Aquí se
resuelve el directorio de datos de forma nativa en cada sistema operativo.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

from .version import NOMBRE_APP

# --------------------------------------------------------------------------- #
# Rutas
# --------------------------------------------------------------------------- #

_NOMBRE_CARPETA = "ControlHorario"


def directorio_datos() -> Path:
    """Directorio donde viven la base de datos, la clave y las copias.

    Se puede forzar con la variable de entorno ``CONTROLHORARIO_DATOS``, lo que
    permite ejecutar la aplicación desde una carpeta compartida o aislarla en
    las pruebas.
    """
    forzado = os.environ.get("CONTROLHORARIO_DATOS")
    if forzado:
        destino = Path(forzado).expanduser()
    elif sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")
        destino = Path(base) / _NOMBRE_CARPETA
    elif sys.platform == "darwin":
        destino = Path.home() / "Library" / "Application Support" / _NOMBRE_CARPETA
    else:
        base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
        destino = Path(base) / "controlhorario"

    destino.mkdir(parents=True, exist_ok=True)
    return destino


def directorio_copias() -> Path:
    destino = directorio_datos() / "copias"
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def directorio_exportaciones() -> Path:
    """Carpeta por defecto para informes: Escritorio si existe, si no datos."""
    for candidato in (Path.home() / "Escritorio", Path.home() / "Desktop"):
        if candidato.is_dir():
            return candidato
    destino = directorio_datos() / "informes"
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def ruta_bd() -> Path:
    return directorio_datos() / "controlhorario.db"


def ruta_clave() -> Path:
    return directorio_datos() / "clave.key"


def ruta_ajustes() -> Path:
    return directorio_datos() / "ajustes.json"


def ruta_bd_antigua() -> Path:
    """Base de datos de la versión 2024-2025, para la importación inicial."""
    return directorio_datos() / "time_tracker.db"


# --------------------------------------------------------------------------- #
# Ajustes
# --------------------------------------------------------------------------- #

@dataclass
class Ajustes:
    """Parámetros de empresa y de cumplimiento.

    Los límites son configurables porque dependen del convenio colectivo
    aplicable: el Estatuto de los Trabajadores fija topes, pero el convenio
    puede mejorarlos.  Los valores por defecto son los legales generales.
    """

    # Identificación de la empresa (aparece en los informes para la ITSS)
    empresa: str = ""
    cif: str = ""
    centro_trabajo: str = ""
    # Nombre corto para la pantalla. Los informes que ve la Inspección llevan
    # la razón social completa, que es la que identifica legalmente a la
    # empresa; en el rótulo del terminal suele quedar mejor el nombre de
    # siempre, sin la forma jurídica.  Vacío: se usa la razón social.
    nombre_visible: str = ""

    # Límites de jornada. Art. 34.1 ET: 40 horas semanales de promedio anual.
    # Es configurable porque el convenio puede fijar una jornada menor.
    horas_semanales: float = 40.0
    # Art. 34.3 ET: máximo 9 horas ordinarias diarias salvo pacto en convenio.
    horas_diarias_ordinarias: float = 9.0
    # Art. 34.3 ET: 12 horas mínimas entre el fin de una jornada y el inicio
    # de la siguiente.
    descanso_entre_jornadas_horas: float = 12.0
    # Art. 34.4 ET: pausa mínima de 15 minutos si la jornada continuada supera
    # las 6 horas (30 minutos para menores de 18 años si supera 4 horas y media).
    pausa_minima_minutos: int = 15
    umbral_pausa_horas: float = 6.0
    # Art. 37.1 ET: descanso semanal mínimo de día y medio ininterrumpido.
    descanso_semanal_horas: float = 36.0
    # Art. 35.2 ET: máximo 80 horas extraordinarias al año.
    horas_extra_anuales: int = 80
    # Art. 34.9 ET: conservación de los registros durante 4 años.
    anios_conservacion: int = 4

    # ¿Las pausas cuentan como tiempo de trabajo efectivo? Depende del convenio.
    pausas_computan_como_trabajo: bool = False

    # Interfaz
    tema: str = "claro"  # "claro" u "oscuro"
    modo_terminal: bool = False  # arranca en pantalla de fichaje a pantalla completa
    copia_automatica: bool = True

    def rotulo(self) -> str:
        """Lo que se lee en pantalla: el nombre corto si lo hay.

        No sustituye a la razón social en los informes: ahí debe figurar la
        denominación completa.
        """
        return self.nombre_visible.strip() or self.empresa.strip()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def cargar(cls, ruta: Path | None = None) -> Ajustes:
        ruta = ruta or ruta_ajustes()
        if not ruta.exists():
            return cls()
        try:
            datos = json.loads(ruta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # Un fichero corrupto no debe impedir arrancar la aplicación.
            return cls()
        validos = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in datos.items() if k in validos})

    def guardar(self, ruta: Path | None = None) -> None:
        ruta = ruta or ruta_ajustes()
        ruta.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


# --------------------------------------------------------------------------- #
# Constantes de dominio
# --------------------------------------------------------------------------- #

TIPOS_EVENTO = (
    "ENTRADA",
    "SALIDA",
    "PAUSA_INICIO",
    "PAUSA_FIN",
    "INCIDENCIA",
    "RECTIFICACION",
)

MODALIDADES = ("PRESENCIAL", "TELETRABAJO")

ROLES = ("EMPLEADO", "RESPONSABLE", "ADMIN")

__all__ = [
    "Ajustes",
    "MODALIDADES",
    "NOMBRE_APP",
    "ROLES",
    "TIPOS_EVENTO",
    "directorio_copias",
    "directorio_datos",
    "directorio_exportaciones",
    "ruta_ajustes",
    "ruta_bd",
    "ruta_bd_antigua",
    "ruta_clave",
]
