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
    assert libro["Resumen"]["B3"].value == "Empresa de Pruebas"


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


def test_los_informes_no_llevan_el_nombre_del_autor(
    conexion, cifrador, ajustes, con_datos, periodo, tmp_path
):
    """Los informes identifican a la empresa y al programa, no a quien lo escribió.

    Se mira dentro del .xlsx descomprimido, no sólo las celdas: el nombre podría
    colarse en las propiedades del documento sin verse en ninguna hoja.
    """
    import zipfile

    from controlhorario.version import AUTOR

    xlsx = informes.exportar_excel(
        conexion, cifrador, ajustes, [con_datos], *periodo, carpeta=tmp_path
    )
    with zipfile.ZipFile(xlsx) as comprimido:
        crudo = b"".join(comprimido.read(n) for n in comprimido.namelist())
    assert AUTOR.encode() not in crudo

    for generar in (
        lambda: informes.expediente_itss(
            conexion, ajustes, [con_datos], *periodo, carpeta=tmp_path
        ),
        lambda: informes.exportar_csv(
            conexion, ajustes, [con_datos], *periodo, carpeta=tmp_path
        ),
        lambda: informes.exportar_trabajador(
            conexion, ajustes, con_datos, *periodo, carpeta=tmp_path
        ),
    ):
        ruta = generar()
        assert AUTOR not in ruta.read_text(encoding="utf-8-sig"), ruta.name


# --------------------------------------------------------------------------- #
# Procedencia de los registros
# --------------------------------------------------------------------------- #

@pytest.fixture
def con_historico_importado(conexion, cifrador, base_antigua_simple):
    """Trabajador cuyas jornadas vienen del programa de 2024."""
    from controlhorario import migracion

    migracion.importar(conexion, cifrador)
    return dom.listar_trabajadores(conexion, cifrador)[0]


@pytest.fixture
def base_antigua_simple():
    import sqlite3

    from controlhorario.config import ruta_bd_antigua

    ruta = ruta_bd_antigua()
    antigua = sqlite3.connect(ruta)
    antigua.executescript(
        """
        CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT);
        CREATE TABLE records (id INTEGER PRIMARY KEY AUTOINCREMENT,
                              user_id INTEGER, entry_time TEXT, exit_time TEXT);
        INSERT INTO users (name) VALUES ('Histórico Pérez');
        INSERT INTO records (user_id, entry_time, exit_time)
            VALUES (1, '03/06/2024 08:00:00', '03/06/2024 17:00:00');
        """
    )
    antigua.commit()
    antigua.close()
    return ruta


def test_una_jornada_importada_se_distingue(conexion, con_historico_importado):
    jornada = dom.jornadas_de(conexion, con_historico_importado.id)[0]
    assert jornada.importada
    assert jornada.registrada is not None
    # Ocurrió en 2024 pero entró en el sistema hoy: esa diferencia es el dato.
    assert jornada.registrada.year > jornada.inicio.year


def test_una_jornada_fichada_aqui_no_se_marca_como_importada(conexion, trabajador):
    dom.fichar(conexion, trabajador.id, "ENTRADA", momento=utc(2026, 3, 2, 8))
    dom.fichar(conexion, trabajador.id, "SALIDA", momento=utc(2026, 3, 2, 17))
    assert not dom.jornadas_de(conexion, trabajador.id)[0].importada


def test_el_excel_no_presenta_lo_importado_como_fichado(
    conexion, cifrador, ajustes, con_historico_importado, tmp_path
):
    """Decir sólo «ÍNTEGRO» ante una inspección sería exagerar el alcance."""
    openpyxl = pytest.importorskip("openpyxl")
    ruta = informes.exportar_excel(
        conexion, cifrador, ajustes, [con_historico_importado],
        utc(2024, 1, 1), utc(2026, 12, 31), carpeta=tmp_path,
    )
    libro = openpyxl.load_workbook(ruta)

    integridad = "\n".join(
        str(c.value) for fila in libro["Integridad"].iter_rows() for c in fila
        if c.value
    )
    assert "acredita únicamente que no se han alterado" in integridad
    assert "programa" in integridad and "anterior" in integridad

    jornadas = "\n".join(
        str(c.value) for fila in libro["Jornadas"].iter_rows() for c in fila
        if c.value
    )
    assert "Procedencia" in jornadas
    assert "Importado del sistema anterior" in jornadas


