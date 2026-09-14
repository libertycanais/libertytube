"""
ui/widgets.py
------------------------------------------------------------
Os componentes visuais do LibertyTube.

Tudo aqui é Tkinter puro — nada pra instalar — mas com cantos
arredondados de verdade (desenhados em Canvas), estados de hover,
foco e carregamento. É o que dá a cara nova do app sem depender de
biblioteca externa.

Componentes:
    Botao       botão arredondado com variantes e estado "carregando"
    Campo       input com rótulo, placeholder de verdade, olho e Caps Lock
    Chave       interruptor liga/desliga (a "chavinha" de aplicativo)
    Cartao      caixa com borda, título e descrição
    Cabecalho   título da página com subtítulo e ações à direita
    Chip        etiqueta arredondada
    Banner      aviso colorido com botão de ação
    Seletor     grupo de opções em pílulas (formato, cor da legenda…)
    Rolagem     área rolável com barra fina
    BarraSuave  barra de progresso desenhada (com modo "indeterminado")
    PainelProgresso  faixa grande de progresso com % , tempo e ETA
    Console     painel de log com barra de progresso
    Divisor / Espaco / Toast
"""

import time
import tkinter as tk
from tkinter import font as tkfont

from .theme import ESPACO, RAIO, mesclar, tema


# ── Desenho ──────────────────────────────────────────────────────────
def retangulo_arredondado(canvas, x0, y0, x1, y1, raio=10, **kwargs):
    """Retângulo com cantos arredondados dentro de um Canvas."""
    raio = max(0, min(raio, int((x1 - x0) / 2), int((y1 - y0) / 2)))
    pontos = [
        x0 + raio, y0, x1 - raio, y0, x1, y0, x1, y0 + raio,
        x1, y1 - raio, x1, y1, x1 - raio, y1, x0 + raio, y1,
        x0, y1, x0, y1 - raio, x0, y0 + raio, x0, y0,
    ]
    return canvas.create_polygon(pontos, smooth=True, **kwargs)


def _bg_do(widget):
    try:
        return widget.cget("bg")
    except Exception:
        return tema.cor("fundo")


def degrade(canvas, cor_a, cor_b, faixas=60, horizontal=False):
    """Pinta um degradê no Canvas inteiro (usado no painel da tela de
    entrar e no topo das janelas de aviso).

    São faixas de retângulo em vez de um gradiente de verdade porque o
    Tk não tem gradiente — com 60 faixas a emenda não aparece.
    """
    largura = canvas.winfo_width()
    altura = canvas.winfo_height()
    if largura <= 1 or altura <= 1:
        return
    for i in range(faixas):
        cor = mesclar(cor_a, cor_b, i / (faixas - 1))
        if horizontal:
            x = largura * i / faixas
            canvas.create_rectangle(x, 0, x + largura / faixas + 1, altura,
                                    fill=cor, outline=cor)
        else:
            y = altura * i / faixas
            canvas.create_rectangle(0, y, largura, y + altura / faixas + 1,
                                    fill=cor, outline=cor)


# ── Botão ────────────────────────────────────────────────────────────
VARIANTES = {
    "primario": ("primario", "primario_hover", "#FFFFFF", None),
    "sucesso": ("sucesso", "sucesso_hover", "#08130B", None),
    "perigo": ("perigo", "perigo_hover", "#FFFFFF", None),
    "aviso": ("aviso", "aviso_hover", "#1A1203", None),
    "whatsapp": ("whatsapp", "whatsapp_hover", "#FFFFFF", None),
    "secundario": ("card_hover", "elevado", None, "borda"),
    "fantasma": (None, "card_hover", None, "borda"),
}


class Botao(tk.Canvas):
    """Botão arredondado. `variante` escolhe as cores; `icone` é só um
    emoji colocado antes do texto."""

    def __init__(self, parent, texto, comando=None, variante="primario",
                 icone="", altura=40, largura=None, raio=RAIO["md"],
                 fonte=None, expandir=False, fundo=None, **kwargs):
        # `fundo` é pra quando o botão fica em cima de algo desenhado (um
        # cartão arredondado, por exemplo): sem isso os cantos do botão
        # aparecem recortados na cor errada
        self._bg = fundo or _bg_do(parent)
        super().__init__(parent, bg=self._bg, highlightthickness=0, bd=0,
                         height=altura, **kwargs)

        self.texto = texto
        self.icone = icone
        self.comando = comando
        self.variante = variante if variante in VARIANTES else "primario"
        self.raio = raio
        self.altura = altura
        self.expandir = expandir
        self.fonte = fonte or tema.fonte("corpo_forte")
        self._estado = "normal"     # normal | hover | pressionado | desativado
        self._carregando = False

        medidor = tkfont.Font(font=self.fonte)
        rotulo = f"{icone}  {texto}".strip()
        self._largura_min = largura or (medidor.measure(rotulo) + 44)
        self.configure(width=self._largura_min)

        self.bind("<Configure>", lambda e: self._desenhar())
        self.bind("<Enter>", self._entrar)
        self.bind("<Leave>", self._sair)
        self.bind("<Button-1>", self._pressionar)
        self.bind("<ButtonRelease-1>", self._soltar)
        self._desenhar()

    # ── cores por estado ──
    def _cores(self):
        base, hover, texto_cor, borda = VARIANTES[self.variante]
        fundo = tema.cor(base) if base else self._bg
        if self._estado == "hover":
            fundo = tema.cor(hover) if hover else fundo
        elif self._estado == "pressionado":
            fundo = mesclar(tema.cor(hover) if hover else fundo, "#000000", 0.18)
        elif self._estado == "desativado":
            fundo = mesclar(fundo, tema.cor("fundo"), 0.55)

        cor_texto = texto_cor or tema.cor("texto")
        if self._estado == "desativado":
            cor_texto = tema.cor("muted")
        cor_borda = tema.cor(borda) if borda else ""
        return fundo, cor_texto, cor_borda

    def _desenhar(self):
        self.delete("all")
        largura = max(self.winfo_width(), self._largura_min if not self.expandir else 40)
        altura = self.altura
        fundo, cor_texto, cor_borda = self._cores()

        retangulo_arredondado(self, 1, 1, largura - 1, altura - 1, self.raio,
                              fill=fundo,
                              outline=cor_borda or fundo,
                              width=1 if cor_borda else 0)

        rotulo = self.texto if not self._carregando else "aguarde…"
        if self.icone and not self._carregando:
            rotulo = f"{self.icone}  {self.texto}"
        self.create_text(largura / 2, altura / 2, text=rotulo, fill=cor_texto,
                         font=self.fonte)

    # ── eventos ──
    def _entrar(self, _=None):
        if self._estado == "desativado":
            return
        self._estado = "hover"
        self.configure(cursor="hand2")
        self._desenhar()

    def _sair(self, _=None):
        if self._estado == "desativado":
            return
        self._estado = "normal"
        self._desenhar()

    def _pressionar(self, _=None):
        if self._estado == "desativado":
            return
        self._estado = "pressionado"
        self._desenhar()

    def _soltar(self, evento=None):
        if self._estado == "desativado":
            return
        self._estado = "hover"
        self._desenhar()
        dentro = (0 <= (evento.x if evento else 0) <= self.winfo_width()
                  and 0 <= (evento.y if evento else 0) <= self.winfo_height())
        if self.comando and dentro:
            self.comando()

    # ── API ──
    def definir_texto(self, texto, icone=None):
        self.texto = texto
        if icone is not None:
            self.icone = icone
        self._desenhar()

    def ativar(self):
        self._estado = "normal"
        self._carregando = False
        self._desenhar()

    def desativar(self):
        self._estado = "desativado"
        self.configure(cursor="")
        self._desenhar()

    def carregando(self, ligado=True, texto="aguarde…"):
        self._carregando = ligado
        if ligado:
            self._texto_antigo = self.texto
            self.texto = texto
            self.desativar()
        else:
            self.texto = getattr(self, "_texto_antigo", self.texto)
            self.ativar()


