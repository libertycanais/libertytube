"""
ui/media.py
------------------------------------------------------------
Galeria de vídeos: miniatura de verdade (tirada do próprio vídeo),
duração, clique pra assistir e lixeira pra apagar.

As miniaturas ficam em cache na pasta de configuração — sem isso, cada
vez que a tela abria o app chamava o FFmpeg de novo pra cada vídeo (era
o que deixava a tela inicial lenta na 2.48).
"""

import hashlib
import os
import subprocess
import sys
import tkinter as tk

from ..core import paths, projects, runtime, tasks
from .theme import tema
from .widgets import Botao, rotulo

try:
    from PIL import Image, ImageOps, ImageTk
    TEM_PIL = True
except ImportError:
    TEM_PIL = False

PASTA_CACHE = os.path.join(paths.CONFIG_DIR, "miniaturas")

# Cada imagem fica presa ao próprio widget que a mostra (`visor.imagem`).
# Antes elas iam pra uma lista global que nunca esvaziava: cada vez que a
# tela era remontada sobrava mais um punhado de imagens na memória.


def formatar_duracao(segundos):
    segundos = int(segundos or 0)
    if segundos <= 0:
        return "--:--"
    if segundos >= 3600:
        return f"{segundos // 3600}:{(segundos % 3600) // 60:02d}:{segundos % 60:02d}"
    return f"{segundos // 60}:{segundos % 60:02d}"


def _caminho_cache(video, largura, altura):
    # o tamanho entra na marca: o mesmo vídeo aparece em card em pé
    # (9:16) e deitado (16:9), e a imagem guardada precisa cobrir os dois
    try:
        marca = f"{video}|{os.path.getmtime(video)}|{largura}x{altura}"
    except OSError:
        marca = f"{video}|{largura}x{altura}"
    nome = hashlib.md5(marca.encode("utf-8")).hexdigest()[:20]
    return os.path.join(PASTA_CACHE, f"{nome}.jpg")


def imagem_do_video(video, largura=240, altura=135):
    """Imagem do primeiro segundo do vídeo, no tamanho exato do card.

    A imagem PREENCHE o card (sobra é cortada nas beiradas), como na
    grade do TikTok ou do Instagram — deixar barra preta em volta fazia
    a galeria parecer quebrada quando o vídeo não era do formato da rede.

    NÃO cria PhotoImage: isto aqui roda em thread (chama o FFmpeg quando
    o vídeo é novo, e isso demora). Quem monta a tela transforma em
    PhotoImage depois, na thread da interface — objeto do Tk só pode
    nascer lá.
    """
    if not TEM_PIL or not os.path.exists(video):
        return None

    os.makedirs(PASTA_CACHE, exist_ok=True)
    destino = _caminho_cache(video, largura, altura)

    if not os.path.exists(destino):
        try:
            # "increase" garante que a imagem guardada cobre o card
            # inteiro; sem isso o corte pra preencher esticava pixel
            runtime.rodar_ffmpeg(
                ["-ss", "1", "-i", video, "-frames:v", "1", "-vf",
                 f"scale={largura * 2}:{altura * 2}"
                 ":force_original_aspect_ratio=increase", destino],
                checar=False)
        except Exception:
            return None
        if not os.path.exists(destino):
            return None

    try:
        imagem = Image.open(destino).convert("RGB")
        return ImageOps.fit(imagem, (largura, altura), Image.LANCZOS)
    except Exception:
        return None


def miniatura(video, largura=240, altura=135):
    """PhotoImage do primeiro segundo do vídeo (ou None).

    Cuidado: só chame na thread da interface E quando o vídeo já tiver
    miniatura em cache — se não tiver, isto chama o FFmpeg e segura a
    tela. A galeria usa o caminho em thread (`imagem_do_video`).
    """
    imagem = imagem_do_video(video, largura, altura)
    return ImageTk.PhotoImage(imagem) if imagem is not None else None


def abrir_arquivo(caminho, pai=None):
    """Abre o vídeo no player padrão do sistema.

    `pai` é qualquer widget da tela — serve pra janela de aviso nascer
    em cima do app. Sem ele, o erro só vai pro console."""
    from . import dialogs

    if not os.path.exists(caminho):
        if pai is not None:
            dialogs.aviso(pai, "Arquivo não encontrado",
                          "Esse arquivo não existe mais — ele pode ter sido "
                          "apagado ou movido de pasta.", icone="!", cor="aviso")
        return False
    try:
        if sys.platform == "win32":
            os.startfile(caminho)  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", caminho])
        else:
            subprocess.Popen(["xdg-open", caminho])
        return True
    except Exception as e:
        if pai is not None:
            dialogs.erro(pai, "Não consegui abrir o arquivo", str(e))
        return False


