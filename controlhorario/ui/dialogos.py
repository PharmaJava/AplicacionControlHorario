"""Diálogos modales: acceso, alta de trabajadores, rectificaciones y periodos."""

from __future__ import annotations

import datetime as dt
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from ..config import MODALIDADES, ROLES
from ..dominio import Trabajador
from ..seguridad import (
    fortaleza_contrasena,
    generar_pin,
    pin_previsible,
    validar_pin,
)
from .tema import Tema
from .widgets import Tarjeta, campo, centrar


class Dialogo(tk.Toplevel):
    """Ventana modal centrada, con Escape para cerrar y Enter para aceptar."""

    ancho = 460
    alto = 340

    def __init__(self, padre: tk.Misc, tema: Tema, titulo: str) -> None:
        super().__init__(padre)
        self.tema = tema
        self.resultado: Any = None
        self.title(titulo)
        self.configure(bg=tema.paleta.fondo)
        self.resizable(False, False)
        self.transient(padre.winfo_toplevel())

        self.contenedor = ttk.Frame(self, padding=20)
        self.contenedor.pack(fill="both", expand=True)
        ttk.Label(self.contenedor, text=titulo, style="Titulo.TLabel").pack(
            anchor="w", pady=(0, 14)
        )
        self.cuerpo = ttk.Frame(self.contenedor)
        self.cuerpo.pack(fill="both", expand=True)
        self.pie = ttk.Frame(self.contenedor)
        self.pie.pack(fill="x", pady=(18, 0))

        self.bind("<Escape>", lambda _e: self.cancelar())
        self.bind("<Return>", lambda _e: self.aceptar())
        self.protocol("WM_DELETE_WINDOW", self.cancelar)

    def botones(self, texto_aceptar: str = "Guardar",
                estilo: str = "Primario.TButton") -> None:
        ttk.Button(self.pie, text="Cancelar", command=self.cancelar).pack(side="right")
        ttk.Button(
            self.pie, text=texto_aceptar, style=estilo, command=self.aceptar
        ).pack(side="right", padx=(0, 8))

    def mostrar(self) -> Any:
        centrar(self, int(self.ancho * self.tema.escala),
                int(self.alto * self.tema.escala))
        self.grab_set()
        self.wait_window()
        return self.resultado

    def aceptar(self) -> None:  # pragma: no cover - lo redefinen las subclases
        self.destroy()

    def cancelar(self) -> None:
        self.resultado = None
        self.destroy()

    def error(self, mensaje: str) -> None:
        messagebox.showerror("No se puede continuar", mensaje, parent=self)

    def pin_aceptable(self, pin: str) -> bool:
        """Valida el PIN y avisa si es de los que cualquiera adivinaría.

        Se permite usar 1234 si quien administra lo prefiere: en una plantilla
        pequeña la comodidad puede pesar más.  Pero conviene saber que el PIN
        es lo que sostiene que un fichaje sea de quien dice ser, así que el
        aviso se da una vez y decide la persona.
        """
        valido, mensaje = validar_pin(pin)
        if not valido:
            self.error(mensaje)
            return False
        if pin_previsible(pin):
            return messagebox.askyesno(
                "PIN fácil de adivinar",
                f"«{pin}» es de los primeros que probaría cualquiera.\n\n"
                "Si otra persona lo adivina podría fichar en su nombre y el "
                "registro dejaría de ser fiable.\n\n¿Usarlo de todas formas?",
                parent=self,
            )
        return True


# --------------------------------------------------------------------------- #
# Acceso de administrador
# --------------------------------------------------------------------------- #

class DialogoAcceso(Dialogo):
    ancho, alto = 430, 260

    def __init__(self, padre: tk.Misc, tema: Tema, motivo: str = "") -> None:
        super().__init__(padre, tema, "Acceso de administración")
        if motivo:
            ttk.Label(
                self.cuerpo, text=motivo, style="SuaveFondo.TLabel", wraplength=380
            ).pack(anchor="w", pady=(0, 10))
        ttk.Label(self.cuerpo, text="Contraseña").pack(anchor="w")
        self.entrada = ttk.Entry(self.cuerpo, show="●", width=34)
        self.entrada.pack(fill="x", pady=(4, 0))
        self.entrada.focus_set()
        self.botones("Entrar")

    def aceptar(self) -> None:
        self.resultado = self.entrada.get()
        self.destroy()