# ── Campo de texto ───────────────────────────────────────────────────
class Campo(tk.Frame):
    """Input com rótulo em cima, placeholder de verdade (label separado,
    não texto dentro do campo), olho pra ver a senha e aviso de Caps Lock."""

    def __init__(self, parent, rotulo="", placeholder="", senha=False,
                 largura=32, ao_enviar=None, valor=""):
        super().__init__(parent, bg=_bg_do(parent))
        self.senha = senha
        self.ao_enviar = ao_enviar
        self._visivel = not senha

        if rotulo:
            tk.Label(self, text=rotulo, font=tema.fonte("pequeno_forte"),
                     bg=_bg_do(parent), fg=tema.cor("texto2"), anchor="w"
                     ).pack(fill="x", pady=(0, 6))

        self.caixa = tk.Frame(self, bg=tema.cor("input"), highlightthickness=1,
                              highlightbackground=tema.cor("borda"),
                              highlightcolor=tema.cor("primario"))
        self.caixa.pack(fill="x")

        self.entrada = tk.Entry(
            self.caixa, bg=tema.cor("input"), fg=tema.cor("texto"),
            insertbackground=tema.cor("primario"), relief="flat", bd=0,
            font=tema.fonte("corpo", 12), width=largura,
            highlightthickness=0, show="•" if senha else "")
        self.entrada.pack(side="left", fill="x", expand=True, padx=(14, 6), pady=12)

        self._placeholder = tk.Label(
            self.caixa, text=placeholder, font=tema.fonte("corpo", 11),
            bg=tema.cor("input"), fg=tema.cor("muted"))
        if placeholder:
            self._placeholder.place(x=16, rely=0.5, anchor="w")
        self._placeholder.bind("<Button-1>", lambda e: self.entrada.focus_set())

        if senha:
            self.olho = tk.Label(self.caixa, text="👁", font=(tema.familia, 12),
                                 bg=tema.cor("input"), fg=tema.cor("muted"),
                                 cursor="hand2", padx=10)
            self.olho.pack(side="right", pady=12)
            self.olho.bind("<Button-1>", lambda e: self.alternar_visibilidade())

        self.aviso = tk.Label(self, text="", font=tema.fonte("micro"),
                              bg=_bg_do(parent), fg=tema.cor("aviso"), anchor="w")

        self.entrada.bind("<FocusIn>", self._focar)
        self.entrada.bind("<FocusOut>", self._desfocar)
        self.entrada.bind("<KeyRelease>", self._digitou)
        if ao_enviar:
            self.entrada.bind("<Return>", lambda e: ao_enviar())

        if valor:
            self.definir(valor)

    # ── estados ──
    def _focar(self, _=None):
        self.caixa.configure(highlightbackground=tema.cor("primario"))
        self._atualizar_placeholder()

    def _desfocar(self, _=None):
        self.caixa.configure(highlightbackground=tema.cor("borda"))
        self._atualizar_placeholder()

    def _digitou(self, evento=None):
        self._atualizar_placeholder()
        if self.senha and evento is not None:
            # bit 0x0002 = Caps Lock ligado
            if evento.state & 0x0002 and self.entrada.get():
                self.mostrar_aviso("Caps Lock está ligado.")
            else:
                self.mostrar_aviso("")

    def _atualizar_placeholder(self):
        if self.entrada.get():
            self._placeholder.place_forget()
        elif self._placeholder.cget("text"):
            self._placeholder.place(x=16, rely=0.5, anchor="w")

    def alternar_visibilidade(self):
        self._visivel = not self._visivel
        self.entrada.configure(show="" if self._visivel else "•")
        self.olho.configure(text="🙈" if self._visivel else "👁")

    def mostrar_aviso(self, texto, cor=None):
        if texto:
            self.aviso.configure(text=texto, fg=cor or tema.cor("aviso"))
            self.aviso.pack(fill="x", pady=(6, 0))
        else:
            self.aviso.pack_forget()

    # ── valor ──
    def valor(self):
        return self.entrada.get().strip()

    def definir(self, texto):
        self.entrada.delete(0, "end")
        self.entrada.insert(0, texto or "")
        self._atualizar_placeholder()

    def focar(self):
        self.entrada.focus_set()


