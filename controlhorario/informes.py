"""Exportación de registros: Excel, CSV y expediente para la Inspección.

La versión de 2024 exportaba con *pandas* dos hojas planas sin totales ni
identificación de la empresa.  Aquí se usa *openpyxl* directamente: evita
arrastrar pandas y NumPy (unos 60 MB de dependencias que complicaban la
instalación) y permite dar formato al informe.

El art. 34.9 ET obliga a que el registro esté a disposición de las personas
trabajadoras, de sus representantes legales y de la Inspección de Trabajo, así
que hay tres salidas distintas:

* ``exportar_excel``      → informe de empresa, legible por una persona.
* ``exportar_trabajador`` → copia del registro propio de un trabajador.
* ``expediente_itss``     → volcado íntegro y verificable en JSON.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import sqlite3
from pathlib import Path
from typing import Any
from collections.abc import Sequence

from . import db, normativa
from .config import Ajustes, directorio_exportaciones
from .dominio import (
    Jornada,
    Trabajador,
    eventos_efectivos,
    formatear_horas,
    jornadas_de,
)
from .seguridad import Cifrador
from .version import __version__


class ErrorInforme(Exception):
    """No se ha podido generar el informe."""


def _marca_tiempo() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _destino(nombre: str, carpeta: Path | None = None) -> Path:
    carpeta = carpeta or directorio_exportaciones()
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta / nombre


def _fila_jornada(jornada: Jornada, trabajador: Trabajador, ajustes: Ajustes) -> list[Any]:
    inicio = db.a_local(jornada.inicio)
    fin = db.a_local(jornada.fin) if jornada.fin else None
    trabajados = jornada.minutos_trabajados(ajustes.pausas_computan_como_trabajo)
    return [
        trabajador.codigo,
        trabajador.nombre,
        inicio.strftime("%d/%m/%Y"),
        inicio.strftime("%H:%M"),
        fin.strftime("%H:%M") if fin else "— sin salida —",
        jornada.minutos_pausa,
        round(trabajados / 60, 2),
        jornada.modalidad.capitalize(),
        "Sí" if jornada.incidencia else "",
        "Sí" if jornada.rectificada else "",
        jornada.nota,
    ]


_CABECERA_JORNADAS = [
    "Código", "Trabajador", "Fecha", "Entrada", "Salida", "Pausa (min)",
    "Horas trabajadas", "Modalidad", "Incidencia", "Rectificada", "Observaciones",
]


# --------------------------------------------------------------------------- #
# Excel
# --------------------------------------------------------------------------- #

def exportar_excel(
    conexion: sqlite3.Connection,
    cifrador: Cifrador,
    ajustes: Ajustes,
    trabajadores: Sequence[Trabajador],
    desde: dt.datetime,
    hasta: dt.datetime,
    *,
    carpeta: Path | None = None,
) -> Path:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError as exc:  # pragma: no cover
        raise ErrorInforme(
            "Falta la dependencia 'openpyxl' para exportar a Excel.\n"
            "Instálala con:  pip install openpyxl\n"
            "Mientras tanto puedes exportar a CSV."
        ) from exc

    libro = Workbook()
    azul = PatternFill("solid", fgColor="1F3A5F")
    blanco_negrita = Font(color="FFFFFF", bold=True)

    def escribir_cabecera(hoja, cabecera: list[str]) -> None:
        hoja.append(cabecera)
        for celda in hoja[1]:
            celda.fill = azul
            celda.font = blanco_negrita
            celda.alignment = Alignment(horizontal="center", vertical="center")
        hoja.freeze_panes = "A2"

    def ajustar(hoja) -> None:
        for columna in hoja.columns:
            ancho = max((len(str(c.value)) for c in columna if c.value), default=8)
            hoja.column_dimensions[
                get_column_letter(columna[0].column)
            ].width = min(max(ancho + 3, 11), 46)

    # -- Resumen ------------------------------------------------------------ #
    resumen = libro.active
    resumen.title = "Resumen"
    resumen["A1"] = "Registro de jornada"
    resumen["A1"].font = Font(size=16, bold=True, color="1F3A5F")
    filas_meta = [
        ("Empresa", ajustes.empresa or "(sin indicar)"),
        ("CIF/NIF", ajustes.cif or "(sin indicar)"),
        ("Centro de trabajo", ajustes.centro_trabajo or "(sin indicar)"),
        ("Periodo", f"{db.a_local(desde):%d/%m/%Y} a {db.a_local(hasta):%d/%m/%Y}"),
        ("Generado", dt.datetime.now().strftime("%d/%m/%Y %H:%M")),
        ("Aplicación", f"Control Horario {__version__}"),
        ("Base legal", "art. 34.9 del Estatuto de los Trabajadores"),
        ("Conservación", f"{ajustes.anios_conservacion} años"),
    ]
    for indice, (etiqueta, valor) in enumerate(filas_meta, start=3):
        resumen.cell(row=indice, column=1, value=etiqueta).font = Font(bold=True)
        resumen.cell(row=indice, column=2, value=valor)

    cabecera_totales = [
        "Código", "Trabajador", "Jornadas", "Días", "Horas trabajadas",
        "Pausas (h)", "Incidencias", "Rectificadas", "Sin cerrar",
    ]
    inicio_totales = len(filas_meta) + 5
    for columna, titulo in enumerate(cabecera_totales, start=1):
        celda = resumen.cell(row=inicio_totales, column=columna, value=titulo)
        celda.fill = azul
        celda.font = blanco_negrita

    total_minutos = 0
    for desplazamiento, trabajador in enumerate(trabajadores, start=1):
        jornadas = jornadas_de(conexion, trabajador.id, desde=desde, hasta=hasta)
        minutos = sum(
            j.minutos_trabajados(ajustes.pausas_computan_como_trabajo)
            for j in jornadas
        )
        total_minutos += minutos
        valores = [
            trabajador.codigo,
            trabajador.nombre,
            len(jornadas),
            len({j.fecha for j in jornadas}),
            round(minutos / 60, 2),
            round(sum(j.minutos_pausa for j in jornadas) / 60, 2),
            sum(1 for j in jornadas if j.incidencia),
            sum(1 for j in jornadas if j.rectificada),
            sum(1 for j in jornadas if j.abierta),
        ]
        for columna, valor in enumerate(valores, start=1):
            resumen.cell(row=inicio_totales + desplazamiento, column=columna, value=valor)

    fila_total = inicio_totales + len(trabajadores) + 1
    resumen.cell(row=fila_total, column=2, value="TOTAL").font = Font(bold=True)
    celda_total = resumen.cell(row=fila_total, column=5, value=round(total_minutos / 60, 2))
    celda_total.font = Font(bold=True)
    ajustar(resumen)

    # -- Jornadas ------------------------------------------------------------ #
    hoja_jornadas = libro.create_sheet("Jornadas")
    escribir_cabecera(hoja_jornadas, _CABECERA_JORNADAS)
    for trabajador in trabajadores:
        for jornada in jornadas_de(conexion, trabajador.id, desde=desde, hasta=hasta):
            hoja_jornadas.append(_fila_jornada(jornada, trabajador, ajustes))
    hoja_jornadas.auto_filter.ref = hoja_jornadas.dimensions
    ajustar(hoja_jornadas)

    # -- Fichajes ------------------------------------------------------------ #
    hoja_fichajes = libro.create_sheet("Fichajes")
    escribir_cabecera(
        hoja_fichajes,
        ["Código", "Trabajador", "Fecha y hora", "Tipo", "Modalidad", "Origen",
         "Autor", "Rectificado", "Hora original", "Motivo"],
    )
    for trabajador in trabajadores:
        for evento in eventos_efectivos(
            conexion, trabajador_id=trabajador.id, desde=desde, hasta=hasta
        ):
            hoja_fichajes.append(
                [
                    trabajador.codigo,
                    trabajador.nombre,
                    db.a_local(evento.momento).strftime("%d/%m/%Y %H:%M:%S"),
                    evento.tipo.replace("_", " ").capitalize(),
                    evento.modalidad.capitalize(),
                    evento.origen,
                    evento.autor,
                    "Sí" if evento.rectificado else "",
                    db.a_local(evento.momento_original).strftime("%d/%m/%Y %H:%M")
                    if evento.momento_original
                    else "",
                    evento.motivo,
                ]
            )
    hoja_fichajes.auto_filter.ref = hoja_fichajes.dimensions
    ajustar(hoja_fichajes)

    # -- Alertas -------------------------------------------------------------- #
    hoja_alertas = libro.create_sheet("Alertas")
    escribir_cabecera(
        hoja_alertas, ["Gravedad", "Código", "Fecha", "Trabajador", "Detalle", "Norma"]
    )
    alertas = normativa.analizar_periodo(conexion, trabajadores, ajustes, desde, hasta)
    rojo = PatternFill("solid", fgColor="F8D7DA")
    ambar = PatternFill("solid", fgColor="FFF3CD")
    for alerta in alertas:
        hoja_alertas.append(
            [
                alerta.gravedad.upper(),
                alerta.codigo,
                alerta.fecha_texto,
                alerta.trabajador,
                alerta.mensaje,
                alerta.referencia,
            ]
        )
        relleno = rojo if alerta.gravedad == normativa.GRAVE else ambar
        for celda in hoja_alertas[hoja_alertas.max_row]:
            celda.fill = relleno
    if not alertas:
        hoja_alertas.append(["—", "", "", "", "Sin alertas en el periodo.", ""])
    ajustar(hoja_alertas)

    # -- Integridad ----------------------------------------------------------- #
    hoja_integridad = libro.create_sheet("Integridad")
    informe = db.verificar_integridad(conexion)
    hoja_integridad["A1"] = "Verificación de integridad del registro"
    hoja_integridad["A1"].font = Font(size=13, bold=True, color="1F3A5F")
    filas = [
        ("Comprobado", informe["verificado_utc"]),
        ("Resultado", "ÍNTEGRO" if informe["integro"] else "ALTERADO"),
        ("Fichajes encadenados", informe["eventos"]["filas"]),
        ("Hash final de fichajes", informe["eventos"]["hash_final"]),
        ("Registros de auditoría", informe["auditoria"]["filas"]),
        ("Hash final de auditoría", informe["auditoria"]["hash_final"]),
    ]
    for indice, (etiqueta, valor) in enumerate(filas, start=3):
        hoja_integridad.cell(row=indice, column=1, value=etiqueta).font = Font(bold=True)
        hoja_integridad.cell(row=indice, column=2, value=str(valor))
    fila = len(filas) + 4
    for incidencia in informe["eventos"]["incidencias"] + informe["auditoria"]["incidencias"]:
        hoja_integridad.cell(
            row=fila, column=1,
            value=f"Fichaje {incidencia['id']}: {incidencia['problema']}",
        ).fill = rojo
        hoja_integridad.cell(row=fila, column=2, value=incidencia["detalle"])
        fila += 1
    ajustar(hoja_integridad)

    ruta = _destino(f"registro_jornada_{_marca_tiempo()}.xlsx", carpeta)
    libro.save(ruta)
    return ruta


# --------------------------------------------------------------------------- #
# CSV
# --------------------------------------------------------------------------- #

def exportar_csv(
    conexion: sqlite3.Connection,
    ajustes: Ajustes,
    trabajadores: Sequence[Trabajador],
    desde: dt.datetime,
    hasta: dt.datetime,
    *,
    carpeta: Path | None = None,
) -> Path:
    """CSV con separador ';' y BOM, que es lo que espera Excel en español."""
    ruta = _destino(f"registro_jornada_{_marca_tiempo()}.csv", carpeta)
    with ruta.open("w", encoding="utf-8-sig", newline="") as fichero:
        escritor = csv.writer(fichero, delimiter=";")
        escritor.writerow(_CABECERA_JORNADAS)
        for trabajador in trabajadores:
            for jornada in jornadas_de(
                conexion, trabajador.id, desde=desde, hasta=hasta
            ):
                fila = _fila_jornada(jornada, trabajador, ajustes)
                fila[6] = str(fila[6]).replace(".", ",")  # decimal español
                escritor.writerow(fila)
    return ruta


# --------------------------------------------------------------------------- #
# Registro individual del trabajador
# --------------------------------------------------------------------------- #

def exportar_trabajador(
    conexion: sqlite3.Connection,
    ajustes: Ajustes,
    trabajador: Trabajador,
    desde: dt.datetime,
    hasta: dt.datetime,
    *,
    carpeta: Path | None = None,
) -> Path:
    """Copia del registro propio, en texto plano legible.

    El art. 34.9 ET reconoce a la persona trabajadora el derecho de acceso a su
    registro; entregarlo en un formato abierto evita discusiones sobre si pudo
    consultarlo.
    """
    jornadas = jornadas_de(conexion, trabajador.id, desde=desde, hasta=hasta)
    total = sum(
        j.minutos_trabajados(ajustes.pausas_computan_como_trabajo) for j in jornadas
    )

    lineas = [
        "REGISTRO DE JORNADA",
        "=" * 68,
        f"Empresa           : {ajustes.empresa or '(sin indicar)'}",
        f"Centro de trabajo : {ajustes.centro_trabajo or '(sin indicar)'}",
        f"Trabajador        : {trabajador.nombre} ({trabajador.codigo})",
        f"DNI               : {trabajador.dni or '(no consta)'}",
        f"Periodo           : {db.a_local(desde):%d/%m/%Y} a {db.a_local(hasta):%d/%m/%Y}",
        f"Expedido          : {dt.datetime.now():%d/%m/%Y %H:%M}",
        "",
        f"{'Fecha':<12}{'Entrada':<10}{'Salida':<10}{'Pausa':<8}{'Trabajado':<12}Obs.",
        "-" * 68,
    ]
    for jornada in jornadas:
        inicio = db.a_local(jornada.inicio)
        fin = db.a_local(jornada.fin) if jornada.fin else None
        observaciones = []
        if jornada.incidencia:
            observaciones.append("incidencia")
        if jornada.rectificada:
            observaciones.append("rectificada")
        if jornada.abierta:
            observaciones.append("sin salida")
        trabajado = formatear_horas(
            jornada.minutos_trabajados(ajustes.pausas_computan_como_trabajo)
        )
        lineas.append(
            f"{inicio:%d/%m/%Y}".ljust(12)
            + f"{inicio:%H:%M}".ljust(10)
            + (f"{fin:%H:%M}" if fin else "--:--").ljust(10)
            + f"{jornada.minutos_pausa} min".ljust(8)
            + trabajado.ljust(12)
            + ", ".join(observaciones)
        )

    lineas += [
        "-" * 68,
        f"TOTAL DEL PERIODO : {formatear_horas(total)} en {len(jornadas)} jornada(s)",
        "",
        "Este documento reproduce el registro diario de jornada previsto en el",
        "artículo 34.9 del Estatuto de los Trabajadores. Si detectas un error,",
        "solicita su rectificación: quedará anotada con fecha, autor y motivo,",
        "sin borrar el dato original.",
    ]

    nombre = trabajador.nombre.replace(" ", "_").replace("/", "-")
    ruta = _destino(f"registro_{trabajador.codigo}_{nombre}_{_marca_tiempo()}.txt", carpeta)
    ruta.write_text("\n".join(lineas), encoding="utf-8")
    return ruta


# --------------------------------------------------------------------------- #
# Expediente para la Inspección de Trabajo
# --------------------------------------------------------------------------- #

def expediente_itss(
    conexion: sqlite3.Connection,
    ajustes: Ajustes,
    trabajadores: Sequence[Trabajador],
    desde: dt.datetime,
    hasta: dt.datetime,
    *,
    carpeta: Path | None = None,
) -> Path:
    """Volcado íntegro en JSON, con la cadena de hashes para verificarlo.

    El borrador de real decreto en tramitación apunta a un acceso telemático y
    a un formato interoperable.  Mientras no se apruebe, un JSON documentado y
    verificable cubre el deber de puesta a disposición del art. 34.9 ET y deja
    el dato preparado para volcarlo a lo que finalmente se exija.
    """
    integridad = db.verificar_integridad(conexion)

    personas = []
    for trabajador in trabajadores:
        jornadas = jornadas_de(conexion, trabajador.id, desde=desde, hasta=hasta)
        personas.append(
            {
                "codigo": trabajador.codigo,
                "nombre": trabajador.nombre,
                "dni": trabajador.dni,
                "rol": trabajador.rol,
                "activo": trabajador.activo,
                "jornada_semanal_pactada": trabajador.jornada_semanal
                or ajustes.horas_semanales,
                "jornadas": [
                    {
                        "fecha": db.a_local(j.inicio).strftime("%Y-%m-%d"),
                        "entrada": db.a_iso(j.inicio),
                        "salida": db.a_iso(j.fin) if j.fin else None,
                        "modalidad": j.modalidad,
                        "pausas": [
                            {
                                "inicio": db.a_iso(p_ini),
                                "fin": db.a_iso(p_fin) if p_fin else None,
                            }
                            for p_ini, p_fin in j.pausas
                        ],
                        "minutos_pausa": j.minutos_pausa,
                        "minutos_trabajados": j.minutos_trabajados(
                            ajustes.pausas_computan_como_trabajo
                        ),
                        "incidencia": j.incidencia,
                        "rectificada": j.rectificada,
                    }
                    for j in jornadas
                ],
                "fichajes": [
                    {
                        "id": e.id,
                        "tipo": e.tipo,
                        "momento_utc": db.a_iso(e.momento),
                        "modalidad": e.modalidad,
                        "origen": e.origen,
                        "autor": e.autor,
                        "rectificado": e.rectificado,
                        "momento_original_utc": db.a_iso(e.momento_original)
                        if e.momento_original
                        else None,
                        "motivo_rectificacion": e.motivo,
                    }
                    for e in eventos_efectivos(
                        conexion, trabajador_id=trabajador.id, desde=desde, hasta=hasta
                    )
                ],
            }
        )

    auditoria = [
        dict(fila)
        for fila in conexion.execute(
            "SELECT id, ts_utc, actor, accion, detalle, hash FROM auditoria "
            "WHERE ts_utc BETWEEN ? AND ? ORDER BY id",
            (db.a_iso(desde), db.a_iso(hasta)),
        )
    ]

    expediente = {
        "formato": "controlhorario/expediente-itss",
        "version_formato": 1,
        "generado_utc": db.a_iso(db.ahora_utc()),
        "aplicacion": f"Control Horario {__version__}",
        "empresa": {
            "razon_social": ajustes.empresa,
            "cif": ajustes.cif,
            "centro_trabajo": ajustes.centro_trabajo,
        },
        "marco_legal": {
            "obligacion": "art. 34.9 del Estatuto de los Trabajadores",
            "introducida_por": "Real Decreto-ley 8/2019, de 8 de marzo",
            "conservacion_anios": ajustes.anios_conservacion,
        },
        "periodo": {"desde_utc": db.a_iso(desde), "hasta_utc": db.a_iso(hasta)},
        "integridad": integridad,
        "trabajadores": personas,
        "auditoria": auditoria,
        "alertas": [
            {
                "codigo": a.codigo,
                "gravedad": a.gravedad,
                "trabajador": a.trabajador,
                "fecha": a.fecha_texto,
                "mensaje": a.mensaje,
                "referencia": a.referencia,
            }
            for a in normativa.analizar_periodo(
                conexion, trabajadores, ajustes, desde, hasta
            )
        ],
    }

    ruta = _destino(f"expediente_itss_{_marca_tiempo()}.json", carpeta)
    ruta.write_text(
        json.dumps(expediente, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return ruta


__all__ = [
    "ErrorInforme",
    "expediente_itss",
    "exportar_csv",
    "exportar_excel",
    "exportar_trabajador",
]
