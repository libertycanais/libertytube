"""
ui/player.py
------------------------------------------------------------
    O player dos cortes prontos, dentro do próprio LibertyTube.

Antes, clicar num corte abria o player do Windows: outra janela, com
outra cara, e o cliente perdia o app de vista. Aqui o corte abre numa
    janela do LibertyTube, **no formato que ele escolheu** (9:16 pro TikTok e
Reels, 1:1 pro feed, 16:9 pro YouTube) — do jeito que o vídeo vai
aparecer pra quem assistir.

Como funciona por dentro:

    imagem   OpenCV lê os quadros numa thread e a tela só desenha o que
             já chegou pronto (a interface nunca decodifica vídeo).
    som      o FFmpeg tira o áudio pra um .wav temporário e o próprio
             Windows toca (winmm/MCI). O FFmpeg que o app baixa não traz
             o ffplay, e o MCI já vem no sistema — não instala nada.
    relógio  quem manda no tempo é o som (a posição do MCI). Assim a
             imagem nunca desencontra do áudio. Sem som, o relógio é o
             do próprio computador.

Se faltar OpenCV ou não der pra tirar o áudio, o player não quebra: ele
mostra o que dá e oferece o botão de abrir no player do Windows.
"""

import ctypes
import glob
import os
import queue
import shutil
import tempfile
import threading
import time
import tkinter as tk

from ..core import paths, projects, runtime, tasks
from .dialogs import Modal
from .theme import ESPACO, escurecer, mesclar, tema
from .widgets import Botao, retangulo_arredondado, rotulo

try:
    from PIL import Image, ImageTk
    TEM_PIL = True
except ImportError:
    TEM_PIL = False

try:
    import cv2
    TEM_CV2 = True
except ImportError:
    TEM_CV2 = False


def formato_disponivel():
    """O player só abre se der pra desenhar os quadros."""
    return TEM_PIL and TEM_CV2


# ── som pelo Windows (winmm/MCI) ─────────────────────────────────────
class _Som:
    """Áudio do corte tocado pelo próprio Windows.

    Serve também de relógio: `posicao_ms()` diz em que ponto o som está,
    e a imagem se guia por ele.
    """

    def __init__(self):
        self.apelido = f"wintube{id(self)}"
        self.pronto = False
        self.mudo = False
        self._pasta = None
        self._aberto = False
        # o cliente pula de corte em corte mais rápido do que o FFmpeg
        # tira o áudio: sem esta marca, o .wav que chegava atrasado ficava
        # esquecido no disco (uns 10 MB por minuto de vídeo)
        self._descartado = False

    # o MCI é uma API de texto: manda comando, recebe resposta
    def _mci(self, comando):
        if os.name != "nt":
            return 1, ""
        buffer = ctypes.create_unicode_buffer(300)
        try:
            codigo = ctypes.windll.winmm.mciSendStringW(comando, buffer, 298, 0)
        except Exception:
            return 1, ""
        return codigo, buffer.value

    def preparar(self, video):
        """Tira o áudio do vídeo e deixa pronto pra tocar. Roda em thread."""
        if os.name != "nt" or self._descartado:
            return False
        try:
            self._fechar_mci()          # se já tinha um áudio aberto aqui
            self._limpar_pasta()
            self._pasta = tempfile.mkdtemp(prefix="wintube_som_")
            wav = os.path.join(self._pasta, "som.wav")
            runtime.rodar_ffmpeg(["-i", video, "-vn", "-acodec", "pcm_s16le",
                                  "-ar", "44100", "-ac", "2", wav], checar=False)
            if self._descartado:            # trocou de corte no meio: joga fora
                self._limpar_pasta()
                return False
            if not os.path.exists(wav) or os.path.getsize(wav) < 1024:
                self._limpar_pasta()
                return False
            codigo, _ = self._mci(f'open "{wav}" type waveaudio alias {self.apelido}')
            if codigo != 0:
                self._limpar_pasta()
                return False
            self._aberto = True
            self._mci(f"set {self.apelido} time format milliseconds")
            self.pronto = True
            if self._descartado:            # fechou a janela enquanto isto rodava
                self.fechar()
                return False
            return True
        except Exception:
            self._limpar_pasta()
            return False

    def tocar(self, ms=0):
        if not self.pronto:
            return
        self._mci(f"play {self.apelido} from {max(0, int(ms))}")
        self._aplicar_volume()

    def pausar(self):
        if self.pronto:
            self._mci(f"stop {self.apelido}")

    def posicao_ms(self):
        if not self.pronto:
            return None
        codigo, resposta = self._mci(f"status {self.apelido} position")
        if codigo != 0 or not resposta.strip().isdigit():
            return None
        return int(resposta.strip())

    def tocando(self):
        if not self.pronto:
            return False
        _, resposta = self._mci(f"status {self.apelido} mode")
        return resposta.strip() == "playing"

    def alternar_mudo(self):
        self.mudo = not self.mudo
        self._aplicar_volume()
        return self.mudo

    def _aplicar_volume(self):
        if self.pronto:
            self._mci(f"setaudio {self.apelido} volume to "
                      f"{0 if self.mudo else 1000}")

    def _fechar_mci(self):
        if self._aberto:
            self._mci(f"stop {self.apelido}")
            self._mci(f"close {self.apelido}")
            self._aberto = False
        self.pronto = False

    def _limpar_pasta(self):
        """Apaga o .wav temporário — insistindo, numa thread.

        O Windows não solta o arquivo no mesmo instante em que o MCI
        fecha. Apagar de primeira falhava calado e cada corte assistido
        deixava uns 10 MB por minuto de vídeo parados no Temp.
        """
        pasta, self._pasta = self._pasta, None
        if not pasta:
            return

        def apagar():
            for _ in range(20):
                shutil.rmtree(pasta, ignore_errors=True)
                if not os.path.exists(pasta):
                    return
                time.sleep(0.15)

        threading.Thread(target=apagar, daemon=True).start()

    def fechar(self):
        self._descartado = True
        self._fechar_mci()
        self._limpar_pasta()


