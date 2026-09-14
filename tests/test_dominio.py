"""Pruebas de la máquina de estados y de la reconstrucción de jornadas."""

from __future__ import annotations

import datetime as dt

import pytest

from controlhorario import db, dominio as dom
from controlhorario.config import TIPOS_EVENTO

from .conftest import utc


# --------------------------------------------------------------------------- #
# Identificación
# --------------------------------------------------------------------------- #

def test_no_se_puede_fichar_por_otro_sin_su_pin(conexion, cifrador, trabajador):
    """La versión de 2024 sólo pedía el ID, visible para todos."""
    with pytest.raises(dom.ErrorDominio):
        dom.autenticar(conexion, cifrador, trabajador.codigo, "0000")
    assert dom.autenticar(conexion, cifrador, trabajador.codigo, "4791").id == trabajador.id


def test_un_trabajador_de_baja_no_puede_fichar(conexion, cifrador, trabajador):
    dom.baja_trabajador(conexion, cifrador, trabajador.id)
    with pytest.raises(dom.ErrorDominio, match="baja"):
        dom.autenticar(conexion, cifrador, trabajador.codigo, "4791")


def test_dni_duplicado_rechazado(conexion, cifrador, trabajador):
    with pytest.raises(dom.ErrorDominio, match="DNI"):
        dom.alta_trabajador(
            conexion, cifrador, nombre="Otra Persona", pin="5832", dni="12345678Z"
        )


def test_no_se_da_de_baja_con_jornada_abierta(conexion, cifrador, trabajador):
    dom.fichar(conexion, trabajador.id, "ENTRADA")
    with pytest.raises(dom.ErrorDominio, match="jornada abierta"):
        dom.baja_trabajador(conexion, cifrador, trabajador.id)


# --------------------------------------------------------------------------- #
# Máquina de estados
# --------------------------------------------------------------------------- #

def test_secuencia_normal(conexion, trabajador):
    assert dom.estado_actual(conexion, trabajador.id) == dom.FUERA
    dom.fichar(conexion, trabajador.id, "ENTRADA", momento=utc(2026, 3, 2, 8))
    assert dom.estado_actual(conexion, trabajador.id) == dom.DENTRO
    dom.fichar(conexion, trabajador.id, "PAUSA_INICIO", momento=utc(2026, 3, 2, 12))
    assert dom.estado_actual(conexion, trabajador.id) == dom.EN_PAUSA
    dom.fichar(conexion, trabajador.id, "PAUSA_FIN", momento=utc(2026, 3, 2, 12, 30))
    assert dom.estado_actual(conexion, trabajador.id) == dom.DENTRO
    dom.fichar(conexion, trabajador.id, "SALIDA", momento=utc(2026, 3, 2, 17))
    assert dom.estado_actual(conexion, trabajador.id) == dom.FUERA


@pytest.mark.parametrize("tipo", ["SALIDA", "PAUSA_INICIO", "PAUSA_FIN"])
def test_transiciones_imposibles_desde_fuera(conexion, trabajador, tipo):
    with pytest.raises(dom.ErrorDominio):
        dom.fichar(conexion, trabajador.id, tipo)


def test_no_hay_dos_entradas_seguidas(conexion, trabajador):
    dom.fichar(conexion, trabajador.id, "ENTRADA", momento=utc(2026, 3, 2, 8))
    with pytest.raises(dom.ErrorDominio):
        dom.fichar(conexion, trabajador.id, "ENTRADA", momento=utc(2026, 3, 2, 9))


def test_no_se_ficha_hacia_atras(conexion, trabajador):
    dom.fichar(conexion, trabajador.id, "ENTRADA", momento=utc(2026, 3, 2, 8))
    with pytest.raises(dom.ErrorDominio, match="anterior"):
        dom.fichar(conexion, trabajador.id, "SALIDA", momento=utc(2026, 3, 1, 8))


# --------------------------------------------------------------------------- #
# Cálculo de jornadas
# --------------------------------------------------------------------------- #

def test_las_pausas_se_descuentan(conexion, trabajador):
    dom.fichar(conexion, trabajador.id, "ENTRADA", momento=utc(2026, 3, 2, 8))
    dom.fichar(conexion, trabajador.id, "PAUSA_INICIO", momento=utc(2026, 3, 2, 12))
    dom.fichar(conexion, trabajador.id, "PAUSA_FIN", momento=utc(2026, 3, 2, 13))
    dom.fichar(conexion, trabajador.id, "SALIDA", momento=utc(2026, 3, 2, 17))

    jornada = dom.jornadas_de(conexion, trabajador.id)[0]
    assert jornada.minutos_presencia == 9 * 60
    assert jornada.minutos_pausa == 60
    assert jornada.minutos_trabajados() == 8 * 60
    assert jornada.minutos_trabajados(pausas_computan=True) == 9 * 60


