"""Pruebas de las reglas de cumplimiento."""

from __future__ import annotations

import datetime as dt


from controlhorario import dominio as dom, normativa

from .conftest import utc


def _codigos(alertas):
    return {a.codigo for a in alertas}


def _jornada(conexion, trabajador_id, dia, hora_entrada, hora_salida, pausa_min=0):
    dom.fichar(
        conexion, trabajador_id, "ENTRADA",
        momento=utc(2026, 3, dia, hora_entrada),
    )
    if pausa_min:
        dom.fichar(
            conexion, trabajador_id, "PAUSA_INICIO",
            momento=utc(2026, 3, dia, hora_entrada + 3),
        )
        dom.fichar(
            conexion, trabajador_id, "PAUSA_FIN",
            momento=utc(2026, 3, dia, hora_entrada + 3)
            + dt.timedelta(minutes=pausa_min),
        )
    dom.fichar(
        conexion, trabajador_id, "SALIDA", momento=utc(2026, 3, dia, hora_salida)
    )


def test_sin_incidencias_una_jornada_normal(conexion, trabajador, ajustes):
    _jornada(conexion, trabajador.id, 2, 8, 17, pausa_min=60)
    alertas = normativa.analizar_trabajador(
        dom.jornadas_de(conexion, trabajador.id), trabajador, ajustes
    )
    assert alertas == []


def test_descanso_entre_jornadas_insuficiente(conexion, trabajador, ajustes):
    """Art. 34.3 ET: 12 horas mínimas entre jornadas."""
    _jornada(conexion, trabajador.id, 2, 8, 22)
    _jornada(conexion, trabajador.id, 3, 6, 14)   # sólo 8 horas de descanso

    alertas = normativa.analizar_trabajador(
        dom.jornadas_de(conexion, trabajador.id), trabajador, ajustes
    )
    assert "DESCANSO_ENTRE_JORNADAS" in _codigos(alertas)
    alerta = next(a for a in alertas if a.codigo == "DESCANSO_ENTRE_JORNADAS")
    assert alerta.gravedad == normativa.GRAVE
    assert "34.3" in alerta.referencia


def test_jornada_diaria_excesiva(conexion, trabajador, ajustes):
    """Art. 34.3 ET: 9 horas ordinarias al día como máximo."""
    _jornada(conexion, trabajador.id, 2, 6, 18)  # 12 horas
    alertas = normativa.analizar_trabajador(
        dom.jornadas_de(conexion, trabajador.id), trabajador, ajustes
    )
    assert "JORNADA_DIARIA" in _codigos(alertas)


def test_pausa_insuficiente_en_jornada_continuada(conexion, trabajador, ajustes):
    """Art. 34.4 ET: 15 minutos si se superan 6 horas continuadas."""
    _jornada(conexion, trabajador.id, 2, 8, 16)  # 8 horas sin pausa
    alertas = normativa.analizar_trabajador(
        dom.jornadas_de(conexion, trabajador.id), trabajador, ajustes
    )
    assert "PAUSA_INSUFICIENTE" in _codigos(alertas)


def test_menor_de_edad_exige_pausa_mayor(conexion, cifrador, ajustes):
    """Art. 34.4 ET: 30 minutos para menores si superan 4 horas y media."""
    menor = dom.alta_trabajador(
        conexion, cifrador, nombre="Menor Prueba", pin="5832", es_menor=True
    )
    _jornada(conexion, menor.id, 2, 8, 14, pausa_min=20)  # 6 h con 20 min

    alertas = normativa.analizar_trabajador(
        dom.jornadas_de(conexion, menor.id), menor, ajustes
    )
    alerta = next(a for a in alertas if a.codigo == "PAUSA_INSUFICIENTE")
    assert "30 min" in alerta.mensaje
    assert "menor" in alerta.mensaje


def test_exceso_semanal(conexion, trabajador, ajustes):
    """Art. 34.1 ET: 40 horas semanales de promedio."""
    for dia in range(2, 8):            # lunes a sábado, 9 h cada día
        _jornada(conexion, trabajador.id, dia, 8, 17)
    alertas = normativa.analizar_trabajador(
        dom.jornadas_de(conexion, trabajador.id), trabajador, ajustes
    )
    assert "EXCESO_SEMANAL" in _codigos(alertas)