# --------------------------------------------------------------------------- #
# Configuración inicial
# --------------------------------------------------------------------------- #

class AsistenteInicial(Dialogo):
    """Primera ejecución: datos de empresa y contraseña de administración."""

    ancho, alto = 560, 560

    def __init__(self, padre: tk.Misc, tema: Tema, hay_historico: bool) -> None:
        super().__init__(padre, tema, "Configuración inicial")
        self.hay_historico = hay_historico

        ttk.Label(
            self.cuerpo,
            text=(
                "Antes de empezar necesitamos dos cosas: identificar la empresa "
                "en los informes y proteger la administración con una contraseña."
            ),
            style="SuaveFondo.TLabel",
            wraplength=int(500 * tema.escala),
            justify="left",
        ).pack(anchor="w", pady=(0, 14))

        tarjeta = Tarjeta(self.cuerpo, tema)
        tarjeta.pack(fill="x")
        marco, self.empresa = campo(tarjeta.cuerpo, "Razón social", ancho=40)
        marco.pack(fill="x", pady=(0, 10))
        marco, self.cif = campo(tarjeta.cuerpo, "CIF / NIF", ancho=40)
        marco.pack(fill="x", pady=(0, 10))
        marco, self.centro = campo(tarjeta.cuerpo, "Centro de trabajo", ancho=40)
        marco.pack(fill="x")

        tarjeta2 = Tarjeta(self.cuerpo, tema)
        tarjeta2.pack(fill="x", pady=(12, 0))
        marco, self.clave1 = campo(
            tarjeta2.cuerpo, "Contraseña de administración", ancho=40, mostrar="●"
        )
        marco.pack(fill="x", pady=(0, 10))
        marco, self.clave2 = campo(
            tarjeta2.cuerpo, "Repite la contraseña", ancho=40, mostrar="●"
        )
        marco.pack(fill="x")
        ttk.Label(
            tarjeta2.cuerpo,
            text=(
                "Mínimo 12 caracteres combinando mayúsculas, minúsculas, números "
                "y símbolos. Apúntala en un gestor de contraseñas: sin ella no "
                "se puede administrar la aplicación."
            ),
            style="Suave.TLabel",
            wraplength=int(460 * tema.escala),
            justify="left",
        ).pack(anchor="w", pady=(10, 0))

        self.importar = tk.BooleanVar(value=hay_historico)
        if hay_historico:
            tarjeta3 = Tarjeta(self.cuerpo, tema)
            tarjeta3.pack(fill="x", pady=(12, 0))
            ttk.Checkbutton(
                tarjeta3.cuerpo,
                text="Importar el histórico de la versión anterior",
                variable=self.importar,
            ).pack(anchor="w")
            ttk.Label(
                tarjeta3.cuerpo,
                text=(
                    "Hemos encontrado la base de datos antigua. Conviene "
                    "importarla: los registros deben conservarse cuatro años."
                ),
                style="Suave.TLabel",
                wraplength=int(460 * tema.escala),
                justify="left",
            ).pack(anchor="w", pady=(6, 0))

        self.botones("Empezar")
        self.empresa.focus_set()

    def cancelar(self) -> None:
        if messagebox.askyesno(
            "Salir",
            "Sin configuración inicial no se puede usar la aplicación.\n"
            "¿Quieres salir?",
            parent=self,
        ):
            self.resultado = None
            self.destroy()

    def aceptar(self) -> None:
        clave = self.clave1.get()
        if clave != self.clave2.get():
            self.error("Las dos contraseñas no coinciden.")
            return
        valida, mensaje = fortaleza_contrasena(clave)
        if not valida:
            self.error(mensaje)
            return
        self.resultado = {
            "empresa": self.empresa.get().strip(),
            "cif": self.cif.get().strip(),
            "centro_trabajo": self.centro.get().strip(),
            "contrasena": clave,
            "importar": bool(self.importar.get()),
        }
        self.destroy()