def test_jornada_abierta_no_suma_salvo_que_se_cronometre(conexion, trabajador):
    inicio = db.ahora_utc() - dt.timedelta(hours=3)
    dom.fichar(conexion, trabajador.id, "ENTRADA", momento=inicio)
    jornada = dom.jornadas_de(conexion, trabajador.id)[0]

    assert jornada.abierta
    assert jornada.minutos_trabajados() == 0
    assert jornada.minutos_trabajados(ahora=db.ahora_utc()) == pytest.approx(180, abs=2)


def test_pausa_abierta_se_descuenta_al_cronometrar(conexion, trabajador):
    ahora = db.ahora_utc()
    dom.fichar(conexion, trabajador.id, "ENTRADA", momento=ahora - dt.timedelta(hours=4))
    dom.fichar(
        conexion, trabajador.id, "PAUSA_INICIO", momento=ahora - dt.timedelta(hours=1)
    )
    jornada = dom.jornadas_de(conexion, trabajador.id)[0]
    assert jornada.minutos_trabajados(ahora=ahora) == pytest.approx(180, abs=2)


def test_la_salida_cierra_una_pausa_olvidada(conexion, trabajador):
    dom.fichar(conexion, trabajador.id, "ENTRADA", momento=utc(2026, 3, 2, 8))
    dom.fichar(conexion, trabajador.id, "PAUSA_INICIO", momento=utc(2026, 3, 2, 12))
    dom.fichar(conexion, trabajador.id, "SALIDA", momento=utc(2026, 3, 2, 17))

    jornada = dom.jornadas_de(conexion, trabajador.id)[0]
    assert jornada.pausas[-1][1] is not None
    assert jornada.minutos_trabajados() == 4 * 60


def test_incidencia_cierra_la_jornada(conexion, trabajador):
    dom.fichar(conexion, trabajador.id, "ENTRADA", momento=utc(2026, 3, 2, 8))
    dom.fichar(conexion, trabajador.id, "INCIDENCIA", momento=utc(2026, 3, 2, 14))

    jornada = dom.jornadas_de(conexion, trabajador.id)[0]
    assert jornada.incidencia
    assert not jornada.abierta
    assert dom.estado_actual(conexion, trabajador.id) == dom.FUERA


# --------------------------------------------------------------------------- #
# Rectificaciones
# --------------------------------------------------------------------------- #

def test_rectificar_conserva_el_original(conexion, trabajador):
    dom.fichar(conexion, trabajador.id, "ENTRADA", momento=utc(2026, 3, 2, 9))
    dom.fichar(conexion, trabajador.id, "SALIDA", momento=utc(2026, 3, 2, 17))
    entrada = dom.eventos_efectivos(conexion, trabajador_id=trabajador.id)[0]

    dom.rectificar(
        conexion, entrada.id, momento_nuevo=utc(2026, 3, 2, 8),
        motivo="Olvidó fichar al llegar; consta en el parte de turno",
        autor="admin",
    )

    original = conexion.execute(
        "SELECT ts_utc FROM eventos WHERE id = ?", (entrada.id,)
    ).fetchone()
    assert original["ts_utc"] == db.a_iso(utc(2026, 3, 2, 9)), "el original no se toca"

    jornada = dom.jornadas_de(conexion, trabajador.id)[0]
    assert jornada.minutos_trabajados() == 9 * 60
    assert jornada.rectificada


def test_la_rectificacion_exige_motivo(conexion, trabajador):
    dom.fichar(conexion, trabajador.id, "ENTRADA", momento=utc(2026, 3, 2, 9))
    evento = dom.eventos_efectivos(conexion, trabajador_id=trabajador.id)[0]
    with pytest.raises(dom.ErrorDominio, match="motivo"):
        dom.rectificar(
            conexion, evento.id, momento_nuevo=utc(2026, 3, 2, 8),
            motivo="   ", autor="admin",
        )


def test_anular_elimina_el_fichaje_del_computo_sin_borrarlo(conexion, trabajador):
    dom.fichar(conexion, trabajador.id, "ENTRADA", momento=utc(2026, 3, 2, 9))
    evento = dom.eventos_efectivos(conexion, trabajador_id=trabajador.id)[0]

    dom.rectificar(
        conexion, evento.id, momento_nuevo=None, anular=True,
        motivo="Fichaje duplicado por error del terminal", autor="admin",
    )

    assert dom.eventos_efectivos(conexion, trabajador_id=trabajador.id) == []
    assert dom.estado_actual(conexion, trabajador.id) == dom.FUERA
    # El dato sigue en la base, sólo deja de computar.
    assert conexion.execute(
        "SELECT COUNT(*) AS n FROM eventos WHERE id = ?", (evento.id,)
    ).fetchone()["n"] == 1


