"""Capa de datos: esquema, inmutabilidad y cadena de integridad.

Diseño
------
El registro de jornada deja de ser una tabla mutable de entradas y salidas y
pasa a ser un **libro de eventos de sólo anexado** (``eventos``).  Cada fichaje
es un hecho que ocurrió y no se reescribe nunca:

* Corregir un fichaje no sobrescribe nada: se anexa un evento
  ``RECTIFICACION`` que apunta al original e incluye autor y motivo.
* Los ``UPDATE`` sobre ``eventos`` están bloqueados por un *trigger* de SQLite,
  de modo que la inmutabilidad no depende de que el código sea correcto.
* Cada evento encadena un SHA-256 con el hash del anterior.  Alterar o borrar
  una fila rompe la cadena y ``verificar_integridad`` lo detecta y señala
  exactamente dónde.

Así el registro es trazable y verificable, que es lo que la Inspección de
Trabajo necesita comprobar y lo que exige el borrador de real decreto en
tramitación (véase ``docs/NORMATIVA.md``).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from collections.abc import Iterator

from .config import ruta_bd

ESQUEMA_VERSION = 3
GENESIS = "GENESIS"
_SEP = "\x1f"  # separador de unidad ASCII: no aparece en los datos

_MSG_INMUTABLE = (
    "Registro inmutable: los fichajes no se modifican ni se borran. "
    "Para corregir uno, anexa una RECTIFICACION."
)


class ErrorIntegridad(Exception):
    """La cadena de hashes no cuadra."""


# --------------------------------------------------------------------------- #
# Tiempo
# --------------------------------------------------------------------------- #

def ahora_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def a_iso(momento: dt.datetime) -> str:
    """ISO-8601 en UTC. Ordenable alfabéticamente, sin ambigüedad horaria."""
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=dt.timezone.utc)
    return momento.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat()


def desde_iso(texto: str) -> dt.datetime:
    return dt.datetime.fromisoformat(texto)


def a_local(momento: dt.datetime) -> dt.datetime:
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=dt.timezone.utc)
    return momento.astimezone()


# --------------------------------------------------------------------------- #
# Conexión y esquema
# --------------------------------------------------------------------------- #

def conectar(ruta: Path | str | None = None) -> sqlite3.Connection:
    ruta = Path(ruta) if ruta else ruta_bd()
    conexion = sqlite3.connect(str(ruta), isolation_level=None)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON")
    # WAL: lecturas concurrentes sin bloquear al que ficha, y menos riesgo de
    # corrupción si el equipo se apaga de golpe.
    conexion.execute("PRAGMA journal_mode = WAL")
    conexion.execute("PRAGMA synchronous = FULL")
    inicializar(conexion)
    return conexion


@contextmanager
def _asegurar_transaccion(conexion: sqlite3.Connection) -> Iterator[None]:
    """Abre una transacción sólo si no hay ya una en curso.

    Permite anexar un evento suelto con seguridad y, a la vez, agrupar varios
    dentro de una ``transaccion()`` del llamante sin anidar BEGIN.
    """
    if conexion.in_transaction:
        yield
        return
    with transaccion(conexion):
        yield


@contextmanager
def transaccion(conexion: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Transacción inmediata: serializa a los que escriben en la cadena."""
    conexion.execute("BEGIN IMMEDIATE")
    try:
        yield conexion
    except Exception:
        conexion.execute("ROLLBACK")
        raise
    conexion.execute("COMMIT")