class DialogoCambiarClave(Dialogo):
    ancho, alto = 460, 330

    def __init__(self, padre: tk.Misc, tema: Tema) -> None:
        super().__init__(padre, tema, "Cambiar la contraseña")
        marco, self.actual = campo(
            self.cuerpo, "Contraseña actual", ancho=36, mostrar="●"
        )
        marco.pack(fill="x", pady=(0, 10))
        marco, self.nueva1 = campo(
            self.cuerpo, "Contraseña nueva", ancho=36, mostrar="●"
        )
        marco.pack(fill="x", pady=(0, 10))
        marco, self.nueva2 = campo(self.cuerpo, "Repítela", ancho=36, mostrar="●")
        marco.pack(fill="x")
        self.botones("Cambiar")
        self.actual.focus_set()

    def aceptar(self) -> None:
        if self.nueva1.get() != self.nueva2.get():
            self.error("Las dos contraseñas nuevas no coinciden.")
            return
        valida, mensaje = fortaleza_contrasena(self.nueva1.get())
        if not valida:
            self.error(mensaje)
            return
        self.resultado = (self.actual.get(), self.nueva1.get())
        self.destroy()


# --------------------------------------------------------------------------- #
# Trabajadores
# --------------------------------------------------------------------------- #

class DialogoTrabajador(Dialogo):
    ancho, alto = 520, 570

    def __init__(
        self, padre: tk.Misc, tema: Tema, trabajador: Trabajador | None = None
    ) -> None:
        titulo = "Nuevo trabajador" if trabajador is None else "Modificar trabajador"
        super().__init__(padre, tema, titulo)
        self.trabajador = trabajador

        tarjeta = Tarjeta(self.cuerpo, tema)
        tarjeta.pack(fill="x")
        marco, self.nombre = campo(
            tarjeta.cuerpo, "Nombre y apellidos", ancho=38,
            valor=trabajador.nombre if trabajador else "",
        )
        marco.pack(fill="x", pady=(0, 10))
        marco, self.dni = campo(
            tarjeta.cuerpo, "DNI / NIE (opcional)", ancho=38,
            valor=trabajador.dni if trabajador else "",
        )
        marco.pack(fill="x", pady=(0, 10))

        fila = ttk.Frame(tarjeta.cuerpo, style="Superficie.TFrame")
        fila.pack(fill="x", pady=(0, 10))
        izquierda = ttk.Frame(fila, style="Superficie.TFrame")
        izquierda.pack(side="left", fill="x", expand=True)
        ttk.Label(
            izquierda, text="Rol (sólo informativo)", style="Suave.TLabel"
        ).pack(anchor="w")
        self.rol = ttk.Combobox(
            izquierda, values=list(ROLES), state="readonly", width=16
        )
        self.rol.set(trabajador.rol if trabajador else "EMPLEADO")
        self.rol.pack(fill="x", pady=(3, 0))
        # Conviene decirlo: marcar a alguien como ADMIN aquí no le da acceso a
        # nada.  Lo que abre la gestión es la contraseña de administración, no
        # el rol, y dar por hecho lo contrario sería un descuido de seguridad.
        ttk.Label(
            izquierda,
            text="No da permisos: la gestión se abre con la contraseña.",
            style="Suave.TLabel",
            wraplength=int(200 * tema.escala), justify="left",
        ).pack(anchor="w", pady=(3, 0))

        derecha = ttk.Frame(fila, style="Superficie.TFrame")
        derecha.pack(side="left", fill="x", expand=True, padx=(12, 0))
        ttk.Label(
            derecha, text="Jornada semanal pactada (h)", style="Suave.TLabel"
        ).pack(anchor="w")
        self.jornada = ttk.Entry(derecha, width=16)
        if trabajador and trabajador.jornada_semanal:
            self.jornada.insert(0, f"{trabajador.jornada_semanal:g}")
        self.jornada.pack(fill="x", pady=(3, 0))

        self.menor = tk.BooleanVar(value=trabajador.es_menor if trabajador else False)
        ttk.Checkbutton(
            tarjeta.cuerpo,
            text="Menor de 18 años (descansos reforzados, art. 34.4 y 37.1 ET)",
            variable=self.menor,
        ).pack(anchor="w")

        if trabajador is None:
            tarjeta2 = Tarjeta(self.cuerpo, tema)
            tarjeta2.pack(fill="x", pady=(12, 0))
            ttk.Label(
                tarjeta2.cuerpo, text="PIN de fichaje", style="Seccion.TLabel"
            ).pack(anchor="w")
            ttk.Label(
                tarjeta2.cuerpo,
                text=(
                    "Cada persona ficha con su código y su PIN. Es lo que hace "
                    "que el registro sea fiable y no pueda fichar uno por otro."
                ),
                style="Suave.TLabel",
                wraplength=int(430 * tema.escala),
                justify="left",
            ).pack(anchor="w", pady=(4, 8))
            fila_pin = ttk.Frame(tarjeta2.cuerpo, style="Superficie.TFrame")
            fila_pin.pack(fill="x")
            self.pin = ttk.Entry(fila_pin, width=12)
            self.pin.insert(0, generar_pin())
            self.pin.pack(side="left")
            ttk.Button(
                fila_pin, text="Generar otro",
                command=lambda: (self.pin.delete(0, "end"),
                                 self.pin.insert(0, generar_pin())),
            ).pack(side="left", padx=(8, 0))
        else:
            self.pin = None

        self.botones()
        self.nombre.focus_set()

    def aceptar(self) -> None:
        nombre = self.nombre.get().strip()
        if not nombre:
            self.error("El nombre es obligatorio.")
            return
        jornada = None
        if self.jornada.get().strip():
            try:
                jornada = float(self.jornada.get().strip().replace(",", "."))
            except ValueError:
                self.error("La jornada semanal debe ser un número de horas.")
                return
        datos: dict[str, Any] = {
            "nombre": nombre,
            "dni": self.dni.get().strip().upper(),
            "rol": self.rol.get(),
            "es_menor": bool(self.menor.get()),
            "jornada_semanal": jornada,
        }
        if self.pin is not None:
            pin = self.pin.get().strip()
            if not self.pin_aceptable(pin):
                return
            datos["pin"] = pin
        self.resultado = datos
        self.destroy()


