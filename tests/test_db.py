"""Pruebas de inmutabilidad, cadena de integridad y conservación."""

from __future__ import annotations

import datetime as dt
import sqlite3

import pytest

from controlhorario import db

from .conftest import utc


def _sembrar(conexion, cifrador, cuantos=3):
    from controlhorario import dominio

    trabajador = dominio.alta_trabajador(
        conexion, cifrador, nombre="Prueba Uno", pin="4791"
    )
    for indice in range(cuantos):
        db.registrar_evento(
            conexion, trabajador_id=trabajador.id, tipo="ENTRADA",
            ts_utc=db.a_iso(utc(2026, 3, 1 + indice, 8)),
        )
    return trabajador


def test_cadena_integra_tras_registrar(conexion, cifrador):
    _sembrar(conexion, cifrador)
    informe = db.verificar_integridad(conexion)
    assert informe["integro"]
    assert informe["eventos"]["filas"] == 3


def test_no_se_puede_modificar_un_fichaje(conexion, cifrador):
    _sembrar(conexion, cifrador, 1)
    with pytest.raises(sqlite3.IntegrityError, match="inmutable"):
        conexion.execute("UPDATE eventos SET ts_utc = '2020-01-01' WHERE id = 1")


def test_no_se_puede_borrar_un_fichaje(conexion, cifrador):
    _sembrar(conexion, cifrador, 1)
    with pytest.raises(sqlite3.IntegrityError, match="inmutable"):
        conexion.execute("DELETE FROM eventos WHERE id = 1")


def test_la_auditoria_es_de_solo_anexado(conexion):
    db.registrar_auditoria(conexion, actor="test", accion="PRUEBA")
    with pytest.raises(sqlite3.IntegrityError):
        conexion.execute("UPDATE auditoria SET actor = 'otro' WHERE id = 1")
    with pytest.raises(sqlite3.IntegrityError):
        conexion.execute("DELETE FROM auditoria WHERE id = 1")


def test_se_detecta_la_manipulacion_directa(conexion, cifrador):
    """Quien esquive los triggers rompe la cadena y queda registrado."""
    _sembrar(conexion, cifrador)
    conexion.execute("DROP TRIGGER eventos_no_update")
    conexion.execute("UPDATE eventos SET ts_utc = '2020-01-01T00:00:00+00:00' WHERE id = 2")

    informe = db.verificar_integridad(conexion)
    assert not informe["integro"]
    problemas = {i["problema"] for i in informe["eventos"]["incidencias"]}
    assert "hash_no_coincide" in problemas
    assert [i["id"] for i in informe["eventos"]["incidencias"]] == [2]


def test_se_detecta_el_borrado_directo(conexion, cifrador):
    _sembrar(conexion, cifrador)
    conexion.execute("DROP TRIGGER eventos_no_delete")
    conexion.execute("DELETE FROM eventos WHERE id = 2")

    informe = db.verificar_integridad(conexion)
    assert not informe["integro"]
    assert any(
        i["problema"] == "cadena_rota" for i in informe["eventos"]["incidencias"]
    )


def test_cada_evento_encadena_con_el_anterior(conexion, cifrador):
    _sembrar(conexion, cifrador)
    filas = list(conexion.execute("SELECT * FROM eventos ORDER BY id"))
    assert filas[0]["hash_previo"] == db.GENESIS
    for anterior, siguiente in zip(filas, filas[1:], strict=False):
        assert siguiente["hash_previo"] == anterior["hash"]


def test_purga_solo_lo_caducado(conexion, cifrador):
    from controlhorario import dominio

    trabajador = dominio.alta_trabajador(
        conexion, cifrador, nombre="Prueba", pin="4791"
    )
    antiguo = db.ahora_utc() - dt.timedelta(days=365 * 5)
    reciente = db.ahora_utc() - dt.timedelta(days=30)
    db.registrar_evento(
        conexion, trabajador_id=trabajador.id, tipo="ENTRADA",
        ts_utc=db.a_iso(antiguo),
    )
    db.registrar_evento(
        conexion, trabajador_id=trabajador.id, tipo="ENTRADA",
        ts_utc=db.a_iso(reciente),
    )

    borrados = db.purgar_caducados(conexion, anios=4)
    assert borrados == 1
    quedan = conexion.execute("SELECT COUNT(*) AS n FROM eventos").fetchone()["n"]
    assert quedan == 1


def test_la_purga_queda_auditada(conexion, cifrador):
    from controlhorario import dominio

    trabajador = dominio.alta_trabajador(
        conexion, cifrador, nombre="Prueba", pin="4791"
    )
    db.registrar_evento(
        conexion, trabajador_id=trabajador.id, tipo="ENTRADA",
        ts_utc=db.a_iso(db.ahora_utc() - dt.timedelta(days=365 * 5)),
    )
    db.purgar_caducados(conexion, anios=4, actor="responsable")

    acciones = [f["accion"] for f in conexion.execute("SELECT accion FROM auditoria")]
    assert "PURGA_CONSERVACION" in acciones


def test_la_purga_vuelve_a_bloquear_el_borrado(conexion, cifrador):
    """El permiso de borrado no debe quedarse abierto tras la purga."""
    _sembrar(conexion, cifrador, 1)
    db.purgar_caducados(conexion, anios=4)
    with pytest.raises(sqlite3.IntegrityError):
        conexion.execute("DELETE FROM eventos WHERE id = 1")


def test_copia_de_seguridad_consistente(conexion, cifrador):
    _sembrar(conexion, cifrador)
    destino = db.copia_seguridad(conexion)
    assert destino.exists()

    copia = db.conectar(destino)
    try:
        assert db.verificar_integridad(copia)["integro"]
        assert copia.execute("SELECT COUNT(*) AS n FROM eventos").fetchone()["n"] == 3
    finally:
        copia.close()


def test_marcas_de_tiempo_ordenables(conexion, cifrador):
    """Las fechas se guardan en ISO-8601 UTC, no en 'dd/mm/aaaa'."""
    _sembrar(conexion, cifrador)
    marcas = [f["ts_utc"] for f in conexion.execute(
        "SELECT ts_utc FROM eventos ORDER BY ts_utc"
    )]
    assert marcas == sorted(marcas)
    assert marcas[0].startswith("2026-03-01T")
