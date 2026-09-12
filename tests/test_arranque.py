"""Pruebas del arranque automático con el sistema."""

from __future__ import annotations

import sys

import pytest

from controlhorario import arranque


@pytest.fixture(autouse=True)
def hogar_aislado(tmp_path, monkeypatch):
    """Redirige el HOME para no tocar el arranque real del equipo."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    return tmp_path


def test_por_defecto_no_esta_activado():
    assert not arranque.esta_activado()


def test_activar_y_desactivar():
    destino = arranque.activar()
    assert destino.exists()
    assert arranque.esta_activado()

    arranque.desactivar()
    assert not destino.exists()
    assert not arranque.esta_activado()


def test_desactivar_es_idempotente():
    arranque.desactivar()
    arranque.desactivar()          # no debe fallar aunque no hubiera nada
    assert not arranque.esta_activado()


def test_activar_dos_veces_no_falla():
    arranque.activar()
    destino = arranque.activar()
    assert destino.exists()


def test_la_orden_apunta_al_paquete():
    orden = arranque.orden()
    assert orden[1:] == ["-m", "controlhorario"]
    assert orden[0]


@pytest.mark.skipif(
    sys.platform.startswith("win") or sys.platform == "darwin",
    reason="formato propio de Linux",
)
def test_en_linux_genera_un_desktop_valido():
    destino = arranque.activar()
    contenido = destino.read_text(encoding="utf-8")

    assert destino.suffix == ".desktop"
    assert "autostart" in str(destino)
    assert contenido.startswith("[Desktop Entry]")
    assert "Type=Application" in contenido
    assert "-m\" \"controlhorario" in contenido
    assert "Terminal=false" in contenido


def test_la_ubicacion_se_puede_explicar():
    texto = arranque.descripcion_ubicacion()
    assert texto and not texto.endswith(".")
