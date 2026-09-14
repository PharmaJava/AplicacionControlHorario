"""Lógica de negocio: trabajadores, fichajes y reconstrucción de jornadas.

Las jornadas no se guardan: se **derivan** del libro de eventos cada vez que se
consultan.  Así el dato almacenado es siempre el hecho registrado (a las 8:02
esta persona fichó entrada) y nunca un total calculado que pueda quedar
desincronizado con los fichajes que lo sustentan.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from dataclasses import dataclass, field
from collections.abc import Sequence

from . import db
from .config import MODALIDADES, ROLES, TIPOS_EVENTO
from .seguridad import Cifrador, hash_secreto, validar_pin, verificar_secreto

FUERA = "FUERA"
DENTRO = "DENTRO"
EN_PAUSA = "EN_PAUSA"


class ErrorDominio(Exception):
    """Operación no válida según las reglas de negocio."""


# --------------------------------------------------------------------------- #
# Modelos
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Trabajador:
    id: int
    codigo: str
    nombre: str
    dni: str
    rol: str
    activo: bool
    es_menor: bool
    jornada_semanal: float | None
    alta: dt.datetime
    baja: dt.datetime | None
    tiene_pin: bool

    @property
    def etiqueta(self) -> str:
        return f"{self.codigo} · {self.nombre}"


@dataclass(frozen=True)
class Evento:
    id: int
    trabajador_id: int
    tipo: str
    momento: dt.datetime
    modalidad: str
    origen: str
    nota: str
    autor: str
    rectificado: bool = False
    momento_original: dt.datetime | None = None
    motivo: str = ""
    # Cuándo entró el dato en el sistema. En un fichaje normal coincide casi
    # con `momento`; en uno importado del sistema anterior son fechas muy
    # distintas, y esa diferencia es justo lo que debe verse en un informe.
    registrado: dt.datetime | None = None


@dataclass
class Jornada:
    trabajador_id: int
    inicio: dt.datetime
    fin: dt.datetime | None = None
    modalidad: str = "PRESENCIAL"
    pausas: list[tuple[dt.datetime, dt.datetime | None]] = field(default_factory=list)
    incidencia: bool = False
    rectificada: bool = False
    nota: str = ""
    origen: str = "APP"
    registrada: dt.datetime | None = None

    @property
    def importada(self) -> bool:
        """¿Viene del programa anterior en vez de haberse fichado aquí?"""
        return self.origen == "MIGRADO"

    @property
    def abierta(self) -> bool:
        return self.fin is None

    @property
    def fecha(self) -> dt.date:
        return self.inicio.date()

    @property
    def minutos_pausa(self) -> int:
        total = 0
        for inicio, fin in self.pausas:
            if fin is not None:
                total += int((fin - inicio).total_seconds() // 60)
        return total

    @property
    def minutos_presencia(self) -> int:
        """Minutos entre la entrada y la salida, pausas incluidas."""
        if self.fin is None:
            return 0
        return int((self.fin - self.inicio).total_seconds() // 60)

    def minutos_trabajados(
        self, pausas_computan: bool = False, ahora: dt.datetime | None = None
    ) -> int:
        """Minutos de trabajo efectivo.

        Una jornada todavía abierta cuenta cero salvo que se indique ``ahora``,
        en cuyo caso se cronometra hasta ese instante.  Los informes la dejan a
        cero (aún no ha terminado); el panel del día sí la cronometra, porque
        de lo contrario mostraría cero mientras la plantilla está trabajando.
        """
        fin = self.fin if self.fin is not None else ahora
        if fin is None:
            return 0
        presencia = max(0, int((fin - self.inicio).total_seconds() // 60))
        if pausas_computan:
            return presencia
        pausa = 0
        for inicio, cierre in self.pausas:
            cierre = cierre if cierre is not None else ahora
            if cierre is None:
                continue
            pausa += max(0, int((cierre - inicio).total_seconds() // 60))
        return max(0, presencia - pausa)


def formatear_horas(minutos: int) -> str:
    signo = "-" if minutos < 0 else ""
    minutos = abs(int(minutos))
    return f"{signo}{minutos // 60}h {minutos % 60:02d}m"


# --------------------------------------------------------------------------- #
# Trabajadores
# --------------------------------------------------------------------------- #

def _siguiente_codigo(conexion: sqlite3.Connection) -> str:
    fila = conexion.execute(
        "SELECT codigo FROM trabajadores WHERE codigo LIKE 'E%' "
        "ORDER BY LENGTH(codigo) DESC, codigo DESC LIMIT 1"
    ).fetchone()
    if not fila:
        return "E001"
    try:
        return f"E{int(fila['codigo'][1:]) + 1:03d}"
    except ValueError:
        total = conexion.execute(
            "SELECT COUNT(*) AS n FROM trabajadores"
        ).fetchone()["n"]
        return f"E{total + 1:03d}"


def alta_trabajador(
    conexion: sqlite3.Connection,
    cifrador: Cifrador,
    *,
    nombre: str,
    pin: str,
    dni: str = "",
    rol: str = "EMPLEADO",
    es_menor: bool = False,
    jornada_semanal: float | None = None,
    autor: str = "admin",
) -> Trabajador:
    nombre = nombre.strip()
    if not nombre:
        raise ErrorDominio("El nombre no puede estar vacío.")
    if rol not in ROLES:
        raise ErrorDominio(f"Rol desconocido: {rol}")
    valido, mensaje = validar_pin(pin)
    if not valido:
        raise ErrorDominio(mensaje)

    dni = dni.strip().upper()
    dni_indice = cifrador.indice(dni) if dni else None
    if dni_indice and conexion.execute(
        "SELECT 1 FROM trabajadores WHERE dni_indice = ?", (dni_indice,)
    ).fetchone():
        raise ErrorDominio(f"Ya existe un trabajador con el DNI {dni}.")

    with db.transaccion(conexion):
        codigo = _siguiente_codigo(conexion)
        cursor = conexion.execute(
            """
            INSERT INTO trabajadores (
                codigo, nombre_cifrado, nombre_indice, dni_cifrado, dni_indice,
                pin_hash, rol, activo, es_menor, jornada_semanal, alta_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (
                codigo,
                cifrador.cifrar(nombre),
                cifrador.indice(nombre),
                cifrador.cifrar(dni) if dni else None,
                dni_indice,
                hash_secreto(pin),
                rol,
                int(es_menor),
                jornada_semanal,
                db.a_iso(db.ahora_utc()),
            ),
        )
        db.registrar_auditoria(
            conexion,
            actor=autor,
            accion="ALTA_TRABAJADOR",
            detalle=f"{codigo} (rol {rol})",
        )
    return obtener_trabajador(conexion, cifrador, int(cursor.lastrowid))


