"""Comprobaciones estáticas del script de Inno Setup.

Inno Setup sólo compila en Windows, así que aquí no se puede validar de verdad.
Estas pruebas cubren los errores que ya han roto la compilación alguna vez y
que se detectan leyendo el fichero, para enterarse al instante y no tres
minutos después en un runner.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
INSTALADOR = RAIZ / "construir" / "instalador.iss"


@pytest.fixture(scope="module")
def guion() -> str:
    return INSTALADOR.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def bloque_code(guion: str) -> str:
    return guion[guion.index("[Code]"):]


def test_el_instalador_existe():
    assert INSTALADOR.is_file()


def test_ninguna_linea_de_code_empieza_por_almohadilla(bloque_code: str):
    """El fallo que abortó la compilación dos veces.

    El preprocesador de Inno trata como directiva cualquier línea que empiece
    por «#», así que partir una concatenación dejando `#13#10` al principio de
    la línea siguiente aborta con «Unknown preprocessor directive». Para eso
    están las constantes SALTO y SALTO2.
    """
    culpables = [
        (numero, linea.strip())
        for numero, linea in enumerate(bloque_code.splitlines(), 1)
        if linea.lstrip().startswith("#")
    ]
    assert not culpables, (
        "Líneas que el preprocesador tomaría por directivas: "
        f"{culpables}. Usa SALTO o SALTO2 en su lugar."
    )


def _sin_comentarios_ni_cadenas(codigo: str) -> str:
    codigo = re.sub(r"\{[^}]*\}", " ", codigo, flags=re.S)
    return re.sub(r"'[^']*'", "''", codigo)


def test_los_bloques_pascal_estan_balanceados(bloque_code: str):
    limpio = _sin_comentarios_ni_cadenas(bloque_code)
    cuenta = {
        palabra: len(re.findall(rf"\b{palabra}\b", limpio, re.I))
        for palabra in ("begin", "end", "try", "repeat", "until")
    }
    assert cuenta["begin"] + cuenta["try"] == cuenta["end"], cuenta
    assert cuenta["repeat"] == cuenta["until"], cuenta


def test_toda_rutina_pascal_se_cierra(bloque_code: str):
    limpio = _sin_comentarios_ni_cadenas(bloque_code)
    rutinas = len(re.findall(r"\b(procedure|function)\b", limpio, re.I))
    assert rutinas >= 5, "faltan rutinas del instalador"


@pytest.mark.parametrize(
    "directiva",
    [
        "AppId",              # identidad estable entre versiones
        "OutputBaseFilename",  # nombre del .exe resultante
        "PrivilegesRequired",  # instalación sin administrador
        "UninstallDisplayIcon",
    ],
)
def test_directivas_imprescindibles(guion: str, directiva: str):
    assert re.search(rf"^{directiva}=", guion, re.M), directiva


def test_el_appid_no_cambia():
    """Cambiarlo haría que Windows tratara la actualización como otro programa,
    dejando dos entradas en «Agregar o quitar programas»."""
    guion = INSTALADOR.read_text(encoding="utf-8")
    assert "AppId={{8F3A1C42-7B9E-4D58-A6C1-2E5F9B0D7A34}" in guion


def test_no_se_borra_la_carpeta_de_datos(guion: str):
    """Los registros de jornada deben sobrevivir a la desinstalación."""
    borrados = re.findall(r"^Type: filesandordirs; Name: \"([^\"]+)\"", guion, re.M)
    for objetivo in borrados:
        assert "userappdata" not in objetivo.lower(), objetivo
        assert "ControlHorario\\" not in objetivo or "{app}" in objetivo, objetivo
