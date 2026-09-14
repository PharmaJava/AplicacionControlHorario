"""Pruebas de la interfaz.

Necesitan una pantalla: en Windows la hay siempre, en Linux basta con Xvfb.
Donde no la haya, se saltan solas en vez de fallar.
"""

from __future__ import annotations

import pytest

tk = pytest.importorskip("tkinter")

from controlhorario import db, dominio as dom  # noqa: E402
from controlhorario.seguridad import hash_secreto  # noqa: E402

CLAVE = "ContrasenaLargaDePrueba"


@pytest.fixture
def app():
    """Aplicación ya configurada, para que no salte el asistente inicial."""
    from controlhorario.ui.app import Aplicacion

    conexion = db.conectar()
    db.guardar_config(conexion, "clave_admin", hash_secreto(CLAVE))
    conexion.close()

    try:
        ventana = Aplicacion()
    except tk.TclError as exc:  # pragma: no cover - depende del entorno
        pytest.skip(f"sin pantalla disponible: {exc}")
    ventana.withdraw()
    yield ventana
    ventana.destroy()


@pytest.fixture
def ana(app):
    return dom.alta_trabajador(
        app.conexion, app.cifrador, nombre="Ana Ruiz Gómez", pin="4791"
    )


def _panel(app):
    app.navegar("panel")
    return app._vistas["panel"]


# --------------------------------------------------------------------------- #
# Autocompletado del código
# --------------------------------------------------------------------------- #

def test_el_autocompletado_propone_por_codigo_y_por_nombre(app, ana):
    """Quien no recuerda su código teclea su nombre y lo encuentra igual."""
    app.navegar("fichar")
    campo = app._vistas["fichar"].entrada_codigo

    assert [c for c, _ in campo._coincidencias("e00")] == [ana.codigo]
    assert [c for c, _ in campo._coincidencias("ana")] == [ana.codigo]
    assert [c for c, _ in campo._coincidencias("ruiz")] == [ana.codigo]
    assert campo._coincidencias("zzz") == []


def test_el_autocompletado_no_enseña_a_quien_está_de_baja(app, ana):
    dom.baja_trabajador(app.conexion, app.cifrador, ana.id)
    app.navegar("fichar")
    vista = app._vistas["fichar"]
    vista.refrescar()
    assert vista.entrada_codigo._coincidencias("ana") == []


# --------------------------------------------------------------------------- #
# Salida rápida desde el panel
# --------------------------------------------------------------------------- #

def test_el_panel_ficha_la_salida_con_la_sesión_abierta(app, ana, monkeypatch):
    from controlhorario.ui import vistas

    dom.fichar(app.conexion, ana.id, "ENTRADA")
    panel = _panel(app)
    assert panel._presentes == {str(ana.id): ana.nombre}

    app._renovar_sesion()
    monkeypatch.setattr(vistas.messagebox, "askyesno", lambda *a, **k: True)
    panel.fichar_salida(str(ana.id))

    assert dom.estado_actual(app.conexion, ana.id) == dom.FUERA
    evento = dom.eventos_efectivos(app.conexion, trabajador_id=ana.id)[-1]
    assert (evento.tipo, evento.origen, evento.autor) == ("SALIDA", "PANEL", "admin")


def test_el_panel_no_ficha_la_salida_sin_contraseña(app, ana, monkeypatch):
    """El panel se ve sin contraseña, así que el cierre ajeno sí la pide.

    De lo contrario cualquiera podría cerrar la jornada de un compañero y el
    registro dejaría de ser fiable, que es justo lo que exige el art. 34.9 ET.
    """
    from controlhorario.ui import app as modulo_app, vistas

    dom.fichar(app.conexion, ana.id, "ENTRADA")
    panel = _panel(app)

    class AccesoCancelado:
        def __init__(self, *args, **kwargs):
            pass

        def mostrar(self):
            return None

    monkeypatch.setattr(modulo_app, "DialogoAcceso", AccesoCancelado)
    monkeypatch.setattr(vistas.messagebox, "askyesno", lambda *a, **k: True)
    panel.fichar_salida(str(ana.id))

    assert dom.estado_actual(app.conexion, ana.id) == dom.DENTRO


def test_el_panel_sin_nadie_dentro_no_ofrece_filas_que_fichar(app, ana):
    panel = _panel(app)
    assert panel._presentes == {}


def test_el_rótulo_de_pantalla_usa_el_nombre_corto(app):
    app.ajustes.empresa = "Farmacia Ejemplo S.L."
    app.ajustes.nombre_visible = "Farmacia Ejemplo"
    app.refrescar_todo()
    assert app.etiqueta_empresa.cget("text") == "Farmacia Ejemplo"


def test_la_lista_de_sugerencias_no_se_queda_flotando(app, ana):
    """Al cambiar de pantalla con la lista abierta, la lista se recoge."""
    app.navegar("fichar")
    campo = app._vistas["fichar"].entrada_codigo
    campo.entrada.insert(0, "an")
    campo._mostrar(campo._coincidencias("an"))
    assert campo._visible

    app._renovar_sesion()
    app.navegar("equipo")
    app.update_idletasks()
    campo._vigilar_visibilidad()
    assert not campo._visible