_ESQUEMA = """
CREATE TABLE IF NOT EXISTS config (
    clave TEXT PRIMARY KEY,
    valor TEXT
);

CREATE TABLE IF NOT EXISTS trabajadores (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo         TEXT    NOT NULL UNIQUE,
    nombre_cifrado BLOB    NOT NULL,
    nombre_indice  TEXT    NOT NULL,
    dni_cifrado    BLOB,
    dni_indice     TEXT    UNIQUE,
    pin_hash       TEXT,
    rol            TEXT    NOT NULL DEFAULT 'EMPLEADO',
    activo         INTEGER NOT NULL DEFAULT 1,
    es_menor       INTEGER NOT NULL DEFAULT 0,
    jornada_semanal REAL,
    alta_utc       TEXT    NOT NULL,
    baja_utc       TEXT
);

CREATE TABLE IF NOT EXISTS eventos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    trabajador_id INTEGER NOT NULL REFERENCES trabajadores(id),
    tipo          TEXT    NOT NULL,
    ts_utc        TEXT    NOT NULL,
    tz_offset     TEXT    NOT NULL DEFAULT '',
    modalidad     TEXT    NOT NULL DEFAULT 'PRESENCIAL',
    origen        TEXT    NOT NULL DEFAULT 'APP',
    nota          TEXT    NOT NULL DEFAULT '',
    autor         TEXT    NOT NULL DEFAULT '',
    rectifica_id  INTEGER REFERENCES eventos(id),
    motivo        TEXT    NOT NULL DEFAULT '',
    creado_utc    TEXT    NOT NULL,
    hash_previo   TEXT    NOT NULL,
    hash          TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_eventos_trabajador ON eventos(trabajador_id, ts_utc);
CREATE INDEX IF NOT EXISTS idx_eventos_ts         ON eventos(ts_utc);

-- Qué se ha traído ya de la base de datos antigua. Sin esto, importar dos
-- veces duplicaría todos los fichajes.
CREATE TABLE IF NOT EXISTS importaciones (
    origen        TEXT    NOT NULL,   -- 'users', 'records' o 'incidents'
    origen_id     INTEGER NOT NULL,   -- id de la fila en la base antigua
    fuente        TEXT    NOT NULL DEFAULT '',
    trabajador_id INTEGER,
    evento_id     INTEGER,
    importado_utc TEXT    NOT NULL,
    PRIMARY KEY (origen, origen_id, fuente)
);

CREATE TABLE IF NOT EXISTS auditoria (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc      TEXT NOT NULL,
    actor       TEXT NOT NULL,
    accion      TEXT NOT NULL,
    detalle     TEXT NOT NULL DEFAULT '',
    hash_previo TEXT NOT NULL,
    hash        TEXT NOT NULL
);
"""

# La inmutabilidad se impone en el motor, no sólo en el código de la aplicación.
# El borrado sólo se permite durante una purga por caducidad legal explícita,
# que se marca en `config` y queda registrada en `auditoria`.
_TRIGGER_DDL: dict[str, str] = {
    "eventos_no_update": f"""
        CREATE TRIGGER IF NOT EXISTS eventos_no_update
        BEFORE UPDATE ON eventos
        BEGIN
            SELECT RAISE(ABORT, '{_MSG_INMUTABLE}');
        END
    """,
    "eventos_no_delete": f"""
        CREATE TRIGGER IF NOT EXISTS eventos_no_delete
        BEFORE DELETE ON eventos
        WHEN COALESCE(
            (SELECT valor FROM config WHERE clave = 'purga_en_curso'), '0'
        ) <> '1'
        BEGIN
            SELECT RAISE(ABORT, '{_MSG_INMUTABLE}');
        END
    """,
    "auditoria_no_update": """
        CREATE TRIGGER IF NOT EXISTS auditoria_no_update
        BEFORE UPDATE ON auditoria
        BEGIN
            SELECT RAISE(ABORT, 'La auditoria es de solo anexado.');
        END
    """,
    "auditoria_no_delete": """
        CREATE TRIGGER IF NOT EXISTS auditoria_no_delete
        BEFORE DELETE ON auditoria
        BEGIN
            SELECT RAISE(ABORT, 'La auditoria es de solo anexado.');
        END
    """,
}


def inicializar(conexion: sqlite3.Connection) -> None:
    conexion.executescript(_ESQUEMA)
    for ddl in _TRIGGER_DDL.values():
        conexion.execute(ddl)
    if leer_config(conexion, "esquema_version") is None:
        guardar_config(conexion, "esquema_version", str(ESQUEMA_VERSION))


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #

def leer_config(conexion: sqlite3.Connection, clave: str) -> str | None:
    fila = conexion.execute(
        "SELECT valor FROM config WHERE clave = ?", (clave,)
    ).fetchone()
    return fila["valor"] if fila else None


def guardar_config(conexion: sqlite3.Connection, clave: str, valor: str) -> None:
    conexion.execute(
        "INSERT INTO config (clave, valor) VALUES (?, ?) "
        "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
        (clave, valor),
    )


# --------------------------------------------------------------------------- #
# Cadena de integridad
# --------------------------------------------------------------------------- #

def _huella(campos: list[Any]) -> str:
    crudo = _SEP.join("" if c is None else str(c) for c in campos)
    return hashlib.sha256(crudo.encode("utf-8")).hexdigest()


