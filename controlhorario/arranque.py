"""Arranque automático del programa al iniciar sesión en el equipo.

Pensado para el ordenador que hace de terminal de fichaje: si nadie tiene que
acordarse de abrir el programa, no hay mañanas sin registrar.

Cada sistema tiene su mecanismo, y en los tres se usa el del **usuario**, no el
del equipo: no hace falta ser administrador y la persona puede quitarlo por su
cuenta sin tocar nada del sistema.

* Windows → acceso directo en la carpeta Inicio (``shell:startup``)
* Linux   → ``~/.config/autostart/controlhorario.desktop`` (estándar XDG)
* macOS   → agente de usuario en ``~/Library/LaunchAgents``
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ETIQUETA_MAC = "com.pharmajava.controlhorario"
_NOMBRE_ENLACE = "Control Horario"


class ErrorArranque(Exception):
    """No se ha podido configurar el arranque automático."""


# --------------------------------------------------------------------------- #
# Cómo se lanza el programa
# --------------------------------------------------------------------------- #

def _directorio_app() -> Path:
    """Carpeta desde la que se importa el paquete."""
    return Path(__file__).resolve().parent.parent


def _interprete() -> Path:
    """Intérprete con el que relanzar el programa.

    En Windows se prefiere ``pythonw.exe``: ``python.exe`` abriría además una
    ventana negra de consola detrás del programa.
    """
    actual = Path(sys.executable)
    if sys.platform.startswith("win"):
        sin_consola = actual.with_name("pythonw.exe")
        if sin_consola.exists():
            return sin_consola
    return actual


def orden() -> list[str]:
    return [str(_interprete()), "-m", "controlhorario"]


# --------------------------------------------------------------------------- #
# Rutas de cada sistema
# --------------------------------------------------------------------------- #

def ruta_arranque() -> Path:
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return (
            Path(base)
            / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
            / f"{_NOMBRE_ENLACE}.lnk"
        )
    if sys.platform == "darwin":
        return Path.home() / "Library" / "LaunchAgents" / f"{ETIQUETA_MAC}.plist"
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "autostart" / "controlhorario.desktop"


def esta_activado() -> bool:
    return ruta_arranque().exists()


# --------------------------------------------------------------------------- #
# Activar y desactivar
# --------------------------------------------------------------------------- #

def activar() -> Path:
    destino = ruta_arranque()
    destino.parent.mkdir(parents=True, exist_ok=True)

    if sys.platform.startswith("win"):
        _activar_windows(destino)
    elif sys.platform == "darwin":
        _activar_mac(destino)
    else:
        _activar_linux(destino)
    return destino


def desactivar() -> None:
    destino = ruta_arranque()
    if sys.platform == "darwin" and destino.exists():
        # Se descarga el agente para que el cambio surta efecto ya, sin
        # esperar al siguiente inicio de sesión.
        subprocess.run(
            ["launchctl", "unload", str(destino)],
            check=False, capture_output=True,
        )
    destino.unlink(missing_ok=True)


def _activar_windows(destino: Path) -> None:
    """Crea el acceso directo con WScript.Shell, a través de PowerShell.

    Es la forma de generar un .lnk de verdad sin depender de pywin32.
    """
    guion = (
        "$s = New-Object -ComObject WScript.Shell; "
        f"$a = $s.CreateShortcut('{destino}'); "
        f"$a.TargetPath = '{_interprete()}'; "
        "$a.Arguments = '-m controlhorario'; "
        f"$a.WorkingDirectory = '{_directorio_app()}'; "
        f"$a.IconLocation = '{_directorio_app() / 'recursos' / 'icono.ico'},0'; "
        "$a.Description = 'Registro de jornada laboral'; "
        "$a.Save()"
    )
    sin_ventana = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    resultado = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", guion],
        capture_output=True, text=True, creationflags=sin_ventana,
    )
    if resultado.returncode != 0 or not destino.exists():
        raise ErrorArranque(
            "No se ha podido crear el acceso directo de inicio.\n"
            f"{resultado.stderr.strip()}"
        )


def _activar_linux(destino: Path) -> None:
    ejecutar = " ".join(f'"{parte}"' for parte in orden())
    destino.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Version=1.0\n"
        "Name=Control Horario\n"
        "Comment=Registro de jornada laboral\n"
        f"Exec={ejecutar}\n"
        f"Path={_directorio_app()}\n"
        "Icon=controlhorario\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n"
        "X-GNOME-Autostart-Delay=10\n",
        encoding="utf-8",
    )
    destino.chmod(0o755)


def _activar_mac(destino: Path) -> None:
    argumentos = "".join(f"        <string>{p}</string>\n" for p in orden())
    destino.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"\n'
        '  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n'
        "<dict>\n"
        "    <key>Label</key>\n"
        f"    <string>{ETIQUETA_MAC}</string>\n"
        "    <key>ProgramArguments</key>\n"
        "    <array>\n"
        f"{argumentos}"
        "    </array>\n"
        "    <key>WorkingDirectory</key>\n"
        f"    <string>{_directorio_app()}</string>\n"
        "    <key>RunAtLoad</key>\n"
        "    <true/>\n"
        "    <key>KeepAlive</key>\n"
        "    <false/>\n"
        "</dict>\n"
        "</plist>\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["launchctl", "load", str(destino)], check=False, capture_output=True
    )


def descripcion_ubicacion() -> str:
    """Dónde queda configurado, para poder decírselo a quien lo administre."""
    if sys.platform.startswith("win"):
        return "la carpeta Inicio de Windows (shell:startup)"
    if sys.platform == "darwin":
        return "los agentes de inicio de sesión de macOS (~/Library/LaunchAgents)"
    return "el arranque automático de sesión (~/.config/autostart)"


__all__ = [
    "ErrorArranque",
    "activar",
    "desactivar",
    "descripcion_ubicacion",
    "esta_activado",
    "orden",
    "ruta_arranque",
]
