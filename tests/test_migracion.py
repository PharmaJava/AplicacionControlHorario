"""Pruebas de la importación del histórico de la versión 2024."""

from __future__ import annotations

import sqlite3

import pytest

from controlhorario import db, dominio as dom, migracion
from controlhorario.config import ruta_bd_antigua


@pytest.fixture
def base_antigua():
    """Reproduce el esquema exacto del programa de 2024."""
    ruta = ruta_bd_antigua()
    antigua = sqlite3.connect(ruta)
    antigua.executescript(
        """
        CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT, encrypted_name BLOB);
        CREATE TABLE records (id INTEGER PRIMARY KEY AUTOINCREMENT,
                              user_id INTEGER, entry_time TEXT, exit_time TEXT);
        CREATE TABLE incidents (id INTEGER PRIMARY KEY AUTOINCREMENT,
                                user_id INTEGER, incident_time TEXT);
        """
    )
    antigua.execute(
        "INSERT INTO users (name, encrypted_name) VALUES ('María López', ?)",
        (b"gAAAAAilegible",),
    )
    antigua.execute("INSERT INTO users (name, encrypted_name) VALUES ('Javier Ortiz', NULL)")
    antigua.executemany(
        "INSERT INTO records (user_id, entry_time, exit_time) VALUES (?, ?, ?)",
        [
            (1, "03/06/2024 08:00:00", "03/06/2024 17:00:00"),
            (1, "04/06/2024 08:05:00", "04/06/2024 17:10:00"),
            (2, "03/06/2024 09:00:00", None),          # sin salida
            (2, "no es una fecha", "05/06/2024 17:00:00"),  # corrupta
        ],
    )
    antigua.execute(
        "INSERT INTO incidents (user_id, incident_time) VALUES (1, '12/03/2025 14:50')"
    )
    antigua.commit()
    antigua.close()
    return ruta


def test_se_detecta_la_base_antigua(base_antigua):
    assert migracion.hay_datos_antiguos()


def test_sin_base_antigua_no_hay_nada_que_importar():
    assert not migracion.hay_datos_antiguos()


def test_importa_trabajadores_y_fichajes(conexion, cifrador, base_antigua):
    resultado = migracion.importar(conexion, cifrador)

    assert resultado.trabajadores == 2
    assert resultado.fichajes == 5      # 2 completos + 1 entrada suelta
    assert resultado.incidencias == 1
    assert len(resultado.omitidos) == 1
    assert "fecha ilegible" in resultado.omitidos[0]


def test_los_nombres_se_recuperan_y_quedan_cifrados(conexion, cifrador, base_antigua):
    migracion.importar(conexion, cifrador)
    nombres = {t.nombre for t in dom.listar_trabajadores(conexion, cifrador)}
    assert nombres == {"María López", "Javier Ortiz"}

    crudo = conexion.execute(
        "SELECT nombre_cifrado FROM trabajadores LIMIT 1"
    ).fetchone()[0]
    assert b"Mar" not in crudo, "el nombre no puede quedar legible en disco"


def test_las_jornadas_importadas_se_calculan_bien(conexion, cifrador, base_antigua):
    migracion.importar(conexion, cifrador)
    maria = next(
        t for t in dom.listar_trabajadores(conexion, cifrador)
        if t.nombre == "María López"
    )
    jornadas = dom.jornadas_de(conexion, maria.id)
    assert len(jornadas) == 2
    assert jornadas[0].minutos_trabajados() == 9 * 60


def test_la_jornada_sin_salida_queda_abierta(conexion, cifrador, base_antigua):
    migracion.importar(conexion, cifrador)
    javier = next(
        t for t in dom.listar_trabajadores(conexion, cifrador)
        if t.nombre == "Javier Ortiz"
    )
    assert dom.jornadas_de(conexion, javier.id)[0].abierta


def test_los_importados_no_tienen_pin(conexion, cifrador, base_antigua):
    """Sin PIN no pueden fichar: hay que asignárselo, y así se avisa."""
    migracion.importar(conexion, cifrador)
    assert all(
        not t.tiene_pin for t in dom.listar_trabajadores(conexion, cifrador)
    )


def test_la_importacion_mantiene_la_integridad(conexion, cifrador, base_antigua):
    migracion.importar(conexion, cifrador)
    assert db.verificar_integridad(conexion)["integro"]


def test_la_importacion_queda_auditada(conexion, cifrador, base_antigua):
    migracion.importar(conexion, cifrador)
    acciones = [f["accion"] for f in conexion.execute("SELECT accion FROM auditoria")]
    assert "IMPORTACION_HISTORICO" in acciones


def test_importar_dos_veces_no_duplica_trabajadores(conexion, cifrador, base_antigua):
    migracion.importar(conexion, cifrador)
    segunda = migracion.importar(conexion, cifrador)
    assert segunda.trabajadores == 0
    assert len(dom.listar_trabajadores(conexion, cifrador)) == 2
