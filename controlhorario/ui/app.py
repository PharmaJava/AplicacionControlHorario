"""Ventana principal: navegación lateral, sesión de administración y arranque."""

from __future__ import annotations

import datetime as dt
import tkinter as tk
from tkinter import messagebox, ttk

from .. import db, migracion, normativa
from ..config import Ajustes, directorio_datos
from ..empaquetado import ruta_recurso
from ..dominio import Trabajador, listar_trabajadores
from ..seguridad import Cifrador, hash_secreto, verificar_secreto
from ..version import NOMBRE_LARGO, __version__
from .dialogos import AsistenteInicial, DialogoAcceso
from .tema import Tema, activar_nitidez
from .vistas import VISTAS
from .widgets import Aviso, Pastilla, centrar

# La sesión de administración caduca sola: el equipo suele estar en una zona
# común y quedarse abierto sería un agujero de acceso a datos personales.
MINUTOS_SESION = 15


class Aplicacion(tk.Tk):
    def __init__(self) -> None:
        activar_nitidez()
        super().__init__()

        self.ajustes = Ajustes.cargar()
        self.title(f"{NOMBRE_LARGO} · {__version__}")
        self.minsize(940, 620)

        self.tema = Tema(self, self.ajustes.tema)
        self.conexion = db.conectar()
        self.cifrador = Cifrador()

        self._admin_hasta: dt.datetime | None = None
        self._vistas: dict[str, ttk.Frame] = {}
        self._botones: dict[str, ttk.Button] = {}
        self.vista_actual = "fichar"

        self._construir()
        self._poner_icono()
        self.aviso_flotante = Aviso(self, self.tema)

        centrar(self, int(1120 * self.tema.escala), int(720 * self.tema.escala))
        if self.ajustes.modo_terminal:
            self._maximizar()
        self.protocol("WM_DELETE_WINDOW", self.cerrar)
        self.bind("<Control-q>", lambda _e: self.cerrar())
        self.bind("<F5>", lambda _e: self.refrescar_todo())

        self.after(200, self._primera_ejecucion)
        self._vigilar_sesion()

    # -- construcción -------------------------------------------------------- #
    def _construir(self) -> None:
        p = self.tema.paleta

        self.lateral = tk.Frame(self, bg=p.superficie, width=int(210 * self.tema.escala))
        self.lateral.pack(side="left", fill="y")
        self.lateral.pack_propagate(False)

        marca = tk.Frame(self.lateral, bg=p.superficie)
        marca.pack(fill="x", padx=18, pady=(20, 6))
        tk.Label(
            marca, text="Control Horario", bg=p.superficie, fg=p.texto,
            font=self.tema.f_seccion, anchor="w",
        ).pack(fill="x")
        self.etiqueta_empresa = tk.Label(
            marca, text=self.ajustes.empresa or "Registro de jornada",
            bg=p.superficie, fg=p.texto_suave, font=self.tema.f_micro,
            anchor="w", wraplength=int(170 * self.tema.escala), justify="left",
        )
        self.etiqueta_empresa.pack(fill="x", pady=(2, 0))

        tk.Frame(self.lateral, height=1, bg=p.borde).pack(fill="x", pady=12, padx=14)

        for clave, etiqueta, _ in VISTAS:
            boton = ttk.Button(
                self.lateral, text=f"  {etiqueta}", style="Nav.TButton",
                command=lambda c=clave: self.navegar(c), takefocus=False,
            )
            boton.pack(fill="x", padx=10, pady=1)
            self._botones[clave] = boton

        pie = tk.Frame(self.lateral, bg=p.superficie)
        pie.pack(side="bottom", fill="x", padx=10, pady=14)
        self.pastilla_sesion = Pastilla(pie, self.tema, "Sin sesión", "neutro")
        self.pastilla_sesion.pack(anchor="w", padx=8, pady=(0, 8))
        ttk.Button(
            pie, text="  Cambiar tema", style="Nav.TButton",
            command=self.alternar_tema, takefocus=False,
        ).pack(fill="x")
        self.boton_sesion = ttk.Button(
            pie, text="  Cerrar sesión", style="Nav.TButton",
            command=self.cerrar_sesion, takefocus=False,
        )
        self.boton_sesion.pack(fill="x")

        self.contenido = ttk.Frame(self)
        self.contenido.pack(side="left", fill="both", expand=True)
        self.navegar("fichar")

    # -- navegación ----------------------------------------------------------- #
    def navegar(self, clave: str) -> None:
        definicion = next((v for v in VISTAS if v[0] == clave), None)
        if definicion is None:
            return
        _, _, clase = definicion

        if clase.requiere_admin and not self.sesion_activa():
            if not self.exigir_admin(f"Para entrar en «{definicion[1]}»"):
                return

        for vista in self._vistas.values():
            vista.pack_forget()

        if clave not in self._vistas:
            self._vistas[clave] = clase(self.contenido, self)
        vista = self._vistas[clave]
        vista.pack(fill="both", expand=True)
        vista.refrescar()
        self.vista_actual = clave

        for otra, boton in self._botones.items():
            boton.configure(
                style="NavActivo.TButton" if otra == clave else "Nav.TButton"
            )

    def refrescar_todo(self) -> None:
        self._cache_trabajadores = None
        self.etiqueta_empresa.configure(
            text=self.ajustes.empresa or "Registro de jornada"
        )
        vista = self._vistas.get(self.vista_actual)
        if vista is not None:
            vista.refrescar()

    # -- sesión de administración ---------------------------------------------- #
    def sesion_activa(self) -> bool:
        return (
            self._admin_hasta is not None
            and dt.datetime.now() < self._admin_hasta
        )

    def exigir_admin(self, motivo: str = "") -> bool:
        if self.sesion_activa():
            self._renovar_sesion()
            return True
        almacenada = db.leer_config(self.conexion, "clave_admin")
        if not almacenada:
            return False
        clave = DialogoAcceso(
            self, self.tema, f"{motivo} necesitas la contraseña de administración."
        ).mostrar()
        if clave is None:
            return False
        if not verificar_secreto(clave, almacenada):
            db.registrar_auditoria(
                self.conexion, actor="desconocido", accion="ACCESO_FALLIDO"
            )
            messagebox.showerror(
                "Acceso denegado", "La contraseña no es correcta.", parent=self
            )
            return False
        self._renovar_sesion()
        db.registrar_auditoria(self.conexion, actor="admin", accion="ACCESO_ADMIN")
        return True

    def _renovar_sesion(self) -> None:
        self._admin_hasta = dt.datetime.now() + dt.timedelta(minutes=MINUTOS_SESION)
        self.pastilla_sesion.tono("info", "Sesión de administración")

    def cerrar_sesion(self) -> None:
        if self._admin_hasta is None:
            self.aviso("No hay ninguna sesión abierta.", "info")
            return
        self._admin_hasta = None
        self.pastilla_sesion.tono("neutro", "Sin sesión")
        for clave, vista in list(self._vistas.items()):
            definicion = next((v for v in VISTAS if v[0] == clave), None)
            if definicion and definicion[2].requiere_admin:
                vista.destroy()
                del self._vistas[clave]
        self.navegar("fichar")
        self.aviso("Sesión de administración cerrada.", "info")

    def _vigilar_sesion(self) -> None:
        if self._admin_hasta is not None and not self.sesion_activa():
            self.cerrar_sesion()
            self.aviso("Sesión cerrada por inactividad.", "aviso")
        self.after(30_000, self._vigilar_sesion)

    def actor(self) -> str:
        return "admin" if self.sesion_activa() else "sistema"

    # -- datos ------------------------------------------------------------------ #
    _cache_trabajadores = None

    def trabajadores(self, incluir_bajas: bool = False) -> list[Trabajador]:
        return listar_trabajadores(self.conexion, self.cifrador, incluir_bajas)

    # -- utilidades -------------------------------------------------------------- #
    def aviso(self, texto: str, tono: str = "info", milisegundos: int = 4000) -> None:
        self.aviso_flotante.mostrar(texto, tono, milisegundos)

    def alternar_tema(self) -> None:
        nuevo = self.tema.alternar()
        self.ajustes.tema = nuevo
        self.ajustes.guardar()
        messagebox.showinfo(
            "Tema cambiado",
            "El tema se aplicará por completo al reiniciar la aplicación.",
            parent=self,
        )
        self.refrescar_todo()

    # -- arranque ---------------------------------------------------------------- #
    def _primera_ejecucion(self) -> None:
        if db.leer_config(self.conexion, "clave_admin"):
            self._avisar_pendientes()
            return

        hay_historico = migracion.hay_datos_antiguos()
        datos = AsistenteInicial(self, self.tema, hay_historico).mostrar()
        if datos is None:
            self.destroy()
            return

        self.ajustes.empresa = datos["empresa"]
        self.ajustes.cif = datos["cif"]
        self.ajustes.centro_trabajo = datos["centro_trabajo"]
        self.ajustes.guardar()

        db.guardar_config(
            self.conexion, "clave_admin", hash_secreto(datos["contrasena"])
        )
        db.registrar_auditoria(
            self.conexion, actor="admin", accion="CONFIGURACION_INICIAL",
            detalle=f"Control Horario {__version__}",
        )
        self._renovar_sesion()

        if datos["importar"] and hay_historico:
            resultado = migracion.importar(self.conexion, self.cifrador)
            messagebox.showinfo(
                "Histórico importado",
                f"{resultado.resumen()}\n\n"
                "Los trabajadores importados no tienen PIN todavía. "
                "Asígnales uno en «Equipo» para que puedan fichar.",
                parent=self,
            )

        self.etiqueta_empresa.configure(
            text=self.ajustes.empresa or "Registro de jornada"
        )
        self.refrescar_todo()
        self._avisar_pendientes()

    def _avisar_pendientes(self) -> None:
        alertas = normativa.diagnostico(
            self.conexion, self.trabajadores(), self.ajustes
        )
        graves = [a for a in alertas if a.gravedad == normativa.GRAVE]
        if graves:
            self.aviso(
                f"{len(graves)} aviso(s) de cumplimiento pendientes. "
                "Míralos en el Panel.",
                "error",
                7000,
            )

    def _poner_icono(self) -> None:
        """Icono de la ventana y de la barra de tareas.

        Se intenta primero el .ico (lo único que entiende Windows para la
        ventana) y luego el .png. Que falle no debe impedir arrancar: sin
        icono el programa funciona igual.
        """
        try:
            ico = ruta_recurso("icono.ico")
            if ico.exists():
                self.iconbitmap(default=str(ico))
                return
        except tk.TclError:
            pass
        try:
            png = ruta_recurso("icono_256.png")
            if png.exists():
                self._icono = tk.PhotoImage(file=str(png))
                self.iconphoto(True, self._icono)
        except tk.TclError:
            pass

    def _maximizar(self) -> None:
        """Pantalla completa para el equipo que hace de terminal de fichaje.

        La forma de maximizar cambia según el gestor de ventanas, así que se
        prueban las dos y se deja pasar el fallo: no arrancar por no poder
        maximizar sería peor.
        """
        for intento in (
            lambda: self.state("zoomed"),
            lambda: self.attributes("-zoomed", True),
        ):
            try:
                intento()
                return
            except tk.TclError:
                continue

    def cerrar(self) -> None:
        try:
            if self.ajustes.copia_automatica:
                db.copia_seguridad(self.conexion, actor="cierre")
        except Exception as exc:  # no impedir el cierre por un fallo de copia
            messagebox.showwarning(
                "Copia de seguridad",
                f"No se ha podido crear la copia automática:\n{exc}\n\n"
                f"Tus datos siguen en {directorio_datos()}.",
                parent=self,
            )
        try:
            self.conexion.close()
        except Exception:
            pass
        self.destroy()


def ejecutar() -> None:
    Aplicacion().mainloop()


__all__ = ["Aplicacion", "ejecutar"]
