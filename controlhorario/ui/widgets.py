"""Componentes reutilizables de la interfaz."""

from __future__ import annotations

import datetime as dt
import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from .tema import Tema


class Tarjeta(tk.Frame):
    """Panel con superficie propia y borde de un píxel."""

    def __init__(self, padre: tk.Misc, tema: Tema, **kwargs) -> None:
        relleno = kwargs.pop("relleno", 16)
        super().__init__(
            padre,
            bg=tema.paleta.superficie,
            highlightbackground=tema.paleta.borde,
            highlightcolor=tema.paleta.borde,
            highlightthickness=1,
            bd=0,
            **kwargs,
        )
        self.tema = tema
        self.cuerpo = tk.Frame(self, bg=tema.paleta.superficie)
        self.cuerpo.pack(fill="both", expand=True, padx=relleno, pady=relleno)

    def titulo(self, texto: str, subtitulo: str = "") -> None:
        ttk.Label(self.cuerpo, text=texto, style="Seccion.TLabel").pack(anchor="w")
        if subtitulo:
            ttk.Label(self.cuerpo, text=subtitulo, style="Suave.TLabel").pack(
                anchor="w", pady=(2, 0)
            )


class Pastilla(tk.Label):
    """Etiqueta de estado con color de fondo (dentro, en pausa, fuera…)."""

    def __init__(
        self, padre: tk.Misc, tema: Tema, texto: str = "", tono: str = "neutro"
    ) -> None:
        super().__init__(
            padre, text=texto, bd=0, padx=10, pady=3, font=tema.f_pequena
        )
        self.tema = tema
        self.tono(tono, texto)

    def tono(self, tono: str, texto: str | None = None) -> None:
        p = self.tema.paleta
        colores = {
            "exito": (p.exito_suave, p.exito),
            "aviso": (p.aviso_suave, p.aviso),
            "error": (p.error_suave, p.error),
            "info": (p.seleccion, p.primario),
            "neutro": (p.superficie_alt, p.texto_suave),
        }
        fondo, frente = colores.get(tono, colores["neutro"])
        self.configure(bg=fondo, fg=frente)
        if texto is not None:
            self.configure(text=texto)


class _Periodico(ttk.Label):
    """Etiqueta que se repinta sola cada cierto tiempo y para al destruirse.

    El latido se cancela solo cuando el widget desaparece.  Antes seguía
    encolándose después de cerrar la ventana y Tk terminaba quejándose de un
    comando que ya no existía.
    """

    _intervalo = 1000

    def __init__(self, padre: tk.Misc, estilo: str) -> None:
        super().__init__(padre, style=estilo)
        self._activo = True
        self._tarea: str | None = None
        self.bind("<Destroy>", lambda _e: self.detener(), add="+")
        self._latido()

    def texto(self) -> str:  # pragma: no cover - lo definen las subclases
        raise NotImplementedError

    def detener(self) -> None:
        self._activo = False
        if self._tarea is not None:
            try:
                self.after_cancel(self._tarea)
            except (ValueError, tk.TclError):
                pass
            self._tarea = None

    def _latido(self) -> None:
        if not self._activo:
            return
        try:
            self.configure(text=self.texto())
            self._tarea = self.after(self._intervalo, self._latido)
        except tk.TclError:  # la ventana ya no está
            self.detener()


class Reloj(_Periodico):
    """Hora local en grande, actualizada cada segundo."""

    _intervalo = 1000

    def __init__(self, padre: tk.Misc, tema: Tema) -> None:
        super().__init__(padre, "Reloj.TLabel")

    def texto(self) -> str:
        return dt.datetime.now().strftime("%H:%M:%S")


