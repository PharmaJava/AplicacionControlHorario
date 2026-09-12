"""Tema visual: paleta, tipografía y estilos ttk.

La versión de 2024 usaba azules pastel sobre gris y tipografía Arial a tamaño
fijo, que en una pantalla moderna se ve pequeño y borroso.  Aquí hay:

* paleta clara y oscura con contraste suficiente (WCAG AA sobre el fondo),
* tipografía nativa de cada sistema (Segoe UI Variable, SF Pro, Inter…),
* escalado por densidad de píxeles, para que no se vea diminuto en pantallas
  4K ni gigante en un portátil antiguo.
"""

from __future__ import annotations

import sys
import tkinter as tk
from dataclasses import dataclass
from tkinter import font as tkfont
from tkinter import ttk


@dataclass(frozen=True)
class Paleta:
    nombre: str
    fondo: str
    superficie: str
    superficie_alt: str
    borde: str
    texto: str
    texto_suave: str
    primario: str
    primario_activo: str
    primario_texto: str
    exito: str
    exito_suave: str
    aviso: str
    aviso_suave: str
    error: str
    error_suave: str
    seleccion: str


CLARO = Paleta(
    nombre="claro",
    fondo="#F1F5F9",
    superficie="#FFFFFF",
    superficie_alt="#F8FAFC",
    borde="#D7DEE8",
    texto="#0F172A",
    texto_suave="#5B6B82",
    primario="#2563EB",
    primario_activo="#1D4ED8",
    primario_texto="#FFFFFF",
    exito="#15803D",
    exito_suave="#DCFCE7",
    aviso="#B45309",
    aviso_suave="#FEF3C7",
    error="#B91C1C",
    error_suave="#FEE2E2",
    seleccion="#DBEAFE",
)

OSCURO = Paleta(
    nombre="oscuro",
    fondo="#0B1220",
    superficie="#151E2E",
    superficie_alt="#1B2739",
    borde="#2C3A50",
    texto="#E8EEF7",
    texto_suave="#96A5BB",
    primario="#3B82F6",
    primario_activo="#60A5FA",
    primario_texto="#0B1220",
    exito="#4ADE80",
    exito_suave="#14321F",
    aviso="#FBBF24",
    aviso_suave="#3A2C0A",
    error="#F87171",
    error_suave="#3B1517",
    seleccion="#1E3A5F",
)

PALETAS = {"claro": CLARO, "oscuro": OSCURO}


def _familia_disponible(raiz: tk.Misc, *candidatas: str) -> str:
    disponibles = {f.lower() for f in tkfont.families(raiz)}
    for candidata in candidatas:
        if candidata.lower() in disponibles:
            return candidata
    return "TkDefaultFont"


def familia_interfaz(raiz: tk.Misc) -> str:
    if sys.platform.startswith("win"):
        return _familia_disponible(
            raiz, "Segoe UI Variable Text", "Segoe UI", "Inter", "Calibri"
        )
    if sys.platform == "darwin":
        return _familia_disponible(raiz, "SF Pro Text", "Helvetica Neue", "Inter")
    return _familia_disponible(
        raiz, "Inter", "Ubuntu", "Cantarell", "Noto Sans", "DejaVu Sans"
    )


def familia_monoespaciada(raiz: tk.Misc) -> str:
    return _familia_disponible(
        raiz, "Cascadia Mono", "Consolas", "SF Mono", "JetBrains Mono",
        "DejaVu Sans Mono", "Courier New",
    )


def activar_nitidez() -> None:
    """Evita que Windows escale la ventana por nosotros y la vea borrosa."""
    if not sys.platform.startswith("win"):
        return
    try:  # pragma: no cover - específico de Windows
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:  # Windows anterior a 8.1
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def escala(raiz: tk.Misc) -> float:
    """Factor de escala según la densidad real de la pantalla."""
    try:
        puntos_por_pulgada = raiz.winfo_fpixels("1i")
    except tk.TclError:
        return 1.0
    return max(1.0, min(round(puntos_por_pulgada / 96.0, 2), 2.0))


