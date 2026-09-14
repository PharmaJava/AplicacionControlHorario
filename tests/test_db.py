"""Pruebas de inmutabilidad, cadena de integridad y conservación."""

from __future__ import annotations

import datetime as dt
import sqlite3

import pytest

from controlhorario import db, dominio as dom

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


def test_la_purga_legal_no_deja_el_registro_como_alterado(conexion, cifrador):
    """Purgar lo caducado abre un hueco en la cadena, pero no es manipulación.

    Antes, usar la purga que ofrece el propio programa hacía que la
    verificación dijera «ALTERADO»: el peor mensaje posible justo cuando lo
    que se quiere acreditar ante la Inspección es que el registro es fiable.
    """
    trabajador = dom.alta_trabajador(
        conexion, cifrador, nombre="Ana Ruiz", pin="4791"
    )
    viejo = db.ahora_utc() - dt.timedelta(days=365 * 6)
    dom.fichar(conexion, trabajador.id, "ENTRADA", momento=viejo)
    dom.fichar(conexion, trabajador.id, "SALIDA", momento=viejo + dt.timedelta(hours=8))
    dom.fichar(conexion, trabajador.id, "ENTRADA")

    assert db.purgar_caducados(conexion, anios=4) == 2

    informe = db.verificar_integridad(conexion)
    assert informe["integro"]
    assert not informe["eventos"]["incidencias"]
    cortes = informe["eventos"]["cortes"]
    assert len(cortes) == 1
    assert cortes[0]["purgados"] == 2


def test_un_borrado_a_escondidas_sigue_detectandose(conexion, cifrador):
    """El hueco sólo se acepta si lo dejó una purga anotada."""
    trabajador = dom.alta_trabajador(
        conexion, cifrador, nombre="Ana Ruiz", pin="4791"
    )
    for tipo in ("ENTRADA", "PAUSA_INICIO", "PAUSA_FIN", "SALIDA"):
        dom.fichar(conexion, trabajador.id, tipo)

    # Saltándose el trigger igual que podría hacerlo alguien con el fichero.
    db.guardar_config(conexion, "purga_en_curso", "1")
    conexion.execute("DELETE FROM eventos WHERE id = 2")
    db.guardar_config(conexion, "purga_en_curso", "0")

    informe = db.verificar_integridad(conexion)
    assert not informe["integro"]
    assert informe["eventos"]["incidencias"][0]["problema"] == "cadena_rota"


def test_un_corte_inventado_no_cuela(conexion, cifrador):
    trabajador = dom.alta_trabajador(
        conexion, cifrador, nombre="Ana Ruiz", pin="4791"
    )
    for tipo in ("ENTRADA", "SALIDA", "ENTRADA"):
        dom.fichar(conexion, trabajador.id, tipo)
    db.guardar_config(conexion, "purga_en_curso", "1")
    conexion.execute("DELETE FROM eventos WHERE id = 2")
    db.guardar_config(conexion, "purga_en_curso", "0")
    db.guardar_config(
        conexion, "cortes_purga",
        '[{"id": 3, "hash_previo": "inventado", "purgados": 1, "utc": "2026-01-01"}]',
    )
    assert not db.verificar_integridad(conexion)["integro"]