def excluir_arquivo(caminho, confirmar=True, pai=None):
    from . import dialogs

    if confirmar and pai is not None:
        if not dialogs.confirmar(
                pai, "Apagar arquivo",
                f"Apagar {os.path.basename(caminho)}?\n\nIsso não tem volta.",
                sim="Apagar", nao="Cancelar", icone="🗑", perigoso=True):
            return False
    try:
        os.remove(caminho)
        return True
    except Exception as e:
        if pai is not None:
            dialogs.erro(pai, "Não consegui apagar", str(e))
        return False


# tamanho do card por formato de saída — o corte já sai nessa proporção,
# e o card mostrando ela deixa o cliente ver de relance como o vídeo vai
# aparecer no TikTok, no feed ou no YouTube
CAIXAS_CARD = {"9:16": (150, 266), "1:1": (200, 200), "16:9": (240, 135)}


class Galeria(tk.Frame):
    """Grade de cards de vídeo, na proporção da rede escolhida.

    Clicar num card abre o player do LibertyTube (`ui/player.py`); só quando
    ele não estiver disponível é que o vídeo vai pro player do Windows.
    """

    def __init__(self, parent, arquivos, colunas=4, ao_atualizar=None,
                 vazio="Nada por aqui ainda.", mostrar_lixeira=True,
                 formato=None, no_player=True):
        super().__init__(parent, bg=tema.cor("fundo"))
        self.ao_atualizar = ao_atualizar
        self.mostrar_lixeira = mostrar_lixeira
        self.no_player = no_player
        self.arquivos = list(arquivos or [])
        self.formato = formato or projects.formato()
        self.caixa = CAIXAS_CARD.get(self.formato, CAIXAS_CARD["16:9"])
        # card em pé cabe mais na linha; deitado, menos
        if self.formato == "9:16":
            colunas = max(colunas, 5)

        if not arquivos:
            caixa = tk.Frame(self, bg=tema.cor("card"), highlightthickness=1,
                             highlightbackground=tema.cor("borda"))
            caixa.pack(fill="x")
            tk.Label(caixa, text="🎬", font=(tema.familia, 22),
                     bg=tema.cor("card"), fg=tema.cor("muted")).pack(pady=(18, 4))
            rotulo(caixa, vazio, "pequeno", "texto2").configure(
                bg=tema.cor("card"), anchor="center", justify="center")
            caixa.winfo_children()[-1].pack(pady=(0, 18), padx=20)
            return

        self._pendentes = []
        for i, caminho in enumerate(arquivos):
            self._card(caminho).grid(row=i // colunas, column=i % colunas,
                                     padx=(0, 12), pady=(0, 12), sticky="nsew")
        for c in range(colunas):
            self.grid_columnconfigure(c, weight=1)
        self._preencher(arquivos)

    # ── miniatura e duração vêm de fora da thread da interface ───────
    def _preencher(self, arquivos):
        """Card nasce com "🎬" e "--:--"; miniatura e duração chegam
        depois, de uma thread.

        Era aqui o congelamento que o cliente sentia ao terminar uma
        etapa: a tela é remontada, e cada card perguntava a duração ao
        ffprobe (~70 ms) e mandava o FFmpeg tirar a miniatura de cada
        vídeo NOVO — tudo na thread da interface. Com 12 cortes recém
        criados, a janela ficava vários segundos sem responder.
        """
        # a tela é remontada a cada etapa que termina; sem esta marca, a
        # thread da galeria velha continuava chamando FFmpeg pra uma tela
        # que já foi fechada — várias delas ao mesmo tempo, disputando o
        # processador com a etapa seguinte
        self._vivo = True
        self.bind("<Destroy>", self._morreu, add="+")

        largura_c, altura_c = self.caixa

        def trabalho():
            pronto = []
            for caminho in arquivos:
                if not self._vivo:
                    break
                pronto.append((imagem_do_video(caminho, largura_c, altura_c),
                               runtime.duracao(caminho)))
            return pronto

        def chegou(dados):
            if not self._vivo or not self.winfo_exists():
                return
            for (imagem, segundos), alvo in zip(dados, self._pendentes):
                if not alvo["visor"].winfo_exists():
                    continue
                alvo["duracao"].configure(text=formatar_duracao(segundos))
                if imagem is None or not TEM_PIL:
                    continue
                foto = ImageTk.PhotoImage(imagem)
                visor = alvo["visor"]
                novo = tk.Label(visor.master, image=foto, bg="#000000",
                                width=self.caixa[0], height=self.caixa[1])
                novo.imagem = foto          # preso ao widget, sem lista global
                for evento, funcao in alvo["cliques"]:
                    novo.bind(evento, funcao)
                visor.destroy()
                novo.pack(fill="x", before=alvo["info"])
                alvo["visor"] = novo

        tasks.em_thread(trabalho, ao_terminar=chegou, root=self)

    def _card(self, caminho):
        card = tk.Frame(self, bg=tema.cor("card"), highlightthickness=1,
                        highlightbackground=tema.cor("borda"), cursor="hand2")

        largura_c, altura_c = self.caixa
        visor = tk.Canvas(card, width=largura_c, height=altura_c,
                          bg="#000000", highlightthickness=0)
        visor.create_text(largura_c // 2, altura_c // 2, text="🎬",
                          font=(tema.familia, 24), fill=tema.cor("muted"))
        visor.pack(fill="x")

        info = tk.Frame(card, bg=tema.cor("card"))
        info.pack(fill="x", padx=10, pady=8)

        limite = 18 if self.caixa[0] < 200 else 26
        nome = os.path.basename(caminho)
        if len(nome) > limite:
            nome = nome[:limite - 3] + "…"
        tk.Label(info, text=nome, font=tema.fonte("pequeno_forte"),
                 bg=tema.cor("card"), fg=tema.cor("texto"), anchor="w"
                 ).pack(fill="x")

        linha = tk.Frame(info, bg=tema.cor("card"))
        linha.pack(fill="x", pady=(2, 0))
        etiqueta_duracao = tk.Label(linha, text="--:--",
                                    font=tema.fonte("micro"),
                                    bg=tema.cor("card"), fg=tema.cor("muted"))
        etiqueta_duracao.pack(side="left")

        if self.mostrar_lixeira:
            lixeira = tk.Label(linha, text="🗑", font=(tema.familia, 10),
                               bg=tema.cor("card"), fg=tema.cor("muted"),
                               cursor="hand2")
            lixeira.pack(side="right")
            lixeira.bind("<Button-1>", lambda e, c=caminho: self._apagar(c))

        def abrir(_=None, c=caminho):
            if self.no_player:
                from . import player
                if player.abrir(self, self.arquivos,
                                self.arquivos.index(c), self.formato):
                    return
            abrir_arquivo(c, pai=self)

        def entrar(_=None):
            card.configure(highlightbackground=tema.cor("primario"))

        def sair(_=None):
            card.configure(highlightbackground=tema.cor("borda"))

        for widget in (card, visor, info):
            widget.bind("<Button-1>", abrir)
        card.bind("<Enter>", entrar)
        card.bind("<Leave>", sair)

        # o que a thread vai preencher quando a miniatura ficar pronta
        self._pendentes.append({
            "visor": visor, "info": info, "duracao": etiqueta_duracao,
            "cliques": (("<Button-1>", abrir), ("<Enter>", entrar),
                        ("<Leave>", sair)),
        })
        return card

    def _morreu(self, _=None):
        """A galeria saiu da tela: a thread para no próximo arquivo."""
        self._vivo = False

    def _apagar(self, caminho):
        if excluir_arquivo(caminho, pai=self) and self.ao_atualizar:
            self.ao_atualizar()


def cabecalho_galeria(parent, titulo, quantidade, pasta, ao_atualizar=None):
    """Linha com o título da galeria, o contador e os botões de abrir
    pasta / atualizar."""
    linha = tk.Frame(parent, bg=tema.cor("fundo"))

    tk.Label(linha, text=titulo, font=tema.fonte("subtitulo"),
             bg=tema.cor("fundo"), fg=tema.cor("texto")).pack(side="left")
    tk.Label(linha, text=f"  ({quantidade})", font=tema.fonte("pequeno"),
             bg=tema.cor("fundo"), fg=tema.cor("muted")).pack(side="left")

    if ao_atualizar:
        Botao(linha, "atualizar", ao_atualizar, variante="fantasma",
              altura=30, fonte=tema.fonte("micro")).pack(side="right", padx=(8, 0))
    Botao(linha, "abrir pasta", lambda: paths.abrir_no_explorador(pasta),
          variante="fantasma", altura=30, icone="📂",
          fonte=tema.fonte("micro")).pack(side="right")
    return linha
