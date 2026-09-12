"""Vistas de la aplicación: fichaje, panel, equipo, registros, informes, ajustes."""

from __future__ import annotations

import datetime as dt
import tkinter as tk
from pathlib import Path
import webbrowser
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING

from .. import arranque, db, dominio as dom, informes, migracion, normativa
from ..config import directorio_datos
from ..dominio import ErrorDominio, formatear_horas
from ..seguridad import hash_secreto, verificar_secreto
from .dialogos import (
    DialogoCambiarClave,
    DialogoFichajeManual,
    DialogoPeriodo,
    DialogoPin,
    DialogoRectificar,
    DialogoTrabajador,
)
from .widgets import Fecha, Pastilla, Reloj, Tabla, Tarjeta, campo, separador

if TYPE_CHECKING:  # pragma: no cover
    from .app import Aplicacion


class Vista(ttk.Frame):
    """Base de todas las vistas: cada una sabe repintarse sola."""

    titulo = ""
    subtitulo = ""
    requiere_admin = False

    def __init__(self, padre: tk.Misc, app: Aplicacion) -> None:
        super().__init__(padre, padding=(24, 20))
        self.app = app
        self.tema = app.tema
        self.construir()

    def construir(self) -> None:  # pragma: no cover - lo definen las subclases
        raise NotImplementedError

    def refrescar(self) -> None:
        pass

    def cabecera(self) -> ttk.Frame:
        marco = ttk.Frame(self)
        marco.pack(fill="x", pady=(0, 16))
        ttk.Label(marco, text=self.titulo, style="Titulo.TLabel").pack(anchor="w")
        if self.subtitulo:
            ttk.Label(marco, text=self.subtitulo, style="SuaveFondo.TLabel").pack(
                anchor="w", pady=(2, 0)
            )
        return marco


# --------------------------------------------------------------------------- #
# 1. Terminal de fichaje
# --------------------------------------------------------------------------- #

class VistaFichar(Vista):
    titulo = "Fichar"
    subtitulo = "Introduce tu código y tu PIN"

    _TONOS = {dom.DENTRO: "exito", dom.EN_PAUSA: "aviso", dom.FUERA: "neutro"}
    _TEXTOS = {
        dom.DENTRO: "Trabajando",
        dom.EN_PAUSA: "En pausa",
        dom.FUERA: "Fuera de jornada",
    }

    def construir(self) -> None:
        self.trabajador: dom.Trabajador | None = None
        self._tarea_reinicio: str | None = None

        columnas = ttk.Frame(self)
        columnas.place(relx=0.5, rely=0.5, anchor="center", relwidth=1.0)

        # -- Izquierda: reloj ------------------------------------------------ #
        izquierda = Tarjeta(columnas, self.tema, relleno=28)
        izquierda.pack(side="left", fill="both", expand=True, padx=(0, 12))
        self.reloj = Reloj(izquierda.cuerpo, self.tema)
        self.reloj.pack(anchor="w")
        Fecha(izquierda.cuerpo).pack(anchor="w", pady=(2, 18))
        ttk.Label(
            izquierda.cuerpo, text=self.app.ajustes.empresa or "Control Horario",
            style="Seccion.TLabel",
        ).pack(anchor="w")
        if self.app.ajustes.centro_trabajo:
            ttk.Label(
                izquierda.cuerpo, text=self.app.ajustes.centro_trabajo,
                style="Suave.TLabel",
            ).pack(anchor="w")
        separador(izquierda.cuerpo, self.tema, pady=16)
        ttk.Label(
            izquierda.cuerpo,
            text=(
                "Tu jornada queda registrada conforme al artículo 34.9 del "
                "Estatuto de los Trabajadores. Puedes pedir una copia de tu "
                "registro cuando quieras."
            ),
            style="Suave.TLabel", wraplength=int(300 * self.tema.escala),
            justify="left",
        ).pack(anchor="w")

        # -- Derecha: identificación y acciones ------------------------------ #
        derecha = Tarjeta(columnas, self.tema, relleno=28)
        derecha.pack(side="left", fill="both", expand=True)
        self.panel = derecha.cuerpo

        self.marco_acceso = ttk.Frame(self.panel, style="Superficie.TFrame")
        self.marco_acceso.pack(fill="x")
        marco, self.entrada_codigo = campo(
            self.marco_acceso, "Código de trabajador (por ejemplo E001)", ancho=22
        )
        marco.pack(fill="x", pady=(0, 12))
        marco, self.entrada_pin = campo(
            self.marco_acceso, "PIN", ancho=22, mostrar="●"
        )
        marco.pack(fill="x", pady=(0, 16))
        ttk.Button(
            self.marco_acceso, text="Identificarme", style="Primario.TButton",
            command=self.identificar,
        ).pack(fill="x")
        self.entrada_codigo.bind("<Return>", lambda _e: self.entrada_pin.focus_set())
        self.entrada_pin.bind("<Return>", lambda _e: self.identificar())

        self.marco_acciones = ttk.Frame(self.panel, style="Superficie.TFrame")

    def refrescar(self) -> None:
        self.reiniciar()

    def reiniciar(self) -> None:
        if self._tarea_reinicio:
            try:
                self.after_cancel(self._tarea_reinicio)
            except (ValueError, tk.TclError):
                pass
            self._tarea_reinicio = None
        self.trabajador = None
        self.marco_acciones.pack_forget()
        for hijo in self.marco_acciones.winfo_children():
            hijo.destroy()
        self.entrada_codigo.delete(0, "end")
        self.entrada_pin.delete(0, "end")
        self.marco_acceso.pack(fill="x")
        try:
            self.entrada_codigo.focus_set()
        except tk.TclError:
            pass

    def identificar(self) -> None:
        codigo = self.entrada_codigo.get().strip()
        pin = self.entrada_pin.get().strip()
        if not codigo or not pin:
            self.app.aviso("Escribe tu código y tu PIN.", "aviso")
            return
        try:
            self.trabajador = dom.autenticar(
                self.app.conexion, self.app.cifrador, codigo, pin
            )
        except ErrorDominio as exc:
            self.app.aviso(str(exc), "error")
            self.entrada_pin.delete(0, "end")
            return
        self.marco_acceso.pack_forget()
        self._pintar_acciones()

    def _pintar_acciones(self) -> None:
        assert self.trabajador is not None
        for hijo in self.marco_acciones.winfo_children():
            hijo.destroy()
        self.marco_acciones.pack(fill="both", expand=True)

        estado = dom.estado_actual(self.app.conexion, self.trabajador.id)
        ttk.Label(
            self.marco_acciones, text=self.trabajador.nombre, style="Seccion.TLabel"
        ).pack(anchor="w")
        fila = ttk.Frame(self.marco_acciones, style="Superficie.TFrame")
        fila.pack(anchor="w", pady=(6, 4))
        Pastilla(fila, self.tema, self._TEXTOS[estado], self._TONOS[estado]).pack(
            side="left"
        )

        hoy = dt.datetime.now().astimezone().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        resumen = dom.resumen_periodo(
            self.app.conexion, self.trabajador.id, hoy,
            hoy + dt.timedelta(days=1),
            pausas_computan=self.app.ajustes.pausas_computan_como_trabajo,
            ahora=db.ahora_utc(),
        )
        ttk.Label(
            self.marco_acciones,
            text=f"Hoy llevas {formatear_horas(int(resumen['minutos_trabajados']))} "
                 f"en {resumen['jornadas']} jornada(s).",
            style="Suave.TLabel",
        ).pack(anchor="w", pady=(4, 16))

        acciones = {
            dom.FUERA: [("Registrar ENTRADA", "ENTRADA", "Exito.TButton")],
            dom.DENTRO: [
                ("Registrar SALIDA", "SALIDA", "Peligro.TButton"),
                ("Iniciar PAUSA", "PAUSA_INICIO", "Aviso.TButton"),
            ],
            dom.EN_PAUSA: [
                ("Terminar PAUSA", "PAUSA_FIN", "Exito.TButton"),
                ("Registrar SALIDA", "SALIDA", "Peligro.TButton"),
            ],
        }[estado]
        for texto, tipo, estilo in acciones:
            ttk.Button(
                self.marco_acciones, text=texto, style=estilo,
                command=lambda t=tipo: self.fichar(t),
            ).pack(fill="x", pady=(0, 8))

        if estado == dom.FUERA:
            self.modalidad = tk.StringVar(value="PRESENCIAL")
            fila_mod = ttk.Frame(self.marco_acciones, style="Superficie.TFrame")
            fila_mod.pack(anchor="w", pady=(0, 8))
            ttk.Label(fila_mod, text="Modalidad:", style="Suave.TLabel").pack(
                side="left", padx=(0, 8)
            )
            for etiqueta, valor in (("Presencial", "PRESENCIAL"),
                                    ("Teletrabajo", "TELETRABAJO")):
                ttk.Radiobutton(
                    fila_mod, text=etiqueta, value=valor, variable=self.modalidad
                ).pack(side="left", padx=(0, 10))
        else:
            self.modalidad = None

        separador(self.marco_acciones, self.tema, pady=10)
        pie = ttk.Frame(self.marco_acciones, style="Superficie.TFrame")
        pie.pack(fill="x")
        ttk.Button(pie, text="Ver mi registro", command=self.mi_registro).pack(
            side="left"
        )
        ttk.Button(pie, text="Salir", command=self.reiniciar).pack(side="right")

    def fichar(self, tipo: str) -> None:
        assert self.trabajador is not None
        modalidad = (
            self.modalidad.get() if self.modalidad is not None else "PRESENCIAL"
        )
        try:
            evento = dom.fichar(
                self.app.conexion, self.trabajador.id, tipo,
                modalidad=modalidad, autor=self.trabajador.codigo, origen="TERMINAL",
            )
        except ErrorDominio as exc:
            self.app.aviso(str(exc), "error")
            return
        hora = db.a_local(evento.momento).strftime("%H:%M:%S")
        self.app.aviso(
            f"{dom.nombre_tipo(tipo).capitalize()} registrada a las {hora}. "
            f"¡Hasta luego, {self.trabajador.nombre.split()[0]}!",
            "exito",
        )
        self._pintar_acciones()
        # El terminal vuelve solo a la pantalla de acceso: es de uso compartido.
        self._tarea_reinicio = self.after(6000, self.reiniciar)

    def mi_registro(self) -> None:
        assert self.trabajador is not None
        hasta = dt.datetime.now().astimezone()
        desde = hasta - dt.timedelta(days=90)
        ruta = informes.exportar_trabajador(
            self.app.conexion, self.app.ajustes, self.trabajador, desde, hasta
        )
        self.app.aviso(f"Registro guardado en {ruta}", "info", 7000)
        _abrir(ruta)