def obtener_trabajador(
    conexion: sqlite3.Connection, cifrador: Cifrador, trabajador_id: int
) -> Trabajador:
    fila = conexion.execute(
        "SELECT * FROM trabajadores WHERE id = ?", (trabajador_id,)
    ).fetchone()
    if not fila:
        raise ErrorDominio(f"No existe el trabajador con id {trabajador_id}.")
    return _a_trabajador(fila, cifrador)


def buscar_por_codigo(
    conexion: sqlite3.Connection, cifrador: Cifrador, codigo: str
) -> Trabajador | None:
    fila = conexion.execute(
        "SELECT * FROM trabajadores WHERE codigo = ? COLLATE NOCASE",
        (codigo.strip(),),
    ).fetchone()
    return _a_trabajador(fila, cifrador) if fila else None


def listar_trabajadores(
    conexion: sqlite3.Connection, cifrador: Cifrador, incluir_bajas: bool = False
) -> list[Trabajador]:
    consulta = "SELECT * FROM trabajadores"
    if not incluir_bajas:
        consulta += " WHERE activo = 1"
    consulta += " ORDER BY codigo"
    personas = [_a_trabajador(f, cifrador) for f in conexion.execute(consulta)]
    return sorted(personas, key=lambda t: t.nombre.casefold())


def _a_trabajador(fila: sqlite3.Row, cifrador: Cifrador) -> Trabajador:
    return Trabajador(
        id=fila["id"],
        codigo=fila["codigo"],
        nombre=cifrador.descifrar(fila["nombre_cifrado"]),
        dni=cifrador.descifrar(fila["dni_cifrado"]),
        rol=fila["rol"],
        activo=bool(fila["activo"]),
        es_menor=bool(fila["es_menor"]),
        jornada_semanal=fila["jornada_semanal"],
        alta=db.desde_iso(fila["alta_utc"]),
        baja=db.desde_iso(fila["baja_utc"]) if fila["baja_utc"] else None,
        tiene_pin=bool(fila["pin_hash"]),
    )


