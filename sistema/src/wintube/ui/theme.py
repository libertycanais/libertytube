"""
ui/theme.py
------------------------------------------------------------
    O visual do LibertyTube num lugar só: cores, fontes, espaçamentos e raios.

Nenhuma tela escreve "#FFFFFF" na mão — todas pedem `t.cor("card")` ou
`t.fonte("titulo")`. Assim dá pra mudar o app inteiro (e o modo claro)
alterando este arquivo.

Modo claro e escuro compartilham os mesmos acentos; só o fundo, as
bordas e o texto mudam — é o que mantém a identidade nos dois modos.
"""

import sys
import tkinter as tk
from tkinter import ttk

from ..core import settings

# ── Paletas ──────────────────────────────────────────────────────────
ESCURO = {
    "fundo": "#0B0E14",
    "sidebar": "#0F131B",
    "card": "#151A24",
    "card_hover": "#1B2233",
    "elevado": "#1E2534",
    "input": "#121722",
    "console": "#080A0F",
    "borda": "#242C3C",
    "borda_suave": "#1B2230",
    "texto": "#E9EEF9",
    "texto2": "#98A2B8",
    "muted": "#5C6579",
    "sombra": "#070910",
}

CLARO = {
    "fundo": "#F4F6FC",
    "sidebar": "#FFFFFF",
    "card": "#FFFFFF",
    "card_hover": "#EDF1FA",
    "elevado": "#FFFFFF",
    "input": "#EFF3FA",
    "console": "#12151D",     # console fica escuro nos dois (legibilidade)
    "borda": "#DCE3F0",
    "borda_suave": "#E7ECF5",
    "texto": "#141A28",
    "texto2": "#4E5769",
    "muted": "#8C96AA",
    "sombra": "#D9DFEC",
}

# acentos iguais nos dois temas
ACENTOS = {
    "primario": "#6C5CE7",
    "primario_hover": "#8577FF",
    "primario_suave": "#2A2350",
    "sucesso": "#22C55E",
    "sucesso_hover": "#4ADE80",
    "aviso": "#F59E0B",
    "aviso_hover": "#FBBF24",
    "perigo": "#EF4444",
    "perigo_hover": "#F87171",
    "info": "#38BDF8",
    "rosa": "#EC4899",
    "whatsapp": "#25D366",
    "whatsapp_hover": "#1EBE5D",
    "branco": "#FFFFFF",
}

# cor de cada etapa do fluxo (a bolinha do menu e o topo das telas)
ETAPAS = {
    1: "#38BDF8",
    2: "#8B7BFF",
    3: "#F59E0B",
    4: "#22C55E",
    5: "#EC4899",
}

# ── Espaçamento e raio ───────────────────────────────────────────────
ESPACO = {"xs": 4, "sm": 8, "md": 14, "lg": 22, "xl": 32}
RAIO = {"sm": 6, "md": 10, "lg": 16, "pill": 999}


