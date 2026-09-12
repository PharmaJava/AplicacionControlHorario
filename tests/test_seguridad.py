"""Pruebas de la capa criptográfica."""

from __future__ import annotations

import pytest

from controlhorario.config import ruta_clave
from controlhorario.seguridad import (
    Cifrador,
    fortaleza_contrasena,
    generar_pin,
    hash_secreto,
    obtener_clave,
    validar_pin,
    verificar_secreto,
)


def test_la_clave_persiste_entre_arranques():
    """El fallo central de la versión de 2024: la clave se regeneraba."""
    primera = obtener_clave()
    segunda = obtener_clave()
    assert primera == segunda


def test_los_datos_cifrados_se_recuperan_tras_reiniciar():
    cifrado = Cifrador().cifrar("María López")
    # Un Cifrador nuevo simula el siguiente arranque del programa.
    assert Cifrador().descifrar(cifrado) == "María López"


def test_el_texto_cifrado_no_contiene_el_original():
    cifrado = Cifrador().cifrar("12345678Z")
    assert b"12345678Z" not in cifrado


def test_la_clave_no_es_legible_por_otros_usuarios():
    obtener_clave()
    modo = ruta_clave().stat().st_mode
    assert modo & 0o077 == 0, "la clave no debe tener permisos de grupo ni otros"


def test_indice_ciego_estable_y_no_reversible(cifrador):
    assert cifrador.indice("12345678Z") == cifrador.indice(" 12345678z ")
    assert "12345678" not in cifrador.indice("12345678Z")


def test_hash_de_contrasena_con_sal_distinta():
    uno = hash_secreto("Farmacia2026!Segura")
    otro = hash_secreto("Farmacia2026!Segura")
    assert uno != otro, "cada hash debe llevar su propia sal"
    assert verificar_secreto("Farmacia2026!Segura", uno)
    assert verificar_secreto("Farmacia2026!Segura", otro)


def test_contrasena_incorrecta_rechazada():
    almacenado = hash_secreto("Farmacia2026!Segura")
    assert not verificar_secreto("otra cosa", almacenado)
    assert not verificar_secreto("", almacenado)
    assert not verificar_secreto("Farmacia2026!Segura", None)
    assert not verificar_secreto("Farmacia2026!Segura", "formato-invalido")


@pytest.mark.parametrize(
    "contrasena",
    ["corta", "123456789012", "RepublicaArgentina", "todominusculas1"],
)
def test_contrasenas_debiles_rechazadas(contrasena):
    valida, _ = fortaleza_contrasena(contrasena)
    assert not valida


def test_contrasena_buena_aceptada():
    valida, _ = fortaleza_contrasena("Farmacia2026!Segura")
    assert valida


@pytest.mark.parametrize("pin", ["0000", "1234", "abc1", "12", "999999999", "7777"])
def test_pines_debiles_rechazados(pin):
    assert not validar_pin(pin)[0]


def test_pin_generado_siempre_valido():
    for _ in range(50):
        assert validar_pin(generar_pin())[0]