def hash_evento(fila: sqlite3.Row | dict[str, Any]) -> str:
    """Hash canónico de un evento, encadenado con el anterior."""
    return _huella(
        [
            fila["hash_previo"],
            fila["id"],
            fila["trabajador_id"],
            fila["tipo"],
            fila["ts_utc"],
            fila["tz_offset"],
            fila["modalidad"],
            fila["origen"],
            fila["nota"],
            fila["autor"],
            fila["rectifica_id"],
            fila["motivo"],
            fila["creado_utc"],
        ]
    )


def hash_auditoria(fila: sqlite3.Row | dict[str, Any]) -> str:
    return _huella(
        [
            fila["hash_previo"],
            fila["id"],
            fila["ts_utc"],
            fila["actor"],
            fila["accion"],
            fila["detalle"],
        ]
    )


def _ultimo_hash(conexion: sqlite3.Connection, tabla: str) -> str:
    fila = conexion.execute(
        f"SELECT hash FROM {tabla} ORDER BY id DESC LIMIT 1"  # noqa: S608
    ).fetchone()
    return fila["hash"] if fila else GENESIS


def registrar_evento(
    conexion: sqlite3.Connection,
    *,
    trabajador_id: int,
    tipo: str,
    ts_utc: str | None = None,
    tz_offset: str = "",
    modalidad: str = "PRESENCIAL",
    origen: str = "APP",
    nota: str = "",
    autor: str = "",
    rectifica_id: int | None = None,
    motivo: str = "",
) -> int:
    """Anexa un evento y cierra su eslabón de la cadena.

    El hash depende del ``id`` que asigna SQLite, así que se inserta primero
    con un hash provisional y se sella después.  El sellado usa una conexión
    interna que sortea el *trigger* de inmutabilidad de forma controlada: es la
    única escritura sobre una fila ya creada y ocurre dentro de la misma
    transacción que la inserta.
    """
    momento = ts_utc or a_iso(ahora_utc())
    creado = a_iso(ahora_utc())
    if not tz_offset:
        tz_offset = _offset_local()

    with _asegurar_transaccion(conexion):
        return _anexar_evento(
            conexion, trabajador_id, tipo, momento, tz_offset, modalidad,
            origen, nota, autor, rectifica_id, motivo, creado,
        )


def _anexar_evento(
    conexion: sqlite3.Connection,
    trabajador_id: int,
    tipo: str,
    momento: str,
    tz_offset: str,
    modalidad: str,
    origen: str,
    nota: str,
    autor: str,
    rectifica_id: int | None,
    motivo: str,
    creado: str,
) -> int:
    previo = _ultimo_hash(conexion, "eventos")
    cursor = conexion.execute(
        """
        INSERT INTO eventos (
            trabajador_id, tipo, ts_utc, tz_offset, modalidad, origen, nota,
            autor, rectifica_id, motivo, creado_utc, hash_previo, hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '')
        """,
        (
            trabajador_id, tipo, momento, tz_offset, modalidad, origen, nota,
            autor, rectifica_id, motivo, creado, previo,
        ),
    )
    evento_id = int(cursor.lastrowid)
    fila = {
        "hash_previo": previo,
        "id": evento_id,
        "trabajador_id": trabajador_id,
        "tipo": tipo,
        "ts_utc": momento,
        "tz_offset": tz_offset,
        "modalidad": modalidad,
        "origen": origen,
        "nota": nota,
        "autor": autor,
        "rectifica_id": rectifica_id,
        "motivo": motivo,
        "creado_utc": creado,
    }
    _sellar(conexion, "eventos", evento_id, hash_evento(fila))
    return evento_id


def registrar_auditoria(
    conexion: sqlite3.Connection,
    *,
    actor: str,
    accion: str,
    detalle: str = "",
) -> int:
    with _asegurar_transaccion(conexion):
        return _anexar_auditoria(conexion, actor, accion, detalle)


def _anexar_auditoria(
    conexion: sqlite3.Connection, actor: str, accion: str, detalle: str
) -> int:
    momento = a_iso(ahora_utc())
    previo = _ultimo_hash(conexion, "auditoria")
    cursor = conexion.execute(
        "INSERT INTO auditoria (ts_utc, actor, accion, detalle, hash_previo, hash)"
        " VALUES (?, ?, ?, ?, ?, '')",
        (momento, actor, accion, detalle, previo),
    )
    registro_id = int(cursor.lastrowid)
    fila = {
        "hash_previo": previo,
        "id": registro_id,
        "ts_utc": momento,
        "actor": actor,
        "accion": accion,
        "detalle": detalle,
    }
    _sellar(conexion, "auditoria", registro_id, hash_auditoria(fila))
    return registro_id


