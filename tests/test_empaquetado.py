"""Pruebas del comportamiento al ejecutarse empaquetado como .exe."""

from __future__ import annotations

import sys

import pytest

from controlhorario import arranque, empaquetado


@pytest.fixture
def congelado(tmp_path, monkeypatch):
    """Simula PyInstaller: sys.frozen, sys._MEIPASS y un .exe instalado."""
    extraccion = tmp_path / "temporal" / "_MEI12345"
    (extraccion / "recursos").mkdir(parents=True)
    (extraccion / "recursos" / "icono.ico").write_bytes(b"falso")

    instalado = tmp_path / "Programas" / "ControlHorario"
    instalado.mkdir(parents=True)
    exe = instalado / "ControlHorario.exe"
    exe.write_bytes(b"falso")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(extraccion), raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    return {"extraccion": extraccion, "instalado": instalado, "exe": exe}


def test_sin_empaquetar_se_detecta_bien():
    assert not empaquetado.esta_empaquetado()


def test_empaquetado_se_detecta(congelado):
    assert empaquetado.esta_empaquetado()


def test_los_recursos_salen_de_la_carpeta_de_extraccion(congelado):
    assert empaquetado.ruta_recurso("icono.ico").exists()
    assert empaquetado.ruta_recurso("icono.ico").parent.parent == congelado["extraccion"]


def test_el_directorio_del_ejecutable_es_estable(congelado):
    """No debe apuntar a la carpeta temporal, que Windows borra al salir."""
    assert empaquetado.directorio_ejecutable() == congelado["instalado"]
    assert empaquetado.directorio_ejecutable() != congelado["extraccion"]


def test_el_arranque_apunta_al_exe_y_no_a_la_carpeta_temporal(congelado):
    """El fallo que rompería el arranque automático del .exe."""
    orden = arranque.orden()
    assert orden == [str(congelado["exe"])]
    assert "_MEI" not in orden[0]


def test_sin_empaquetar_el_arranque_invoca_el_modulo():
    orden = arranque.orden()
    assert orden[1:] == ["-m", "controlhorario"]


def test_los_recursos_existen_en_el_repositorio():
    """Lo que el empaquetado tiene que incluir."""
    for nombre in ("icono.ico", "icono.png", "icono_256.png"):
        assert empaquetado.ruta_recurso(nombre).exists(), nombre
