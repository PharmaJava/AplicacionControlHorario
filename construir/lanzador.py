"""Punto de entrada del ejecutable de Windows.

PyInstaller necesita un fichero de guion concreto, no vale ``-m paquete``.
Además, un .exe sin consola no tiene dónde escribir un error de arranque: si
algo falla antes de que exista la ventana, el programa se cerraría sin decir
nada. Por eso aquí se captura cualquier fallo y se enseña en un cuadro de
diálogo, junto con un registro en la carpeta de datos.
"""

from __future__ import annotations

import sys
import traceback


def main() -> int:
    if "--diagnostico" in sys.argv:
        return _diagnostico()
    try:
        from controlhorario.ui.app import ejecutar

        ejecutar()
        return 0
    except SystemExit:
        raise
    except BaseException:
        _avisar_del_fallo(traceback.format_exc())
        return 1


def _diagnostico() -> int:
    """Imprime cómo está instalado el programa.

    Sirve para resolver incidencias sin estar delante del equipo: basta con
    pedir que ejecuten «ControlHorario.exe --diagnostico» desde una ventana de
    comandos y peguen lo que sale.
    """
    from controlhorario import arranque, empaquetado
    from controlhorario.config import directorio_datos, ruta_bd, ruta_clave
    from controlhorario.version import __version__

    lineas = [
        f"Control Horario {__version__}",
        f"Empaquetado      : {empaquetado.esta_empaquetado()}",
        f"Ejecutable       : {empaquetado.ejecutable()}",
        f"Carpeta programa : {empaquetado.directorio_ejecutable()}",
        f"Recursos         : {empaquetado.directorio_base() / 'recursos'}",
        f"Icono presente   : {empaquetado.ruta_recurso('icono.ico').exists()}",
        f"Carpeta de datos : {directorio_datos()}",
        f"Base de datos    : {ruta_bd()} (existe: {ruta_bd().exists()})",
        f"Clave de cifrado : {ruta_clave()} (existe: {ruta_clave().exists()})",
        f"Arranque auto.   : {arranque.esta_activado()} -> {arranque.ruta_arranque()}",
        f"Orden de arranque: {arranque.orden()}",
        f"Python           : {sys.version.split()[0]}",
        f"Plataforma       : {sys.platform}",
    ]
    for modulo in ("cryptography", "openpyxl", "tkinter"):
        try:
            __import__(modulo)
            estado = "OK"
        except ImportError as exc:
            estado = f"FALTA ({exc})"
        lineas.append(f"  {modulo:14} : {estado}")

    print("\n".join(lineas))
    return 0


def _avisar_del_fallo(detalle: str) -> None:
    registro = _guardar_registro(detalle)
    mensaje = (
        "Control Horario no ha podido arrancar.\n\n"
        f"{detalle.strip().splitlines()[-1]}\n\n"
    )
    if registro:
        mensaje += f"Detalle completo en:\n{registro}\n\n"
    mensaje += "Tus datos no se han tocado."

    try:
        import tkinter as tk
        from tkinter import messagebox

        raiz = tk.Tk()
        raiz.withdraw()
        messagebox.showerror("Control Horario", mensaje)
        raiz.destroy()
    except Exception:
        print(mensaje, file=sys.stderr)


def _guardar_registro(detalle: str) -> str | None:
    try:
        import datetime as dt

        from controlhorario.config import directorio_datos

        ruta = directorio_datos() / "error_arranque.log"
        with ruta.open("a", encoding="utf-8") as fichero:
            fichero.write(f"\n===== {dt.datetime.now():%Y-%m-%d %H:%M:%S} =====\n")
            fichero.write(detalle)
        return str(ruta)
    except Exception:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
