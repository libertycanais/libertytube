"""
pipeline/face_track.py
------------------------------------------------------------
"Câmera que segue o rosto" para cortes verticais (9:16).

Como funciona, pra ficar bom sem ficar lento:
  1. detecta o rosto a cada ~0,4 s (não em todo frame)
  2. monta um caminho horizontal de pra onde a câmera deve olhar
  3. suaviza esse caminho (média móvel) pra a imagem não tremer
  4. se perder o rosto, mantém a última posição em vez de pular
  5. se não achar rosto nenhum, devolve None e quem chamou usa o
     corte central normal

Precisa do opencv-python. Sem ele, devolve None com segurança.
"""

from .base import normalizar


def tem_opencv():
    try:
        import cv2  # noqa: F401
        return True
    except Exception:
        return False


def caminho_do_rosto(video, amostra_seg=0.4, log=None):
    """Lista de (tempo_segundos, centro_x_normalizado) ou None."""
    log, _ = normalizar(log, None)
    if not tem_opencv():
        log("Rastreio de rosto indisponível (opencv não instalado); "
            "usando corte central.", "aviso")
        return None

    import cv2

    captura = cv2.VideoCapture(video)
    if not captura.isOpened():
        return None

    fps = captura.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(captura.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    largura = int(captura.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    if largura <= 0 or total <= 0:
        captura.release()
        return None

    try:
        detector = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        if detector.empty():
            captura.release()
            return None
    except Exception:
        captura.release()
        return None

    intervalo = max(1, int(fps * amostra_seg))
    pontos, ultimo_x, achou = [], 0.5, False
    indice = 0

    while True:
        if not captura.grab():
            break
        if indice % intervalo == 0:
            ok, frame = captura.retrieve()
            if ok and frame is not None:
                escala = 480.0 / max(1, frame.shape[1])
                pequeno = cv2.resize(frame, None, fx=escala, fy=escala)
                cinza = cv2.cvtColor(pequeno, cv2.COLOR_BGR2GRAY)
                rostos = detector.detectMultiScale(cinza, scaleFactor=1.2,
                                                   minNeighbors=5, minSize=(30, 30))
                if len(rostos) > 0:
                    x, y, w, h = max(rostos, key=lambda r: r[2] * r[3])
                    ultimo_x = (x + w / 2.0) / pequeno.shape[1]
                    achou = True
                pontos.append((indice / fps, ultimo_x))
        indice += 1

    captura.release()

    if not achou or len(pontos) < 2:
        log("Nenhum rosto detectado; usando corte central.", "aviso")
        return None

    xs = [p[1] for p in pontos]
    janela = 5
    suave = []
    for i in range(len(xs)):
        ini = max(0, i - janela)
        fim = min(len(xs), i + janela + 1)
        suave.append(sum(xs[ini:fim]) / (fim - ini))

    return [(pontos[i][0], suave[i]) for i in range(len(pontos))]


def _expressao_crop(caminho, largura_video, largura_alvo, max_pontos=40):
    """Expressão de X do crop que desliza no tempo acompanhando o rosto."""
    if not caminho:
        return None

    limite = max(0, largura_video - largura_alvo)

    def em_pixel(centro):
        px = centro * largura_video - largura_alvo / 2.0
        return max(0, min(limite, px))

    if len(caminho) > max_pontos:
        passo = len(caminho) / max_pontos
        reduzido = [caminho[int(i * passo)] for i in range(max_pontos)]
        reduzido.append(caminho[-1])
        caminho = reduzido

    partes = []
    for i in range(len(caminho) - 1):
        t0, c0 = caminho[i]
        t1, c1 = caminho[i + 1]
        if t1 <= t0:
            continue
        x0, x1 = em_pixel(c0), em_pixel(c1)
        partes.append(f"if(between(t,{t0:.2f},{t1:.2f}),"
                      f"{x0:.1f}+({x1:.1f}-{x0:.1f})*(t-{t0:.2f})/{(t1 - t0):.2f}")

    if not partes:
        return None
    final = em_pixel(caminho[-1][1])
    return ",".join(partes) + f",{final:.1f}" + (")" * len(partes))


def filtro_seguindo_rosto(video, largura_alvo, altura_alvo, log=None):
    """Filtro -vf completo que corta seguindo o rosto, ou None."""
    caminho = caminho_do_rosto(video, log=log)
    if not caminho:
        return None

    import cv2
    captura = cv2.VideoCapture(video)
    largura = int(captura.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    altura = int(captura.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    captura.release()
    if largura <= 0 or altura <= 0:
        return None

    # escala pela altura e depois corta a largura acompanhando o rosto
    largura_escalada = int(round(largura * (altura_alvo / altura)))
    expressao = _expressao_crop(caminho, largura_escalada, largura_alvo)
    if not expressao:
        return None

    return (f"scale={largura_escalada}:{altura_alvo},"
            f"crop={largura_alvo}:{altura_alvo}:'{expressao}':0")