def prontos_do_projeto():
    """Os vídeos mais adiantados do projeto.

    O legendado (o que vai pro ar) na frente; sem ele, a montagem; sem
    ela, os cortes. Serve pro modo automático, que roda várias etapas de
    uma vez e no fim precisa saber o que mostrar.
    """
    from ..pipeline import base

    proj = projects.atual()
    if os.path.exists(proj.video_legendado):
        return [proj.video_legendado]

    montados = [os.path.join(proj.montagem, a)
                for a in base.listar_videos(proj.montagem)]
    if os.path.exists(proj.video_sonorizado):
        montados.insert(0, proj.video_sonorizado)
    if montados:
        return montados

    return [os.path.join(proj.cenas_cortadas, c)
            for c in base.listar_videos(proj.cenas_cortadas)]


def limpar_sobras():
    """Joga fora áudios de sessões passadas.

    Se o app foi fechado no tapa (ou o Windows travou), o .wav ficou lá.
    O que ainda estiver em uso pelo player aberto está preso pelo próprio
    Windows e não é apagado — então é seguro varrer tudo.
    """
    def varrer():
        for pasta in glob.glob(os.path.join(tempfile.gettempdir(),
                                            "wintube_som_*")):
            shutil.rmtree(pasta, ignore_errors=True)

    threading.Thread(target=varrer, daemon=True).start()