# ── Campo arredondado ────────────────────────────────────────────────
class CampoRedondo(tk.Frame):
    """Campo de texto com cantos arredondados de verdade.

    O `Campo` normal usa a borda do Tk, que só faz canto quadrado. Aqui a
    caixa é desenhada num Canvas e o `Entry` (sem borda) fica por cima —
    é o que dá o visual das telas de conta.
    """

    def __init__(self, parent, rotulo="", placeholder="", senha=False,
                 largura=360, altura=52, fundo=None, raio=12, ao_enviar=None):
        self._fundo = fundo or _bg_do(parent)
        super().__init__(parent, bg=self._fundo)
        self.senha = senha
        self.altura = altura
        self.raio = raio
        self._visivel = not senha
        self._focado = False

        if rotulo:
            tk.Label(self, text=rotulo, font=tema.fonte("pequeno_forte"),
                     bg=self._fundo, fg=tema.cor("texto2"), anchor="w"
                     ).pack(fill="x", pady=(0, 8))

        self.tela = tk.Canvas(self, bg=self._fundo, height=altura,
                              width=largura, highlightthickness=0, bd=0)
        self.tela.pack(fill="x")

        self.entrada = tk.Entry(
            self.tela, bg=tema.cor("input"), fg=tema.cor("texto"),
            insertbackground=tema.cor("primario"), relief="flat", bd=0,
            font=tema.fonte("corpo", 11), highlightthickness=0,
            show="•" if senha else "")

        # placeholder de verdade: um rótulo por cima do campo, não texto
        # dentro dele (senão quem digitasse "seu@email.com" não entrava)
        self._placeholder = tk.Label(
            self.entrada, text=placeholder, font=tema.fonte("corpo", 11),
            bg=tema.cor("input"), fg=tema.cor("muted"), anchor="w")
        if placeholder:
            self._placeholder.place(x=1, rely=0.5, anchor="w")
        self._placeholder.bind("<Button-1>", lambda e: self.entrada.focus_set())

        self.aviso = tk.Label(self, text="", font=tema.fonte("micro"),
                              bg=self._fundo, fg=tema.cor("aviso"), anchor="w")

        self.entrada.bind("<FocusIn>", self._focar)
        self.entrada.bind("<FocusOut>", self._desfocar)
        self.entrada.bind("<KeyRelease>", self._digitou)
        if ao_enviar:
            self.entrada.bind("<Return>", lambda e: ao_enviar())

        self.tela.bind("<Configure>", lambda e: self._desenhar())
        self.tela.bind("<Button-1>", lambda e: self.entrada.focus_set())
        self._desenhar()

    # ── desenho ──
    def _desenhar(self):
        self.tela.delete("all")
        largura = self.tela.winfo_width()
        if largura <= 1:
            largura = int(self.tela["width"])

        borda = tema.cor("primario") if self._focado else tema.cor("borda")
        retangulo_arredondado(self.tela, 1, 1, largura - 1, self.altura - 1,
                              self.raio, fill=tema.cor("input"), outline=borda,
                              width=1)

        espaco_direita = 44 if self.senha else 18
        self.tela.create_window(
            17, self.altura / 2, anchor="w", window=self.entrada,
            width=max(40, largura - 17 - espaco_direita), height=self.altura - 16)

        if self.senha:
            self._desenhar_olho(largura - 26, self.altura / 2)

    def _desenhar_olho(self, x, y):
        """O olho é desenhado, não escrito: o emoji 👁 sai como um símbolo
        qualquer dependendo da fonte que o Windows escolhe."""
        cor = tema.cor("muted")
        itens = [
            # contorno em formato de olho (duas curvas)
            self.tela.create_arc(x - 9, y - 7, x + 9, y + 7, start=20,
                                 extent=140, style="arc", outline=cor),
            self.tela.create_arc(x - 9, y - 7, x + 9, y + 7, start=200,
                                 extent=140, style="arc", outline=cor),
            self.tela.create_oval(x - 2.5, y - 2.5, x + 2.5, y + 2.5,
                                  fill=cor, outline=cor),
            # área de clique invisível (o traço fino é difícil de acertar)
            self.tela.create_rectangle(x - 12, y - 11, x + 12, y + 11,
                                       outline="", fill=""),
        ]
        if self._visivel:
            itens.append(self.tela.create_line(x - 9, y + 7, x + 9, y - 7,
                                               fill=cor, width=1))

        for item in itens:
            self.tela.tag_bind(item, "<Button-1>",
                               lambda e: self.alternar_visibilidade())
            self.tela.tag_bind(item, "<Enter>",
                               lambda e: self.tela.configure(cursor="hand2"))
            self.tela.tag_bind(item, "<Leave>",
                               lambda e: self.tela.configure(cursor=""))

    # ── estados ──
    def _focar(self, _=None):
        self._focado = True
        self._desenhar()
        self._atualizar_placeholder()

    def _desfocar(self, _=None):
        self._focado = False
        self._desenhar()
        self._atualizar_placeholder()

    def _digitou(self, evento=None):
        self._atualizar_placeholder()
        if self.senha and evento is not None:
            if evento.state & 0x0002 and self.entrada.get():   # Caps Lock
                self.mostrar_aviso("Caps Lock está ligado.")
            else:
                self.mostrar_aviso("")

    def _atualizar_placeholder(self):
        if self.entrada.get():
            self._placeholder.place_forget()
        elif self._placeholder.cget("text"):
            self._placeholder.place(x=1, rely=0.5, anchor="w")

    def alternar_visibilidade(self):
        self._visivel = not self._visivel
        self.entrada.configure(show="" if self._visivel else "•")
        self._desenhar()

    def mostrar_aviso(self, texto, cor=None):
        if texto:
            self.aviso.configure(text=texto, fg=cor or tema.cor("aviso"))
            self.aviso.pack(fill="x", pady=(6, 0))
        else:
            self.aviso.pack_forget()

    # ── valor ──
    def valor(self):
        return self.entrada.get().strip()

    def definir(self, texto):
        self.entrada.delete(0, "end")
        self.entrada.insert(0, texto or "")
        self._atualizar_placeholder()

    def focar(self):
        self.entrada.focus_set()