class Fecha(_Periodico):
    """Fecha larga en español, sin depender del locale del sistema."""

    _intervalo = 60_000

    _DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
    _MESES = (
        "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
        "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    )

    def __init__(self, padre: tk.Misc, estilo: str = "Suave.TLabel") -> None:
        super().__init__(padre, estilo)

    @classmethod
    def texto_de(cls, momento: dt.date) -> str:
        return (
            f"{cls._DIAS[momento.weekday()]}, {momento.day} "
            f"de {cls._MESES[momento.month - 1]} de {momento.year}"
        )

    def texto(self) -> str:
        return self.texto_de(dt.date.today()).capitalize()


class Aviso(tk.Frame):
    """Mensaje efímero en la esquina inferior; sustituye a los messagebox
    encadenados de la versión anterior para las confirmaciones rutinarias."""

    def __init__(self, raiz: tk.Tk, tema: Tema) -> None:
        super().__init__(raiz, bd=0, highlightthickness=1)
        self.raiz = raiz
        self.tema = tema
        self.etiqueta = tk.Label(
            self, font=tema.f_normal, justify="left", wraplength=380, padx=16, pady=12
        )
        self.etiqueta.pack(fill="both", expand=True)
        self._tarea: str | None = None

    def mostrar(self, texto: str, tono: str = "exito", milisegundos: int = 4000) -> None:
        p = self.tema.paleta
        colores = {
            "exito": (p.exito_suave, p.exito),
            "aviso": (p.aviso_suave, p.aviso),
            "error": (p.error_suave, p.error),
            "info": (p.seleccion, p.primario),
        }
        fondo, frente = colores.get(tono, colores["info"])
        self.configure(bg=fondo, highlightbackground=frente, highlightcolor=frente)
        self.etiqueta.configure(bg=fondo, fg=frente, text=texto)
        self.place(relx=0.99, rely=0.98, anchor="se")
        self.lift()
        if self._tarea:
            self.after_cancel(self._tarea)
        self._tarea = self.after(milisegundos, self.ocultar)

    def ocultar(self) -> None:
        self._tarea = None
        self.place_forget()


class Tabla(ttk.Frame):
    """Treeview con barra de desplazamiento y filas alternas."""

    def __init__(
        self,
        padre: tk.Misc,
        tema: Tema,
        columnas: list[tuple[str, str, int]],
        *,
        altura: int = 14,
        seleccion: str = "browse",
    ) -> None:
        super().__init__(padre)
        self.tema = tema
        claves = [c[0] for c in columnas]
        self.arbol = ttk.Treeview(
            self, columns=claves, show="headings", height=altura,
            selectmode=seleccion,
        )
        for clave, titulo, ancho in columnas:
            self.arbol.heading(clave, text=titulo)
            self.arbol.column(
                clave, width=int(ancho * tema.escala), anchor="w", stretch=True
            )
        barra = ttk.Scrollbar(self, orient="vertical", command=self.arbol.yview)
        self.arbol.configure(yscrollcommand=barra.set)
        self.arbol.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        self._configurar_etiquetas()

    def _configurar_etiquetas(self) -> None:
        p = self.tema.paleta
        self.arbol.tag_configure("par", background=p.superficie)
        self.arbol.tag_configure("impar", background=p.superficie_alt)
        self.arbol.tag_configure("grave", background=p.error_suave, foreground=p.error)
        self.arbol.tag_configure("aviso", background=p.aviso_suave, foreground=p.aviso)
        self.arbol.tag_configure("exito", background=p.exito_suave, foreground=p.exito)
        self.arbol.tag_configure("apagado", foreground=p.texto_suave)

    def limpiar(self) -> None:
        self.arbol.delete(*self.arbol.get_children())

    def anadir(self, valores: list, etiqueta: str = "", iid: str | None = None) -> str:
        indice = len(self.arbol.get_children())
        etiquetas = (etiqueta,) if etiqueta else ("par" if indice % 2 == 0 else "impar",)
        return self.arbol.insert("", "end", iid=iid, values=valores, tags=etiquetas)

    def seleccionado(self) -> str | None:
        seleccion = self.arbol.selection()
        return seleccion[0] if seleccion else None


def campo(
    padre: tk.Misc,
    etiqueta: str,
    *,
    ancho: int = 28,
    mostrar: str | None = None,
    valor: str = "",
) -> tuple[ttk.Frame, ttk.Entry]:
    """Etiqueta encima del campo: patrón habitual en formularios actuales."""
    marco = ttk.Frame(padre, style="Superficie.TFrame")
    ttk.Label(marco, text=etiqueta, style="Suave.TLabel").pack(anchor="w")
    entrada = ttk.Entry(marco, width=ancho, show=mostrar)
    entrada.pack(fill="x", pady=(3, 0))
    if valor:
        entrada.insert(0, valor)
    return marco, entrada


def separador(padre: tk.Misc, tema: Tema, pady: int = 12) -> tk.Frame:
    linea = tk.Frame(padre, height=1, bg=tema.paleta.borde)
    linea.pack(fill="x", pady=pady)
    return linea


def centrar(ventana: tk.Misc, ancho: int, alto: int) -> None:
    ventana.update_idletasks()
    pantalla_ancho = ventana.winfo_screenwidth()
    pantalla_alto = ventana.winfo_screenheight()
    x = max(0, (pantalla_ancho - ancho) // 2)
    y = max(0, (pantalla_alto - alto) // 3)
    ventana.geometry(f"{ancho}x{alto}+{x}+{y}")


__all__ = [
    "Aviso", "Fecha", "Pastilla", "Reloj", "Tabla", "Tarjeta",
    "campo", "centrar", "separador",
]


class CampoAutocompletado(ttk.Frame):
    """Campo de texto que sugiere mientras se escribe.

    Pensado para el código de trabajador en el terminal: se puede teclear el
    código, parte del nombre, o desplegar la lista con la flecha abajo y elegir
    con el ratón. Lo que queda en el campo es siempre el código, que es lo que
    espera la autenticación.
    """

    ALTURA_MAXIMA = 6

    def __init__(
        self,
        padre: tk.Misc,
        tema: Tema,
        *,
        ancho: int = 22,
        al_elegir: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(padre, style="Superficie.TFrame")
        self.tema = tema
        self._al_elegir = al_elegir
        self._opciones: list[tuple[str, str]] = []   # (valor, etiqueta)
        self._filtradas: list[tuple[str, str]] = []

        self.entrada = ttk.Entry(self, width=ancho)
        self.entrada.pack(fill="x")

        p = tema.paleta
        self._lista = tk.Listbox(
            self.winfo_toplevel(), height=0, activestyle="none",
            bg=p.superficie, fg=p.texto, selectbackground=p.seleccion,
            selectforeground=p.texto, font=tema.f_normal,
            highlightthickness=1, highlightbackground=p.primario,
            borderwidth=0, exportselection=False,
        )
        self._visible = False

        self.entrada.bind("<KeyRelease>", self._al_teclear)
        self.entrada.bind("<Down>", self._bajar)
        self.entrada.bind("<Up>", self._subir)
        self.entrada.bind("<Return>", self._confirmar)
        self.entrada.bind("<Escape>", lambda _e: self._ocultar())
        self.entrada.bind("<FocusOut>", self._quizas_ocultar)
        # La lista cuelga de la ventana, no del campo, para poder dibujarse por
        # encima de todo; a cambio hay que recogerla a mano cuando el campo
        # deja de verse, o se quedaría flotando sobre la pantalla siguiente.
        self.bind("<Destroy>", lambda _e: self._lista.destroy(), add="+")
        self._lista.bind("<ButtonRelease-1>", self._confirmar)
        self._lista.bind("<Return>", self._confirmar)

    # -- API ---------------------------------------------------------------- #
    def opciones(self, opciones: list[tuple[str, str]]) -> None:
        self._opciones = list(opciones)

    def get(self) -> str:
        return self.entrada.get().strip()

    def set(self, texto: str) -> None:
        self.entrada.delete(0, "end")
        self.entrada.insert(0, texto)

    def limpiar(self) -> None:
        self._ocultar()
        self.entrada.delete(0, "end")

    def ocultar_sugerencias(self) -> None:
        """Recoge la lista desplegada, si la hay."""
        self._ocultar()

    def focus_set(self) -> None:  # noqa: A003 - nombre heredado de tkinter
        self.entrada.focus_set()

    # -- interno ------------------------------------------------------------ #
    def _coincidencias(self, texto: str) -> list[tuple[str, str]]:
        texto = texto.strip().casefold()
        if not texto:
            return list(self._opciones)
        # Primero lo que empieza por lo tecleado, luego lo que lo contiene:
        # teclear «E01» debe ofrecer E010 antes que «Marcelo».
        empiezan = [o for o in self._opciones if o[1].casefold().startswith(texto)]
        contienen = [
            o for o in self._opciones
            if texto in o[1].casefold() and o not in empiezan
        ]
        return empiezan + contienen

    def _al_teclear(self, evento) -> None:
        if evento.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            return
        self._mostrar(self._coincidencias(self.entrada.get()))

    def _mostrar(self, coincidencias: list[tuple[str, str]]) -> None:
        self._filtradas = coincidencias
        if not coincidencias:
            self._ocultar()
            return

        self._lista.delete(0, "end")
        for _, etiqueta in coincidencias[: self.ALTURA_MAXIMA]:
            self._lista.insert("end", etiqueta)
        self._lista.configure(height=min(len(coincidencias), self.ALTURA_MAXIMA))

        self.update_idletasks()
        x = self.entrada.winfo_rootx() - self.winfo_toplevel().winfo_rootx()
        y = (self.entrada.winfo_rooty() - self.winfo_toplevel().winfo_rooty()
             + self.entrada.winfo_height())
        self._lista.place(x=x, y=y, width=self.entrada.winfo_width())
        self._lista.lift()
        self._visible = True
        self.after(200, self._vigilar_visibilidad)

    def _vigilar_visibilidad(self) -> None:
        """Recoge la lista si el campo ha dejado de estar a la vista."""
        if not self._visible:
            return
        try:
            visible = self.winfo_ismapped()
        except tk.TclError:  # pragma: no cover - la ventana ya no está
            return
        if not visible:
            self._ocultar()
            return
        self.after(200, self._vigilar_visibilidad)

    def _ocultar(self) -> None:
        if self._visible:
            self._lista.place_forget()
            self._visible = False

    def _quizas_ocultar(self, _evento) -> None:
        # Sin retardo, el clic sobre la lista llega después de ocultarla y no
        # se llega a elegir nada.
        self.after(150, self._ocultar)

    def _bajar(self, _evento) -> str:
        if not self._visible:
            self._mostrar(self._coincidencias(self.entrada.get()))
            return "break"
        self._mover(1)
        return "break"

    def _subir(self, _evento) -> str:
        self._mover(-1)
        return "break"

    def _mover(self, paso: int) -> None:
        if not self._visible or not self._lista.size():
            return
        actual = self._lista.curselection()
        indice = (actual[0] + paso) if actual else (0 if paso > 0 else 0)
        indice = max(0, min(indice, self._lista.size() - 1))
        self._lista.selection_clear(0, "end")
        self._lista.selection_set(indice)
        self._lista.see(indice)

    def _confirmar(self, _evento=None) -> str:
        seleccion = self._lista.curselection() if self._visible else ()
        if seleccion:
            valor = self._filtradas[seleccion[0]][0]
        elif self._visible and len(self._filtradas) == 1:
            # Una sola coincidencia: se da por elegida sin tener que bajar.
            valor = self._filtradas[0][0]
        else:
            self._ocultar()
            if self._al_elegir:
                self._al_elegir()
            return "break"

        self.set(valor)
        self._ocultar()
        if self._al_elegir:
            self._al_elegir()
        return "break"


__all__ += ["CampoAutocompletado"]