class DialogoPin(Dialogo):
    ancho, alto = 420, 260

    def __init__(self, padre: tk.Misc, tema: Tema, nombre: str) -> None:
        super().__init__(padre, tema, "Asignar PIN")
        ttk.Label(
            self.cuerpo, text=f"Nuevo PIN para {nombre}", style="SuaveFondo.TLabel"
        ).pack(anchor="w", pady=(0, 8))
        fila = ttk.Frame(self.cuerpo)
        fila.pack(fill="x")
        self.pin = ttk.Entry(fila, width=14)
        self.pin.insert(0, generar_pin())
        self.pin.pack(side="left")
        ttk.Button(
            fila, text="Generar otro",
            command=lambda: (self.pin.delete(0, "end"),
                             self.pin.insert(0, generar_pin())),
        ).pack(side="left", padx=(8, 0))
        self.botones("Asignar")
        self.pin.focus_set()

    def aceptar(self) -> None:
        pin = self.pin.get().strip()
        if not self.pin_aceptable(pin):
            return
        self.resultado = pin
        self.destroy()


# --------------------------------------------------------------------------- #
# Fichajes
# --------------------------------------------------------------------------- #

def _analizar_fecha_hora(texto: str) -> dt.datetime:
    """Acepta 'dd/mm/aaaa HH:MM' con o sin segundos."""
    texto = texto.strip()
    for formato in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            return dt.datetime.strptime(texto, formato).astimezone()
        except ValueError:
            continue
    raise ValueError("Usa el formato dd/mm/aaaa HH:MM")


