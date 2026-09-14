"""
main.py
------------------------------------------------------------
Ponto de entrada do LibertyTube.

Ordem:
    1. prepara o ambiente (FFmpeg, subprocess, DPI)
    2. abre a janela imediatamente
    3. o resto (login, atualização, conteúdo) acontece em thread

Se algo essencial falhar — inclusive o módulo de login — o app mostra
uma tela de erro e NÃO abre o painel. Segurança que falha aberta não é
segurança.
"""

import os
import sys
import traceback
import tkinter as tk
from datetime import datetime


def _registrar_erro(erro):
    """Guarda o erro num arquivo de log pra dar pra investigar depois."""
    try:
        from .core import paths
        with open(paths.ARQ_LOG, "a", encoding="utf-8") as f:
            f.write(f"\n===== {datetime.now():%d/%m/%Y %H:%M:%S} =====\n")
            f.write("".join(traceback.format_exception(
                type(erro), erro, erro.__traceback__)))
    except Exception:
        pass


def _tela_de_erro(mensagem, detalhe=""):
    """Última linha de defesa: uma janela explicando o problema."""
    janela = tk.Tk()
    janela.title("LibertyTube — erro ao abrir")
    janela.configure(bg="#0B0E14")
    janela.geometry("620x360")

    tk.Label(janela, text="Não consegui abrir o LibertyTube",
             font=("Segoe UI", 16, "bold"), bg="#0B0E14", fg="#E9EEF9"
             ).pack(pady=(34, 10), padx=30, anchor="w")
    tk.Label(janela, text=mensagem, font=("Segoe UI", 10), bg="#0B0E14",
             fg="#98A2B8", wraplength=540, justify="left"
             ).pack(padx=30, anchor="w")

    if detalhe:
        caixa = tk.Text(janela, height=8, bg="#12151D", fg="#5C6579",
                        font=("Consolas", 9), relief="flat", wrap="word",
                        padx=12, pady=10)
        caixa.pack(fill="both", expand=True, padx=30, pady=20)
        caixa.insert("1.0", detalhe)
        caixa.configure(state="disabled")

    tk.Button(janela, text="Fechar", command=janela.destroy, bg="#6C5CE7",
              fg="#FFFFFF", bd=0, font=("Segoe UI", 10, "bold"),
              padx=20, pady=8, cursor="hand2").pack(pady=(0, 24))
    janela.mainloop()


def executar():
    # garante que o pacote é importável quando roda por duplo clique
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if raiz not in sys.path:
        sys.path.insert(0, raiz)

    try:
        from .core import runtime
        runtime.preparar()
        runtime.dpi_aware()

        # o módulo de acesso é obrigatório: sem ele, o app não abre
        from .backend import auth  # noqa: F401
        from .ui.shell import LibertyTubeApp
    except Exception as erro:  # noqa: BLE001
        _registrar_erro(erro)
        _tela_de_erro(
            "Faltou uma parte essencial do programa (ou ela foi alterada).\n\n"
            "Rode o instalador do LibertyTube de novo pra reparar. Se continuar, "
            "fale com o suporte e mande o arquivo de log.",
            f"{type(erro).__name__}: {erro}")
        return 1

    root = tk.Tk()
    try:
        # áudio temporário do player que sobrou de uma sessão fechada no
        # tapa (o app não fica limpando isso enquanto roda)
        from .ui import player
        player.limpar_sobras()

        LibertyTubeApp(root)
        root.mainloop()
    except Exception as erro:  # noqa: BLE001
        _registrar_erro(erro)
        try:
            root.destroy()
        except Exception:
            pass
        _tela_de_erro("O LibertyTube fechou por causa de um erro inesperado.",
                      f"{type(erro).__name__}: {erro}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(executar())