def test_la_rectificacion_queda_auditada(conexion, trabajador):
    dom.fichar(conexion, trabajador.id, "ENTRADA", momento=utc(2026, 3, 2, 9))
    evento = dom.eventos_efectivos(conexion, trabajador_id=trabajador.id)[0]
    dom.rectificar(
        conexion, evento.id, momento_nuevo=utc(2026, 3, 2, 8),
        motivo="Corrección del responsable de turno", autor="admin",
    )
    auditoria = list(conexion.execute("SELECT accion, detalle FROM auditoria"))
    assert any(f["accion"] == "RECTIFICA_FICHAJE" for f in auditoria)


def test_la_integridad_aguanta_tras_rectificar(conexion, trabajador):
    dom.fichar(conexion, trabajador.id, "ENTRADA", momento=utc(2026, 3, 2, 9))
    evento = dom.eventos_efectivos(conexion, trabajador_id=trabajador.id)[0]
    dom.rectificar(
        conexion, evento.id, momento_nuevo=utc(2026, 3, 2, 8),
        motivo="Prueba de integridad", autor="admin",
    )
    assert db.verificar_integridad(conexion)["integro"]


def test_reactivar_devuelve_el_alta_sin_duplicar_la_ficha(
    conexion, cifrador, trabajador
):
    """Volver de una baja no debe obligar a crear la persona otra vez.

    Si hubiera que darla de alta de nuevo, sus fichajes antiguos quedarían
    colgando de otra ficha y el historial de cuatro años del art. 34.9 ET
    aparecería partido en dos.
    """
    dom.fichar(conexion, trabajador.id, "ENTRADA", momento=utc(2026, 3, 2, 9))
    dom.fichar(conexion, trabajador.id, "SALIDA", momento=utc(2026, 3, 2, 17))
    dom.baja_trabajador(conexion, cifrador, trabajador.id)
    with pytest.raises(dom.ErrorDominio):
        dom.autenticar(conexion, cifrador, trabajador.codigo, "4791")

    dom.reactivar_trabajador(conexion, trabajador.id, autor="admin")

    vuelto = dom.obtener_trabajador(conexion, cifrador, trabajador.id)
    assert vuelto.activo
    assert vuelto.baja is None
    # El PIN de siempre sigue sirviendo: no se le cambia nada por volver.
    assert dom.autenticar(conexion, cifrador, trabajador.codigo, "4791").id == (
        trabajador.id
    )
    # Y sus fichajes anteriores siguen siendo suyos.
    assert len(dom.eventos_efectivos(conexion, trabajador_id=trabajador.id)) == 2
    assert any(
        f["accion"] == "REACTIVA_TRABAJADOR"
        for f in conexion.execute("SELECT accion FROM auditoria")
    )
    assert len(conexion.execute("SELECT id FROM trabajadores").fetchall()) == 1


def test_los_tipos_que_se_fichan_son_los_del_libro_menos_la_rectificacion():
    """Una sola lista de tipos de evento, no dos que puedan separarse."""
    assert set(dom.TIPOS_FICHAJE) == set(TIPOS_EVENTO) - {"RECTIFICACION"}


def test_no_se_ficha_una_rectificacion_a_mano(conexion, trabajador):
    with pytest.raises(dom.ErrorDominio):
        dom.fichar(conexion, trabajador.id, "RECTIFICACION")


def test_la_salida_registrada_desde_el_panel_deja_su_procedencia(
    conexion, trabajador
):
    """La cierra la administración, no la persona: tiene que notarse.

    El registro debe poder decir quién anotó cada hora, así que un cierre
    hecho desde el panel queda con origen «PANEL» y con el autor que lo hizo,
    no como si lo hubiera fichado el propio trabajador en el terminal.
    """
    dom.fichar(conexion, trabajador.id, "ENTRADA", momento=utc(2026, 3, 2, 9))
    evento = dom.fichar(
        conexion, trabajador.id, "SALIDA", momento=utc(2026, 3, 2, 17),
        autor="admin", origen="PANEL",
    )
    assert evento.origen == "PANEL"
    assert evento.autor == "admin"
    assert dom.estado_actual(conexion, trabajador.id) == dom.FUERA