def modificar_trabajador(
    conexion: sqlite3.Connection,
    cifrador: Cifrador,
    trabajador_id: int,
    *,
    nombre: str | None = None,
    dni: str | None = None,
    rol: str | None = None,
    es_menor: bool | None = None,
    jornada_semanal: float | None = None,
    autor: str = "admin",
) -> Trabajador:
    actual = obtener_trabajador(conexion, cifrador, trabajador_id)
    cambios: list[str] = []
    asignaciones: list[str] = []
    valores: list[object] = []

    if nombre is not None and nombre.strip() and nombre.strip() != actual.nombre:
        asignaciones += ["nombre_cifrado = ?", "nombre_indice = ?"]
        valores += [cifrador.cifrar(nombre.strip()), cifrador.indice(nombre.strip())]
        cambios.append("nombre")
    if dni is not None and dni.strip().upper() != actual.dni:
        limpio = dni.strip().upper()
        asignaciones += ["dni_cifrado = ?", "dni_indice = ?"]
        valores += [
            cifrador.cifrar(limpio) if limpio else None,
            cifrador.indice(limpio) if limpio else None,
        ]
        cambios.append("DNI")
    if rol is not None and rol != actual.rol:
        if rol not in ROLES:
            raise ErrorDominio(f"Rol desconocido: {rol}")
        asignaciones.append("rol = ?")
        valores.append(rol)
        cambios.append(f"rol → {rol}")
    if es_menor is not None and es_menor != actual.es_menor:
        asignaciones.append("es_menor = ?")
        valores.append(int(es_menor))
        cambios.append("condición de menor")
    if jornada_semanal is not None and jornada_semanal != actual.jornada_semanal:
        asignaciones.append("jornada_semanal = ?")
        valores.append(jornada_semanal)
        cambios.append("jornada semanal")

    if not asignaciones:
        return actual

    with db.transaccion(conexion):
        valores.append(trabajador_id)
        conexion.execute(
            f"UPDATE trabajadores SET {', '.join(asignaciones)} WHERE id = ?",
            valores,
        )
        db.registrar_auditoria(
            conexion,
            actor=autor,
            accion="MODIFICA_TRABAJADOR",
            detalle=f"{actual.codigo}: {', '.join(cambios)}",
        )
    return obtener_trabajador(conexion, cifrador, trabajador_id)


def cambiar_pin(
    conexion: sqlite3.Connection,
    trabajador_id: int,
    pin_nuevo: str,
    *,
    autor: str = "admin",
) -> None:
    valido, mensaje = validar_pin(pin_nuevo)
    if not valido:
        raise ErrorDominio(mensaje)
    with db.transaccion(conexion):
        conexion.execute(
            "UPDATE trabajadores SET pin_hash = ? WHERE id = ?",
            (hash_secreto(pin_nuevo), trabajador_id),
        )
        db.registrar_auditoria(
            conexion,
            actor=autor,
            accion="CAMBIO_PIN",
            detalle=f"trabajador id {trabajador_id}",
        )


def baja_trabajador(
    conexion: sqlite3.Connection,
    cifrador: Cifrador,
    trabajador_id: int,
    *,
    autor: str = "admin",
) -> None:
    """Baja lógica: los fichajes deben conservarse cuatro años (art. 34.9 ET)."""
    trabajador = obtener_trabajador(conexion, cifrador, trabajador_id)
    if estado_actual(conexion, trabajador_id) != FUERA:
        raise ErrorDominio(
            f"{trabajador.nombre} tiene una jornada abierta. "
            "Ciérrala antes de dar de baja."
        )
    with db.transaccion(conexion):
        conexion.execute(
            "UPDATE trabajadores SET activo = 0, baja_utc = ? WHERE id = ?",
            (db.a_iso(db.ahora_utc()), trabajador_id),
        )
        db.registrar_auditoria(
            conexion,
            actor=autor,
            accion="BAJA_TRABAJADOR",
            detalle=trabajador.codigo,
        )


def reactivar_trabajador(
    conexion: sqlite3.Connection, trabajador_id: int, *, autor: str = "admin"
) -> None:
    with db.transaccion(conexion):
        conexion.execute(
            "UPDATE trabajadores SET activo = 1, baja_utc = NULL WHERE id = ?",
            (trabajador_id,),
        )
        db.registrar_auditoria(
            conexion,
            actor=autor,
            accion="REACTIVA_TRABAJADOR",
            detalle=f"trabajador id {trabajador_id}",
        )


