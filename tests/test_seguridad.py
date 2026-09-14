"""Pruebas de la capa criptográfica."""

from __future__ import annotations

import sys

import pytest

from controlhorario.config import ruta_clave
from controlhorario.seguridad import (
    Cifrador,
    fortaleza_contrasena,
    generar_pin,
    hash_secreto,
    obtener_clave,
    pin_previsible,
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


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="Windows no implementa los bits de permiso de POSIX",
)
def test_en_posix_la_clave_no_es_legible_por_otros_usuarios():
    obtener_clave()
    modo = ruta_clave().stat().st_mode
    assert modo & 0o077 == 0, "la clave no debe tener permisos de grupo ni otros"


@pytest.mark.skipif(
    not sys.platform.startswith("win"), reason="específico de Windows"
)
def test_en_windows_la_clave_vive_dentro_del_perfil_del_usuario(monkeypatch, tmp_path):
    """En Windows la protección no son los bits POSIX, sino dónde está el fichero.

    `os.chmod` en Windows sólo conmuta el atributo de sólo lectura, así que la
    comprobación equivalente es que la clave quede dentro de %APPDATA%, cuyas
    ACL impiden por defecto que la lean otras cuentas del equipo.
    """
    from controlhorario.config import ruta_clave as ruta

    monkeypatch.delenv("CONTROLHORARIO_DATOS", raising=False)
    perfil = tmp_path / "Roaming"
    monkeypatch.setenv("APPDATA", str(perfil))
    assert str(ruta()).startswith(str(perfil))


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
    [
        "corta",                 # demasiado corta
        "123456789012",          # sólo números
        "todominusculas1",       # corta y sin variedad suficiente
        "contrasena123",         # de las habituales
        "aaaaaaaaaaaaaaaaaa",    # larga pero repetitiva
        "RepublicaArg",          # 12 caracteres con sólo dos familias
    ],
)
def test_contrasenas_debiles_rechazadas(contrasena):
    valida, _ = fortaleza_contrasena(contrasena)
    assert not valida


@pytest.mark.parametrize(
    "contrasena",
    [
        "Farmacia2026!Segura",   # corta pero con cuatro familias
        "RepublicaArgentina",    # 18 caracteres: la longitud compensa
        "el caballo blanco de santiago",
    ],
)
def test_contrasenas_validas_aceptadas(contrasena):
    valida, motivo = fortaleza_contrasena(contrasena)
    assert valida, motivo


def test_la_longitud_puede_sustituir_a_la_complejidad():
    """Una frase larga vale, aunque no lleve números ni símbolos.

    Es lo que recomienda el NIST (SP 800-63B): la longitud protege más que
    obligar a meter un signo de puntuación que luego nadie recuerda.
    """
    corta = "RepublicaArg"           # 12 caracteres, dos familias
    larga = "RepublicaArgentina"     # 18 caracteres, dos familias

    assert not fortaleza_contrasena(corta)[0]
    assert fortaleza_contrasena(larga)[0]


@pytest.mark.parametrize("pin", ["abc1", "12", "999999999", "12 34", ""])
def test_pines_con_formato_invalido_rechazados(pin):
    assert not validar_pin(pin)[0]


@pytest.mark.parametrize("pin", ["0000", "1234", "7777", "2026"])
def test_pines_faciles_se_permiten_pero_se_avisan(pin):
    """Quien administra decide: se permite 1234, pero sabiendo lo que es.

    Obligar a un PIN complicado en una plantilla de cinco personas acaba con
    el PIN escrito en un papel pegado al monitor, que protege menos que un
    1234 que sólo conoce quien lo usa.
    """
    assert validar_pin(pin)[0]
    assert pin_previsible(pin)


@pytest.mark.parametrize("pin", ["4715", "9038", "271828"])
def test_pines_normales_no_se_avisan(pin):
    assert validar_pin(pin)[0]
    assert not pin_previsible(pin)


def test_pin_generado_siempre_valido_y_no_previsible():
    """El que propone el programa nunca sale un 1234 por casualidad."""
    for _ in range(200):
        pin = generar_pin()
        assert validar_pin(pin)[0]
        assert not pin_previsible(pin)
