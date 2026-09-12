"""Importación de la base de datos de la versión 2024-2025.

El histórico desde 2024 hay que conservarlo: el art. 34.9 ET exige guardar los
registros cuatro años.  Esta importación los trae al formato nuevo marcándolos
con origen ``MIGRADO`` para que se distingan de los fichajes nativos.

Garantías de esta importación
-----------------------------

* **No toca la base de datos antigua.**  Se abre en modo sólo lectura
  (``mode=ro``) y el fichero original se conserva intacto como respaldo.
* **Se puede repetir sin duplicar nada.**  Cada fila traída queda anotada en la
  tabla ``importaciones``; al repetir, las filas ya importadas se saltan.  Esto
  importa porque la importación se puede lanzar a mano desde Ajustes y porque
  el programa puede arrancar solo con el equipo.
* **No mezcla personas.**  La correspondencia entre el trabajador antiguo y el
  nuevo se guarda explícitamente, en vez de deducirla del código: si alguien ya
  había dado de alta un ``E001`` distinto, el importado se crea aparte.

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
import shutil
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from . import db
from .config import directorio_copias, ruta_bd_antigua
from .seguridad import Cifrador


@dataclass
class ResultadoMigracion:
    trabajadores: int = 0
    fichajes: int = 0
    incidencias: int = 0
    ya_estaban: int = 0
    omitidos: list[str] = field(default_factory=list)
    respaldo: Path | None = None

    @property
    def hubo_datos(self) -> bool:
        return bool(self.trabajadores or self.fichajes or self.incidencias)

    def resumen(self) -> str:
        if not self.hubo_datos and self.ya_estaban:
            return (
                f"No había nada nuevo que importar: los {self.ya_estaban} "
                "registros de la base antigua ya estaban traídos."
            )
        if not self.hubo_datos:
            return "No se ha encontrado ningún registro que importar."
        texto = (
            "Importados "
            + ", ".join(
                (
                    f"{self.trabajadores} trabajador(es)",
                    f"{self.fichajes} fichaje(s)",
                    f"{self.incidencias} incidencia(s)",
                )
            )
            + "."
        )
        if self.ya_estaban:
            texto += f" Se saltaron {self.ya_estaban} ya importados."
        if self.omitidos:
            texto += f" Se omitieron {len(self.omitidos)} registro(s) ilegibles."
        return texto


# --------------------------------------------------------------------------- #
# Detección
# --------------------------------------------------------------------------- #

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


def pendiente_de_importar(
    conexion: sqlite3.Connection, ruta: Path | None = None
) -> int:
    """Cuántas filas de la base antigua quedan por traer.

    Sólo cuenta las que **se pueden** traer: una fila con la fecha corrupta no
    es trabajo pendiente, es un registro ilegible, y dejarla en la cuenta haría
    que el aviso de «quedan registros por importar» no se apagara nunca.
    """
    ruta = ruta or ruta_bd_antigua()
    if not hay_datos_antiguos(ruta):
        return 0
    fuente = _clave_fuente(ruta)
    antigua = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    antigua.row_factory = sqlite3.Row
    try:
        total = 0
        for tabla, columna in (("records", "entry_time"), ("incidents", "incident_time")):
            try:
                filas = list(
                    antigua.execute(f"SELECT id, {columna} AS momento FROM {tabla}")  # noqa: S608
                )
            except sqlite3.Error:
                continue
            traidas = {
                f["origen_id"]
                for f in conexion.execute(
                    "SELECT origen_id FROM importaciones "
                    "WHERE origen = ? AND fuente = ?",
                    (tabla, fuente),
                )
            }
            total += sum(
                1
                for f in filas
                if f["id"] not in traidas and _a_utc(f["momento"]) is not None
            )
        return total
    finally:
        antigua.close()


def _clave_fuente(ruta: Path) -> str:
    """Identifica el fichero de origen, para poder importar de varios sitios."""
    return ruta.name.lower()


# --------------------------------------------------------------------------- #
# Conversión de fechas
# --------------------------------------------------------------------------- #

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


# --------------------------------------------------------------------------- #
# Importación
# --------------------------------------------------------------------------- #

def importar(
    conexion: sqlite3.Connection,
    cifrador: Cifrador,
    ruta: Path | None = None,
    *,
    actor: str = "migracion",
    hacer_respaldo: bool = True,
) -> ResultadoMigracion:
    """Trae al formato nuevo lo que falte de la base antigua.

    Es seguro llamarla las veces que haga falta: sólo importa lo que aún no
    estaba.
    """
    ruta = ruta or ruta_bd_antigua()
    resultado = ResultadoMigracion()
    if not hay_datos_antiguos(ruta):
        return resultado

    if hacer_respaldo:
        resultado.respaldo = _respaldar(ruta)

    fuente = _clave_fuente(ruta)
    antigua = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    antigua.row_factory = sqlite3.Row
    try:
        with db.transaccion(conexion):
            equivalencias = _importar_usuarios(
                antigua, conexion, cifrador, resultado, fuente
            )
            _importar_registros(antigua, conexion, equivalencias, resultado, fuente)
            _importar_incidencias(antigua, conexion, equivalencias, resultado, fuente)
            db.guardar_config(
                conexion, "migracion_2024_hecha", db.a_iso(db.ahora_utc())
            )
            db.registrar_auditoria(
                conexion,
                actor=actor,
                accion="IMPORTACION_HISTORICO",
                detalle=f"{ruta.name}: {resultado.resumen()}",
            )
    finally:
        antigua.close()
    return resultado


def _respaldar(ruta: Path) -> Path | None:
    """Guarda una copia intacta de la base antigua antes de tocar nada."""
    destino = directorio_copias() / f"original_2024_{ruta.stem}.db"
    if destino.exists():
        return destino
    try:
        shutil.copy2(ruta, destino)
    except OSError:
        return None
    return destino


def _ya_importado(
    conexion: sqlite3.Connection, origen: str, origen_id: int, fuente: str
) -> sqlite3.Row | None:
    return conexion.execute(
        "SELECT * FROM importaciones "
        "WHERE origen = ? AND origen_id = ? AND fuente = ?",
        (origen, origen_id, fuente),
    ).fetchone()


def _anotar(
    conexion: sqlite3.Connection,
    origen: str,
    origen_id: int,
    fuente: str,
    *,
    trabajador_id: int | None = None,
    evento_id: int | None = None,
) -> None:
    conexion.execute(
        "INSERT OR REPLACE INTO importaciones "
        "(origen, origen_id, fuente, trabajador_id, evento_id, importado_utc) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (origen, origen_id, fuente, trabajador_id, evento_id,
         db.a_iso(db.ahora_utc())),
    )


def _importar_usuarios(
    antigua: sqlite3.Connection,
    conexion: sqlite3.Connection,
    cifrador: Cifrador,
    resultado: ResultadoMigracion,
    fuente: str,
) -> dict[int, int]:
    from .dominio import _siguiente_codigo

    equivalencias: dict[int, int] = {}
    for fila in antigua.execute("SELECT id, name FROM users ORDER BY id"):
        anterior = _ya_importado(conexion, "users", fila["id"], fuente)
        if anterior and anterior["trabajador_id"]:
            # Comprobamos que el trabajador siga existiendo antes de reusarlo.
            existe = conexion.execute(
                "SELECT 1 FROM trabajadores WHERE id = ?",
                (anterior["trabajador_id"],),
            ).fetchone()
            if existe:
                equivalencias[fila["id"]] = anterior["trabajador_id"]
                continue

        nombre = (fila["name"] or "").strip() or f"Trabajador {fila['id']}"
        cursor = conexion.execute(
            """
            INSERT INTO trabajadores (
                codigo, nombre_cifrado, nombre_indice, pin_hash, rol, activo,
                es_menor, alta_utc
            ) VALUES (?, ?, ?, NULL, 'EMPLEADO', 1, 0, ?)
            """,
            (
                _siguiente_codigo(conexion),
                cifrador.cifrar(nombre),
                cifrador.indice(nombre),
                db.a_iso(db.ahora_utc()),
            ),
        )
        nuevo_id = int(cursor.lastrowid)
        equivalencias[fila["id"]] = nuevo_id
        _anotar(conexion, "users", fila["id"], fuente, trabajador_id=nuevo_id)
        resultado.trabajadores += 1
    return equivalencias


def _importar_registros(
    antigua: sqlite3.Connection,
    conexion: sqlite3.Connection,
    equivalencias: dict[int, int],
    resultado: ResultadoMigracion,
    fuente: str,
) -> None:
    convertidos = []
    for fila in antigua.execute(
        "SELECT id, user_id, entry_time, exit_time FROM records ORDER BY id"
    ):
        if _ya_importado(conexion, "records", fila["id"], fuente):
            resultado.ya_estaban += 1
            continue
        entrada = _a_utc(fila["entry_time"])
        if entrada is None or fila["user_id"] not in equivalencias:
            resultado.omitidos.append(
                f"records#{fila['id']}: fecha ilegible «{fila['entry_time']}»"
            )
            continue
        convertidos.append((entrada, _a_utc(fila["exit_time"]), fila))

    # Se ordenan por instante real: la cadena de hashes debe quedar coherente
    # con la cronología, y en la base antigua el id no siempre lo respetaba.
    convertidos.sort(key=lambda t: t[0])

    for entrada, salida, fila in convertidos:
        trabajador_id = equivalencias[fila["user_id"]]
        evento_id = db.registrar_evento(
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
        _anotar(
            conexion, "records", fila["id"], fuente,
            trabajador_id=trabajador_id, evento_id=evento_id,
        )


def _importar_incidencias(
    antigua: sqlite3.Connection,
    conexion: sqlite3.Connection,
    equivalencias: dict[int, int],
    resultado: ResultadoMigracion,
    fuente: str,
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
        if _ya_importado(conexion, "incidents", fila["id"], fuente):
            resultado.ya_estaban += 1
            continue
        momento = _a_utc(fila["incident_time"])
        if momento is None or fila["user_id"] not in equivalencias:
            resultado.omitidos.append(f"incidents#{fila['id']}: fecha ilegible")
            continue
        evento_id = db.registrar_evento(
            conexion,
            trabajador_id=equivalencias[fila["user_id"]],
            tipo="INCIDENCIA",
            ts_utc=momento,
            origen="MIGRADO",
            nota="Incidencia importada de la versión 2024",
        )
        _anotar(
            conexion, "incidents", fila["id"], fuente,
            trabajador_id=equivalencias[fila["user_id"]], evento_id=evento_id,
        )
        resultado.incidencias += 1


__all__ = [
    "ResultadoMigracion",
    "hay_datos_antiguos",
    "importar",
    "pendiente_de_importar",
]
