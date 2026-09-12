"""Componentes reutilizables de la interfaz."""

from __future__ import annotations

import datetime as dt
import tkinter as tk
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


class Reloj(ttk.Label):
    """Hora local en grande, actualizada cada segundo."""

    def __init__(self, padre: tk.Misc, tema: Tema) -> None:
        super().__init__(padre, style="Reloj.TLabel")
        self._activo = True
        self._latido()

    def _latido(self) -> None:
        if not self._activo:
            return
        self.configure(text=dt.datetime.now().strftime("%H:%M:%S"))
        self.after(1000, self._latido)

    def detener(self) -> None:
        self._activo = False


class Fecha(ttk.Label):
    """Fecha larga en español, sin depender del locale del sistema."""

    _DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
    _MESES = (
        "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
        "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    )

    def __init__(self, padre: tk.Misc, estilo: str = "Suave.TLabel") -> None:
        super().__init__(padre, style=estilo)
        self._refrescar()

    @classmethod
    def texto_de(cls, momento: dt.date) -> str:
        return (
            f"{cls._DIAS[momento.weekday()]}, {momento.day} "
            f"de {cls._MESES[momento.month - 1]} de {momento.year}"
        )

    def _refrescar(self) -> None:
        self.configure(text=self.texto_de(dt.date.today()).capitalize())
        self.after(60_000, self._refrescar)


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