def _sellar(
    conexion: sqlite3.Connection, tabla: str, registro_id: int, huella: str
) -> None:
    """Escribe el hash recién calculado desactivando el trigger un instante.

    Se recrea el trigger con ``execute`` y no con ``executescript`` porque este
    último confirmaría la transacción en curso y rompería la atomicidad.
    """
    trigger = f"{tabla}_no_update"
    conexion.execute(f"DROP TRIGGER IF EXISTS {trigger}")
    try:
        conexion.execute(
            f"UPDATE {tabla} SET hash = ? WHERE id = ?",  # noqa: S608
            (huella, registro_id),
        )
    finally:
        conexion.execute(_TRIGGER_DDL[trigger])


def _offset_local() -> str:
    desplazamiento = dt.datetime.now().astimezone().utcoffset()
    if desplazamiento is None:
        return "+00:00"
    total = int(desplazamiento.total_seconds())
    signo = "+" if total >= 0 else "-"
    total = abs(total)
    return f"{signo}{total // 3600:02d}:{(total % 3600) // 60:02d}"


def verificar_integridad(conexion: sqlite3.Connection) -> dict[str, Any]:
    """Recorre las cadenas y devuelve un informe verificable.

    Detecta tanto la modificación de una fila (su hash deja de cuadrar) como
    su borrado (el eslabón siguiente apunta a un hash que ya no existe).
    """
    informe: dict[str, Any] = {
        "verificado_utc": a_iso(ahora_utc()),
        "integro": True,
        "eventos": {"filas": 0, "incidencias": [], "cortes": []},
        "auditoria": {"filas": 0, "incidencias": [], "cortes": []},
    }
    # Una purga legal borra fichajes caducados y deja la cadena con un hueco.
    # Ese hueco queda anotado al purgar, para poder distinguirlo de un borrado
    # a escondidas: si no, usar la purga que ofrece el propio programa dejaría
    # el registro marcado como alterado justo cuando viene una inspección.
    cortes = {c["id"]: c for c in _cortes_purga(conexion)}

    for tabla, calculador in (("eventos", hash_evento), ("auditoria", hash_auditoria)):
        previo_esperado = GENESIS
        total = 0
        for fila in conexion.execute(
            f"SELECT * FROM {tabla} ORDER BY id ASC"  # noqa: S608
        ):
            total += 1
            if fila["hash_previo"] != previo_esperado:
                corte = cortes.get(fila["id"]) if tabla == "eventos" else None
                if corte and corte.get("hash_previo") == fila["hash_previo"]:
                    informe[tabla]["cortes"].append(
                        {
                            "id": fila["id"],
                            "purgados": corte.get("purgados", 0),
                            "cuando": corte.get("utc", ""),
                            "detalle": (
                                "Aquí termina lo que se borró en la purga de "
                                "registros caducados, anotada en la auditoría."
                            ),
                        }
                    )
                else:
                    informe[tabla]["incidencias"].append(
                        {
                            "id": fila["id"],
                            "problema": "cadena_rota",
                            "detalle": (
                                "El eslabón anterior no coincide: puede haberse "
                                "borrado o reordenado una fila."
                            ),
                        }
                    )
                    informe["integro"] = False
            esperado = calculador(fila)
            if fila["hash"] != esperado:
                informe[tabla]["incidencias"].append(
                    {
                        "id": fila["id"],
                        "problema": "hash_no_coincide",
                        "detalle": "La fila se ha modificado fuera de la aplicación.",
                    }
                )
                informe["integro"] = False
            previo_esperado = fila["hash"]
        informe[tabla]["filas"] = total
        informe[tabla]["hash_final"] = previo_esperado

    return informe


# --------------------------------------------------------------------------- #
# Conservación legal (art. 34.9 ET: cuatro años)
# --------------------------------------------------------------------------- #

def _cortes_purga(conexion: sqlite3.Connection) -> list[dict[str, Any]]:
    """Huecos que las purgas legales han dejado en la cadena de fichajes."""
    bruto = leer_config(conexion, "cortes_purga")
    if not bruto:
        return []
    try:
        datos = json.loads(bruto)
    except json.JSONDecodeError:
        return []
    return datos if isinstance(datos, list) else []


