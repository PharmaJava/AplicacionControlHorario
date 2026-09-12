"""Cifrado en reposo, contraseñas y PIN de fichaje.

Problemas de la versión de 2024 que resuelve este módulo:

* ``Fernet.generate_key()`` se ejecutaba en cada arranque, así que la clave se
  perdía al cerrar el programa y el campo ``encrypted_name`` quedaba
  irrecuperable.  El cifrado era decorativo.
* El nombre se guardaba además en claro en la columna ``name``.
* La contraseña de administrador estaba escrita en el código fuente, visible
  para cualquiera con acceso al fichero y publicada en el repositorio.
* Cualquiera podía fichar por otra persona escribiendo su ID.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import stat
from pathlib import Path

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError as exc:  # pragma: no cover - depende del entorno
    raise SystemExit(
        "Falta la dependencia 'cryptography'.\n"
        "Instálala con:  pip install cryptography"
    ) from exc

from .config import ruta_clave

# PBKDF2-HMAC-SHA256. 600.000 iteraciones es la recomendación de OWASP (2023)
# para SHA-256 y sigue siendo un coste asumible en un equipo de oficina.
_ITERACIONES = 600_000
_LONGITUD_SAL = 16


class ErrorSeguridad(Exception):
    """Error irrecuperable de la capa criptográfica."""


# --------------------------------------------------------------------------- #
# Clave maestra
# --------------------------------------------------------------------------- #

def obtener_clave(ruta: Path | None = None) -> bytes:
    """Devuelve la clave maestra, creándola la primera vez.

    La clave se guarda con permisos ``0600`` (sólo el propietario) en el
    directorio de datos de la aplicación.
    """
    ruta = ruta or ruta_clave()
    if ruta.exists():
        clave = ruta.read_bytes().strip()
        if not clave:
            raise ErrorSeguridad(
                f"El fichero de clave {ruta} está vacío. Restaura una copia de "
                "seguridad: sin la clave original no se pueden descifrar los "
                "datos personales."
            )
        return clave

    clave = Fernet.generate_key()
    # Se escribe con O_EXCL para no pisar una clave creada por otro proceso.
    descriptor = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(descriptor, clave)
    finally:
        os.close(descriptor)
    _restringir_permisos(ruta)
    return clave


def _restringir_permisos(ruta: Path) -> None:
    """Deja el fichero accesible sólo para el usuario actual."""
    try:
        os.chmod(ruta, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        # En algunos sistemas de ficheros de Windows chmod no aplica; el
        # control de acceso lo dan los permisos NTFS de la carpeta de usuario.
        pass


class Cifrador:
    """Cifra y descifra los datos personales guardados en la base de datos."""

    def __init__(self, clave: bytes | None = None) -> None:
        self._clave = clave or obtener_clave()
        self._fernet = Fernet(self._clave)

    def cifrar(self, texto: str) -> bytes:
        return self._fernet.encrypt(texto.encode("utf-8"))

    def descifrar(self, dato: bytes | None) -> str:
        if not dato:
            return ""
        try:
            return self._fernet.decrypt(dato).decode("utf-8")
        except InvalidToken:
            # Ocurre con datos cifrados por la versión antigua, cuya clave se
            # regeneraba en cada arranque y por tanto se perdió.
            return "«dato ilegible: clave distinta»"

    def indice(self, texto: str) -> str:
        """Índice ciego para buscar por un campo cifrado sin descifrarlo.

        HMAC con la clave maestra: permite comprobar duplicados (por ejemplo un
        DNI repetido) sin guardar el valor en claro ni poder invertirlo.
        """
        normalizado = texto.strip().casefold().encode("utf-8")
        return hmac.new(self._clave, normalizado, hashlib.sha256).hexdigest()


# --------------------------------------------------------------------------- #
# Contraseñas y PIN
# --------------------------------------------------------------------------- #

def hash_secreto(secreto: str, sal: bytes | None = None) -> str:
    """Deriva un hash almacenable de una contraseña o PIN.

    Formato: ``pbkdf2_sha256$<iteraciones>$<sal_b64>$<hash_b64>``.
    """
    if not secreto:
        raise ValueError("El secreto no puede estar vacío")
    sal = sal or secrets.token_bytes(_LONGITUD_SAL)
    derivado = hashlib.pbkdf2_hmac(
        "sha256", secreto.encode("utf-8"), sal, _ITERACIONES
    )
    return "$".join(
        (
            "pbkdf2_sha256",
            str(_ITERACIONES),
            base64.b64encode(sal).decode("ascii"),
            base64.b64encode(derivado).decode("ascii"),
        )
    )


def verificar_secreto(secreto: str, almacenado: str | None) -> bool:
    """Comprueba una contraseña o PIN en tiempo constante."""
    if not secreto or not almacenado:
        return False
    try:
        algoritmo, iteraciones, sal_b64, hash_b64 = almacenado.split("$")
        if algoritmo != "pbkdf2_sha256":
            return False
        derivado = hashlib.pbkdf2_hmac(
            "sha256",
            secreto.encode("utf-8"),
            base64.b64decode(sal_b64),
            int(iteraciones),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(derivado, base64.b64decode(hash_b64))


def fortaleza_contrasena(contrasena: str) -> tuple[bool, str]:
    """Valida una contraseña de administración.

    Criterio de longitud antes que de composición, que es lo que recomiendan
    hoy el NIST (SP 800-63B) y el INCIBE: obligar a meter un símbolo y un
    número produce contraseñas cortas y difíciles de recordar, mientras que una
    frase larga resiste mucho mejor.  Por eso una contraseña de 16 caracteres o
    más se acepta con dos tipos de carácter, y sólo se exige mezclar tres tipos
    en las más cortas.
    """
    if len(contrasena) < 12:
        return False, "Debe tener al menos 12 caracteres."
    if contrasena.isdigit():
        return False, "No puede ser sólo números."
    if contrasena.lower() in _CONTRASENAS_HABITUALES:
        return False, "Es una contraseña demasiado común."
    if len(set(contrasena)) < 5:
        return False, "Repite demasiado los mismos caracteres."

    familias = sum(
        (
            any(c.islower() for c in contrasena),
            any(c.isupper() for c in contrasena),
            any(c.isdigit() for c in contrasena),
            any(not c.isalnum() for c in contrasena),
        )
    )
    minimo = 2 if len(contrasena) >= 16 else 3
    if familias < minimo:
        if minimo == 3:
            return False, (
                "Combina mayúsculas, minúsculas, números y símbolos, "
                "o alárgala a 16 caracteres."
            )
        return False, "Mezcla al menos mayúsculas y minúsculas."
    return True, "Contraseña válida."


def validar_pin(pin: str) -> tuple[bool, str]:
    """El PIN identifica al trabajador en el terminal de fichaje."""
    if not pin.isdigit():
        return False, "El PIN debe ser numérico."
    if not 4 <= len(pin) <= 8:
        return False, "El PIN debe tener entre 4 y 8 dígitos."
    if pin in {"0000", "1234", "1111", "12345678", "123456"}:
        return False, "Ese PIN es demasiado previsible."
    if len(set(pin)) == 1:
        return False, "El PIN no puede ser un dígito repetido."
    return True, "PIN válido."


def generar_pin(longitud: int = 4) -> str:
    """PIN aleatorio para altas de trabajadores."""
    while True:
        pin = "".join(secrets.choice("0123456789") for _ in range(longitud))
        if validar_pin(pin)[0]:
            return pin


_CONTRASENAS_HABITUALES = frozenset(
    {
        "contrasena123",
        "administrador",
        "password1234",
        "qwertyuiop12",
        "123456789012",
        "controlhorario",
    }
)

__all__ = [
    "Cifrador",
    "ErrorSeguridad",
    "fortaleza_contrasena",
    "generar_pin",
    "hash_secreto",
    "obtener_clave",
    "validar_pin",
    "verificar_secreto",
]