class DialogoRectificar(Dialogo):
    """Corrección trazable de un fichaje: nunca borra el original."""

    ancho, alto = 540, 460

    def __init__(
        self, padre: tk.Misc, tema: Tema, descripcion: str, momento: dt.datetime
    ) -> None:
        super().__init__(padre, tema, "Rectificar fichaje")

        ttk.Label(
            self.cuerpo,
            text=(
                "El fichaje original no se borra. Se añade una rectificación "
                "con tu nombre, la fecha y el motivo, de modo que quede "
                "constancia de la corrección."
            ),
            style="SuaveFondo.TLabel",
            wraplength=int(480 * tema.escala),
            justify="left",
        ).pack(anchor="w", pady=(0, 12))

        tarjeta = Tarjeta(self.cuerpo, tema)
        tarjeta.pack(fill="x")
        ttk.Label(tarjeta.cuerpo, text="Fichaje", style="Suave.TLabel").pack(anchor="w")
        ttk.Label(
            tarjeta.cuerpo, text=descripcion, style="Superficie.TLabel",
            wraplength=int(450 * tema.escala), justify="left",
        ).pack(anchor="w", pady=(2, 12))

        marco, self.momento = campo(
            tarjeta.cuerpo, "Fecha y hora correctas (dd/mm/aaaa HH:MM)", ancho=30,
            valor=momento.strftime("%d/%m/%Y %H:%M"),
        )
        marco.pack(fill="x", pady=(0, 10))

        self.anular = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            tarjeta.cuerpo,
            text="Anular el fichaje (se registró por error)",
            variable=self.anular,
            command=self._alternar,
        ).pack(anchor="w", pady=(0, 10))

        ttk.Label(tarjeta.cuerpo, text="Motivo", style="Suave.TLabel").pack(anchor="w")
        self.motivo = tk.Text(
            tarjeta.cuerpo, height=3, width=44, font=tema.f_normal,
            bg=tema.paleta.superficie, fg=tema.paleta.texto,
            insertbackground=tema.paleta.texto,
            highlightthickness=1, highlightbackground=tema.paleta.borde,
            highlightcolor=tema.paleta.primario, bd=0, wrap="word",
        )
        self.motivo.pack(fill="x", pady=(3, 0))

        self.botones("Rectificar")
        self.motivo.focus_set()
        # Enter dentro del motivo debe insertar un salto de línea, no aceptar.
        self.unbind("<Return>")

    def _alternar(self) -> None:
        self.momento.configure(state="disabled" if self.anular.get() else "normal")

    def aceptar(self) -> None:
        motivo = self.motivo.get("1.0", "end").strip()
        if len(motivo) < 5:
            self.error("Explica brevemente el motivo de la rectificación.")
            return
        momento = None
        if not self.anular.get():
            try:
                momento = _analizar_fecha_hora(self.momento.get())
            except ValueError as exc:
                self.error(str(exc))
                return
        self.resultado = {
            "momento": momento,
            "motivo": motivo,
            "anular": bool(self.anular.get()),
        }
        self.destroy()