# ── Chave liga/desliga ───────────────────────────────────────────────
class Chave(tk.Frame):
    """A "chavinha" de aplicativo: título à esquerda, interruptor à
    direita, e a linha inteira é clicável.

        Chave(pai, "Transcrever", "a IA ouve as cenas", valor=True,
              ao_mudar=lambda ligada: ...)

    O botão desliza de verdade (animação curta), porque é isso que dá a
    sensação de app em vez de "checkbox do Windows".
    """

    PASSOS = 6          # quadros da animação
    INTERVALO = 14      # ms entre quadros

    def __init__(self, parent, texto="", descricao="", valor=False,
                 ao_mudar=None, cor="primario", compacto=False):
        super().__init__(parent, bg=_bg_do(parent))
        self._bg = _bg_do(parent)
        self.ao_mudar = ao_mudar
        self.cor = cor
        self._valor = bool(valor)
        self._pos = 1.0 if self._valor else 0.0   # 0 = desligada, 1 = ligada
        self._animacao = None
        self._bloqueada = False

        self.largura, self.altura = (40, 22) if compacto else (48, 26)

        self.trilho = tk.Canvas(self, bg=self._bg, highlightthickness=0, bd=0,
                                width=self.largura, height=self.altura,
                                cursor="hand2")
        self.trilho.pack(side="right", padx=(14, 0))

        textos = tk.Frame(self, bg=self._bg)
        textos.pack(side="left", fill="x", expand=True)

        self.rotulo = tk.Label(
            textos, text=texto, font=tema.fonte("corpo_forte" if not compacto
                                                else "pequeno_forte"),
            bg=self._bg, fg=tema.cor("texto"), anchor="w", justify="left")
        self.rotulo.pack(fill="x")

        self.descricao = None
        if descricao:
            self.descricao = tk.Label(
                textos, text=descricao, font=tema.fonte("pequeno"),
                bg=self._bg, fg=tema.cor("texto2"), anchor="w",
                justify="left", wraplength=520)
            self.descricao.pack(fill="x", pady=(2, 0))

        for widget in (self, textos, self.trilho, self.rotulo, self.descricao):
            if widget is not None:
                widget.bind("<Button-1>", lambda e: self.alternar())
                widget.configure(cursor="hand2")

        self._desenhar()

    # ── desenho ──
    def _desenhar(self):
        self.trilho.delete("all")
        desligada = mesclar(tema.cor("borda"), tema.cor("fundo"), 0.2)
        ligada = tema.cor(self.cor)
        fundo = mesclar(desligada, ligada, self._pos)
        if self._bloqueada:
            fundo = mesclar(fundo, tema.cor("fundo"), 0.55)

        retangulo_arredondado(self.trilho, 1, 1, self.largura - 1,
                              self.altura - 1, self.altura / 2,
                              fill=fundo, outline=fundo)

        raio = (self.altura - 8) / 2
        centro_min = 4 + raio
        centro_max = self.largura - 4 - raio
        cx = centro_min + (centro_max - centro_min) * self._pos
        cy = self.altura / 2
        botao = "#FFFFFF" if not self._bloqueada else tema.cor("muted")
        self.trilho.create_oval(cx - raio, cy - raio, cx + raio, cy + raio,
                                fill=botao, outline=botao)

    def _animar(self, destino):
        if self._animacao:
            try:
                self.after_cancel(self._animacao)
            except Exception:
                pass
            self._animacao = None

        passo = (destino - self._pos) / self.PASSOS

        def quadro(restantes):
            # a tela pode ser reconstruída no meio da animação (troca de
            # tema, por exemplo) — aí não há mais o que desenhar
            if not self.winfo_exists():
                self._animacao = None
                return
            self._pos = destino if restantes <= 1 else self._pos + passo
            self._desenhar()
            if restantes > 1:
                self._animacao = self.after(self.INTERVALO,
                                            lambda: quadro(restantes - 1))
            else:
                self._animacao = None

        quadro(self.PASSOS)

    # ── API ──
    def ligada(self):
        return self._valor

    def alternar(self):
        if self._bloqueada:
            return
        self.definir(not self._valor, avisar=True)

    def definir(self, valor, avisar=False):
        self._valor = bool(valor)
        self._animar(1.0 if self._valor else 0.0)
        if avisar and self.ao_mudar:
            self.ao_mudar(self._valor)
        return self._valor

    def bloquear(self, motivo=""):
        """Deixa a chave apagada e sem clique (etapa que ainda não dá
        pra usar). `motivo` entra no lugar da descrição."""
        self._bloqueada = True
        self.rotulo.configure(fg=tema.cor("muted"))
        if motivo and self.descricao is not None:
            self.descricao.configure(text=motivo, fg=tema.cor("aviso"))
        for widget in (self, self.trilho, self.rotulo, self.descricao):
            if widget is not None:
                widget.configure(cursor="")
        self._desenhar()


# ── Cartão ───────────────────────────────────────────────────────────
class Cartao(tk.Frame):
    """Caixa com borda fina e respiro. `corpo` é onde você coloca o
    conteúdo."""

    def __init__(self, parent, titulo="", descricao="", accent=None,
                 preenchimento=ESPACO["md"]):
        super().__init__(parent, bg=tema.cor("card"),
                         highlightthickness=1,
                         highlightbackground=tema.cor("borda"),
                         highlightcolor=tema.cor("borda"))

        if accent:
            tk.Frame(self, bg=accent, height=3).pack(fill="x")

        self.corpo = tk.Frame(self, bg=tema.cor("card"))
        self.corpo.pack(fill="both", expand=True,
                        padx=preenchimento + 4, pady=preenchimento)

        if titulo:
            linha = tk.Frame(self.corpo, bg=tema.cor("card"))
            linha.pack(fill="x")
            if accent:
                tk.Label(linha, text="●", font=(tema.familia, 8),
                         bg=tema.cor("card"), fg=accent).pack(side="left",
                                                              padx=(0, 8))
            tk.Label(linha, text=titulo, font=tema.fonte("subtitulo"),
                     bg=tema.cor("card"), fg=tema.cor("texto"), anchor="w"
                     ).pack(side="left")

        if descricao:
            tk.Label(self.corpo, text=descricao, font=tema.fonte("pequeno"),
                     bg=tema.cor("card"), fg=tema.cor("texto2"), anchor="w",
                     justify="left", wraplength=760
                     ).pack(fill="x", pady=(6, 0))