def autenticar(
    conexion: sqlite3.Connection, cifrador: Cifrador, codigo: str, pin: str
) -> Trabajador:
    """Identificación fiable en el terminal: código + PIN personal.

    En la versión de 2024 bastaba con teclear el ID ajeno para fichar por otra
    persona, lo que hacía el registro poco fiable a efectos probatorios.
    """
    fila = conexion.execute(
        "SELECT * FROM trabajadores WHERE codigo = ? COLLATE NOCASE",
        (codigo.strip(),),
    ).fetchone()
    if not fila or not verificar_secreto(pin, fila["pin_hash"]):
        raise ErrorDominio("Código o PIN incorrectos.")
    if not fila["activo"]:
        raise ErrorDominio("Este trabajador está dado de baja.")
    return _a_trabajador(fila, cifrador)


# --------------------------------------------------------------------------- #
# Fichajes
# --------------------------------------------------------------------------- #

_TRANSICIONES = {
    (FUERA, "ENTRADA"): DENTRO,
    (DENTRO, "PAUSA_INICIO"): EN_PAUSA,
    (EN_PAUSA, "PAUSA_FIN"): DENTRO,
    (DENTRO, "SALIDA"): FUERA,
    (EN_PAUSA, "SALIDA"): FUERA,
    (DENTRO, "INCIDENCIA"): FUERA,
    (EN_PAUSA, "INCIDENCIA"): FUERA,
}

_EXPLICACION = {
    FUERA: "sin jornada abierta",
    DENTRO: "trabajando",
    EN_PAUSA: "en pausa",
}


def estado_actual(conexion: sqlite3.Connection, trabajador_id: int) -> str:
    eventos = eventos_efectivos(conexion, trabajador_id=trabajador_id)
    estado = FUERA
    for evento in eventos:
        estado = _TRANSICIONES.get((estado, evento.tipo), estado)
    return estado


# Lo que una persona puede registrar al fichar.  «RECTIFICACION» también es un
# tipo de evento del libro, pero lo genera rectificar(): nadie lo teclea.
TIPOS_FICHAJE = tuple(t for t in TIPOS_EVENTO if t != "RECTIFICACION")


def fichar(
    conexion: sqlite3.Connection,
    trabajador_id: int,
    tipo: str,
    *,
    momento: dt.datetime | None = None,
    modalidad: str = "PRESENCIAL",
    nota: str = "",
    autor: str = "",
    origen: str = "APP",
) -> Evento:
    if tipo not in TIPOS_FICHAJE:
        raise ErrorDominio(f"Tipo de fichaje desconocido: {tipo}")
    if modalidad not in MODALIDADES:
        raise ErrorDominio(f"Modalidad desconocida: {modalidad}")

    estado = estado_actual(conexion, trabajador_id)
    if (estado, tipo) not in _TRANSICIONES:
        raise ErrorDominio(
            f"No se puede registrar «{nombre_tipo(tipo)}» estando "
            f"{_EXPLICACION[estado]}."
        )

    momento = momento or db.ahora_utc()
    ultimo = ultimo_evento(conexion, trabajador_id)
    if ultimo and momento < ultimo.momento:
        raise ErrorDominio(
            "El fichaje sería anterior al último registrado "
            f"({db.a_local(ultimo.momento):%d/%m/%Y %H:%M})."
        )

    evento_id = db.registrar_evento(
        conexion,
        trabajador_id=trabajador_id,
        tipo=tipo,
        ts_utc=db.a_iso(momento),
        modalidad=modalidad,
        origen=origen,
        nota=nota,
        autor=autor,
    )
    return _leer_evento(conexion, evento_id)


def rectificar(
    conexion: sqlite3.Connection,
    evento_id: int,
    *,
    momento_nuevo: dt.datetime | None,
    motivo: str,
    autor: str,
    anular: bool = False,
) -> Evento:
    """Corrige un fichaje sin borrarlo: anexa una RECTIFICACION trazable.

    El evento original permanece en el libro; la corrección deja constancia de
    quién la hizo, cuándo y por qué, que es exactamente lo que debe poder
    acreditarse ante la Inspección de Trabajo.
    """
    motivo = motivo.strip()
    if not motivo:
        raise ErrorDominio("La rectificación requiere un motivo.")

    original = conexion.execute(
        "SELECT * FROM eventos WHERE id = ?", (evento_id,)
    ).fetchone()
    if not original:
        raise ErrorDominio(f"No existe el fichaje {evento_id}.")
    if original["tipo"] == "RECTIFICACION":
        raise ErrorDominio("No se rectifica una rectificación; corrige el original.")
    if not anular and momento_nuevo is None:
        raise ErrorDominio("Indica la nueva fecha y hora o marca la anulación.")

    nuevo_id = db.registrar_evento(
        conexion,
        trabajador_id=original["trabajador_id"],
        tipo="RECTIFICACION",
        ts_utc=db.a_iso(momento_nuevo) if momento_nuevo else original["ts_utc"],
        modalidad=original["modalidad"],
        origen="RECTIFICACION",
        nota="ANULAR" if anular else "",
        autor=autor,
        rectifica_id=evento_id,
        motivo=motivo,
    )
    db.registrar_auditoria(
        conexion,
        actor=autor,
        accion="ANULA_FICHAJE" if anular else "RECTIFICA_FICHAJE",
        detalle=f"fichaje {evento_id}: {motivo}",
    )
    return _leer_evento(conexion, nuevo_id)