# --------------------------------------------------------------------------- #
# 2. Panel
# --------------------------------------------------------------------------- #

class VistaPanel(Vista):
    titulo = "Panel"
    subtitulo = "Situación de hoy y estado de cumplimiento"

    def construir(self) -> None:
        self.cabecera()

        self.tarjetas = ttk.Frame(self)
        self.tarjetas.pack(fill="x", pady=(0, 14))

        medio = ttk.Frame(self)
        medio.pack(fill="both", expand=True)

        izquierda = Tarjeta(medio, self.tema)
        izquierda.pack(side="left", fill="both", expand=True, padx=(0, 12))
        izquierda.titulo("Quién está fichado ahora")
        self.tabla_presentes = Tabla(
            izquierda.cuerpo, self.tema,
            [("nombre", "Trabajador", 170), ("estado", "Estado", 90),
             ("desde", "Desde", 70), ("acumulado", "Hoy", 80)],
            altura=9,
        )
        self.tabla_presentes.pack(fill="both", expand=True, pady=(10, 0))

        derecha = Tarjeta(medio, self.tema)
        derecha.pack(side="left", fill="both", expand=True)
        derecha.titulo("Avisos de cumplimiento")
        self.tabla_alertas = Tabla(
            derecha.cuerpo, self.tema,
            [("gravedad", "Nivel", 62), ("detalle", "Detalle", 300),
             ("norma", "Norma", 110)],
            altura=9,
        )
        self.tabla_alertas.pack(fill="both", expand=True, pady=(10, 0))

    def refrescar(self) -> None:
        for hijo in self.tarjetas.winfo_children():
            hijo.destroy()

        trabajadores = self.app.trabajadores()
        hoy = dt.datetime.now().astimezone().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        manana = hoy + dt.timedelta(days=1)
        ahora_utc = db.ahora_utc()

        dentro = 0
        minutos_hoy = 0
        self.tabla_presentes.limpiar()
        for trabajador in trabajadores:
            estado = dom.estado_actual(self.app.conexion, trabajador.id)
            resumen = dom.resumen_periodo(
                self.app.conexion, trabajador.id, hoy, manana,
                pausas_computan=self.app.ajustes.pausas_computan_como_trabajo,
                ahora=ahora_utc,
            )
            minutos_hoy += int(resumen["minutos_trabajados"])
            if estado == dom.FUERA:
                continue
            dentro += 1
            jornadas = [
                j for j in dom.jornadas_de(self.app.conexion, trabajador.id)
                if j.abierta
            ]
            desde = (
                db.a_local(jornadas[-1].inicio).strftime("%H:%M") if jornadas else "—"
            )
            self.tabla_presentes.anadir(
                [
                    trabajador.nombre,
                    "Trabajando" if estado == dom.DENTRO else "En pausa",
                    desde,
                    formatear_horas(int(resumen["minutos_trabajados"])),
                ],
                etiqueta="exito" if estado == dom.DENTRO else "aviso",
            )
        if dentro == 0:
            self.tabla_presentes.anadir(
                ["Nadie con jornada abierta", "", "", ""], etiqueta="apagado"
            )

        alertas = normativa.diagnostico(
            self.app.conexion, trabajadores, self.app.ajustes
        )
        conteo = normativa.resumen_gravedad(alertas)

        self._tarjeta_dato(
            "Plantilla activa", str(len(trabajadores)), "info",
            f"{len(trabajadores) - dentro} sin fichar",
        )
        self._tarjeta_dato(
            "Fichados ahora", str(dentro), "exito",
            "en jornada" if dentro else "nadie en jornada",
        )
        self._tarjeta_dato(
            "Horas de hoy", formatear_horas(minutos_hoy), "info",
            "jornadas abiertas incluidas" if dentro else "cerrado",
        )
        total_avisos = conteo[normativa.GRAVE] + conteo[normativa.AVISO]
        self._tarjeta_dato(
            "Avisos", str(total_avisos),
            "error" if conteo[normativa.GRAVE] else
            ("aviso" if conteo[normativa.AVISO] else "exito"),
            f"{conteo[normativa.GRAVE]} grave(s)" if conteo[normativa.GRAVE]
            else ("revisar" if total_avisos else "todo en orden"),
        )

        self.tabla_alertas.limpiar()
        for alerta in alertas:
            self.tabla_alertas.anadir(
                [alerta.gravedad.capitalize(), alerta.mensaje, alerta.referencia],
                etiqueta={"grave": "grave", "aviso": "aviso"}.get(alerta.gravedad, ""),
            )
        if not alertas:
            self.tabla_alertas.anadir(
                ["", "Sin avisos. Todo en orden.", ""], etiqueta="exito"
            )

    def _tarjeta_dato(
        self, etiqueta: str, valor: str, tono: str, nota: str = ""
    ) -> None:
        tarjeta = Tarjeta(self.tarjetas, self.tema, relleno=14)
        tarjeta.pack(side="left", fill="both", expand=True, padx=(0, 10))
        ttk.Label(tarjeta.cuerpo, text=etiqueta, style="Suave.TLabel").pack(anchor="w")
        ttk.Label(tarjeta.cuerpo, text=valor, style="Dato.TLabel").pack(
            anchor="w", pady=(4, 0)
        )
        if nota:
            Pastilla(tarjeta.cuerpo, self.tema, nota, tono).pack(
                anchor="w", pady=(8, 0)
            )