# ── o player ─────────────────────────────────────────────────────────
class Player(Modal):
    """Janela do corte pronto, no formato da rede escolhida."""

    # o quadro do vídeo, por formato (o corte já vem nessa proporção)
    CAIXAS = {"9:16": (315, 560), "1:1": (460, 460), "16:9": (620, 349)}

    def __init__(self, app, arquivos, indice=0, formato=None):
        self.arquivos = [a for a in arquivos if os.path.exists(a)]
        if not self.arquivos:
            raise ValueError("nenhum vídeo pra mostrar")
        self.indice = max(0, min(indice, len(self.arquivos) - 1))
        self.formato = formato or projects.formato()

        largura_v, altura_v = self.CAIXAS.get(self.formato, self.CAIXAS["9:16"])
        # tela baixa (notebook de 768px): encolhe o vídeo em vez de deixar
        # os controles pra fora da tela
        raiz = getattr(app, "root", app)
        tela = raiz.winfo_screenheight()
        teto = tela - 330
        if altura_v > teto:
            escala = max(0.45, teto / altura_v)
            largura_v, altura_v = int(largura_v * escala), int(altura_v * escala)
        self.caixa = (largura_v, altura_v)

        largura_janela = max(430, largura_v + 90)
        super().__init__(app, "Seu corte está pronto",
                         f"formato {self.formato} · {self._rede()}",
                         icone="▶", largura=largura_janela,
                         altura=altura_v + 300, cor="primario")

        # estado da reprodução
        self._som = _Som()
        self._fila = queue.Queue(maxsize=3)
        self._vivo = True
        self._tocando = False
        self._duracao = 0.0
        self._posicao = 0.0
        self._pedido_seek = None
        self._arrastando = False
        self._base_relogio = 0.0
        self._marca = 0.0
        self._decodificador = None
        self._foto = None

        limpar_sobras()
        self._montar()
        self._ajustar_altura()
        self._abrir_clipe()
        self.ao_fechar(self._encerrar)

    ONDE_POSTAR = {"9:16": "TikTok, Reels e Shorts",
                   "1:1": "feed do Instagram",
                   "16:9": "YouTube e Facebook"}

    def _ajustar_altura(self):
        """A janela fica do tamanho exato do conteúdo.

        Chutar a altura deixava o rodapé (pular de corte, abrir pasta)
        pra fora da tela em alguns formatos.
        """
        self.update_idletasks()
        altura = self.winfo_reqheight()
        tela = self.winfo_screenheight()
        altura = max(360, min(altura, tela - 60))
        self._centralizar(self.winfo_width(), altura)

    def _rede(self):
        """Onde este formato se posta.

        Se a rede escolhida bate com o formato, mostra o nome dela; senão
        mostra as redes do formato — dizer "1:1 · Instagram Reels" seria
        mentira, o Reels é 9:16.
        """
        nome, formato_da_rede = projects.PLATAFORMAS.get(
            projects.plataforma(), ("TikTok", "9:16"))
        if formato_da_rede == self.formato:
            return nome
        return self.ONDE_POSTAR.get(self.formato, "")

    # ── tela ─────────────────────────────────────────────────────────
    def _montar(self):
        largura_v, altura_v = self.caixa

        palco = tk.Frame(self.corpo, bg=tema.cor("fundo"))
        palco.pack()

        self.tela = tk.Canvas(palco, width=largura_v, height=altura_v,
                              bg="#000000", highlightthickness=1,
                              highlightbackground=tema.cor("borda"),
                              cursor="hand2")
        self.tela.pack()
        self.tela.bind("<Button-1>", lambda e: self.alternar())
        self._aviso_tela = self.tela.create_text(
            largura_v // 2, altura_v // 2, text="preparando…",
            font=tema.fonte("pequeno"), fill="#8892A6")

        # ── controles ──
        controles = tk.Frame(self.corpo, bg=tema.cor("fundo"))
        controles.pack(fill="x", pady=(ESPACO["md"], 0))

        self.barra = tk.Canvas(controles, height=16, bg=tema.cor("fundo"),
                               highlightthickness=0, cursor="hand2")
        self.barra.pack(fill="x")
        self.barra.bind("<Button-1>", self._clique_barra)
        self.barra.bind("<B1-Motion>", self._arrasta_barra)
        self.barra.bind("<ButtonRelease-1>", self._solta_barra)
        self.barra.bind("<Configure>", lambda e: self._pintar_barra())

        linha = tk.Frame(controles, bg=tema.cor("fundo"))
        linha.pack(fill="x", pady=(6, 0))

        self.btn_play = Botao(linha, "Pausar", self.alternar, icone="⏸",
                              altura=38, largura=112)
        self.btn_play.pack(side="left")

        self.btn_som = Botao(linha, "", self._alternar_som, icone="🔊",
                             variante="secundario", altura=38, largura=46)
        self.btn_som.pack(side="left", padx=(8, 0))

        self.lbl_tempo = rotulo(linha, "0:00 / 0:00", "pequeno", "texto2")
        self.lbl_tempo.pack(side="right")

        # ── quem é este corte ──
        cartao = tk.Frame(self.corpo, bg=tema.cor("card"), highlightthickness=1,
                          highlightbackground=tema.cor("borda"))
        cartao.pack(fill="x", pady=(ESPACO["md"], 0))
        dentro = tk.Frame(cartao, bg=tema.cor("card"))
        dentro.pack(fill="x", padx=12, pady=10)

        self.lbl_nome = rotulo(dentro, "", "corpo_forte", "texto")
        self.lbl_nome.configure(bg=tema.cor("card"), anchor="w")
        self.lbl_nome.pack(fill="x")

        self.lbl_arquivo = rotulo(dentro, "", "micro", "muted")
        self.lbl_arquivo.configure(bg=tema.cor("card"), anchor="w")
        self.lbl_arquivo.pack(fill="x", pady=(2, 0))

        # ── navegação e atalhos ──
        rodape = tk.Frame(self.rodape, bg=tema.cor("fundo"))
        rodape.pack(fill="x")

        self.btn_anterior = Botao(rodape, "", lambda: self.pular(-1), icone="‹",
                                  variante="secundario", altura=38, largura=46)
        self.btn_anterior.pack(side="left")
        self.btn_proximo = Botao(rodape, "", lambda: self.pular(1), icone="›",
                                 variante="secundario", altura=38, largura=46)
        self.btn_proximo.pack(side="left", padx=(8, 0))

        Botao(rodape, "Abrir pasta",
              lambda: paths.abrir_no_explorador(
                  os.path.dirname(self.arquivos[self.indice])),
              variante="fantasma", altura=38, icone="📂",
              fonte=tema.fonte("micro")).pack(side="right")

        self.lbl_contador = rotulo(rodape, "", "micro", "muted")
        self.lbl_contador.pack(side="left", padx=(12, 0))

        self.bind("<space>", lambda e: self.alternar())
        self.bind("<Left>", lambda e: self.correr(-5))
        self.bind("<Right>", lambda e: self.correr(5))
        self.bind("<Prior>", lambda e: self.pular(-1))
        self.bind("<Next>", lambda e: self.pular(1))

    # ── barra de progresso ───────────────────────────────────────────
    def _pintar_barra(self):
        if not self.barra.winfo_exists():
            return
        self.barra.delete("all")
        largura = max(1, self.barra.winfo_width())
        meio = 8
        retangulo_arredondado(self.barra, 0, meio - 3, largura, meio + 3, raio=3,
                              fill=tema.cor("borda"), outline="")
        fracao = (self.posicao_mostrada() / self._duracao) if self._duracao else 0
        fim = max(6, min(largura, largura * fracao))
        retangulo_arredondado(self.barra, 0, meio - 3, fim, meio + 3, raio=3,
                              fill=tema.cor("primario"), outline="")
        self.barra.create_oval(fim - 6, meio - 6, fim + 6, meio + 6,
                               fill=tema.cor("primario"),
                               outline=mesclar(tema.cor("primario"), "#FFFFFF", 0.4))

    def posicao_mostrada(self):
        return self._posicao

    def _tempo_do_clique(self, evento):
        largura = max(1, self.barra.winfo_width())
        fracao = min(1.0, max(0.0, evento.x / largura))
        return fracao * self._duracao

    def _clique_barra(self, evento):
        self._arrastando = True
        self._posicao = self._tempo_do_clique(evento)
        self._pintar_barra()

    def _arrasta_barra(self, evento):
        if self._arrastando:
            self._posicao = self._tempo_do_clique(evento)
            self._pintar_barra()

    def _solta_barra(self, evento):
        if not self._arrastando:
            return
        self._arrastando = False
        self.ir_para(self._tempo_do_clique(evento))

    # ── comandos ─────────────────────────────────────────────────────
    def alternar(self):
        self.tocar(not self._tocando)

    def tocar(self, ligar=True):
        self._tocando = ligar
        if ligar:
            self._marca = time.monotonic()
            self._base_relogio = self._posicao
            self._som.tocar(self._posicao * 1000)
            self.btn_play.definir_texto("Pausar", icone="⏸")
        else:
            self._som.pausar()
            self.btn_play.definir_texto("Assistir", icone="▶")

    def ir_para(self, segundos):
        self._posicao = max(0.0, min(segundos, max(0.0, self._duracao - 0.05)))
        self._pedido_seek = self._posicao
        self._base_relogio = self._posicao
        self._marca = time.monotonic()
        if self._tocando:
            self._som.tocar(self._posicao * 1000)
        self._pintar_barra()

    def correr(self, segundos):
        self.ir_para(self._posicao + segundos)

    def _alternar_som(self):
        mudo = self._som.alternar_mudo()
        self.btn_som.definir_texto("", icone="🔇" if mudo else "🔊")

    def pular(self, passo):
        novo = self.indice + passo
        if 0 <= novo < len(self.arquivos):
            self.indice = novo
            self._abrir_clipe()

    # ── abrir um corte ───────────────────────────────────────────────
    def _abrir_clipe(self):
        self._parar_decodificador()
        self._som.fechar()
        self._som = _Som()

        caminho = self.arquivos[self.indice]
        nome = os.path.splitext(os.path.basename(caminho))[0]
        bonito = nome.replace("_", " ").replace("-", " ").strip().capitalize()
        self.lbl_nome.configure(text=f"{self.indice + 1}. {bonito}")
        self.lbl_arquivo.configure(text=os.path.basename(caminho))
        self.lbl_contador.configure(
            text=f"corte {self.indice + 1} de {len(self.arquivos)}")
        (self.btn_anterior.ativar if self.indice > 0
         else self.btn_anterior.desativar)()
        (self.btn_proximo.ativar if self.indice < len(self.arquivos) - 1
         else self.btn_proximo.desativar)()

        self._posicao = 0.0
        self._duracao = 0.0
        self._pedido_seek = None
        self._esvaziar_fila()
        self.tela.itemconfigure(self._aviso_tela, text="preparando…")
        self.tela.tag_raise(self._aviso_tela)
        self._pintar_barra()

        if not formato_disponivel():
            self.tela.itemconfigure(
                self._aviso_tela,
                text="não consigo mostrar o vídeo aqui\nuse 'Abrir pasta'")
            return

        # o som demora um pouco (o FFmpeg tem que tirar o áudio); a
        # imagem não espera por ele
        som = self._som
        tasks.em_thread(lambda: som.preparar(caminho),
                        ao_terminar=lambda ok: self._som_pronto(som, ok),
                        root=self)

        self._decodificador = threading.Thread(
            target=self._decodificar, args=(caminho,), daemon=True)
        self._decodificador.start()
        self._tocando = True
        self._marca = time.monotonic()
        self._base_relogio = 0.0
        self.btn_play.definir_texto("Pausar", icone="⏸")
        self.after(30, self._desenhar)

    def _som_pronto(self, som, deu_certo):
        if not self._vivo or not self.winfo_exists():
            return
        if som is not self._som:        # já pulou pro corte seguinte
            som.fechar()
            return
        if deu_certo and self._tocando:
            self._som.tocar(self._posicao * 1000)
        elif not deu_certo:
            # sem áudio a imagem continua; o cliente só não ouve
            self.btn_som.definir_texto("", icone="🔇")
            self.btn_som.desativar()

    # ── thread que lê os quadros ─────────────────────────────────────
    def _decodificar(self, caminho):
        captura = cv2.VideoCapture(caminho)
        if not captura.isOpened():
            self._fila.put(("erro", None))
            return

        fps = captura.get(cv2.CAP_PROP_FPS) or 30
        quadros = captura.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        duracao = (quadros / fps) if fps else 0
        if duracao <= 0:
            duracao = runtime.duracao(caminho) or 0
        self._fila.put(("duracao", duracao))

        largura_v, altura_v = self.caixa
        meu = self._decodificador

        while self._vivo and self._decodificador is meu:
            if self._pedido_seek is not None:
                alvo = self._pedido_seek
                self._pedido_seek = None
                captura.set(cv2.CAP_PROP_POS_MSEC, alvo * 1000)
                self._esvaziar_fila()

            if not self._tocando:
                time.sleep(0.04)
                continue

            ok, quadro = captura.read()
            if not ok:
                self._fila.put(("fim", None))
                while self._vivo and self._decodificador is meu \
                        and self._pedido_seek is None:
                    time.sleep(0.05)
                continue

            momento = captura.get(cv2.CAP_PROP_POS_MSEC) / 1000.0

            # atrasado demais (computador fraco): pula o quadro em vez de
            # deixar a imagem correr atrás do som
            relogio = self._relogio()
            if momento < relogio - 0.25:
                continue

            try:
                quadro = cv2.cvtColor(quadro, cv2.COLOR_BGR2RGB)
                imagem = Image.fromarray(quadro)
                imagem.thumbnail((largura_v, altura_v))
            except Exception:
                continue

            # espera a hora certa deste quadro
            while self._vivo and self._decodificador is meu and self._tocando:
                falta = momento - self._relogio()
                if falta <= 0.005 or self._pedido_seek is not None:
                    break
                time.sleep(min(0.03, falta))

            if self._pedido_seek is not None:
                continue
            try:
                self._fila.put(("quadro", (momento, imagem)), timeout=0.5)
            except queue.Full:
                pass

        captura.release()

    def _relogio(self):
        """Em que segundo a reprodução está agora.

        O som é quem manda: se ele estiver tocando, a imagem segue a
        posição dele. Sem som, vale o relógio do computador.
        """
        if self._som.pronto and self._tocando:
            ms = self._som.posicao_ms()
            if ms is not None:
                return ms / 1000.0
        if not self._tocando:
            return self._posicao
        return self._base_relogio + (time.monotonic() - self._marca)

    def _esvaziar_fila(self):
        while True:
            try:
                self._fila.get_nowait()
            except queue.Empty:
                return

    # ── desenho, na thread da interface ──────────────────────────────
    def _desenhar(self):
        if not self._vivo or not self.winfo_exists():
            return

        ultimo = None
        while True:
            try:
                tipo, dado = self._fila.get_nowait()
            except queue.Empty:
                break
            if tipo == "quadro":
                ultimo = dado
            elif tipo == "duracao":
                self._duracao = dado or 0
            elif tipo == "fim":
                self._terminou()
            elif tipo == "erro":
                self.tela.itemconfigure(
                    self._aviso_tela,
                    text="não consegui abrir este vídeo\nuse 'Abrir pasta'")
                self.tela.tag_raise(self._aviso_tela)

        if ultimo is not None:
            momento, imagem = ultimo
            self._mostrar(imagem)
            if not self._arrastando:
                self._posicao = momento

        if not self._arrastando:
            self._pintar_barra()
        self.lbl_tempo.configure(
            text=f"{_mmss(self._posicao)} / {_mmss(self._duracao)}")
        self.after(16, self._desenhar)

    def _mostrar(self, imagem):
        try:
            foto = ImageTk.PhotoImage(imagem)
        except Exception:
            return
        largura_v, altura_v = self.caixa
        if getattr(self, "_id_imagem", None) is None:
            self._id_imagem = self.tela.create_image(
                largura_v // 2, altura_v // 2, image=foto)
        else:
            self.tela.itemconfigure(self._id_imagem, image=foto)
        self._foto = foto            # sem isto o Tk descarta a imagem
        self.tela.itemconfigure(self._aviso_tela, text="")

    def _terminou(self):
        """Acabou o corte: volta pro começo, parado."""
        self._tocando = False
        self._som.pausar()
        self._posicao = self._duracao
        self.btn_play.definir_texto("Ver de novo", icone="↻")
        self._pedido_seek = 0.0
        self._posicao = 0.0

    # ── fechar ───────────────────────────────────────────────────────
    def _parar_decodificador(self):
        self._decodificador = None
        self._tocando = False

    def _encerrar(self):
        self._vivo = False
        self._parar_decodificador()
        self._som.fechar()


def _mmss(segundos):
    segundos = max(0, int(segundos or 0))
    return f"{segundos // 60}:{segundos % 60:02d}"


def abrir(app, arquivos, indice=0, formato=None):
    """Abre o player. Se não der (falta OpenCV), abre no player do
    Windows — o cliente não fica sem ver o corte."""
    from . import media

    lista = [a for a in arquivos if os.path.exists(a)]
    if not lista:
        return None
    if not formato_disponivel():
        media.abrir_arquivo(lista[min(indice, len(lista) - 1)], pai=app)
        return None
    try:
        return Player(app, lista, indice, formato)
    except Exception:
        media.abrir_arquivo(lista[min(indice, len(lista) - 1)], pai=app)
        return None