def nombre_tipo(tipo: str) -> str:
    return {
        "ENTRADA": "entrada",
        "SALIDA": "salida",
        "PAUSA_INICIO": "inicio de pausa",
        "PAUSA_FIN": "fin de pausa",
        "INCIDENCIA": "incidencia",
        "RECTIFICACION": "rectificación",
    }.get(tipo, tipo.lower())


def _leer_evento(conexion: sqlite3.Connection, evento_id: int) -> Evento:
    fila = conexion.execute(
        "SELECT * FROM eventos WHERE id = ?", (evento_id,)
    ).fetchone()
    return Evento(
        id=fila["id"],
        trabajador_id=fila["trabajador_id"],
        tipo=fila["tipo"],
        momento=db.desde_iso(fila["ts_utc"]),
        modalidad=fila["modalidad"],
        origen=fila["origen"],
        nota=fila["nota"],
        autor=fila["autor"],
        motivo=fila["motivo"],
        registrado=db.desde_iso(fila["creado_utc"]),
    )


def ultimo_evento(
    conexion: sqlite3.Connection, trabajador_id: int
) -> Evento | None:
    eventos = eventos_efectivos(conexion, trabajador_id=trabajador_id)
    return eventos[-1] if eventos else None


# --------------------------------------------------------------------------- #
# Vista efectiva: aplica las rectificaciones sobre los originales
# --------------------------------------------------------------------------- #

def eventos_efectivos(
    conexion: sqlite3.Connection,
    *,
    trabajador_id: int | None = None,
    desde: dt.datetime | None = None,
    hasta: dt.datetime | None = None,
) -> list[Evento]:
    """Devuelve los fichajes ya corregidos, listos para calcular jornadas.

    Se leen todos los eventos del trabajador (las rectificaciones pueden ser
    posteriores al rango pedido) y el filtro por fechas se aplica al final,
    sobre el momento ya corregido.
    """
    condicion, parametros = "", []
    if trabajador_id is not None:
        condicion = " WHERE trabajador_id = ?"
        parametros.append(trabajador_id)
    filas = list(
        conexion.execute(
            f"SELECT * FROM eventos{condicion} ORDER BY ts_utc, id", parametros
        )
    )

    correcciones: dict[int, sqlite3.Row] = {}
    anulados: set[int] = set()
    for fila in filas:
        if fila["tipo"] != "RECTIFICACION" or fila["rectifica_id"] is None:
            continue
        objetivo = int(fila["rectifica_id"])
        if fila["nota"] == "ANULAR":
            anulados.add(objetivo)
            correcciones.pop(objetivo, None)
        else:
            anulados.discard(objetivo)
            correcciones[objetivo] = fila

    resultado: list[Evento] = []
    for fila in filas:
        if fila["tipo"] == "RECTIFICACION" or fila["id"] in anulados:
            continue
        correccion = correcciones.get(fila["id"])
        momento = db.desde_iso(
            correccion["ts_utc"] if correccion else fila["ts_utc"]
        )
        resultado.append(
            Evento(
                id=fila["id"],
                trabajador_id=fila["trabajador_id"],
                tipo=fila["tipo"],
                momento=momento,
                modalidad=fila["modalidad"],
                origen=fila["origen"],
                nota=fila["nota"],
                autor=fila["autor"],
                rectificado=correccion is not None,
                momento_original=(
                    db.desde_iso(fila["ts_utc"]) if correccion else None
                ),
                motivo=correccion["motivo"] if correccion else "",
                registrado=db.desde_iso(fila["creado_utc"]),
            )
        )

    resultado.sort(key=lambda e: (e.momento, e.id))
    if desde is not None:
        resultado = [e for e in resultado if e.momento >= desde]
    if hasta is not None:
        resultado = [e for e in resultado if e.momento <= hasta]
    return resultado