class DialogoFichajeManual(Dialogo):
    """Alta de un fichaje olvidado, siempre con motivo."""

    ancho, alto = 520, 440

    def __init__(self, padre: tk.Misc, tema: Tema, nombre: str) -> None:
        super().__init__(padre, tema, "Registrar fichaje manual")
        ttk.Label(
            self.cuerpo,
            text=(
                f"Fichaje manual para {nombre}. Queda marcado como manual y con "
                "el motivo indicado, para poder justificarlo después."
            ),
            style="SuaveFondo.TLabel",
            wraplength=int(460 * tema.escala),
            justify="left",
        ).pack(anchor="w", pady=(0, 12))

        tarjeta = Tarjeta(self.cuerpo, tema)
        tarjeta.pack(fill="x")
        ttk.Label(tarjeta.cuerpo, text="Tipo", style="Suave.TLabel").pack(anchor="w")
        self.tipo = ttk.Combobox(
            tarjeta.cuerpo, state="readonly", width=24,
            values=["ENTRADA", "SALIDA", "PAUSA_INICIO", "PAUSA_FIN", "INCIDENCIA"],
        )
        self.tipo.set("ENTRADA")
        self.tipo.pack(fill="x", pady=(3, 10))

        marco, self.momento = campo(
            tarjeta.cuerpo, "Fecha y hora (dd/mm/aaaa HH:MM)", ancho=28,
            valor=dt.datetime.now().strftime("%d/%m/%Y %H:%M"),
        )
        marco.pack(fill="x", pady=(0, 10))

        ttk.Label(tarjeta.cuerpo, text="Modalidad", style="Suave.TLabel").pack(anchor="w")
        self.modalidad = ttk.Combobox(
            tarjeta.cuerpo, state="readonly", width=24, values=list(MODALIDADES)
        )
        self.modalidad.set("PRESENCIAL")
        self.modalidad.pack(fill="x", pady=(3, 10))

        marco, self.nota = campo(tarjeta.cuerpo, "Motivo", ancho=40)
        marco.pack(fill="x")

        self.botones("Registrar")

    def aceptar(self) -> None:
        try:
            momento = _analizar_fecha_hora(self.momento.get())
        except ValueError as exc:
            self.error(str(exc))
            return
        if len(self.nota.get().strip()) < 5:
            self.error("Indica el motivo del fichaje manual.")
            return
        self.resultado = {
            "tipo": self.tipo.get(),
            "momento": momento,
            "modalidad": self.modalidad.get(),
            "nota": self.nota.get().strip(),
        }
        self.destroy()


class DialogoPeriodo(Dialogo):
    ancho, alto = 470, 330

    ATAJOS = {
        "Este mes": 0,
        "Últimos 30 días": 30,
        "Últimos 90 días": 90,
        "Este año": -1,
    }

    def __init__(self, padre: tk.Misc, tema: Tema) -> None:
        super().__init__(padre, tema, "Periodo del informe")
        hoy = dt.date.today()
        inicio_mes = hoy.replace(day=1)

        atajos = ttk.Frame(self.cuerpo)
        atajos.pack(fill="x", pady=(0, 14))
        for etiqueta in self.ATAJOS:
            ttk.Button(
                atajos, text=etiqueta,
                command=lambda e=etiqueta: self._atajo(e),
            ).pack(side="left", padx=(0, 6))

        marco, self.desde = campo(
            self.cuerpo, "Desde (dd/mm/aaaa)", ancho=20,
            valor=inicio_mes.strftime("%d/%m/%Y"),
        )
        marco.pack(fill="x", pady=(0, 10))
        marco, self.hasta = campo(
            self.cuerpo, "Hasta (dd/mm/aaaa)", ancho=20,
            valor=hoy.strftime("%d/%m/%Y"),
        )
        marco.pack(fill="x")
        self.botones("Aceptar")

    def _atajo(self, etiqueta: str) -> None:
        hoy = dt.date.today()
        dias = self.ATAJOS[etiqueta]
        if dias == 0:
            desde = hoy.replace(day=1)
        elif dias == -1:
            desde = hoy.replace(month=1, day=1)
        else:
            desde = hoy - dt.timedelta(days=dias)
        self.desde.delete(0, "end")
        self.desde.insert(0, desde.strftime("%d/%m/%Y"))
        self.hasta.delete(0, "end")
        self.hasta.insert(0, hoy.strftime("%d/%m/%Y"))

    def aceptar(self) -> None:
        try:
            desde = dt.datetime.strptime(self.desde.get().strip(), "%d/%m/%Y")
            hasta = dt.datetime.strptime(self.hasta.get().strip(), "%d/%m/%Y")
        except ValueError:
            self.error("Las fechas deben tener el formato dd/mm/aaaa.")
            return
        if hasta < desde:
            self.error("La fecha final es anterior a la inicial.")
            return
        self.resultado = (
            desde.replace(hour=0, minute=0).astimezone(),
            hasta.replace(hour=23, minute=59, second=59).astimezone(),
        )
        self.destroy()


__all__ = [
    "AsistenteInicial", "Dialogo", "DialogoAcceso", "DialogoCambiarClave",
    "DialogoFichajeManual", "DialogoPeriodo", "DialogoPin", "DialogoRectificar",
    "DialogoTrabajador",
]