class Tema:
    """Aplica una paleta a toda la ventana y expone las fuentes."""

    def __init__(self, raiz: tk.Tk, modo: str = "claro") -> None:
        self.raiz = raiz
        self.paleta = PALETAS.get(modo, CLARO)
        self.escala = escala(raiz)
        self.familia = familia_interfaz(raiz)
        self.mono = familia_monoespaciada(raiz)
        self.estilo = ttk.Style(raiz)
        self._crear_fuentes()
        self.aplicar(modo)

    # -- fuentes ------------------------------------------------------------ #
    def _px(self, puntos: int) -> int:
        return max(8, int(round(puntos * self.escala)))

    def _crear_fuentes(self) -> None:
        self.f_normal = tkfont.Font(family=self.familia, size=self._px(10))
        self.f_pequena = tkfont.Font(family=self.familia, size=self._px(9))
        self.f_micro = tkfont.Font(family=self.familia, size=self._px(8))
        self.f_media = tkfont.Font(family=self.familia, size=self._px(11))
        self.f_negrita = tkfont.Font(
            family=self.familia, size=self._px(10), weight="bold"
        )
        self.f_titulo = tkfont.Font(
            family=self.familia, size=self._px(15), weight="bold"
        )
        self.f_seccion = tkfont.Font(
            family=self.familia, size=self._px(12), weight="bold"
        )
        self.f_reloj = tkfont.Font(
            family=self.familia, size=self._px(38), weight="bold"
        )
        self.f_mono = tkfont.Font(family=self.mono, size=self._px(9))

    # -- estilos ------------------------------------------------------------ #
    def aplicar(self, modo: str) -> None:
        self.paleta = PALETAS.get(modo, CLARO)
        p = self.paleta
        estilo = self.estilo
        estilo.theme_use("clam")

        self.raiz.configure(bg=p.fondo)

        estilo.configure(".", background=p.fondo, foreground=p.texto,
                         font=self.f_normal, borderwidth=0, focuscolor=p.primario)
        estilo.configure("TFrame", background=p.fondo)
        estilo.configure("Superficie.TFrame", background=p.superficie)
        estilo.configure("Lateral.TFrame", background=p.superficie)
        estilo.configure("Alt.TFrame", background=p.superficie_alt)

        estilo.configure("TLabel", background=p.fondo, foreground=p.texto)
        estilo.configure("Superficie.TLabel", background=p.superficie,
                         foreground=p.texto)
        estilo.configure("Suave.TLabel", background=p.superficie,
                         foreground=p.texto_suave, font=self.f_pequena)
        estilo.configure("SuaveFondo.TLabel", background=p.fondo,
                         foreground=p.texto_suave, font=self.f_pequena)
        estilo.configure("Titulo.TLabel", background=p.fondo, foreground=p.texto,
                         font=self.f_titulo)
        estilo.configure("Seccion.TLabel", background=p.superficie,
                         foreground=p.texto, font=self.f_seccion)
        estilo.configure("Reloj.TLabel", background=p.superficie,
                         foreground=p.texto, font=self.f_reloj)
        estilo.configure("Dato.TLabel", background=p.superficie,
                         foreground=p.primario, font=self.f_titulo)

        # Botones
        estilo.configure(
            "TButton", background=p.superficie_alt, foreground=p.texto,
            font=self.f_normal, padding=(self._px(12), self._px(8)),
            borderwidth=1, relief="flat",
        )
        estilo.map(
            "TButton",
            background=[("pressed", p.borde), ("active", p.seleccion),
                        ("disabled", p.superficie_alt)],
            foreground=[("disabled", p.texto_suave)],
            bordercolor=[("!disabled", p.borde)],
        )
        estilo.configure(
            "Primario.TButton", background=p.primario, foreground=p.primario_texto,
            font=self.f_negrita, padding=(self._px(14), self._px(9)), borderwidth=0,
        )
        estilo.map(
            "Primario.TButton",
            background=[("pressed", p.primario_activo), ("active", p.primario_activo),
                        ("disabled", p.borde)],
            foreground=[("disabled", p.texto_suave)],
        )
        estilo.configure(
            "Exito.TButton", background=p.exito, foreground="#FFFFFF",
            font=self.f_negrita, padding=(self._px(14), self._px(11)), borderwidth=0,
        )
        estilo.map("Exito.TButton",
                   background=[("active", p.exito), ("disabled", p.borde)],
                   foreground=[("disabled", p.texto_suave)])
        estilo.configure(
            "Peligro.TButton", background=p.error, foreground="#FFFFFF",
            font=self.f_negrita, padding=(self._px(14), self._px(11)), borderwidth=0,
        )
        estilo.map("Peligro.TButton",
                   background=[("active", p.error), ("disabled", p.borde)],
                   foreground=[("disabled", p.texto_suave)])
        estilo.configure(
            "Aviso.TButton", background=p.aviso, foreground="#FFFFFF",
            font=self.f_negrita, padding=(self._px(14), self._px(11)), borderwidth=0,
        )
        estilo.map("Aviso.TButton",
                   background=[("active", p.aviso), ("disabled", p.borde)],
                   foreground=[("disabled", p.texto_suave)])

        # Navegación lateral
        estilo.configure(
            "Nav.TButton", background=p.superficie, foreground=p.texto_suave,
            font=self.f_normal, anchor="w", borderwidth=0,
            padding=(self._px(16), self._px(11)),
        )
        estilo.map("Nav.TButton",
                   background=[("active", p.superficie_alt)],
                   foreground=[("active", p.texto)])
        estilo.configure(
            "NavActivo.TButton", background=p.seleccion, foreground=p.primario,
            font=self.f_negrita, anchor="w", borderwidth=0,
            padding=(self._px(16), self._px(11)),
        )
        estilo.map("NavActivo.TButton", background=[("active", p.seleccion)])

        # Campos
        estilo.configure(
            "TEntry", fieldbackground=p.superficie, foreground=p.texto,
            bordercolor=p.borde, lightcolor=p.borde, darkcolor=p.borde,
            insertcolor=p.texto, padding=self._px(7), borderwidth=1,
        )
        estilo.map("TEntry", bordercolor=[("focus", p.primario)])
        estilo.configure(
            "TCombobox", fieldbackground=p.superficie, background=p.superficie,
            foreground=p.texto, arrowcolor=p.texto_suave, bordercolor=p.borde,
            padding=self._px(6),
        )
        estilo.map("TCombobox", fieldbackground=[("readonly", p.superficie)])
        estilo.configure("TCheckbutton", background=p.superficie,
                         foreground=p.texto, focuscolor=p.superficie)
        estilo.map("TCheckbutton", background=[("active", p.superficie)])

        # Tabla
        estilo.configure(
            "Treeview", background=p.superficie, fieldbackground=p.superficie,
            foreground=p.texto, borderwidth=0, rowheight=self._px(26),
            font=self.f_normal,
        )
        estilo.configure(
            "Treeview.Heading", background=p.superficie_alt, foreground=p.texto_suave,
            font=self.f_pequena, relief="flat", padding=self._px(7),
        )
        estilo.map("Treeview.Heading", background=[("active", p.borde)])
        estilo.map("Treeview",
                   background=[("selected", p.seleccion)],
                   foreground=[("selected", p.texto)])

        # Barras de desplazamiento planas: las de 'clam' por defecto tienen
        # relieve y flechas grandes que delatan la edad del kit gráfico.
        for orientacion in ("Vertical", "Horizontal"):
            estilo.configure(
                f"{orientacion}.TScrollbar",
                background=p.borde, troughcolor=p.superficie_alt,
                bordercolor=p.superficie_alt, darkcolor=p.borde,
                lightcolor=p.borde, arrowcolor=p.texto_suave,
                relief="flat", borderwidth=0, arrowsize=self._px(11),
            )
            estilo.map(
                f"{orientacion}.TScrollbar",
                background=[("active", p.texto_suave), ("pressed", p.texto_suave)],
            )

        estilo.configure("TSeparator", background=p.borde)
        estilo.configure("TNotebook", background=p.fondo, borderwidth=0)
        estilo.configure("TNotebook.Tab", background=p.superficie_alt,
                         foreground=p.texto_suave,
                         padding=(self._px(14), self._px(8)))
        estilo.map("TNotebook.Tab",
                   background=[("selected", p.superficie)],
                   foreground=[("selected", p.primario)])
        estilo.configure("Barra.Horizontal.TProgressbar", background=p.primario,
                         troughcolor=p.superficie_alt, borderwidth=0)

        # Diálogos nativos (messagebox) coherentes con el tema
        self.raiz.option_add("*Dialog.msg.font", self.f_normal)

    def alternar(self) -> str:
        nuevo = "oscuro" if self.paleta.nombre == "claro" else "claro"
        self.aplicar(nuevo)
        return nuevo


__all__ = ["CLARO", "OSCURO", "PALETAS", "Paleta", "Tema", "activar_nitidez"]