# --------------------------------------------------------------------------- #
# 3. Equipo
# --------------------------------------------------------------------------- #

class VistaEquipo(Vista):
    titulo = "Equipo"
    subtitulo = "Altas, bajas y PIN de fichaje"
    requiere_admin = True

    def construir(self) -> None:
        cabecera = self.cabecera()
        botones = ttk.Frame(cabecera)
        botones.pack(side="right")
        ttk.Button(
            botones, text="Nuevo trabajador", style="Primario.TButton",
            command=self.alta,
        ).pack(side="left")

        tarjeta = Tarjeta(self, self.tema)
        tarjeta.pack(fill="both", expand=True)

        filtros = ttk.Frame(tarjeta.cuerpo, style="Superficie.TFrame")
        filtros.pack(fill="x", pady=(0, 10))
        self.ver_bajas = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            filtros, text="Mostrar también las bajas", variable=self.ver_bajas,
            command=self.refrescar,
        ).pack(side="left")

        self.tabla = Tabla(
            tarjeta.cuerpo, self.tema,
            [("codigo", "Código", 70), ("nombre", "Nombre", 200),
             ("dni", "DNI", 95), ("rol", "Rol", 100),
             ("jornada", "Jornada/sem.", 90), ("pin", "PIN", 70),
             ("estado", "Estado", 80)],
            altura=15,
        )
        self.tabla.pack(fill="both", expand=True)
        self.tabla.arbol.bind("<Double-1>", lambda _e: self.modificar())

        acciones = ttk.Frame(tarjeta.cuerpo, style="Superficie.TFrame")
        acciones.pack(fill="x", pady=(12, 0))
        for texto, orden in (
            ("Modificar", self.modificar),
            ("Asignar PIN", self.asignar_pin),
            ("Fichaje manual", self.fichaje_manual),
            ("Entregar su registro", self.entregar_registro),
        ):
            ttk.Button(acciones, text=texto, command=orden).pack(
                side="left", padx=(0, 8)
            )
        ttk.Button(
            acciones, text="Dar de baja", style="Peligro.TButton", command=self.baja
        ).pack(side="right")

    def refrescar(self) -> None:
        self.tabla.limpiar()
        for trabajador in self.app.trabajadores(incluir_bajas=self.ver_bajas.get()):
            self.tabla.anadir(
                [
                    trabajador.codigo,
                    trabajador.nombre,
                    trabajador.dni or "—",
                    trabajador.rol.capitalize(),
                    f"{trabajador.jornada_semanal:g} h"
                    if trabajador.jornada_semanal
                    else f"{self.app.ajustes.horas_semanales:g} h (general)",
                    "Sí" if trabajador.tiene_pin else "SIN PIN",
                    "Activo" if trabajador.activo else "Baja",
                ],
                etiqueta=(
                    "apagado" if not trabajador.activo
                    else ("grave" if not trabajador.tiene_pin else "")
                ),
                iid=str(trabajador.id),
            )

    def _seleccionado(self) -> dom.Trabajador | None:
        iid = self.tabla.seleccionado()
        if not iid:
            self.app.aviso("Selecciona antes un trabajador de la lista.", "aviso")
            return None
        return dom.obtener_trabajador(self.app.conexion, self.app.cifrador, int(iid))

    def alta(self) -> None:
        datos = DialogoTrabajador(self, self.tema).mostrar()
        if not datos:
            return
        try:
            trabajador = dom.alta_trabajador(
                self.app.conexion, self.app.cifrador, autor=self.app.actor(), **datos
            )
        except ErrorDominio as exc:
            messagebox.showerror("No se ha podido dar de alta", str(exc), parent=self)
            return
        messagebox.showinfo(
            "Trabajador dado de alta",
            f"{trabajador.nombre}\n\n"
            f"Código: {trabajador.codigo}\n"
            f"PIN: {datos['pin']}\n\n"
            "Entrégale estos datos: los necesita para fichar. "
            "El PIN no se puede volver a consultar, sólo cambiar.",
            parent=self,
        )
        self.app.refrescar_todo()

    def modificar(self) -> None:
        trabajador = self._seleccionado()
        if not trabajador:
            return
        datos = DialogoTrabajador(self, self.tema, trabajador).mostrar()
        if not datos:
            return
        try:
            dom.modificar_trabajador(
                self.app.conexion, self.app.cifrador, trabajador.id,
                autor=self.app.actor(), **datos
            )
        except ErrorDominio as exc:
            messagebox.showerror("No se ha podido modificar", str(exc), parent=self)
            return
        self.app.aviso("Datos actualizados.", "exito")
        self.app.refrescar_todo()

    def asignar_pin(self) -> None:
        trabajador = self._seleccionado()
        if not trabajador:
            return
        pin = DialogoPin(self, self.tema, trabajador.nombre).mostrar()
        if not pin:
            return
        dom.cambiar_pin(
            self.app.conexion, trabajador.id, pin, autor=self.app.actor()
        )
        messagebox.showinfo(
            "PIN asignado",
            f"El PIN de {trabajador.nombre} ({trabajador.codigo}) es {pin}.\n\n"
            "Entrégaselo ahora: no podrás volver a verlo.",
            parent=self,
        )
        self.app.refrescar_todo()

    def fichaje_manual(self) -> None:
        trabajador = self._seleccionado()
        if not trabajador:
            return
        datos = DialogoFichajeManual(self, self.tema, trabajador.nombre).mostrar()
        if not datos:
            return
        try:
            dom.fichar(
                self.app.conexion, trabajador.id, datos["tipo"],
                momento=datos["momento"], modalidad=datos["modalidad"],
                nota=datos["nota"], autor=self.app.actor(), origen="MANUAL",
            )
        except ErrorDominio as exc:
            messagebox.showerror("No se ha podido registrar", str(exc), parent=self)
            return
        self.app.aviso("Fichaje manual registrado.", "exito")
        self.app.refrescar_todo()

    def entregar_registro(self) -> None:
        trabajador = self._seleccionado()
        if not trabajador:
            return
        periodo = DialogoPeriodo(self, self.tema).mostrar()
        if not periodo:
            return
        ruta = informes.exportar_trabajador(
            self.app.conexion, self.app.ajustes, trabajador, *periodo
        )
        self.app.aviso(f"Registro guardado en {ruta}", "info", 7000)
        _abrir(ruta)

    def baja(self) -> None:
        trabajador = self._seleccionado()
        if not trabajador:
            return
        if not messagebox.askyesno(
            "Dar de baja",
            f"¿Dar de baja a {trabajador.nombre}?\n\n"
            "Sus fichajes se conservan: la ley obliga a guardarlos cuatro años. "
            "Sólo dejará de aparecer en el listado y no podrá fichar.",
            parent=self,
        ):
            return
        try:
            dom.baja_trabajador(
                self.app.conexion, self.app.cifrador, trabajador.id,
                autor=self.app.actor(),
            )
        except ErrorDominio as exc:
            messagebox.showerror("No se ha podido dar de baja", str(exc), parent=self)
            return
        self.app.aviso("Trabajador dado de baja.", "exito")
        self.app.refrescar_todo()