def test_el_expediente_declara_la_procedencia(
    conexion, ajustes, con_historico_importado, tmp_path
):
    ruta = informes.expediente_itss(
        conexion, ajustes, [con_historico_importado],
        utc(2024, 1, 1), utc(2026, 12, 31), carpeta=tmp_path,
    )
    datos = json.loads(ruta.read_text(encoding="utf-8"))

    assert datos["procedencia"]["importados"] == 2      # entrada y salida
    assert datos["procedencia"]["nativos"] == 0
    assert datos["procedencia"]["fecha_importacion"]
    assert "acredita únicamente" in datos["alcance_de_la_verificacion"]
    assert datos["trabajadores"][0]["jornadas"][0]["origen"] == "MIGRADO"


# --------------------------------------------------------------------------- #
# Informe imprimible
# --------------------------------------------------------------------------- #

def test_el_informe_de_inspeccion_es_html_valido(
    conexion, ajustes, con_datos, periodo, tmp_path
):
    from html.parser import HTMLParser

    ruta = informes.informe_inspeccion(
        conexion, ajustes, [con_datos], *periodo, carpeta=tmp_path
    )
    assert ruta.suffix == ".html"
    texto = ruta.read_text(encoding="utf-8")

    class Verificador(HTMLParser):
        def __init__(self):
            super().__init__()
            self.pila, self.errores = [], []

        def handle_starttag(self, tag, attrs):
            if tag not in ("meta", "br", "hr", "img", "input", "link"):
                self.pila.append(tag)

        def handle_endtag(self, tag):
            if self.pila and self.pila[-1] == tag:
                self.pila.pop()
            else:
                self.errores.append(tag)

    verificador = Verificador()
    verificador.feed(texto)
    assert not verificador.errores and not verificador.pila


def test_el_informe_de_inspeccion_lleva_lo_imprescindible(
    conexion, ajustes, con_datos, periodo, tmp_path
):
    ruta = informes.informe_inspeccion(
        conexion, ajustes, [con_datos], *periodo, carpeta=tmp_path
    )
    texto = ruta.read_text(encoding="utf-8")

    for imprescindible in (
        ajustes.empresa,                 # identificación de la empresa
        ajustes.cif,
        con_datos.nombre,                # de la persona
        "34.9",                          # base legal
        "Firma y sello",                 # para entregarlo firmado
        "cuatro años",                   # deber de conservación
        "@media print",                  # se puede imprimir en condiciones
    ):
        assert imprescindible in texto, imprescindible


def test_el_informe_avisa_de_lo_importado(
    conexion, ajustes, con_historico_importado, tmp_path
):
    ruta = informes.informe_inspeccion(
        conexion, ajustes, [con_historico_importado],
        utc(2024, 1, 1), utc(2026, 12, 31), carpeta=tmp_path,
    )
    texto = ruta.read_text(encoding="utf-8")
    assert "proceden del programa anterior" in texto
    assert "acredita únicamente que no se han alterado" in texto


def test_el_informe_escapa_el_html_de_los_datos(
    conexion, cifrador, ajustes, periodo, tmp_path
):
    """Un nombre con caracteres raros no debe romper ni inyectar en el documento."""
    trabajador = dom.alta_trabajador(
        conexion, cifrador, nombre="Ana <script>alert(1)</script> Ruiz", pin="4791"
    )
    dom.fichar(conexion, trabajador.id, "ENTRADA", momento=utc(2026, 3, 2, 8))
    dom.fichar(conexion, trabajador.id, "SALIDA", momento=utc(2026, 3, 2, 17))

    ruta = informes.informe_inspeccion(
        conexion, ajustes, [trabajador], *periodo, carpeta=tmp_path
    )
    texto = ruta.read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in texto
    assert "&lt;script&gt;" in texto
