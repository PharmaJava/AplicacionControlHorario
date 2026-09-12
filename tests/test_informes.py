"""Pruebas de la generación de informes."""

from __future__ import annotations

import json

import pytest

from controlhorario import dominio as dom, informes

from .conftest import utc


@pytest.fixture
def con_datos(conexion, cifrador, trabajador):
    for dia in (2, 3, 4):
        dom.fichar(conexion, trabajador.id, "ENTRADA", momento=utc(2026, 3, dia, 8))
        dom.fichar(
            conexion, trabajador.id, "PAUSA_INICIO", momento=utc(2026, 3, dia, 12)
        )
        dom.fichar(
            conexion, trabajador.id, "PAUSA_FIN", momento=utc(2026, 3, dia, 12, 30)
        )
        dom.fichar(conexion, trabajador.id, "SALIDA", momento=utc(2026, 3, dia, 17))
    return trabajador


@pytest.fixture
def periodo():
    return utc(2026, 3, 1), utc(2026, 3, 31, 23)


def test_excel_se_genera_con_todas_las_hojas(
    conexion, cifrador, ajustes, con_datos, periodo, tmp_path
):
    openpyxl = pytest.importorskip("openpyxl")
    ruta = informes.exportar_excel(
        conexion, cifrador, ajustes, [con_datos], *periodo, carpeta=tmp_path
    )
    assert ruta.exists()

    libro = openpyxl.load_workbook(ruta)
    assert libro.sheetnames == [
        "Resumen", "Jornadas", "Fichajes", "Alertas", "Integridad"
    ]
    assert libro["Jornadas"].max_row == 4       # cabecera + 3 jornadas
    assert "PharmaJava" not in str(libro["Resumen"]["B3"].value)
    assert libro["Resumen"]["B3"].value == "Pruebas S.L."


def test_csv_usa_formato_espanol(conexion, ajustes, con_datos, periodo, tmp_path):
    ruta = informes.exportar_csv(
        conexion, ajustes, [con_datos], *periodo, carpeta=tmp_path
    )
    contenido = ruta.read_text(encoding="utf-8-sig")
    assert ";" in contenido
    assert "8,5" in contenido, "las horas deben usar coma decimal"
    assert contenido.count("\n") >= 4


def test_informe_individual_legible(conexion, ajustes, con_datos, periodo, tmp_path):
    ruta = informes.exportar_trabajador(
        conexion, ajustes, con_datos, *periodo, carpeta=tmp_path
    )
    texto = ruta.read_text(encoding="utf-8")
    assert "Ana Ruiz Gómez" in texto
    assert "12345678Z" in texto
    assert "TOTAL DEL PERIODO : 25h 30m" in texto
    assert "34.9" in texto


def test_expediente_itss_verificable(conexion, ajustes, con_datos, periodo, tmp_path):
    ruta = informes.expediente_itss(
        conexion, ajustes, [con_datos], *periodo, carpeta=tmp_path
    )
    datos = json.loads(ruta.read_text(encoding="utf-8"))

    assert datos["integridad"]["integro"] is True
    assert datos["marco_legal"]["conservacion_anios"] == 4
    assert len(datos["trabajadores"]) == 1
    persona = datos["trabajadores"][0]
    assert len(persona["jornadas"]) == 3
    assert persona["jornadas"][0]["minutos_trabajados"] == 510
    assert len(persona["jornadas"][0]["pausas"]) == 1


def test_el_expediente_refleja_las_rectificaciones(
    conexion, ajustes, con_datos, periodo, tmp_path
):
    entrada = dom.eventos_efectivos(conexion, trabajador_id=con_datos.id)[0]
    dom.rectificar(
        conexion, entrada.id, momento_nuevo=utc(2026, 3, 2, 7),
        motivo="Entró antes; lo confirma el responsable", autor="admin",
    )
    ruta = informes.expediente_itss(
        conexion, ajustes, [con_datos], *periodo, carpeta=tmp_path
    )
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    fichaje = datos["trabajadores"][0]["fichajes"][0]

    assert fichaje["rectificado"] is True
    assert fichaje["momento_original_utc"] is not None
    assert "responsable" in fichaje["motivo_rectificacion"]


def test_las_alertas_viajan_en_el_expediente(
    conexion, cifrador, ajustes, trabajador, periodo, tmp_path
):
    dom.fichar(conexion, trabajador.id, "ENTRADA", momento=utc(2026, 3, 2, 6))
    dom.fichar(conexion, trabajador.id, "SALIDA", momento=utc(2026, 3, 2, 20))

    ruta = informes.expediente_itss(
        conexion, ajustes, [trabajador], *periodo, carpeta=tmp_path
    )
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    codigos = {a["codigo"] for a in datos["alertas"]}
    assert "JORNADA_DIARIA" in codigos