# --------------------------------------------------------------------------- #
# 4. Registros
# --------------------------------------------------------------------------- #

class VistaRegistros(Vista):
    titulo = "Registros"
    subtitulo = "Jornadas registradas y rectificaciones"
    requiere_admin = True

    def construir(self) -> None:
        self.cabecera()

        tarjeta = Tarjeta(self, self.tema)
        tarjeta.pack(fill="both", expand=True)

        filtros = ttk.Frame(tarjeta.cuerpo, style="Superficie.TFrame")
        filtros.pack(fill="x", pady=(0, 12))
        ttk.Label(filtros, text="Trabajador:", style="Suave.TLabel").pack(side="left")
        self.selector = ttk.Combobox(filtros, state="readonly", width=32)
        self.selector.pack(side="left", padx=(8, 16))
        self.selector.bind("<<ComboboxSelected>>", lambda _e: self.refrescar_tabla())

        ttk.Label(filtros, text="Días:", style="Suave.TLabel").pack(side="left")
        self.dias = ttk.Combobox(
            filtros, state="readonly", width=8, values=["7", "30", "90", "365", "Todo"]
        )
        self.dias.set("30")
        self.dias.pack(side="left", padx=(8, 16))
        self.dias.bind("<<ComboboxSelected>>", lambda _e: self.refrescar_tabla())

        self.ver_fichajes = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            filtros, text="Ver fichajes sueltos", variable=self.ver_fichajes,
            command=self.refrescar_tabla,
        ).pack(side="left")

        self.resumen = ttk.Label(filtros, text="", style="Suave.TLabel")
        self.resumen.pack(side="right")

        self.tabla = Tabla(
            tarjeta.cuerpo, self.tema,
            [("fecha", "Fecha", 90), ("entrada", "Entrada", 80),
             ("salida", "Salida", 80), ("pausa", "Pausa", 70),
             ("trabajado", "Trabajado", 90), ("modalidad", "Modalidad", 95),
             ("obs", "Observaciones", 200)],
            altura=15,
        )
        self.tabla.pack(fill="both", expand=True)

        acciones = ttk.Frame(tarjeta.cuerpo, style="Superficie.TFrame")
        acciones.pack(fill="x", pady=(12, 0))
        ttk.Button(
            acciones, text="Rectificar el fichaje seleccionado",
            style="Primario.TButton", command=self.rectificar,
        ).pack(side="left")
        ttk.Label(
            acciones,
            text="Marca «Ver fichajes sueltos» para rectificar una hora concreta.",
            style="Suave.TLabel",
        ).pack(side="left", padx=(12, 0))

    def refrescar(self) -> None:
        trabajadores = self.app.trabajadores(incluir_bajas=True)
        self._por_etiqueta = {t.etiqueta: t for t in trabajadores}
        self.selector["values"] = list(self._por_etiqueta)
        if trabajadores and self.selector.get() not in self._por_etiqueta:
            self.selector.set(trabajadores[0].etiqueta)
        self.refrescar_tabla()

    def _trabajador(self) -> dom.Trabajador | None:
        return self._por_etiqueta.get(self.selector.get())

    def _rango(self) -> tuple[dt.datetime | None, dt.datetime]:
        hasta = dt.datetime.now().astimezone() + dt.timedelta(days=1)
        if self.dias.get() == "Todo":
            return None, hasta
        return hasta - dt.timedelta(days=int(self.dias.get())), hasta

    def refrescar_tabla(self) -> None:
        self.tabla.limpiar()
        trabajador = self._trabajador()
        if trabajador is None:
            self.resumen.configure(text="")
            return
        desde, hasta = self._rango()

        if self.ver_fichajes.get():
            self._pintar_fichajes(trabajador, desde, hasta)
        else:
            self._pintar_jornadas(trabajador, desde, hasta)

    def _pintar_jornadas(self, trabajador, desde, hasta) -> None:
        jornadas = dom.jornadas_de(
            self.app.conexion, trabajador.id, desde=desde, hasta=hasta
        )
        total = 0
        for jornada in jornadas:
            inicio = db.a_local(jornada.inicio)
            fin = db.a_local(jornada.fin) if jornada.fin else None
            trabajado = jornada.minutos_trabajados(
                self.app.ajustes.pausas_computan_como_trabajo
            )
            total += trabajado
            observaciones = []
            if jornada.incidencia:
                observaciones.append("incidencia")
            if jornada.rectificada:
                observaciones.append("rectificada")
            if jornada.abierta:
                observaciones.append("sin fichaje de salida")
            self.tabla.anadir(
                [
                    inicio.strftime("%d/%m/%Y"),
                    inicio.strftime("%H:%M"),
                    fin.strftime("%H:%M") if fin else "—",
                    f"{jornada.minutos_pausa} min",
                    formatear_horas(trabajado),
                    jornada.modalidad.capitalize(),
                    ", ".join(observaciones),
                ],
                etiqueta="aviso" if jornada.abierta or jornada.incidencia else "",
            )
        self.resumen.configure(
            text=f"{len(jornadas)} jornada(s) · {formatear_horas(total)} en total"
        )

    def _pintar_fichajes(self, trabajador, desde, hasta) -> None:
        eventos = dom.eventos_efectivos(
            self.app.conexion, trabajador_id=trabajador.id, desde=desde, hasta=hasta
        )
        for evento in eventos:
            momento = db.a_local(evento.momento)
            observaciones = []
            if evento.rectificado and evento.momento_original:
                observaciones.append(
                    f"rectificado (antes {db.a_local(evento.momento_original):%d/%m %H:%M})"
                )
            if evento.motivo:
                observaciones.append(evento.motivo)
            if evento.origen != "TERMINAL":
                observaciones.append(evento.origen.lower())
            self.tabla.anadir(
                [
                    momento.strftime("%d/%m/%Y"),
                    momento.strftime("%H:%M:%S"),
                    dom.nombre_tipo(evento.tipo).capitalize(),
                    "",
                    "",
                    evento.modalidad.capitalize(),
                    " · ".join(observaciones),
                ],
                etiqueta="aviso" if evento.rectificado else "",
                iid=str(evento.id),
            )
        self.resumen.configure(text=f"{len(eventos)} fichaje(s)")

    def rectificar(self) -> None:
        if not self.ver_fichajes.get():
            self.app.aviso(
                "Marca «Ver fichajes sueltos» y elige la hora que quieres corregir.",
                "aviso",
            )
            return
        iid = self.tabla.seleccionado()
        if not iid:
            self.app.aviso("Selecciona el fichaje que quieres rectificar.", "aviso")
            return
        evento_id = int(iid)
        fila = self.app.conexion.execute(
            "SELECT * FROM eventos WHERE id = ?", (evento_id,)
        ).fetchone()
        momento = db.a_local(db.desde_iso(fila["ts_utc"]))
        descripcion = (
            f"{dom.nombre_tipo(fila['tipo']).capitalize()} del "
            f"{momento:%d/%m/%Y} a las {momento:%H:%M:%S}"
        )
        datos = DialogoRectificar(self, self.tema, descripcion, momento).mostrar()
        if not datos:
            return
        try:
            dom.rectificar(
                self.app.conexion, evento_id,
                momento_nuevo=datos["momento"], motivo=datos["motivo"],
                autor=self.app.actor(), anular=datos["anular"],
            )
        except ErrorDominio as exc:
            messagebox.showerror("No se ha podido rectificar", str(exc), parent=self)
            return
        self.app.aviso("Rectificación registrada con su motivo y autor.", "exito")
        self.app.refrescar_todo()