def purgar_caducados(
    conexion: sqlite3.Connection, anios: int = 4, actor: str = "sistema"
) -> int:
    """Borra los eventos que superan el plazo legal de conservación.

    El art. 34.9 ET obliga a conservar los registros **cuatro años**; el
    principio de limitación del plazo de conservación del art. 5.1.e) del RGPD
    empuja en sentido contrario a guardarlos indefinidamente.  Esta purga es
    voluntaria y siempre queda anotada en la auditoría.
    """
    limite = a_iso(ahora_utc() - dt.timedelta(days=int(365.25 * anios)))
    pendientes = conexion.execute(
        "SELECT COUNT(*) AS n FROM eventos WHERE ts_utc < ?", (limite,)
    ).fetchone()["n"]
    if not pendientes:
        return 0

    # Antes de borrar se apunta dónde va a quedar el hueco: qué fichaje pasa a
    # ser el primero de los que sobreviven y a qué hash apunta.  Así la
    # verificación de integridad puede decir «aquí se purgó», con fecha y con
    # el asiento de auditoría correspondiente, en vez de «esto está alterado».
    filas = conexion.execute(
        "SELECT id, hash_previo, ts_utc FROM eventos ORDER BY id ASC"
    ).fetchall()
    ahora = a_iso(ahora_utc())
    cortes = _cortes_purga(conexion)
    anterior_se_va = False
    for fila in filas:
        if fila["ts_utc"] < limite:
            anterior_se_va = True
            continue
        if anterior_se_va:
            cortes.append(
                {
                    "id": fila["id"],
                    "hash_previo": fila["hash_previo"],
                    "purgados": pendientes,
                    "utc": ahora,
                }
            )
        anterior_se_va = False

    guardar_config(conexion, "purga_en_curso", "1")
    try:
        conexion.execute("DELETE FROM eventos WHERE ts_utc < ?", (limite,))
    finally:
        guardar_config(conexion, "purga_en_curso", "0")
    guardar_config(conexion, "cortes_purga", json.dumps(cortes, ensure_ascii=False))

    registrar_auditoria(
        conexion,
        actor=actor,
        accion="PURGA_CONSERVACION",
        detalle=(
            f"Eliminados {pendientes} eventos anteriores a {limite} "
            f"(plazo de conservación: {anios} años)."
        ),
    )
    return int(pendientes)


def eventos_proximos_a_caducar(
    conexion: sqlite3.Connection, anios: int = 4, margen_dias: int = 30
) -> int:
    inicio = a_iso(ahora_utc() - dt.timedelta(days=int(365.25 * anios)))
    fin = a_iso(
        ahora_utc() - dt.timedelta(days=int(365.25 * anios) - margen_dias)
    )
    fila = conexion.execute(
        "SELECT COUNT(*) AS n FROM eventos WHERE ts_utc >= ? AND ts_utc < ?",
        (inicio, fin),
    ).fetchone()
    return int(fila["n"])


__all__ = [
    "ErrorIntegridad",
    "GENESIS",
    "a_iso",
    "a_local",
    "ahora_utc",
    "conectar",
    "desde_iso",
    "eventos_proximos_a_caducar",
    "guardar_config",
    "hash_auditoria",
    "hash_evento",
    "inicializar",
    "leer_config",
    "purgar_caducados",
    "registrar_auditoria",
    "registrar_evento",
    "transaccion",
    "verificar_integridad",
]


# --------------------------------------------------------------------------- #
# Copias de seguridad
# --------------------------------------------------------------------------- #

def copia_seguridad(
    conexion: sqlite3.Connection,
    destino: Path | None = None,
    *,
    actor: str = "sistema",
    conservar: int = 30,
) -> Path:
    """Copia consistente usando la API de respaldo de SQLite.

    La versión de 2024 hacía ``shutil.copy2`` del fichero con la base abierta,
    lo que puede producir una copia corrupta: en modo WAL parte de los datos
    todavía vive en el diario y no en el ``.db``.  ``Connection.backup``
    resuelve esto y funciona con la base en uso.
    """
    from .config import directorio_copias

    if destino is None:
        marca = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        destino = directorio_copias() / f"controlhorario_{marca}.db"
    destino.parent.mkdir(parents=True, exist_ok=True)

    respaldo = sqlite3.connect(str(destino))
    try:
        conexion.backup(respaldo)
    finally:
        respaldo.close()

    registrar_auditoria(
        conexion, actor=actor, accion="COPIA_SEGURIDAD", detalle=destino.name
    )
    _rotar_copias(destino.parent, conservar)
    return destino


def _rotar_copias(carpeta: Path, conservar: int) -> None:
    """Deja sólo las N copias más recientes para no llenar el disco."""
    copias = sorted(
        carpeta.glob("controlhorario_*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for sobrante in copias[conservar:]:
        try:
            sobrante.unlink()
        except OSError:
            pass


__all__ += ["copia_seguridad"]