# ── Cabeçalho de página ──────────────────────────────────────────────
class Cabecalho(tk.Frame):
    def __init__(self, parent, titulo, subtitulo="", etapa=None):
        super().__init__(parent, bg=_bg_do(parent))
        esquerda = tk.Frame(self, bg=_bg_do(parent))
        esquerda.pack(side="left", fill="x", expand=True)

        linha = tk.Frame(esquerda, bg=_bg_do(parent))
        linha.pack(fill="x")

        if etapa:
            selo = tk.Label(linha, text=f" {etapa} ", font=tema.fonte("pequeno_forte"),
                            bg=tema.etapa(etapa), fg="#08111C", padx=6, pady=2)
            selo.pack(side="left", padx=(0, 10))

        tk.Label(linha, text=titulo, font=tema.fonte("display"),
                 bg=_bg_do(parent), fg=tema.cor("texto"), anchor="w"
                 ).pack(side="left")

        if subtitulo:
            tk.Label(esquerda, text=subtitulo, font=tema.fonte("corpo"),
                     bg=_bg_do(parent), fg=tema.cor("texto2"), anchor="w",
                     justify="left", wraplength=820
                     ).pack(fill="x", pady=(6, 0))

        self.acoes = tk.Frame(self, bg=_bg_do(parent))
        self.acoes.pack(side="right")


# ── Chip / etiqueta ──────────────────────────────────────────────────
class Chip(tk.Canvas):
    def __init__(self, parent, texto, cor=None, cor_texto=None, altura=24):
        bg = _bg_do(parent)
        fonte = tema.fonte("micro")
        largura = tkfont.Font(font=fonte).measure(texto) + 22
        super().__init__(parent, bg=bg, highlightthickness=0, bd=0,
                         width=largura, height=altura)
        cor = cor or tema.cor("card_hover")
        retangulo_arredondado(self, 0, 0, largura, altura, altura / 2,
                              fill=cor, outline=cor)
        self.create_text(largura / 2, altura / 2, text=texto, font=fonte,
                         fill=cor_texto or tema.cor("texto2"))


# ── Banner (próximo passo / avisos) ──────────────────────────────────
class Banner(tk.Frame):
    CORES = {
        "sucesso": ("sucesso", "#0C1A12"),
        "aviso": ("aviso", "#1C1405"),
        "erro": ("perigo", "#1D0B0B"),
        "info": ("info", "#06151E"),
    }

    def __init__(self, parent, texto, tipo="sucesso", acao=None, icone="✓"):
        super().__init__(parent, bg=_bg_do(parent))
        nome_cor, fundo_escuro = self.CORES.get(tipo, self.CORES["sucesso"])
        cor = tema.cor(nome_cor)
        fundo = fundo_escuro if tema.escuro else mesclar(cor, "#FFFFFF", 0.86)

        caixa = tk.Frame(self, bg=fundo, highlightthickness=1,
                         highlightbackground=mesclar(cor, fundo, 0.55))
        caixa.pack(fill="x")

        tk.Frame(caixa, bg=cor, width=4).pack(side="left", fill="y")

        interno = tk.Frame(caixa, bg=fundo)
        interno.pack(side="left", fill="both", expand=True, padx=14, pady=12)

        tk.Label(interno, text=f"{icone}  {texto}", font=tema.fonte("corpo"),
                 bg=fundo, fg=tema.cor("texto") if not tema.escuro else cor,
                 anchor="w", justify="left", wraplength=640
                 ).pack(side="left", fill="x", expand=True)

        if acao:
            rotulo, comando = acao
            Botao(interno, rotulo, comando, variante="secundario",
                  altura=32, fonte=tema.fonte("pequeno_forte")
                  ).pack(side="right", padx=(12, 0))


# ── Seletor em pílulas ───────────────────────────────────────────────
class Seletor(tk.Frame):
    """Grupo de opções tipo "segmented control".

    opcoes: lista de (valor, rótulo) ou de strings.
    """

    def __init__(self, parent, opcoes, valor=None, ao_mudar=None, colunas=None):
        super().__init__(parent, bg=_bg_do(parent))
        self.ao_mudar = ao_mudar
        self.valor = valor
        self.botoes = {}

        normalizadas = [(o, o) if isinstance(o, str) else o for o in opcoes]
        for i, (chave, rotulo) in enumerate(normalizadas):
            botao = Botao(
                self, rotulo, comando=lambda c=chave: self.selecionar(c),
                variante="primario" if chave == valor else "secundario",
                altura=36, fonte=tema.fonte("pequeno_forte"))
            if colunas:
                botao.grid(row=i // colunas, column=i % colunas,
                           padx=(0, 8), pady=(0, 8), sticky="w")
            else:
                botao.pack(side="left", padx=(0, 8))
            self.botoes[chave] = botao

    def selecionar(self, chave):
        self.valor = chave
        for c, botao in self.botoes.items():
            botao.variante = "primario" if c == chave else "secundario"
            botao._desenhar()
        if self.ao_mudar:
            self.ao_mudar(chave)