class Tema:
    """Instância única compartilhada por todas as telas."""

    def __init__(self):
        self.modo = settings.get("tema", "escuro")
        self._ouvintes = []
        self.familia = self._familia_padrao()
        self.mono = self._familia_mono()

    # ── fontes ──
    @staticmethod
    def _familia_padrao():
        if sys.platform == "win32":
            return "Segoe UI"
        if sys.platform == "darwin":
            return "SF Pro Text"
        return "DejaVu Sans"

    @staticmethod
    def _familia_mono():
        if sys.platform == "win32":
            return "Consolas"
        if sys.platform == "darwin":
            return "Menlo"
        return "DejaVu Sans Mono"

    ESCALA = {
        "display": (23, "bold"),
        "titulo": (17, "bold"),
        "subtitulo": (13, "bold"),
        "corpo_forte": (11, "bold"),
        "corpo": (11, "normal"),
        "pequeno": (9, "normal"),
        "pequeno_forte": (9, "bold"),
        "micro": (8, "normal"),
    }

    def fonte(self, nome="corpo", tamanho=None, peso=None):
        base_tamanho, base_peso = self.ESCALA.get(nome, self.ESCALA["corpo"])
        return (self.familia, tamanho or base_tamanho, peso or base_peso)

    def fonte_mono(self, tamanho=10):
        return (self.mono, tamanho)

    # ── cores ──
    @property
    def paleta(self):
        return CLARO if self.modo == "claro" else ESCURO

    def cor(self, nome):
        if nome in ACENTOS:
            return ACENTOS[nome]
        return self.paleta.get(nome, ACENTOS.get(nome, "#FF00FF"))

    def etapa(self, numero):
        return ETAPAS.get(numero, ACENTOS["primario"])

    @property
    def escuro(self):
        return self.modo != "claro"

    # ── troca de tema ──
    def alternar(self):
        return self.definir("claro" if self.escuro else "escuro")

    def definir(self, modo):
        self.modo = "claro" if modo == "claro" else "escuro"
        settings.set("tema", self.modo)
        for ouvinte in list(self._ouvintes):
            try:
                ouvinte()
            except Exception:
                pass
        return self.modo

    def ao_mudar(self, funcao):
        self._ouvintes.append(funcao)

    def limpar_ouvintes(self):
        self._ouvintes = []

    # ── estilos do ttk (scrollbar, barra de progresso, combobox) ──
    def aplicar_ttk(self, root):
        estilo = ttk.Style(root)
        try:
            estilo.theme_use("clam")
        except Exception:
            pass

        estilo.configure(
            "WT.Vertical.TScrollbar",
            background=self.cor("borda"), troughcolor=self.cor("fundo"),
            bordercolor=self.cor("fundo"), arrowcolor=self.cor("texto2"),
            darkcolor=self.cor("borda"), lightcolor=self.cor("borda"),
            relief="flat", borderwidth=0, arrowsize=12, width=10)
        estilo.map("WT.Vertical.TScrollbar",
                   background=[("active", self.cor("primario"))])

        estilo.configure(
            "WT.Horizontal.TProgressbar",
            background=self.cor("primario"), troughcolor=self.cor("borda_suave"),
            bordercolor=self.cor("borda_suave"), lightcolor=self.cor("primario"),
            darkcolor=self.cor("primario"), thickness=6, borderwidth=0)

        estilo.configure(
            "Sucesso.Horizontal.TProgressbar",
            background=self.cor("sucesso"), troughcolor=self.cor("borda_suave"),
            bordercolor=self.cor("borda_suave"), lightcolor=self.cor("sucesso"),
            darkcolor=self.cor("sucesso"), thickness=6, borderwidth=0)

        estilo.configure(
            "WT.TCombobox",
            fieldbackground=self.cor("input"), background=self.cor("input"),
            foreground=self.cor("texto"), arrowcolor=self.cor("texto2"),
            bordercolor=self.cor("borda"), lightcolor=self.cor("borda"),
            darkcolor=self.cor("borda"), selectbackground=self.cor("primario"),
            selectforeground="#FFFFFF", padding=6)
        root.option_add("*TCombobox*Listbox.background", self.cor("card"))
        root.option_add("*TCombobox*Listbox.foreground", self.cor("texto"))
        root.option_add("*TCombobox*Listbox.selectBackground", self.cor("primario"))
        root.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")


# instância usada pelo app inteiro
tema = Tema()


def mesclar(cor_a, cor_b, proporcao=0.5):
    """Mistura duas cores hex — usado em hovers e estados desativados."""
    def partes(c):
        c = c.lstrip("#")
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))

    ra, ga, ba = partes(cor_a)
    rb, gb, bb = partes(cor_b)
    m = lambda x, y: int(x + (y - x) * proporcao)  # noqa: E731
    return f"#{m(ra, rb):02x}{m(ga, gb):02x}{m(ba, bb):02x}"


def clarear(cor, quanto=0.15):
    return mesclar(cor, "#FFFFFF", quanto)


def escurecer(cor, quanto=0.15):
    return mesclar(cor, "#000000", quanto)