# --------------------------------------------------------------------------- #
# Reconstrucción de jornadas
# --------------------------------------------------------------------------- #

def construir_jornadas(eventos: Sequence[Evento]) -> list[Jornada]:
    """Empareja el flujo de eventos de UNA persona en jornadas."""
    jornadas: list[Jornada] = []
    actual: Jornada | None = None

    for evento in eventos:
        if evento.tipo == "ENTRADA":
            if actual is not None:
                # Entrada sin salida previa: se cierra la anterior como abierta
                # para no perderla y se avisa en el módulo de normativa.
                jornadas.append(actual)
            actual = Jornada(
                trabajador_id=evento.trabajador_id,
                inicio=evento.momento,
                modalidad=evento.modalidad,
                rectificada=evento.rectificado,
                origen=evento.origen,
                registrada=evento.registrado,
            )
        elif actual is None:
            continue  # salida o pausa huérfana: sin jornada abierta
        elif evento.tipo == "PAUSA_INICIO":
            actual.pausas.append((evento.momento, None))
            actual.rectificada |= evento.rectificado
        elif evento.tipo == "PAUSA_FIN":
            if actual.pausas and actual.pausas[-1][1] is None:
                inicio, _ = actual.pausas[-1]
                actual.pausas[-1] = (inicio, evento.momento)
            actual.rectificada |= evento.rectificado
        elif evento.tipo in {"SALIDA", "INCIDENCIA"}:
            actual.fin = evento.momento
            actual.incidencia = evento.tipo == "INCIDENCIA"
            actual.rectificada |= evento.rectificado
            if evento.nota:
                actual.nota = evento.nota
            # Una pausa abierta al salir se cierra en el momento de la salida.
            if actual.pausas and actual.pausas[-1][1] is None:
                inicio, _ = actual.pausas[-1]
                actual.pausas[-1] = (inicio, evento.momento)
            jornadas.append(actual)
            actual = None

    if actual is not None:
        jornadas.append(actual)
    return jornadas


def jornadas_de(
    conexion: sqlite3.Connection,
    trabajador_id: int,
    *,
    desde: dt.datetime | None = None,
    hasta: dt.datetime | None = None,
) -> list[Jornada]:
    """Jornadas de un trabajador que *empiezan* dentro del rango pedido."""
    todos = eventos_efectivos(conexion, trabajador_id=trabajador_id)
    jornadas = construir_jornadas(todos)
    if desde is not None:
        jornadas = [j for j in jornadas if j.inicio >= desde]
    if hasta is not None:
        jornadas = [j for j in jornadas if j.inicio <= hasta]
    return jornadas


def resumen_periodo(
    conexion: sqlite3.Connection,
    trabajador_id: int,
    desde: dt.datetime,
    hasta: dt.datetime,
    *,
    pausas_computan: bool = False,
    ahora: dt.datetime | None = None,
) -> dict[str, object]:
    jornadas = jornadas_de(conexion, trabajador_id, desde=desde, hasta=hasta)
    trabajados = sum(j.minutos_trabajados(pausas_computan, ahora) for j in jornadas)
    return {
        "jornadas": len(jornadas),
        "abiertas": sum(1 for j in jornadas if j.abierta),
        "minutos_trabajados": trabajados,
        "minutos_pausa": sum(j.minutos_pausa for j in jornadas),
        "incidencias": sum(1 for j in jornadas if j.incidencia),
        "rectificadas": sum(1 for j in jornadas if j.rectificada),
        "dias_distintos": len({j.fecha for j in jornadas}),
    }


__all__ = [
    "DENTRO",
    "EN_PAUSA",
    "ErrorDominio",
    "Evento",
    "FUERA",
    "Jornada",
    "Trabajador",
    "alta_trabajador",
    "autenticar",
    "baja_trabajador",
    "buscar_por_codigo",
    "cambiar_pin",
    "construir_jornadas",
    "estado_actual",
    "eventos_efectivos",
    "fichar",
    "formatear_horas",
    "nombre_tipo",
    "jornadas_de",
    "listar_trabajadores",
    "modificar_trabajador",
    "obtener_trabajador",
    "reactivar_trabajador",
    "rectificar",
    "resumen_periodo",
    "TIPOS_FICHAJE",
    "ultimo_evento",
]