# ── Área rolável ─────────────────────────────────────────────────────
class Rolagem(tk.Frame):
    """Área com rolagem. A barra só aparece quando o conteúdo passa da
    tela, e a roda do mouse só age quando há o que rolar."""

    def __init__(self, parent, bg=None):
        cor = bg or tema.cor("fundo")
        super().__init__(parent, bg=cor)

        self.canvas = tk.Canvas(self, bg=cor, highlightthickness=0, bd=0)
        self.canvas.pack(side="left", fill="both", expand=True)

        from tkinter import ttk
        self.barra = ttk.Scrollbar(self, orient="vertical",
                                   style="WT.Vertical.TScrollbar",
                                   command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self._ao_rolar)

        self.corpo = tk.Frame(self.canvas, bg=cor)
        self._janela = self.canvas.create_window((0, 0), window=self.corpo,
                                                 anchor="nw")

        self.corpo.bind("<Configure>", self._conteudo_mudou)
        self.canvas.bind("<Configure>", self._canvas_mudou)
        self.bind_all("<MouseWheel>", self._roda, add="+")
        self.bind_all("<Button-4>", self._roda, add="+")
        self.bind_all("<Button-5>", self._roda, add="+")

    def _ao_rolar(self, inicio, fim):
        # mostra/esconde a barra conforme a necessidade
        if float(inicio) <= 0.0 and float(fim) >= 1.0:
            self.barra.pack_forget()
        else:
            self.barra.pack(side="right", fill="y")
        self.barra.set(inicio, fim)

    def _conteudo_mudou(self, _=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _canvas_mudou(self, evento):
        self.canvas.itemconfigure(self._janela, width=evento.width)

    def _roda(self, evento):
        if not self.canvas.winfo_exists():
            return
        try:
            inicio, fim = self.canvas.yview()
        except Exception:
            return
        if inicio <= 0.0 and fim >= 1.0:
            return  # nada pra rolar
        # só rola se o ponteiro estiver sobre esta área
        widget = self.winfo_containing(evento.x_root, evento.y_root)
        if widget is None:
            return
        pai = widget
        while pai is not None:
            if pai == self:
                break
            pai = getattr(pai, "master", None)
        else:
            return
        if pai != self:
            return

        if getattr(evento, "num", None) == 4:
            passos = -1
        elif getattr(evento, "num", None) == 5:
            passos = 1
        else:
            passos = -1 if evento.delta > 0 else 1
        self.canvas.yview_scroll(passos, "units")

    def ao_topo(self):
        self.canvas.yview_moveto(0)


# ── Progresso ────────────────────────────────────────────────────────
def tempo_humano(segundos):
    """12 s · 3 min · 1 h 20 min — sempre curto, pra caber na faixa."""
    segundos = max(0, int(segundos or 0))
    if segundos < 60:
        return f"{segundos} s"
    if segundos < 3600:
        minutos, resto = divmod(segundos, 60)
        return f"{minutos} min" if minutos >= 10 or not resto else f"{minutos} min {resto} s"
    horas, resto = divmod(segundos, 3600)
    return f"{horas} h {resto // 60} min"


class BarraSuave(tk.Canvas):
    """Barra de progresso desenhada à mão.

    Dois modos:
      * determinado    — anda até a porcentagem, deslizando (sem "pulos")
      * indeterminado  — um pedaço vai e volta, pra tarefa que não sabe
                         quanto falta (carregar a IA, por exemplo)
    """

    INTERVALO = 30  # ms

    def __init__(self, parent, altura=12, cor="primario"):
        self._bg = _bg_do(parent)
        super().__init__(parent, bg=self._bg, highlightthickness=0, bd=0,
                         height=altura)
        self.altura = altura
        self.cor = cor
        self._alvo = 0.0
        self._atual = 0.0
        self._modo = "determinado"
        self._fase = 0.0
        self._anim = None
        self.bind("<Configure>", lambda e: self._desenhar())

    # ── API ──
    def definir(self, pct):
        self._modo = "determinado"
        self._alvo = max(0.0, min(100.0, float(pct or 0)))
        self._rodar()

    def indeterminado(self):
        if self._modo != "indeterminado":
            self._modo = "indeterminado"
            self._fase = 0.0
        self._rodar()

    def cor_de(self, nome):
        self.cor = nome
        self._desenhar()

    def parar(self):
        if self._anim:
            try:
                self.after_cancel(self._anim)
            except Exception:
                pass
            self._anim = None

    def zerar(self):
        self.parar()
        self._modo = "determinado"
        self._atual = self._alvo = 0.0
        self._desenhar()

    # ── animação ──
    def _rodar(self):
        if self._anim is None:
            self._passo()

    def _passo(self):
        self._anim = None
        if not self.winfo_exists():
            return

        continuar = True
        if self._modo == "indeterminado":
            self._fase = (self._fase + 0.018) % 1.0
        else:
            diferenca = self._alvo - self._atual
            if abs(diferenca) < 0.4:
                self._atual = self._alvo
                continuar = False
            else:
                self._atual += diferenca * 0.22

        self._desenhar()
        if continuar:
            try:
                self._anim = self.after(self.INTERVALO, self._passo)
            except Exception:
                self._anim = None

    def _desenhar(self):
        self.delete("all")
        largura = self.winfo_width()
        if largura <= 1:
            return
        altura = self.altura
        raio = altura / 2

        trilho = mesclar(tema.cor("borda"), tema.cor("fundo"), 0.35)
        retangulo_arredondado(self, 0, 0, largura, altura, raio,
                              fill=trilho, outline=trilho)

        cor = tema.cor(self.cor)
        if self._modo == "indeterminado":
            pedaco = largura * 0.3
            # vai e volta em vez de "teleportar" do fim pro começo
            caminho = (largura + pedaco) * 2
            andado = self._fase * caminho
            x0 = andado - pedaco if andado <= largura + pedaco else caminho - andado - pedaco
            x1 = x0 + pedaco
            x0, x1 = max(0, x0), min(largura, x1)
            if x1 - x0 > 2:
                retangulo_arredondado(self, x0, 0, x1, altura, raio,
                                      fill=cor, outline=cor)
            return

        if self._atual <= 0:
            return
        fim = max(altura, largura * self._atual / 100.0)
        retangulo_arredondado(self, 0, 0, fim, altura, raio,
                              fill=cor, outline=cor)


class PainelProgresso(tk.Frame):
    """A faixa grande de progresso que fica em cima da tela enquanto o
    LibertyTube trabalha.

    Existe porque o cliente reclamava — com razão — que o app parecia
    travado: só o console lá embaixo dizia alguma coisa. Aqui ele vê,
    sem procurar, o que está rodando, quantos por cento já foi, há
    quanto tempo e quanto ainda falta.
    """

    def __init__(self, parent, ao_cancelar=None, pack_opcoes=None):
        super().__init__(parent, bg=tema.cor("card"), highlightthickness=1,
                         highlightbackground=tema.cor("borda"))
        self.ao_cancelar = ao_cancelar
        self._pack = pack_opcoes or {"fill": "x"}
        self._inicio = 0.0
        self._eta = None
        self._ultimo_pct = 0.0
        self._relogio = None
        self._sumico = None
        self._rodando = False

        self.faixa = tk.Frame(self, bg=tema.cor("primario"), height=3)
        self.faixa.pack(fill="x")

        corpo = tk.Frame(self, bg=tema.cor("card"))
        corpo.pack(fill="x", padx=16, pady=12)

        topo = tk.Frame(corpo, bg=tema.cor("card"))
        topo.pack(fill="x")

        self.titulo = tk.Label(topo, text="", font=tema.fonte("subtitulo"),
                               bg=tema.cor("card"), fg=tema.cor("texto"),
                               anchor="w")
        self.titulo.pack(side="left")

        self.percentual = tk.Label(topo, text="", font=tema.fonte("titulo", 15),
                                   bg=tema.cor("card"), fg=tema.cor("primario"))
        self.percentual.pack(side="right")

        self.restante = tk.Label(topo, text="", font=tema.fonte("pequeno"),
                                 bg=tema.cor("card"), fg=tema.cor("texto2"))
        self.restante.pack(side="right", padx=(0, 12))

        self.barra = BarraSuave(corpo, altura=12)
        self.barra.pack(fill="x", pady=(10, 8))

        base = tk.Frame(corpo, bg=tema.cor("card"))
        base.pack(fill="x")

        self.detalhe = tk.Label(base, text="", font=tema.fonte("pequeno"),
                                bg=tema.cor("card"), fg=tema.cor("texto2"),
                                anchor="w", justify="left")
        self.detalhe.pack(side="left", fill="x", expand=True)

        self.cancelar_btn = Botao(base, "Cancelar", self._cancelar,
                                  variante="fantasma", altura=30,
                                  fonte=tema.fonte("micro"))
        self.cancelar_btn.pack(side="right", padx=(10, 0))

        self.decorrido = tk.Label(base, text="", font=tema.fonte("micro"),
                                  bg=tema.cor("card"), fg=tema.cor("muted"))
        self.decorrido.pack(side="right")

    # ── ciclo de vida ────────────────────────────────────────────────
    def iniciar(self, nome):
        self._cancelar_sumico()
        self._inicio = time.time()
        self._eta = None
        self._ultimo_pct = 0.0
        self._rodando = True

        self.faixa.configure(bg=tema.cor("primario"))
        self.titulo.configure(text=nome, fg=tema.cor("texto"))
        self.percentual.configure(text="", fg=tema.cor("primario"))
        self.restante.configure(text="")
        self.detalhe.configure(text="começando…", fg=tema.cor("texto2"))
        self.barra.cor_de("primario")
        self.barra.zerar()
        self.barra.indeterminado()
        self.cancelar_btn.pack(side="right", padx=(10, 0))

        self.pack(**self._pack)
        self._tique()

    def atualizar(self, texto="", pct=None):
        if not self._rodando:
            return
        if texto:
            self.detalhe.configure(text=texto)

        if pct is None:
            self.barra.indeterminado()
            self.percentual.configure(text="")
            self.restante.configure(text="trabalhando…")
            return

        pct = max(0.0, min(100.0, float(pct)))
        # progresso só anda pra frente: etapa nova não joga a barra pra trás
        pct = max(pct, self._ultimo_pct)
        self._ultimo_pct = pct
        self.barra.definir(pct)
        self.percentual.configure(text=f"{int(pct)}%")
        self._calcular_eta(pct)

    def finalizar(self, estado="ok", texto=""):
        self._rodando = False
        self._parar_relogio()
        cores = {"ok": "sucesso", "erro": "perigo", "cancelado": "aviso"}
        cor = cores.get(estado, "sucesso")
        gasto = tempo_humano(time.time() - self._inicio) if self._inicio else ""

        self.faixa.configure(bg=tema.cor(cor))
        self.barra.cor_de(cor)
        self.barra.definir(100 if estado == "ok" else max(self._ultimo_pct, 4))
        self.percentual.configure(text="100%" if estado == "ok" else "",
                                  fg=tema.cor(cor))
        self.restante.configure(text="")
        self.titulo.configure(fg=tema.cor(cor))
        self.detalhe.configure(text=texto or {
            "ok": f"pronto em {gasto}",
            "erro": "não deu certo — veja o console aqui embaixo",
            "cancelado": "cancelado por você",
        }.get(estado, ""), fg=tema.cor(cor))
        self.decorrido.configure(text=f"levou {gasto}" if gasto else "")
        self.cancelar_btn.pack_forget()

        segundos = 6000 if estado == "ok" else 12000
        try:
            self._sumico = self.after(segundos, self.esconder)
        except Exception:
            pass

    def esconder(self):
        self._rodando = False
        self._parar_relogio()
        self._cancelar_sumico()
        self.barra.parar()
        self.pack_forget()

    # ── miudezas ─────────────────────────────────────────────────────
    def _calcular_eta(self, pct):
        gasto = time.time() - self._inicio
        if pct < 3 or gasto < 6:
            self.restante.configure(text="calculando o tempo…")
            return
        estimativa = gasto * (100 - pct) / pct
        # suaviza: sem isso o "faltam X" fica pulando a cada atualização
        self._eta = estimativa if self._eta is None else (self._eta * 0.7
                                                          + estimativa * 0.3)
        self.restante.configure(text=f"faltam ~{tempo_humano(self._eta)}")

    def _tique(self):
        if not self._rodando or not self.winfo_exists():
            return
        gasto = time.time() - self._inicio
        self.decorrido.configure(text=f"rodando há {tempo_humano(gasto)}")
        if self._eta is not None:
            self._eta = max(0, self._eta - 1)
            self.restante.configure(text=f"faltam ~{tempo_humano(self._eta)}")
        try:
            self._relogio = self.after(1000, self._tique)
        except Exception:
            self._relogio = None

    def _parar_relogio(self):
        if self._relogio:
            try:
                self.after_cancel(self._relogio)
            except Exception:
                pass
            self._relogio = None

    def _cancelar_sumico(self):
        if self._sumico:
            try:
                self.after_cancel(self._sumico)
            except Exception:
                pass
            self._sumico = None

    def _cancelar(self):
        self.detalhe.configure(text="cancelando… (pode levar alguns segundos)",
                               fg=tema.cor("aviso"))
        if self.ao_cancelar:
            self.ao_cancelar()


# ── Console ──────────────────────────────────────────────────────────
class Console(tk.Frame):
    """Painel inferior: mostra o que o app está fazendo, com barra de
    progresso e botão de cancelar."""

    NIVEIS = {
        "info": "texto2",
        "ok": "sucesso",
        "aviso": "aviso",
        "erro": "perigo",
        "sistema": "info",
    }

    def __init__(self, parent, ao_cancelar=None, altura=170):
        super().__init__(parent, bg=tema.cor("console"), height=altura,
                         highlightthickness=1,
                         highlightbackground=tema.cor("borda"))
        self.pack_propagate(False)
        self.ao_cancelar = ao_cancelar

        # o console é escuro nos dois temas (legibilidade do log), então o
        # cabeçalho também precisa ser escuro — senão fica uma faixa branca
        # em cima de um bloco preto no modo claro.
        cor_cabecalho = mesclar(tema.cor("console"), "#FFFFFF", 0.10)

        cabecalho = tk.Frame(self, bg=cor_cabecalho)
        cabecalho.pack(fill="x")

        tk.Label(cabecalho, text="  ⚡  CONSOLE", font=tema.fonte("micro", peso="bold"),
                 bg=cor_cabecalho, fg="#98A2B8"
                 ).pack(side="left", padx=8, pady=6)

        self.status = tk.Label(cabecalho, text="● pronto",
                               font=tema.fonte("micro"), bg=cor_cabecalho,
                               fg=tema.cor("sucesso"))
        self.status.pack(side="left", padx=6)

        self.limpar_btn = tk.Label(cabecalho, text="limpar", font=tema.fonte("micro"),
                                   bg=cor_cabecalho, fg="#5C6579",
                                   cursor="hand2")
        self.limpar_btn.pack(side="right", padx=10)
        self.limpar_btn.bind("<Button-1>", lambda e: self.limpar())

        self.cancelar_btn = tk.Label(cabecalho, text="cancelar",
                                     font=tema.fonte("micro", peso="bold"),
                                     bg=cor_cabecalho, fg=tema.cor("perigo"),
                                     cursor="hand2")
        self.cancelar_btn.bind("<Button-1>", lambda e: self._cancelar())

        from tkinter import ttk
        self.barra = ttk.Progressbar(self, style="WT.Horizontal.TProgressbar",
                                     mode="determinate", maximum=100)

        self.rotulo_progresso = tk.Label(
            self, text="", font=tema.fonte("micro"), bg=tema.cor("console"),
            fg="#98A2B8", anchor="w")

        corpo = tk.Frame(self, bg=tema.cor("console"))
        corpo.pack(fill="both", expand=True)

        barra_rolagem = ttk.Scrollbar(corpo, orient="vertical",
                                      style="WT.Vertical.TScrollbar")
        barra_rolagem.pack(side="right", fill="y")

        self.texto = tk.Text(
            corpo, bg=tema.cor("console"), fg="#98A2B8",
            font=tema.fonte_mono(10), relief="flat", bd=0, wrap="word",
            state="disabled", padx=12, pady=8,
            insertbackground=tema.cor("texto"),
            selectbackground=tema.cor("primario"),
            yscrollcommand=barra_rolagem.set)
        self.texto.pack(side="left", fill="both", expand=True)
        barra_rolagem.config(command=self.texto.yview)

        for nivel, cor in self.NIVEIS.items():
            # "texto2" muda com o tema e some no fundo escuro do console
            self.texto.tag_config(
                nivel, foreground="#98A2B8" if cor == "texto2" else tema.cor(cor))

    # ── API ──
    def escrever(self, mensagem, nivel="info"):
        self.texto.configure(state="normal")
        self.texto.insert("end", f"{mensagem}\n", nivel)
        self.texto.see("end")
        self.texto.configure(state="disabled")

    def limpar(self):
        self.texto.configure(state="normal")
        self.texto.delete("1.0", "end")
        self.texto.configure(state="disabled")

    def progresso(self, mensagem="", pct=None):
        if not self.barra.winfo_ismapped():
            self.rotulo_progresso.pack(fill="x", padx=12, pady=(8, 0))
            self.barra.pack(fill="x", padx=12, pady=(4, 8))
        if pct is None:
            self.barra.configure(mode="indeterminate")
            self.barra.start(14)
        else:
            self.barra.stop()
            self.barra.configure(mode="determinate", value=max(0, min(100, pct)))
        self.rotulo_progresso.configure(text=mensagem)

    def ocupado(self, ligado=True, texto="processando…"):
        if ligado:
            self.status.configure(text=f"● {texto}", fg=tema.cor("aviso"))
            self.cancelar_btn.pack(side="right", padx=4)
        else:
            self.status.configure(text="● pronto", fg=tema.cor("sucesso"))
            self.cancelar_btn.pack_forget()
            self.barra.stop()
            self.barra.pack_forget()
            self.rotulo_progresso.pack_forget()

    def _cancelar(self):
        if self.ao_cancelar:
            self.ao_cancelar()


# ── Miudezas ─────────────────────────────────────────────────────────
def divisor(parent, pady=ESPACO["md"]):
    linha = tk.Frame(parent, bg=tema.cor("borda_suave"), height=1)
    linha.pack(fill="x", pady=pady)
    return linha


def espaco(parent, altura=ESPACO["md"]):
    vazio = tk.Frame(parent, bg=_bg_do(parent), height=altura)
    vazio.pack(fill="x")
    return vazio


def rotulo(parent, texto, estilo="corpo", cor="texto", **kwargs):
    return tk.Label(parent, text=texto, font=tema.fonte(estilo),
                    bg=_bg_do(parent), fg=tema.cor(cor), anchor="w",
                    justify="left", **kwargs)


def link(parent, texto, comando, cor="primario"):
    etiqueta = tk.Label(parent, text=texto, font=tema.fonte("pequeno"),
                        bg=_bg_do(parent), fg=tema.cor(cor), cursor="hand2")
    etiqueta.bind("<Button-1>", lambda e: comando())
    etiqueta.bind("<Enter>", lambda e: etiqueta.configure(
        font=(tema.familia, 9, "underline")))
    etiqueta.bind("<Leave>", lambda e: etiqueta.configure(font=tema.fonte("pequeno")))
    return etiqueta


class Toast:
    """Mensagem flutuante que some sozinha."""

    def __init__(self, root, texto, tipo="sucesso", duracao=3200):
        cores = {"sucesso": "sucesso", "erro": "perigo",
                 "aviso": "aviso", "info": "info"}
        cor = tema.cor(cores.get(tipo, "sucesso"))

        self.caixa = tk.Frame(root, bg=tema.cor("elevado"), highlightthickness=1,
                              highlightbackground=cor)
        tk.Frame(self.caixa, bg=cor, width=4).pack(side="left", fill="y")
        tk.Label(self.caixa, text=texto, font=tema.fonte("pequeno"),
                 bg=tema.cor("elevado"), fg=tema.cor("texto"),
                 wraplength=340, justify="left"
                 ).pack(side="left", padx=14, pady=12)
        self.caixa.place(relx=0.5, rely=0.04, anchor="n")
        root.after(duracao, self.fechar)

    def fechar(self):
        try:
            self.caixa.destroy()
        except Exception:
            pass
