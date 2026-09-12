"""Pruebas de la importación del histórico de la versión 2024."""

from __future__ import annotations

import hashlib
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


def test_importar_dos_veces_no_duplica_nada(conexion, cifrador, base_antigua):
    """La importación se puede lanzar a mano, así que debe ser idempotente."""
    primera = migracion.importar(conexion, cifrador)
    eventos_tras_la_primera = conexion.execute(
        "SELECT COUNT(*) AS n FROM eventos"
    ).fetchone()["n"]

    segunda = migracion.importar(conexion, cifrador)
    tercera = migracion.importar(conexion, cifrador)

    assert primera.fichajes > 0
    assert segunda.fichajes == 0
    assert segunda.trabajadores == 0
    assert tercera.fichajes == 0
    assert len(dom.listar_trabajadores(conexion, cifrador)) == 2
    assert conexion.execute(
        "SELECT COUNT(*) AS n FROM eventos"
    ).fetchone()["n"] == eventos_tras_la_primera


def test_no_mezcla_con_trabajadores_dados_de_alta_antes(
    conexion, cifrador, base_antigua
):
    """Si ya existe un E001 de otra persona, el importado va aparte."""
    previo = dom.alta_trabajador(
        conexion, cifrador, nombre="Pedro Sánchez Gil", pin="4791"
    )
    dom.fichar(conexion, previo.id, "ENTRADA", momento=db.ahora_utc())

    migracion.importar(conexion, cifrador)

    gente = {t.nombre: t for t in dom.listar_trabajadores(conexion, cifrador)}
    assert set(gente) == {"Pedro Sánchez Gil", "María López", "Javier Ortiz"}
    assert len(dom.jornadas_de(conexion, gente["Pedro Sánchez Gil"].id)) == 1
    assert len(dom.jornadas_de(conexion, gente["María López"].id)) == 2


def test_no_modifica_la_base_antigua(conexion, cifrador, base_antigua):
    """El fichero de 2024 queda intacto como respaldo."""
    antes = hashlib.sha256(base_antigua.read_bytes()).hexdigest()
    migracion.importar(conexion, cifrador)
    assert hashlib.sha256(base_antigua.read_bytes()).hexdigest() == antes


def test_guarda_una_copia_del_fichero_original(conexion, cifrador, base_antigua):
    resultado = migracion.importar(conexion, cifrador)
    assert resultado.respaldo is not None
    assert resultado.respaldo.exists()
    assert resultado.respaldo.read_bytes() == base_antigua.read_bytes()


def test_cuenta_lo_que_queda_por_importar(conexion, cifrador, base_antigua):
    # 3 records legibles + 1 incidencia; la fila con la fecha corrupta no cuenta
    assert migracion.pendiente_de_importar(conexion) == 4
    migracion.importar(conexion, cifrador)
    assert migracion.pendiente_de_importar(conexion) == 0


def test_importa_lo_nuevo_que_aparezca_despues(conexion, cifrador, base_antigua):
    """Si el programa antiguo siguió usándose, lo nuevo se trae luego."""
    migracion.importar(conexion, cifrador)

    antigua = sqlite3.connect(base_antigua)
    antigua.execute(
        "INSERT INTO records (user_id, entry_time, exit_time) "
        "VALUES (1, '10/06/2024 08:00:00', '10/06/2024 16:00:00')"
    )
    antigua.commit()
    antigua.close()

    assert migracion.pendiente_de_importar(conexion) == 1
    segunda = migracion.importar(conexion, cifrador)
    assert segunda.fichajes == 2      # entrada y salida de la jornada nueva

    maria = next(
        t for t in dom.listar_trabajadores(conexion, cifrador)
        if t.nombre == "María López"
    )
    assert len(dom.jornadas_de(conexion, maria.id)) == 3