# --------------------------------------------------------------------------- #
# 5. Informes
# --------------------------------------------------------------------------- #

class VistaInformes(Vista):
    titulo = "Informes"
    subtitulo = "Puesta a disposición del registro (art. 34.9 ET)"
    requiere_admin = True

    def construir(self) -> None:
        self.cabecera()

        opciones = [
            (
                "Informe de empresa (Excel)",
                "Resumen por trabajador, jornadas, fichajes, avisos de "
                "cumplimiento y verificación de integridad.",
                "Primario.TButton",
                self.excel,
            ),
            (
                "Listado de jornadas (CSV)",
                "Formato abierto, separado por punto y coma, para abrir en "
                "cualquier hoja de cálculo o importar en la gestoría.",
                "TButton",
                self.csv,
            ),
            (
                "Expediente para Inspección de Trabajo (JSON)",
                "Volcado íntegro y verificable: fichajes originales, "
                "rectificaciones con su motivo, auditoría y cadena de hashes.",
                "TButton",
                self.itss,
            ),
        ]
        for titulo, descripcion, estilo, orden in opciones:
            tarjeta = Tarjeta(self, self.tema)
            tarjeta.pack(fill="x", pady=(0, 12))
            fila = ttk.Frame(tarjeta.cuerpo, style="Superficie.TFrame")
            fila.pack(fill="x")
            texto = ttk.Frame(fila, style="Superficie.TFrame")
            texto.pack(side="left", fill="x", expand=True)
            ttk.Label(texto, text=titulo, style="Seccion.TLabel").pack(anchor="w")
            ttk.Label(
                texto, text=descripcion, style="Suave.TLabel",
                wraplength=int(560 * self.tema.escala), justify="left",
            ).pack(anchor="w", pady=(4, 0))
            ttk.Button(fila, text="Generar", style=estilo, command=orden).pack(
                side="right", padx=(16, 0)
            )

        nota = Tarjeta(self, self.tema)
        nota.pack(fill="x")
        ttk.Label(
            nota.cuerpo,
            text=(
                "El registro debe estar a disposición de las personas "
                "trabajadoras, de sus representantes legales y de la Inspección "
                "de Trabajo, y conservarse cuatro años. Los informes se guardan "
                "en el Escritorio."
            ),
            style="Suave.TLabel",
            wraplength=int(700 * self.tema.escala), justify="left",
        ).pack(anchor="w")

    def _periodo_y_gente(self):
        periodo = DialogoPeriodo(self, self.tema).mostrar()
        if not periodo:
            return None, None
        return periodo, self.app.trabajadores(incluir_bajas=True)

    def excel(self) -> None:
        periodo, gente = self._periodo_y_gente()
        if not periodo:
            return
        try:
            ruta = informes.exportar_excel(
                self.app.conexion, self.app.cifrador, self.app.ajustes,
                gente, *periodo,
            )
        except informes.ErrorInforme as exc:
            messagebox.showerror("No se ha podido exportar", str(exc), parent=self)
            return
        self._hecho(ruta)

    def csv(self) -> None:
        periodo, gente = self._periodo_y_gente()
        if not periodo:
            return
        self._hecho(
            informes.exportar_csv(
                self.app.conexion, self.app.ajustes, gente, *periodo
            )
        )

    def itss(self) -> None:
        periodo, gente = self._periodo_y_gente()
        if not periodo:
            return
        self._hecho(
            informes.expediente_itss(
                self.app.conexion, self.app.ajustes, gente, *periodo
            )
        )

    def _hecho(self, ruta) -> None:
        self.app.aviso(f"Informe generado: {ruta.name}", "exito", 6000)
        if messagebox.askyesno(
            "Informe generado",
            f"Guardado en:\n{ruta}\n\n¿Quieres abrirlo?",
            parent=self,
        ):
            _abrir(ruta)