def test_descanso_semanal_insuficiente(conexion, trabajador, ajustes):
    """Art. 37.1 ET: día y medio ininterrumpido."""
    for dia in range(2, 9):            # siete días seguidos
        _jornada(conexion, trabajador.id, dia, 8, 16)
    alertas = normativa.analizar_trabajador(
        dom.jornadas_de(conexion, trabajador.id), trabajador, ajustes
    )
    assert "DESCANSO_SEMANAL" in _codigos(alertas)


def test_jornada_sin_cerrar(conexion, trabajador, ajustes):
    from controlhorario import db

    dom.fichar(
        conexion, trabajador.id, "ENTRADA",
        momento=db.ahora_utc() - dt.timedelta(days=2),
    )
    alertas = normativa.analizar_trabajador(
        dom.jornadas_de(conexion, trabajador.id), trabajador, ajustes
    )
    assert "JORNADA_SIN_CERRAR" in _codigos(alertas)


def test_limite_por_trabajador_prevalece(conexion, cifrador, ajustes):
    """La jornada pactada de la persona manda sobre la general."""
    parcial = dom.alta_trabajador(
        conexion, cifrador, nombre="Media Jornada", pin="5832", jornada_semanal=20
    )
    for dia in range(2, 7):            # 5 días × 8 h = 40 h
        _jornada(conexion, parcial.id, dia, 8, 16)
    alertas = normativa.analizar_trabajador(
        dom.jornadas_de(conexion, parcial.id), parcial, ajustes
    )
    alerta = next(a for a in alertas if a.codigo == "EXCESO_SEMANAL")
    assert "20 h" in alerta.mensaje


def test_umbral_configurable_por_convenio(conexion, trabajador, ajustes):
    """Con jornada de 37,5 h el mismo horario ya genera aviso."""
    for dia in range(2, 7):            # 5 días × 8 h = 40 h
        _jornada(conexion, trabajador.id, dia, 8, 16)

    sin_aviso = normativa.analizar_trabajador(
        dom.jornadas_de(conexion, trabajador.id), trabajador, ajustes
    )
    assert "EXCESO_SEMANAL" not in _codigos(sin_aviso)

    ajustes.horas_semanales = 37.5
    con_aviso = normativa.analizar_trabajador(
        dom.jornadas_de(conexion, trabajador.id), trabajador, ajustes
    )
    assert "EXCESO_SEMANAL" in _codigos(con_aviso)


# --------------------------------------------------------------------------- #
# Diagnóstico de la instalación
# --------------------------------------------------------------------------- #

def test_diagnostico_avisa_de_trabajadores_sin_pin(conexion, cifrador, ajustes):
    conexion.execute(
        "INSERT INTO trabajadores (codigo, nombre_cifrado, nombre_indice, "
        "pin_hash, alta_utc) VALUES ('E900', ?, 'x', NULL, '2026-01-01T00:00:00+00:00')",
        (cifrador.cifrar("Sin Pin"),),
    )
    alertas = normativa.diagnostico(
        conexion, dom.listar_trabajadores(conexion, cifrador), ajustes
    )
    alerta = next(a for a in alertas if a.codigo == "SIN_PIN")
    assert alerta.gravedad == normativa.GRAVE


def test_diagnostico_avisa_de_empresa_sin_configurar(conexion, cifrador):
    from controlhorario.config import Ajustes

    alertas = normativa.diagnostico(conexion, [], Ajustes())
    assert "SIN_EMPRESA" in _codigos(alertas)


def test_diagnostico_detecta_integridad_rota(conexion, trabajador, ajustes, cifrador):
    dom.fichar(conexion, trabajador.id, "ENTRADA", momento=utc(2026, 3, 2, 8))
    conexion.execute("DROP TRIGGER eventos_no_update")
    conexion.execute("UPDATE eventos SET ts_utc = '2020-01-01T00:00:00+00:00'")

    alertas = normativa.diagnostico(
        conexion, dom.listar_trabajadores(conexion, cifrador), ajustes
    )
    assert "INTEGRIDAD" in _codigos(alertas)
