"""
core/tasks.py
------------------------------------------------------------
Executor de tarefas pesadas (download, transcrição, montagem…).

Regra de ouro do app: **nada demorado roda na thread da interface**.
Na 2.48 o login, a checagem de licença e o update rodavam na thread do
    Tkinter — por isso o Windows mostrava "LibertyTube não está respondendo".

Como funciona:
    executor.rodar(funcao, nome="Baixando cenas", ao_terminar=...)

A `funcao` recebe (log, progresso, ctx) e roda numa thread. Tudo que ela
manda por `log`/`progresso` entra numa fila; a interface esvazia essa
fila no seu próprio ritmo (a cada 80 ms). Assim nenhum widget é tocado
de fora da thread principal — que é o que faz o Tkinter travar de forma
aleatória.

Cancelar é de verdade: o contexto guarda os processos de FFmpeg abertos
e mata todos eles.
"""

import queue
import threading


class Cancelado(Exception):
    """Levantada dentro da tarefa quando o usuário aperta Cancelar."""


class Contexto:
    """Passado pra tarefa. Serve pra ela saber que foi cancelada e pra
    registrar processos externos que precisam morrer junto."""

    def __init__(self):
        self._evento = threading.Event()
        self._processos = []
        self._lock = threading.Lock()

    # ── cancelamento ──
    def cancelar(self):
        self._evento.set()
        with self._lock:
            processos = list(self._processos)
        for p in processos:
            try:
                p.terminate()
            except Exception:
                pass

    def abortado(self):
        return self._evento.is_set()

    def checar(self):
        """Chame entre etapas: levanta Cancelado se o usuário pediu."""
        if self._evento.is_set():
            raise Cancelado()

    # ── processos externos (ffmpeg, yt-dlp) ──
    def registrar_processo(self, proc):
        with self._lock:
            self._processos = [p for p in self._processos if p.poll() is None]
            self._processos.append(proc)
        if self._evento.is_set():
            try:
                proc.terminate()
            except Exception:
                pass


class Tarefa:
    """Uma execução em andamento."""

    def __init__(self, nome, ctx, thread):
        self.nome = nome
        self.ctx = ctx
        self.thread = thread

    def viva(self):
        return self.thread.is_alive()


class Executor:
    """Ponte entre as threads de trabalho e a interface Tkinter."""

    INTERVALO_MS = 80

    def __init__(self, root):
        self.root = root
        self.fila = queue.Queue()
        self.tarefa = None
        self._bombeando = False

    # ── API usada pelas telas ────────────────────────────────────────
    def ocupado(self):
        return self.tarefa is not None and self.tarefa.viva()

    def rodar(self, funcao, nome="Processando", ao_log=None, ao_progresso=None,
              ao_terminar=None, ao_falhar=None, ao_cancelar=None, ao_fim=None):
        """Roda `funcao(log, progresso, ctx)` numa thread.

        Callbacks (todos opcionais) são chamados NA THREAD DA INTERFACE:
            ao_log(texto, nivel)        linha de console
            ao_progresso(texto, pct)    barra de progresso (pct 0-100 ou None)
            ao_terminar(resultado)      terminou bem
            ao_falhar(excecao)          estourou erro
            ao_cancelar()               usuário cancelou
            ao_fim()                    sempre, no final de tudo
        """
        if self.ocupado():
            if ao_falhar:
                ao_falhar(RuntimeError(
                    f"Já tem uma tarefa rodando ({self.tarefa.nome}). "
                    "Espere terminar ou clique em Cancelar."))
            return None

        ctx = Contexto()

        def log(texto, nivel="info"):
            self.fila.put(("log", (texto, nivel)))

        def progresso(texto, pct=None):
            self.fila.put(("progresso", (texto, pct)))

        def alvo():
            try:
                resultado = funcao(log, progresso, ctx)
                if ctx.abortado():
                    self.fila.put(("cancelado", None))
                else:
                    self.fila.put(("ok", resultado))
            except Cancelado:
                self.fila.put(("cancelado", None))
            except Exception as e:  # noqa: BLE001 — erro vira mensagem na tela
                self.fila.put(("erro", e))

        thread = threading.Thread(target=alvo, name=f"libertytube:{nome}", daemon=True)
        self.tarefa = Tarefa(nome, ctx, thread)

        self._callbacks = {
            "log": ao_log, "progresso": ao_progresso, "ok": ao_terminar,
            "erro": ao_falhar, "cancelado": ao_cancelar, "fim": ao_fim,
        }
        thread.start()
        self._bombear()
        return self.tarefa

    def cancelar(self):
        if self.tarefa:
            self.tarefa.ctx.cancelar()

    # ── bomba de eventos ─────────────────────────────────────────────
    def _bombear(self):
        """Esvazia a fila dentro da thread da interface e reagenda."""
        cb = getattr(self, "_callbacks", {})
        terminou = False
        try:
            while True:
                tipo, dados = self.fila.get_nowait()
                if tipo == "log":
                    if cb.get("log"):
                        cb["log"](dados[0], dados[1])
                elif tipo == "progresso":
                    if cb.get("progresso"):
                        cb["progresso"](dados[0], dados[1])
                elif tipo == "ok":
                    terminou = True
                    if cb.get("ok"):
                        cb["ok"](dados)
                elif tipo == "erro":
                    terminou = True
                    if cb.get("erro"):
                        cb["erro"](dados)
                elif tipo == "cancelado":
                    terminou = True
                    if cb.get("cancelado"):
                        cb["cancelado"]()
        except queue.Empty:
            pass
        except Exception:
            terminou = True

        if terminou:
            self.tarefa = None
            if cb.get("fim"):
                try:
                    cb["fim"]()
                except Exception:
                    pass
            return

        try:
            self.root.after(self.INTERVALO_MS, self._bombear)
        except Exception:
            pass  # janela fechou no meio


def em_thread(funcao, ao_terminar=None, ao_falhar=None, root=None,
              intervalo_ms=60):
    """Atalho pra chamadas curtas de rede (login, buscar aulas, checar
    update) que não precisam de log nem progresso.

    O resultado volta pelos callbacks, sempre na thread da interface.

    Detalhe importante: quem agenda o `after` é a thread da interface,
    nunca a thread de trabalho. Chamar `after` de fora só funciona
    enquanto o mainloop está rodando — fora dele o Tk levanta
    "main thread is not in main loop" e o resultado se perdia em
    silêncio. Aqui a thread só põe o resultado numa fila; a interface
    busca no ritmo dela.
    """
    fila = queue.Queue()

    def alvo():
        try:
            fila.put(("ok", funcao()))
        except Exception as e:  # noqa: BLE001
            fila.put(("erro", e))

    t = threading.Thread(target=alvo, daemon=True)
    t.start()

    if root is None:
        # sem interface (testes, linha de comando): espera e entrega
        t.join()
        tipo, valor = fila.get()
        if tipo == "ok" and ao_terminar:
            ao_terminar(valor)
        elif tipo == "erro" and ao_falhar:
            ao_falhar(valor)
        return t

    def conferir():
        try:
            tipo, valor = fila.get_nowait()
        except queue.Empty:
            try:
                root.after(intervalo_ms, conferir)
            except Exception:
                pass  # janela fechada
            return
        try:
            if tipo == "ok":
                if ao_terminar:
                    ao_terminar(valor)
            elif ao_falhar:
                ao_falhar(valor)
        except Exception:
            pass  # widget destruído enquanto a consulta rodava

    try:
        root.after(intervalo_ms, conferir)
    except Exception:
        pass
    return t