# --------------------------------------------------------------------------- #
# 6. Ajustes
# --------------------------------------------------------------------------- #

class VistaAjustes(Vista):
    titulo = "Ajustes"
    subtitulo = "Empresa, límites de jornada, seguridad y mantenimiento"
    requiere_admin = True

    def construir(self) -> None:
        self.cabecera()

        lienzo = tk.Canvas(
            self, bg=self.tema.paleta.fondo, highlightthickness=0, bd=0
        )
        barra = ttk.Scrollbar(self, orient="vertical", command=lienzo.yview)
        self.interior = ttk.Frame(lienzo)
        self.interior.bind(
            "<Configure>",
            lambda _e: lienzo.configure(scrollregion=lienzo.bbox("all")),
        )
        ventana = lienzo.create_window((0, 0), window=self.interior, anchor="nw")
        lienzo.bind(
            "<Configure>", lambda e: lienzo.itemconfigure(ventana, width=e.width)
        )
        lienzo.configure(yscrollcommand=barra.set)
        lienzo.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")

        self._empresa()
        self._limites()
        self._arranque()
        self._historico()
        self._seguridad()
        self._mantenimiento()

    # -- secciones ---------------------------------------------------------- #
    def _empresa(self) -> None:
        tarjeta = Tarjeta(self.interior, self.tema)
        tarjeta.pack(fill="x", pady=(0, 12))
        tarjeta.titulo(
            "Datos de la empresa",
            "Aparecen en los informes que se entregan a la Inspección.",
        )
        aj = self.app.ajustes
        marco, self.empresa = campo(
            tarjeta.cuerpo, "Razón social", ancho=44, valor=aj.empresa
        )
        marco.pack(fill="x", pady=(12, 8))
        marco, self.cif = campo(tarjeta.cuerpo, "CIF / NIF", ancho=44, valor=aj.cif)
        marco.pack(fill="x", pady=(0, 8))
        marco, self.centro = campo(
            tarjeta.cuerpo, "Centro de trabajo", ancho=44, valor=aj.centro_trabajo
        )
        marco.pack(fill="x", pady=(0, 12))
        ttk.Button(
            tarjeta.cuerpo, text="Guardar datos de empresa",
            style="Primario.TButton", command=self.guardar_empresa,
        ).pack(anchor="w")

    def _limites(self) -> None:
        tarjeta = Tarjeta(self.interior, self.tema)
        tarjeta.pack(fill="x", pady=(0, 12))
        tarjeta.titulo(
            "Límites de jornada",
            "Valores por defecto del Estatuto de los Trabajadores. "
            "Ajústalos a tu convenio colectivo si mejora estos mínimos.",
        )
        aj = self.app.ajustes
        rejilla = ttk.Frame(tarjeta.cuerpo, style="Superficie.TFrame")
        rejilla.pack(fill="x", pady=(12, 12))

        self.campos_limite: dict[str, ttk.Entry] = {}
        definicion = [
            ("horas_semanales", "Jornada semanal (h)", f"{aj.horas_semanales:g}"),
            ("horas_diarias_ordinarias", "Jornada diaria ordinaria (h)",
             f"{aj.horas_diarias_ordinarias:g}"),
            ("descanso_entre_jornadas_horas", "Descanso entre jornadas (h)",
             f"{aj.descanso_entre_jornadas_horas:g}"),
            ("descanso_semanal_horas", "Descanso semanal (h)",
             f"{aj.descanso_semanal_horas:g}"),
            ("pausa_minima_minutos", "Pausa mínima (min)",
             str(aj.pausa_minima_minutos)),
            ("umbral_pausa_horas", "A partir de (h continuadas)",
             f"{aj.umbral_pausa_horas:g}"),
            ("horas_extra_anuales", "Tope de horas extra al año",
             str(aj.horas_extra_anuales)),
            ("anios_conservacion", "Años de conservación",
             str(aj.anios_conservacion)),
        ]
        for indice, (clave, etiqueta, valor) in enumerate(definicion):
            fila, columna = divmod(indice, 2)
            celda = ttk.Frame(rejilla, style="Superficie.TFrame")
            celda.grid(row=fila, column=columna, sticky="ew", padx=(0, 16), pady=5)
            rejilla.columnconfigure(columna, weight=1)
            ttk.Label(celda, text=etiqueta, style="Suave.TLabel").pack(anchor="w")
            entrada = ttk.Entry(celda, width=12)
            entrada.insert(0, valor)
            entrada.pack(anchor="w", pady=(3, 0))
            self.campos_limite[clave] = entrada

        self.pausas_computan = tk.BooleanVar(value=aj.pausas_computan_como_trabajo)
        ttk.Checkbutton(
            tarjeta.cuerpo,
            text="Las pausas cuentan como tiempo de trabajo efectivo "
                 "(según convenio)",
            variable=self.pausas_computan,
        ).pack(anchor="w", pady=(0, 12))
        ttk.Button(
            tarjeta.cuerpo, text="Guardar límites", style="Primario.TButton",
            command=self.guardar_limites,
        ).pack(anchor="w")

        ttk.Label(
            tarjeta.cuerpo,
            text=(
                "Nota: la jornada semanal legal sigue siendo de 40 horas. La "
                "reducción a 37,5 horas no está en vigor; si tu convenio ya la "
                "aplica, cámbiala aquí."
            ),
            style="Suave.TLabel",
            wraplength=int(640 * self.tema.escala), justify="left",
        ).pack(anchor="w", pady=(12, 0))

    def _arranque(self) -> None:
        tarjeta = Tarjeta(self.interior, self.tema)
        tarjeta.pack(fill="x", pady=(0, 12))
        tarjeta.titulo(
            "Arranque",
            "Para el ordenador que hace de terminal de fichaje.",
        )

        self.arranca_solo = tk.BooleanVar(value=arranque.esta_activado())
        ttk.Checkbutton(
            tarjeta.cuerpo,
            text="Iniciar Control Horario al encender el equipo",
            variable=self.arranca_solo,
            command=self.cambiar_arranque,
        ).pack(anchor="w", pady=(12, 0))
        ttk.Label(
            tarjeta.cuerpo,
            text=(
                f"Se configura en {arranque.descripcion_ubicacion()}, sólo para "
                "este usuario. No hace falta ser administrador y se puede "
                "quitar desde aquí mismo."
            ),
            style="Suave.TLabel",
            wraplength=int(640 * self.tema.escala), justify="left",
        ).pack(anchor="w", padx=(24, 0), pady=(2, 10))

        self.terminal = tk.BooleanVar(value=self.app.ajustes.modo_terminal)
        ttk.Checkbutton(
            tarjeta.cuerpo,
            text="Abrir maximizado en la pantalla de Fichar",
            variable=self.terminal,
            command=self.cambiar_terminal,
        ).pack(anchor="w")
        ttk.Label(
            tarjeta.cuerpo,
            text=(
                "Recomendado si el equipo es de uso compartido: al arrancar "
                "queda listo para que la plantilla fiche."
            ),
            style="Suave.TLabel",
            wraplength=int(640 * self.tema.escala), justify="left",
        ).pack(anchor="w", padx=(24, 0), pady=(2, 0))

    def _historico(self) -> None:
        tarjeta = Tarjeta(self.interior, self.tema)
        tarjeta.pack(fill="x", pady=(0, 12))
        tarjeta.titulo(
            "Histórico de la versión anterior",
            "Importación de la base de datos de 2024.",
        )

        pendientes = migracion.pendiente_de_importar(self.app.conexion)
        if pendientes:
            texto = (
                f"Quedan {pendientes} registro(s) por traer de la base de datos "
                "antigua."
            )
            tono = "aviso"
        elif migracion.hay_datos_antiguos():
            texto = "El histórico antiguo ya está importado por completo."
            tono = "exito"
        else:
            texto = "No se ha encontrado ninguna base de datos anterior."
            tono = "neutro"
        Pastilla(tarjeta.cuerpo, self.tema, texto, tono).pack(
            anchor="w", pady=(12, 10)
        )

        fila = ttk.Frame(tarjeta.cuerpo, style="Superficie.TFrame")
        fila.pack(fill="x")
        ttk.Button(
            fila, text="Importar histórico",
            style="Primario.TButton" if pendientes else "TButton",
            command=self.importar_historico,
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            fila, text="Buscar otra base de datos...",
            command=self.importar_de_otro_sitio,
        ).pack(side="left")

        ttk.Label(
            tarjeta.cuerpo,
            text=(
                "Se puede repetir sin miedo: sólo trae lo que aún no estuviera, "
                "nunca duplica fichajes y no modifica el fichero antiguo, del "
                "que además se guarda una copia."
            ),
            style="Suave.TLabel",
            wraplength=int(640 * self.tema.escala), justify="left",
        ).pack(anchor="w", pady=(10, 0))

    def _seguridad(self) -> None:
        tarjeta = Tarjeta(self.interior, self.tema)
        tarjeta.pack(fill="x", pady=(0, 12))
        tarjeta.titulo("Seguridad")
        fila = ttk.Frame(tarjeta.cuerpo, style="Superficie.TFrame")
        fila.pack(fill="x", pady=(12, 0))
        ttk.Button(
            fila, text="Cambiar la contraseña de administración",
            command=self.cambiar_clave,
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            fila, text="Verificar la integridad del registro",
            command=self.verificar,
        ).pack(side="left")
        ttk.Label(
            tarjeta.cuerpo,
            text=(
                "Los nombres y DNI se guardan cifrados. La clave de cifrado "
                f"está en {directorio_datos() / 'clave.key'} — inclúyela en tus "
                "copias de seguridad o los datos personales serán ilegibles."
            ),
            style="Suave.TLabel",
            wraplength=int(640 * self.tema.escala), justify="left",
        ).pack(anchor="w", pady=(12, 0))

    def _mantenimiento(self) -> None:
        tarjeta = Tarjeta(self.interior, self.tema)
        tarjeta.pack(fill="x", pady=(0, 12))
        tarjeta.titulo("Mantenimiento")
        fila = ttk.Frame(tarjeta.cuerpo, style="Superficie.TFrame")
        fila.pack(fill="x", pady=(12, 0))
        ttk.Button(fila, text="Hacer copia de seguridad", command=self.copia).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(fila, text="Abrir la carpeta de datos", command=self.abrir_datos).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(
            fila, text="Purgar registros caducados", style="Peligro.TButton",
            command=self.purgar,
        ).pack(side="right")

        self.aviso_tema = ttk.Frame(tarjeta.cuerpo, style="Superficie.TFrame")
        self.aviso_tema.pack(fill="x", pady=(12, 0))
        ttk.Label(
            self.aviso_tema,
            text=(
                "La purga borra definitivamente los fichajes que ya han "
                "superado el plazo de conservación. Antes de purgar, exporta "
                "un expediente por si acaso."
            ),
            style="Suave.TLabel",
            wraplength=int(640 * self.tema.escala), justify="left",
        ).pack(anchor="w")

    # -- acciones ------------------------------------------------------------ #
    def guardar_empresa(self) -> None:
        self.app.ajustes.empresa = self.empresa.get().strip()
        self.app.ajustes.cif = self.cif.get().strip()
        self.app.ajustes.centro_trabajo = self.centro.get().strip()
        self.app.ajustes.guardar()
        db.registrar_auditoria(
            self.app.conexion, actor=self.app.actor(),
            accion="AJUSTES_EMPRESA", detalle=self.app.ajustes.empresa,
        )
        self.app.aviso("Datos de la empresa guardados.", "exito")
        self.app.refrescar_todo()

    def guardar_limites(self) -> None:
        enteros = {"pausa_minima_minutos", "horas_extra_anuales", "anios_conservacion"}
        nuevos: dict[str, float | int] = {}
        for clave, entrada in self.campos_limite.items():
            texto = entrada.get().strip().replace(",", ".")
            try:
                valor = int(float(texto)) if clave in enteros else float(texto)
            except ValueError:
                messagebox.showerror(
                    "Valor no válido",
                    f"«{texto}» no es un número válido.", parent=self,
                )
                return
            if valor <= 0:
                messagebox.showerror(
                    "Valor no válido", "Los límites deben ser mayores que cero.",
                    parent=self,
                )
                return
            nuevos[clave] = valor

        if nuevos["anios_conservacion"] < 4:
            if not messagebox.askyesno(
                "Por debajo del mínimo legal",
                "El artículo 34.9 del Estatuto de los Trabajadores obliga a "
                "conservar los registros cuatro años.\n\n"
                f"Has puesto {nuevos['anios_conservacion']}. ¿Seguro?",
                parent=self,
            ):
                return

        for clave, valor in nuevos.items():
            setattr(self.app.ajustes, clave, valor)
        self.app.ajustes.pausas_computan_como_trabajo = bool(
            self.pausas_computan.get()
        )
        self.app.ajustes.guardar()
        db.registrar_auditoria(
            self.app.conexion, actor=self.app.actor(), accion="AJUSTES_LIMITES",
            detalle=", ".join(f"{k}={v}" for k, v in nuevos.items()),
        )
        self.app.aviso("Límites guardados.", "exito")
        self.app.refrescar_todo()

    def cambiar_arranque(self) -> None:
        quiere = bool(self.arranca_solo.get())
        try:
            if quiere:
                destino = arranque.activar()
                self.app.aviso(f"El programa se abrirá solo. ({destino.name})", "exito")
            else:
                arranque.desactivar()
                self.app.aviso("El programa ya no se abrirá solo.", "info")
        except (arranque.ErrorArranque, OSError) as exc:
            self.arranca_solo.set(not quiere)
            messagebox.showerror(
                "No se ha podido cambiar el arranque",
                f"{exc}\n\nPuedes hacerlo a mano desde "
                f"{arranque.descripcion_ubicacion()}.",
                parent=self,
            )
            return
        db.registrar_auditoria(
            self.app.conexion, actor=self.app.actor(),
            accion="ARRANQUE_AUTOMATICO",
            detalle="activado" if quiere else "desactivado",
        )

    def cambiar_terminal(self) -> None:
        self.app.ajustes.modo_terminal = bool(self.terminal.get())
        self.app.ajustes.guardar()
        self.app.aviso(
            "Se aplicará al abrir el programa la próxima vez.", "info"
        )

    def importar_historico(self, ruta=None) -> None:
        if ruta is None and not migracion.hay_datos_antiguos():
            messagebox.showinfo(
                "Nada que importar",
                "No se ha encontrado la base de datos de la versión anterior "
                f"en {directorio_datos()}.\n\n"
                "Si la tienes en otro sitio, usa «Buscar otra base de datos».",
                parent=self,
            )
            return
        try:
            resultado = migracion.importar(
                self.app.conexion, self.app.cifrador, ruta,
                actor=self.app.actor(),
            )
        except Exception as exc:  # noqa: BLE001 - se muestra tal cual al usuario
            messagebox.showerror(
                "No se ha podido importar",
                f"{exc}\n\nLa base de datos antigua no se ha modificado.",
                parent=self,
            )
            return

        detalle = resultado.resumen()
        if resultado.trabajadores:
            detalle += (
                "\n\nLos trabajadores importados no tienen PIN todavía. "
                "Asígnales uno en «Equipo» para que puedan fichar."
            )
        if resultado.omitidos:
            detalle += "\n\nOmitidos:\n" + "\n".join(
                f"  · {o}" for o in resultado.omitidos[:8]
            )
        if resultado.respaldo:
            detalle += f"\n\nCopia del fichero original: {resultado.respaldo}"
        messagebox.showinfo("Importación del histórico", detalle, parent=self)
        self.app.refrescar_todo()
        self.app.navegar("ajustes")

    def importar_de_otro_sitio(self) -> None:
        elegido = filedialog.askopenfilename(
            parent=self,
            title="Elige la base de datos de la versión anterior",
            filetypes=[("Base de datos SQLite", "*.db"), ("Todos", "*.*")],
        )
        if not elegido:
            return
        ruta = Path(elegido)
        if not migracion.hay_datos_antiguos(ruta):
            messagebox.showerror(
                "No es una base de datos válida",
                f"{ruta.name} no parece la base de datos del Control Horario "
                "de 2024: no se encuentran las tablas «users» y «records».",
                parent=self,
            )
            return
        self.importar_historico(ruta)

    def cambiar_clave(self) -> None:
        datos = DialogoCambiarClave(self, self.tema).mostrar()
        if not datos:
            return
        actual, nueva = datos
        almacenada = db.leer_config(self.app.conexion, "clave_admin")
        if not verificar_secreto(actual, almacenada):
            messagebox.showerror(
                "Contraseña incorrecta", "La contraseña actual no es correcta.",
                parent=self,
            )
            return
        db.guardar_config(self.app.conexion, "clave_admin", hash_secreto(nueva))
        db.registrar_auditoria(
            self.app.conexion, actor=self.app.actor(), accion="CAMBIO_CLAVE_ADMIN"
        )
        self.app.aviso("Contraseña cambiada.", "exito")

    def verificar(self) -> None:
        informe = db.verificar_integridad(self.app.conexion)
        if informe["integro"]:
            messagebox.showinfo(
                "Registro íntegro",
                f"Comprobados {informe['eventos']['filas']} fichajes y "
                f"{informe['auditoria']['filas']} registros de auditoría.\n\n"
                "La cadena de integridad es correcta: ningún dato se ha "
                "alterado fuera de la aplicación.\n\n"
                f"Hash final: {informe['eventos']['hash_final'][:32]}…",
                parent=self,
            )
        else:
            incidencias = (
                informe["eventos"]["incidencias"] + informe["auditoria"]["incidencias"]
            )
            detalle = "\n".join(
                f"• Registro {i['id']}: {i['detalle']}" for i in incidencias[:10]
            )
            messagebox.showerror(
                "Integridad comprometida",
                f"Se han detectado {len(incidencias)} incidencia(s):\n\n{detalle}\n\n"
                "La base de datos se ha modificado fuera de la aplicación. "
                "Restaura la copia de seguridad más reciente.",
                parent=self,
            )

    def copia(self) -> None:
        ruta = db.copia_seguridad(self.app.conexion, actor=self.app.actor())
        self.app.aviso(f"Copia creada: {ruta.name}", "exito", 6000)

    def abrir_datos(self) -> None:
        _abrir(directorio_datos())

    def purgar(self) -> None:
        anios = self.app.ajustes.anios_conservacion
        if not messagebox.askyesno(
            "Purgar registros caducados",
            f"Se borrarán los fichajes con más de {anios} años, que ya han "
            "cumplido el plazo legal de conservación.\n\n"
            "Es irreversible. ¿Continuar?",
            parent=self,
        ):
            return
        borrados = db.purgar_caducados(
            self.app.conexion, anios, actor=self.app.actor()
        )
        if borrados:
            self.app.aviso(f"Purgados {borrados} fichajes caducados.", "exito", 6000)
        else:
            self.app.aviso("No había ningún fichaje caducado.", "info")
        self.app.refrescar_todo()


# --------------------------------------------------------------------------- #

def _abrir(ruta) -> None:
    """Abre un fichero o carpeta con la aplicación por defecto del sistema."""
    import os
    import subprocess
    import sys

    try:
        if sys.platform.startswith("win"):
            os.startfile(str(ruta))  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(ruta)])
        else:
            subprocess.Popen(["xdg-open", str(ruta)])
    except Exception:
        webbrowser.open(f"file://{ruta}")


VISTAS = [
    ("fichar", "Fichar", VistaFichar),
    ("panel", "Panel", VistaPanel),
    ("equipo", "Equipo", VistaEquipo),
    ("registros", "Registros", VistaRegistros),
    ("informes", "Informes", VistaInformes),
    ("ajustes", "Ajustes", VistaAjustes),
]

__all__ = ["VISTAS", "Vista"]
