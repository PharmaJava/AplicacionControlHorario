"""Reglas de cumplimiento y alertas.

Cada alerta cita el precepto que la sostiene para que quien la lea pueda
comprobarla.  Las referencias corresponden al texto refundido del Estatuto de
los Trabajadores (Real Decreto Legislativo 2/2015).

Aviso importante: esta comprobación es una **ayuda**, no un dictamen jurídico.
Los convenios colectivos pueden endurecer o flexibilizar varios de estos
límites (distribución irregular de jornada, descansos compensatorios, jornadas
especiales del RD 1561/1995…), así que los umbrales son configurables en
``Ajustes`` y las alertas deben revisarse con criterio.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from collections.abc import Iterable, Sequence

from . import db
from .config import Ajustes
from .dominio import Jornada, Trabajador, formatear_horas, jornadas_de

GRAVE = "grave"
AVISO = "aviso"
INFO = "info"

_ORDEN_GRAVEDAD = {GRAVE: 0, AVISO: 1, INFO: 2}


@dataclass(frozen=True)
class Alerta:
    codigo: str
    gravedad: str
    mensaje: str
    referencia: str
    trabajador_id: int | None = None
    trabajador: str = ""
    fecha: dt.date | None = None

    @property
    def fecha_texto(self) -> str:
        return self.fecha.strftime("%d/%m/%Y") if self.fecha else ""


# --------------------------------------------------------------------------- #
# Reglas sobre jornadas
# --------------------------------------------------------------------------- #

def analizar_trabajador(
    jornadas: Sequence[Jornada],
    trabajador: Trabajador,
    ajustes: Ajustes,
    *,
    ahora: dt.datetime | None = None,
) -> list[Alerta]:
    """Aplica todas las reglas de jornada a una persona."""
    ahora = ahora or db.ahora_utc()
    alertas: list[Alerta] = []
    ordenadas = sorted(jornadas, key=lambda j: j.inicio)

    def alerta(codigo: str, gravedad: str, mensaje: str, referencia: str,
               fecha: dt.date | None) -> None:
        alertas.append(
            Alerta(
                codigo=codigo,
                gravedad=gravedad,
                mensaje=mensaje,
                referencia=referencia,
                trabajador_id=trabajador.id,
                trabajador=trabajador.nombre,
                fecha=fecha,
            )
        )

    # -- Jornadas abiertas -------------------------------------------------- #
    for jornada in ordenadas:
        if not jornada.abierta:
            continue
        horas = (ahora - jornada.inicio).total_seconds() / 3600
        if horas > 16:
            alerta(
                "JORNADA_SIN_CERRAR",
                GRAVE,
                f"Jornada del {db.a_local(jornada.inicio):%d/%m/%Y %H:%M} sin "
                f"salida desde hace {horas:.0f} horas. Falta el fichaje de "
                "salida: regístralo mediante una rectificación motivada.",
                "art. 34.9 ET (el registro debe reflejar inicio y fin)",
                jornada.fecha,
            )

    # -- Jornada diaria y pausas -------------------------------------------- #
    umbral_pausa = 4.5 if trabajador.es_menor else ajustes.umbral_pausa_horas
    minutos_pausa_exigidos = 30 if trabajador.es_menor else ajustes.pausa_minima_minutos

    for jornada in ordenadas:
        if jornada.abierta:
            continue
        trabajadas = jornada.minutos_trabajados(ajustes.pausas_computan_como_trabajo)
        if trabajadas > ajustes.horas_diarias_ordinarias * 60:
            alerta(
                "JORNADA_DIARIA",
                AVISO,
                f"{formatear_horas(trabajadas)} trabajados en un día "
                f"(ordinaria máxima: {ajustes.horas_diarias_ordinarias:g} h). "
                "Sólo es válido si el convenio permite otra distribución.",
                "art. 34.3 ET",
                jornada.fecha,
            )
        if jornada.minutos_presencia > umbral_pausa * 60 and (
            jornada.minutos_pausa < minutos_pausa_exigidos
        ):
            alerta(
                "PAUSA_INSUFICIENTE",
                AVISO,
                f"Jornada continuada de {formatear_horas(jornada.minutos_presencia)} "
                f"con sólo {jornada.minutos_pausa} min de pausa "
                f"(mínimo {minutos_pausa_exigidos} min"
                + (" por ser menor de 18 años" if trabajador.es_menor else "")
                + ").",
                "art. 34.4 ET",
                jornada.fecha,
            )

    # -- Descanso entre jornadas -------------------------------------------- #
    cerradas = [j for j in ordenadas if not j.abierta]
    for anterior, siguiente in zip(cerradas, cerradas[1:], strict=False):
        if anterior.fin is None:
            continue
        descanso = (siguiente.inicio - anterior.fin).total_seconds() / 3600
        if 0 <= descanso < ajustes.descanso_entre_jornadas_horas:
            alerta(
                "DESCANSO_ENTRE_JORNADAS",
                GRAVE,
                f"Sólo {descanso:.1f} h entre la salida del "
                f"{db.a_local(anterior.fin):%d/%m} y la entrada del "
                f"{db.a_local(siguiente.inicio):%d/%m} "
                f"(mínimo {ajustes.descanso_entre_jornadas_horas:g} h).",
                "art. 34.3 ET",
                siguiente.fecha,
            )

    # -- Descanso semanal ---------------------------------------------------- #
    alertas.extend(_descanso_semanal(cerradas, trabajador, ajustes))

    # -- Cómputo semanal ----------------------------------------------------- #
    limite_semanal = trabajador.jornada_semanal or ajustes.horas_semanales
    for (anio, semana), grupo in _por_semana(ordenadas).items():
        minutos = sum(
            j.minutos_trabajados(ajustes.pausas_computan_como_trabajo) for j in grupo
        )
        if minutos > limite_semanal * 60:
            exceso = minutos - int(limite_semanal * 60)
            alerta(
                "EXCESO_SEMANAL",
                AVISO,
                f"Semana {semana}/{anio}: {formatear_horas(minutos)} trabajados, "
                f"{formatear_horas(exceso)} por encima de las "
                f"{limite_semanal:g} h pactadas. Deben registrarse como horas "
                "extraordinarias o compensarse.",
                "art. 34.1 y 35 ET",
                min(j.fecha for j in grupo),
            )

    # -- Horas extraordinarias anuales --------------------------------------- #
    for anio, grupo in _por_anio(ordenadas).items():
        minutos = sum(
            j.minutos_trabajados(ajustes.pausas_computan_como_trabajo) for j in grupo
        )
        semanas = len({(j.inicio.isocalendar()[0], j.inicio.isocalendar()[1])
                       for j in grupo})
        ordinarias = limite_semanal * 60 * semanas
        extra = minutos - ordinarias
        if extra > ajustes.horas_extra_anuales * 60:
            alerta(
                "HORAS_EXTRA_ANUALES",
                GRAVE,
                f"Año {anio}: aproximadamente {formatear_horas(int(extra))} por "
                f"encima de la jornada ordinaria, más del tope anual de "
                f"{ajustes.horas_extra_anuales} horas extraordinarias.",
                "art. 35.2 ET",
                dt.date(anio, 12, 31),
            )

    return alertas


def _por_semana(
    jornadas: Iterable[Jornada],
) -> dict[tuple[int, int], list[Jornada]]:
    grupos: dict[tuple[int, int], list[Jornada]] = defaultdict(list)
    for jornada in jornadas:
        local = db.a_local(jornada.inicio)
        anio, semana, _ = local.isocalendar()
        grupos[(anio, semana)].append(jornada)
    return grupos


def _por_anio(jornadas: Iterable[Jornada]) -> dict[int, list[Jornada]]:
    grupos: dict[int, list[Jornada]] = defaultdict(list)
    for jornada in jornadas:
        grupos[db.a_local(jornada.inicio).year].append(jornada)
    return grupos


def _descanso_semanal(
    cerradas: Sequence[Jornada], trabajador: Trabajador, ajustes: Ajustes
) -> list[Alerta]:
    """Comprueba el descanso semanal ininterrumpido de día y medio."""
    alertas: list[Alerta] = []
    minimo = ajustes.descanso_semanal_horas
    if trabajador.es_menor:
        minimo = max(minimo, 48)  # art. 37.1 ET: dos días para menores de 18

    for (anio, semana), grupo in sorted(_por_semana(cerradas).items()):
        if len(grupo) < 6:
            continue  # con cinco jornadas o menos hay hueco de sobra
        ordenadas = sorted(grupo, key=lambda j: j.inicio)
        mayor = 0.0
        for anterior, siguiente in zip(ordenadas, ordenadas[1:], strict=False):
            if anterior.fin is None:
                continue
            mayor = max(
                mayor, (siguiente.inicio - anterior.fin).total_seconds() / 3600
            )
        if mayor < minimo:
            alertas.append(
                Alerta(
                    codigo="DESCANSO_SEMANAL",
                    gravedad=GRAVE,
                    mensaje=(
                        f"Semana {semana}/{anio}: el mayor descanso continuado "
                        f"fue de {mayor:.1f} h, por debajo de las {minimo:g} h "
                        "de descanso semanal."
                    ),
                    referencia="art. 37.1 ET",
                    trabajador_id=trabajador.id,
                    trabajador=trabajador.nombre,
                    fecha=min(j.fecha for j in grupo),
                )
            )
    return alertas


# --------------------------------------------------------------------------- #
# Diagnóstico global de la instalación
# --------------------------------------------------------------------------- #

def analizar_periodo(
    conexion: sqlite3.Connection,
    trabajadores: Sequence[Trabajador],
    ajustes: Ajustes,
    desde: dt.datetime,
    hasta: dt.datetime,
) -> list[Alerta]:
    alertas: list[Alerta] = []
    for trabajador in trabajadores:
        jornadas = jornadas_de(conexion, trabajador.id, desde=desde, hasta=hasta)
        alertas.extend(analizar_trabajador(jornadas, trabajador, ajustes))
    return ordenar(alertas)


def diagnostico(
    conexion: sqlite3.Connection,
    trabajadores: Sequence[Trabajador],
    ajustes: Ajustes,
) -> list[Alerta]:
    """Revisa el estado de cumplimiento de la propia instalación."""
    alertas: list[Alerta] = []

    if not ajustes.empresa.strip():
        alertas.append(
            Alerta(
                "SIN_EMPRESA",
                AVISO,
                "No has rellenado los datos de la empresa. Los informes para la "
                "Inspección de Trabajo deben identificar a la empresa y el "
                "centro de trabajo.",
                "art. 34.9 ET",
            )
        )

    sin_pin = [t for t in trabajadores if not t.tiene_pin]
    if sin_pin:
        alertas.append(
            Alerta(
                "SIN_PIN",
                GRAVE,
                f"{len(sin_pin)} trabajador(es) sin PIN: "
                f"{', '.join(t.codigo for t in sin_pin[:5])}"
                + (" …" if len(sin_pin) > 5 else "")
                + ". Sin identificación personal el registro no es fiable, "
                "porque cualquiera puede fichar por otro.",
                "art. 34.9 ET (registro fiable)",
            )
        )

    informe = db.verificar_integridad(conexion)
    if not informe["integro"]:
        total = len(informe["eventos"]["incidencias"]) + len(
            informe["auditoria"]["incidencias"]
        )
        alertas.append(
            Alerta(
                "INTEGRIDAD",
                GRAVE,
                f"La cadena de integridad presenta {total} incidencia(s): la "
                "base de datos se ha modificado fuera de la aplicación. "
                "Revisa el informe de integridad y restaura una copia.",
                "trazabilidad del registro",
            )
        )

    caducan = db.eventos_proximos_a_caducar(conexion, ajustes.anios_conservacion)
    if caducan:
        alertas.append(
            Alerta(
                "CONSERVACION",
                INFO,
                f"{caducan} fichaje(s) cumplen en los próximos 30 días los "
                f"{ajustes.anios_conservacion} años de conservación obligatoria. "
                "A partir de esa fecha puedes purgarlos.",
                "art. 34.9 ET · art. 5.1.e) RGPD",
            )
        )

    abiertas = 0
    for trabajador in trabajadores:
        abiertas += sum(1 for j in jornadas_de(conexion, trabajador.id) if j.abierta)
    if abiertas:
        alertas.append(
            Alerta(
                "JORNADAS_ABIERTAS",
                AVISO,
                f"Hay {abiertas} jornada(s) sin fichaje de salida.",
                "art. 34.9 ET",
            )
        )

    return ordenar(alertas)


def ordenar(alertas: Iterable[Alerta]) -> list[Alerta]:
    return sorted(
        alertas,
        key=lambda a: (
            _ORDEN_GRAVEDAD.get(a.gravedad, 9),
            a.fecha or dt.date.min,
            a.trabajador,
        ),
    )


def resumen_gravedad(alertas: Sequence[Alerta]) -> dict[str, int]:
    conteo = {GRAVE: 0, AVISO: 0, INFO: 0}
    for alerta in alertas:
        conteo[alerta.gravedad] = conteo.get(alerta.gravedad, 0) + 1
    return conteo


__all__ = [
    "AVISO",
    "Alerta",
    "GRAVE",
    "INFO",
    "analizar_periodo",
    "analizar_trabajador",
    "diagnostico",
    "ordenar",
    "resumen_gravedad",
]
