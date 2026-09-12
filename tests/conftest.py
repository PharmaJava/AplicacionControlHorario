"""Utilidades comunes de las pruebas."""

from __future__ import annotations

import datetime as dt

import pytest


@pytest.fixture(autouse=True)
def datos_aislados(tmp_path, monkeypatch):
    """Cada prueba usa su propia carpeta de datos y su propia clave."""
    monkeypatch.setenv("CONTROLHORARIO_DATOS", str(tmp_path / "datos"))
    yield tmp_path


@pytest.fixture
def conexion():
    from controlhorario import db

    conexion = db.conectar()
    yield conexion
    conexion.close()


@pytest.fixture
def cifrador():
    from controlhorario.seguridad import Cifrador

    return Cifrador()


@pytest.fixture
def ajustes():
    from controlhorario.config import Ajustes

    return Ajustes(empresa="Empresa de Pruebas", cif="B00000000")


@pytest.fixture
def trabajador(conexion, cifrador):
    from controlhorario import dominio

    return dominio.alta_trabajador(
        conexion, cifrador, nombre="Ana Ruiz Gómez", pin="4791", dni="12345678Z"
    )


def utc(anio, mes, dia, hora=0, minuto=0):
    return dt.datetime(anio, mes, dia, hora, minuto, tzinfo=dt.timezone.utc)
