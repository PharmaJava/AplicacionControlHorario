"""Importación de la base de datos de la versión 2024-2025.

El histórico desde 2024 hay que conservarlo: el art. 34.9 ET exige guardar los
registros cuatro años.  Esta importación los trae al formato nuevo marcándolos
con origen ``MIGRADO`` para que se distingan de los fichajes nativos.

Qué se puede y qué no se puede recuperar del formato antiguo:

* Los nombres se recuperan de la columna ``name``, que estaba en claro.  La
  columna ``encrypted_name`` es irrecuperable: la clave Fernet se regeneraba en
  cada arranque y nunca se guardó.
* Las fechas venían como texto ``dd/mm/aaaa HH:MM:SS`` en hora local, sin zona
  horaria.  Se interpretan en la zona local del equipo, que es donde se
  registraron.
* No había PIN.  Los trabajadores importados quedan sin PIN y no pueden fichar
  hasta que se les asigne uno; el diagnóstico de la aplicación lo recuerda.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from . import db
from .config import ruta_bd_antigua
from .seguridad import Cifrador


@dataclass
class ResultadoMigracion:
    trabajadores: int = 0
    fichajes: int = 0
    incidencias: int = 0
    omitidos: list[str] = field(default_factory=list)

    @property
    def hubo_datos(self) -> bool:
        return bool(self.trabajadores or self.fichajes)

    def resumen(self) -> str:
        partes = [
            f"{self.trabajadores} trabajador(es)",
            f"{self.fichajes} fichaje(s)",
            f"{self.incidencias} incidencia(s)",
        ]
        texto = "Importados " + ", ".join(partes) + "."
        if self.omitidos:
            texto += f" Se omitieron {len(self.omitidos)} registro(s) ilegibles."
        return texto


def hay_datos_antiguos(ruta: Path | None = None) -> bool:
    ruta = ruta or ruta_bd_antigua()
    if not ruta.exists():
        return False
    try:
        antigua = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    except sqlite3.Error:
        return False
    try:
        tablas = {
            f[0]
            for f in antigua.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if not {"users", "records"} <= tablas:
            return False
        return bool(antigua.execute("SELECT 1 FROM users LIMIT 1").fetchone())
    except sqlite3.Error:
        return False
    finally:
        antigua.close()


def _a_utc(texto: str | None) -> str | None:
    """Convierte 'dd/mm/aaaa HH:MM[:SS]' local a ISO-8601 UTC."""
    if not texto:
        return None
    texto = texto.strip()
    for formato in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            ingenuo = dt.datetime.strptime(texto, formato)
        except ValueError:
            continue
        local = ingenuo.astimezone()  # asume la zona horaria del equipo
        return db.a_iso(local)
    return None


def importar(
    conexion: sqlite3.Connection,
    cifrador: Cifrador,
    ruta: Path | None = None,
    *,
    actor: str = "migracion",
) -> ResultadoMigracion:
    ruta = ruta or ruta_bd_antigua()
    resultado = ResultadoMigracion()
    if not hay_datos_antiguos(ruta):
        return resultado

    antigua = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    antigua.row_factory = sqlite3.Row
    try:
        with db.transaccion(conexion):
            equivalencias = _importar_usuarios(
                antigua, conexion, cifrador, resultado
            )
            _importar_registros(antigua, conexion, equivalencias, resultado)
            _importar_incidencias(antigua, conexion, equivalencias, resultado)
            db.guardar_config(conexion, "migracion_2024_hecha", db.a_iso(db.ahora_utc()))
            db.registrar_auditoria(
                conexion,
                actor=actor,
                accion="IMPORTACION_HISTORICO",
                detalle=f"{ruta.name}: {resultado.resumen()}",
            )
    finally:
        antigua.close()
    return resultado


def _importar_usuarios(
    antigua: sqlite3.Connection,
    conexion: sqlite3.Connection,
    cifrador: Cifrador,
    resultado: ResultadoMigracion,
) -> dict[int, int]:
    equivalencias: dict[int, int] = {}
    for fila in antigua.execute("SELECT id, name FROM users ORDER BY id"):
        nombre = (fila["name"] or "").strip() or f"Trabajador {fila['id']}"
        codigo = f"E{fila['id']:03d}"
        existente = conexion.execute(
            "SELECT id FROM trabajadores WHERE codigo = ?", (codigo,)
        ).fetchone()
        if existente:
            equivalencias[fila["id"]] = existente["id"]
            continue
        cursor = conexion.execute(
            """
            INSERT INTO trabajadores (
                codigo, nombre_cifrado, nombre_indice, pin_hash, rol, activo,
                es_menor, alta_utc
            ) VALUES (?, ?, ?, NULL, 'EMPLEADO', 1, 0, ?)
            """,
            (
                codigo,
                cifrador.cifrar(nombre),
                cifrador.indice(nombre),
                db.a_iso(db.ahora_utc()),
            ),
        )
        equivalencias[fila["id"]] = int(cursor.lastrowid)
        resultado.trabajadores += 1
    return equivalencias


def _importar_registros(
    antigua: sqlite3.Connection,
    conexion: sqlite3.Connection,
    equivalencias: dict[int, int],
    resultado: ResultadoMigracion,
) -> None:
    filas = list(
        antigua.execute(
            "SELECT id, user_id, entry_time, exit_time FROM records ORDER BY id"
        )
    )
    # Se ordenan por instante real: la cadena de hashes debe quedar coherente
    # con la cronología, y en la base antigua el id no siempre lo respetaba.
    convertidos = []
    for fila in filas:
        entrada = _a_utc(fila["entry_time"])
        if entrada is None or fila["user_id"] not in equivalencias:
            resultado.omitidos.append(
                f"records#{fila['id']}: fecha ilegible «{fila['entry_time']}»"
            )
            continue
        convertidos.append((entrada, _a_utc(fila["exit_time"]), fila))
    convertidos.sort(key=lambda t: t[0])

    for entrada, salida, fila in convertidos:
        trabajador_id = equivalencias[fila["user_id"]]
        db.registrar_evento(
            conexion,
            trabajador_id=trabajador_id,
            tipo="ENTRADA",
            ts_utc=entrada,
            origen="MIGRADO",
            nota="Importado de la versión 2024",
        )
        resultado.fichajes += 1
        if salida:
            db.registrar_evento(
                conexion,
                trabajador_id=trabajador_id,
                tipo="SALIDA",
                ts_utc=salida,
                origen="MIGRADO",
                nota="Importado de la versión 2024",
            )
            resultado.fichajes += 1


def _importar_incidencias(
    antigua: sqlite3.Connection,
    conexion: sqlite3.Connection,
    equivalencias: dict[int, int],
    resultado: ResultadoMigracion,
) -> None:
    tablas = {
        f[0]
        for f in antigua.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    if "incidents" not in tablas:
        return
    for fila in antigua.execute(
        "SELECT id, user_id, incident_time FROM incidents ORDER BY id"
    ):
        momento = _a_utc(fila["incident_time"])
        if momento is None or fila["user_id"] not in equivalencias:
            resultado.omitidos.append(f"incidents#{fila['id']}: fecha ilegible")
            continue
        db.registrar_evento(
            conexion,
            trabajador_id=equivalencias[fila["user_id"]],
            tipo="INCIDENCIA",
            ts_utc=momento,
            origen="MIGRADO",
            nota="Incidencia importada de la versión 2024",
        )
        resultado.incidencias += 1


__all__ = ["ResultadoMigracion", "hay_datos_antiguos", "importar"]
