# ============================================================
#  LibertyTube 1.0 - Instalador automatico
#  Baixa e configura tudo sozinho: Python, FFmpeg, IA e o app.
#  O cliente nao instala nada na mao.
#
#  A janela usa a mesma cara do app (mesmas cores, cantos
#  arredondados, lista de etapas, barra com porcentagem e tempo
#  restante). Tudo e desenhado na mao porque o WinForms padrao tem
#  jeitao de Windows XP e o produto e vendido como aplicativo.
#
#  Estrutura que este instalador espera ao lado dele:
#     sistema\instalador.ps1   (este arquivo)
#     sistema\src\             (codigo do LibertyTube)
#     sistema\assets\          (logo, letterbox, prompts, novidades)
#
#  Modo silencioso (sem janela, pra suporte remoto e testes):
#     powershell -ExecutionPolicy Bypass -File instalador.ps1 -Silencioso
#
#  IMPORTANTE: este arquivo e salvo em UTF-8 COM BOM. Sem o BOM o
#  PowerShell 5.1 le os acentos errado e a janela mostra "InstalaþÒo".
# ============================================================

param([switch]$Silencioso)

$ErrorActionPreference = "Stop"
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

# ---------------- Caminhos ----------------
$Origem       = Split-Path -Parent $MyInvocation.MyCommand.Path
$PastaSrc     = Join-Path $Origem "src"
$PastaAssets  = Join-Path $Origem "assets"
$Destino      = Join-Path $env:LOCALAPPDATA "LibertyTube"
$PastaApp     = Join-Path $Destino "app"
$PastaPython  = Join-Path $Destino "python"
$PastaFfmpeg  = Join-Path $Destino "ffmpeg"
$PastaTemp    = Join-Path $env:TEMP "libertytube_setup"
$LogFile      = Join-Path $Destino "instalacao.log"

$PythonUrls = @("https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe")
$FfmpegUrls = @(
    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
    "https://github.com/GyanD/codexffmpeg/releases/latest/download/ffmpeg-release-essentials.zip",
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
)

# ---------------- Versao ----------------
# Fonte unica: o proprio codigo do app. Assim a janela nunca mostra uma
# versao diferente da que esta sendo instalada.
$Versao = "2.6"
$arqVersao = Join-Path $PastaSrc "wintube\version.py"
if (Test-Path $arqVersao) {
    try {
        $achado = Select-String -Path $arqVersao -Pattern '^VERSAO\s*=\s*"([^"]+)"'
        if ($achado) { $Versao = $achado.Matches[0].Groups[1].Value }
    } catch {}
}

# ---------------- Paleta (a mesma do app) ----------------
$CorFundo    = "#0B0E14"
$CorCard     = "#151A24"
$CorBorda    = "#242C3C"
$CorTexto    = "#E9EEF9"
$CorTexto2   = "#98A2B8"
$CorMuted    = "#5C6579"
$CorPrimaria = "#6C5CE7"
$CorHover    = "#8577FF"
$CorSucesso  = "#22C55E"
$CorPerigo   = "#EF4444"

function Cor($hex) { return [System.Drawing.ColorTranslator]::FromHtml($hex) }

function Caminho-Arredondado($x, $y, $largura, $altura, $raio) {
    $caminho = New-Object System.Drawing.Drawing2D.GraphicsPath
    $d = $raio * 2
    if ($d -gt $altura) { $d = $altura }
    if ($d -gt $largura) { $d = $largura }
    if ($d -le 0) {
        $caminho.AddRectangle((New-Object System.Drawing.RectangleF($x, $y, $largura, $altura)))
        return $caminho
    }
    $caminho.AddArc($x, $y, $d, $d, 180, 90)
    $caminho.AddArc($x + $largura - $d, $y, $d, $d, 270, 90)
    $caminho.AddArc($x + $largura - $d, $y + $altura - $d, $d, $d, 0, 90)
    $caminho.AddArc($x, $y + $altura - $d, $d, $d, 90, 90)
    $caminho.CloseFigure()
    return $caminho
}

function Suavizar($g) {
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::ClearTypeGridFit
}

function Bufferizar($controle) {
    # sem isto a barra e o botao piscam a cada redesenho
    try {
        $prop = [System.Windows.Forms.Control].GetProperty(
            "DoubleBuffered",
            [System.Reflection.BindingFlags]"Instance,NonPublic")
        $prop.SetValue($controle, $true, $null)
    } catch {}
}

function Tempo-Humano($segundos) {
    $s = [int][Math]::Max(0, $segundos)
    if ($s -lt 60) { return "$s s" }
    if ($s -lt 3600) {
        $min = [int]($s / 60)
        $resto = $s % 60
        if ($min -ge 10 -or $resto -eq 0) { return "$min min" }
        return "$min min $resto s"
    }
    $h = [int]($s / 3600)
    $m = [int](($s % 3600) / 60)
    return "$h h $m min"
}

# ---------------- Janela ----------------
$form = New-Object System.Windows.Forms.Form
$form.Text = "Instalador do LibertyTube $Versao"
$form.ClientSize = New-Object System.Drawing.Size(640, 730)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "None"     # a barra de titulo e desenhada por nos
$form.MaximizeBox = $false
$form.BackColor = Cor $CorFundo
$form.KeyPreview = $true
Bufferizar $form

$icone = Join-Path $PastaAssets "libertytube.ico"
if ((Test-Path $icone) -and (-not $Silencioso)) {
    try { $form.Icon = New-Object System.Drawing.Icon($icone) } catch {}
}

# borda fina em volta da janela (ela nao tem moldura do Windows)
$form.Add_Paint({
    param($s, $e)
    $caneta = New-Object System.Drawing.Pen((Cor $CorBorda), 1)
    $e.Graphics.DrawRectangle($caneta, 0, 0,
        $form.ClientSize.Width - 1, $form.ClientSize.Height - 1)
    $caneta.Dispose()
})

# ---- cabecalho em degrade (igual ao painel da tela de login) ----
$cabecalho = New-Object System.Windows.Forms.Panel
$cabecalho.Size = New-Object System.Drawing.Size(640, 96)
$cabecalho.Location = New-Object System.Drawing.Point(0, 0)
Bufferizar $cabecalho
$cabecalho.Add_Paint({
    param($s, $e)
    Suavizar $e.Graphics
    $retangulo = New-Object System.Drawing.Rectangle(0, 0, $s.Width, $s.Height)
    $pincel = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
        $retangulo, (Cor $CorHover), (Cor "#3B2F8F"),
        [System.Drawing.Drawing2D.LinearGradientMode]::Horizontal)
    $e.Graphics.FillRectangle($pincel, $retangulo)
    $pincel.Dispose()
    # circulo de luz, so pra nao ficar chapado
    $brilho = New-Object System.Drawing.SolidBrush(
        [System.Drawing.Color]::FromArgb(28, 255, 255, 255))
    $e.Graphics.FillEllipse($brilho, -120, -180, 460, 320)
    $brilho.Dispose()
})
$form.Controls.Add($cabecalho)

# arrastar a janela pelo cabecalho
$script:arrastando = $false
$script:pontoClique = New-Object System.Drawing.Point(0, 0)
$aoPressionar = {
    param($s, $e)
    if ($e.Button -eq [System.Windows.Forms.MouseButtons]::Left) {
        $script:arrastando = $true
        $script:pontoClique = [System.Windows.Forms.Cursor]::Position
        $script:posicaoJanela = $form.Location
    }
}
$aoMover = {
    param($s, $e)
    if ($script:arrastando) {
        $agora = [System.Windows.Forms.Cursor]::Position
        $form.Location = New-Object System.Drawing.Point(
            ($script:posicaoJanela.X + $agora.X - $script:pontoClique.X),
            ($script:posicaoJanela.Y + $agora.Y - $script:pontoClique.Y))
    }
}
$aoSoltar = { $script:arrastando = $false }
$cabecalho.Add_MouseDown($aoPressionar)
$cabecalho.Add_MouseMove($aoMover)
$cabecalho.Add_MouseUp($aoSoltar)

$logoPath = Join-Path $PastaAssets "libertytube.png"
if ((Test-Path $logoPath) -and (-not $Silencioso)) {
    $pic = New-Object System.Windows.Forms.PictureBox
    try {
        # carrega uma COPIA em memoria: o .NET segura o arquivo aberto e
        # isso trava quem tentar copiar/apagar a pasta durante a instalacao
        $bytes = [System.IO.File]::ReadAllBytes($logoPath)
        $memoria = New-Object System.IO.MemoryStream(,$bytes)
        $pic.Image = [System.Drawing.Image]::FromStream($memoria)
        $pic.SizeMode = "Zoom"
        $pic.Size = New-Object System.Drawing.Size(150, 54)
        $pic.Location = New-Object System.Drawing.Point(28, 21)
        $pic.BackColor = [System.Drawing.Color]::Transparent
        $pic.Add_MouseDown($aoPressionar)
        $pic.Add_MouseMove($aoMover)
        $pic.Add_MouseUp($aoSoltar)
        $cabecalho.Controls.Add($pic)
    } catch {}
}

function Novo-Texto($pai, $texto, $x, $y, $largura, $altura, $tamanho, $estilo, $cor, $alinhamento) {
    $l = New-Object System.Windows.Forms.Label
    $l.Text = $texto
    $l.Font = New-Object System.Drawing.Font("Segoe UI", $tamanho, $estilo)
    $l.ForeColor = Cor $cor
    $l.BackColor = [System.Drawing.Color]::Transparent
    $l.TextAlign = $alinhamento
    $l.AutoSize = $false
    $l.Size = New-Object System.Drawing.Size($largura, $altura)
    $l.Location = New-Object System.Drawing.Point($x, $y)
    $pai.Controls.Add($l)
    return $l
}

$regular = [System.Drawing.FontStyle]::Regular
$negrito = [System.Drawing.FontStyle]::Bold

$lblProduto = Novo-Texto $cabecalho "Instalador oficial" 190 30 240 22 10 $negrito "#FFFFFF" "MiddleLeft"
$lblVersao  = Novo-Texto $cabecalho "versão $Versao  ·  Windows" 190 50 240 18 8 $regular "#D9D2FF" "MiddleLeft"
$lblProduto.Add_MouseDown($aoPressionar); $lblProduto.Add_MouseMove($aoMover); $lblProduto.Add_MouseUp($aoSoltar)

# botoes de minimizar e fechar (a janela nao tem os do Windows)
function Botao-Janela($texto, $x, $acao) {
    $b = New-Object System.Windows.Forms.Label
    $b.Text = $texto
    $b.Font = New-Object System.Drawing.Font("Segoe UI", 11, [System.Drawing.FontStyle]::Regular)
    $b.ForeColor = Cor "#E4DEFF"
    $b.BackColor = [System.Drawing.Color]::Transparent
    $b.TextAlign = "MiddleCenter"
    $b.Size = New-Object System.Drawing.Size(34, 30)
    $b.Location = New-Object System.Drawing.Point($x, 12)
    $b.Cursor = [System.Windows.Forms.Cursors]::Hand
    $b.Add_MouseEnter({ param($s, $e) $s.ForeColor = [System.Drawing.Color]::White })
    $b.Add_MouseLeave({ param($s, $e) $s.ForeColor = (Cor "#E4DEFF") })
    $b.Add_Click($acao)
    $cabecalho.Controls.Add($b)
    return $b
}

$script:instalando = $false
Botao-Janela "—" 560 { $form.WindowState = "Minimized" } | Out-Null
Botao-Janela "✕" 598 {
    if ($script:instalando) {
        $r = [System.Windows.Forms.MessageBox]::Show(
            "A instalacao esta no meio do caminho.`n`nFechar agora? Da pra rodar o instalador de novo depois: ele continua de onde parou.",
            "LibertyTube", "YesNo", "Warning")
        if ($r -ne "Yes") { return }
    }
    $form.Close()
} | Out-Null

# ---- corpo ----
$lblTitulo = Novo-Texto $form "Instalação automática" 28 116 584 30 16 $negrito $CorTexto "MiddleLeft"
$lblInfo   = Novo-Texto $form "Vou baixar e configurar tudo pra você: Python, IA de transcrição, FFmpeg e o LibertyTube." 28 150 584 20 9 $regular $CorTexto2 "MiddleLeft"
$lblInfo2  = Novo-Texto $form "São cerca de 600 MB. Leva de 10 a 25 minutos, dependendo da internet." 28 172 584 20 9 $regular $CorMuted "MiddleLeft"

# ---- escolha do disco ----
# Existe porque o SSD do Windows costuma viver cheio: o cliente instalava
# no C:, os videos iam pro C: e o download morria pela metade sem dizer
# por que. Aqui ele escolhe o disco ANTES, ja vendo o espaco livre.
$cartaoDisco = New-Object System.Windows.Forms.Panel
$cartaoDisco.Size = New-Object System.Drawing.Size(584, 74)
$cartaoDisco.Location = New-Object System.Drawing.Point(28, 194)
$cartaoDisco.BackColor = Cor $CorFundo
Bufferizar $cartaoDisco
$cartaoDisco.Add_Paint({
    param($s, $e)
    Suavizar $e.Graphics
    $caminho = Caminho-Arredondado 0 0 ($s.Width - 1) ($s.Height - 1) 10
    $pincel = New-Object System.Drawing.SolidBrush((Cor $CorCard))
    $e.Graphics.FillPath($pincel, $caminho)
    $caneta = New-Object System.Drawing.Pen((Cor $CorBorda), 1)
    $e.Graphics.DrawPath($caneta, $caminho)
    $pincel.Dispose(); $caneta.Dispose(); $caminho.Dispose()
})
$form.Controls.Add($cartaoDisco)

Novo-Texto $cartaoDisco "Em qual disco instalar?" 20 12 300 20 10 $negrito $CorTexto "MiddleLeft" | Out-Null
$lblDisco = Novo-Texto $cartaoDisco "" 20 44 330 18 8 $regular $CorMuted "MiddleLeft"

$comboDisco = New-Object System.Windows.Forms.ComboBox
$comboDisco.DropDownStyle = "DropDownList"
$comboDisco.Font = New-Object System.Drawing.Font("Segoe UI", 10, $regular)
$comboDisco.Size = New-Object System.Drawing.Size(200, 28)
$comboDisco.Location = New-Object System.Drawing.Point(364, 22)
$comboDisco.FlatStyle = "Flat"
$comboDisco.BackColor = Cor $CorFundo
$comboDisco.ForeColor = Cor $CorTexto
# sem isto a lista nasce com a faixa azul de "selecionado" do Windows,
# que destoa do resto da janela
$comboDisco.TabStop = $false
$cartaoDisco.Controls.Add($comboDisco)

function Discos-Fixos {
    $lista = @()
    try {
        foreach ($d in (Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" -ErrorAction Stop)) {
            $lista += [PSCustomObject]@{
                Letra   = $d.DeviceID
                LivreGB = [math]::Round($d.FreeSpace / 1GB, 1)
                TotalGB = [math]::Round($d.Size / 1GB, 1)
            }
        }
    } catch {
        $lista += [PSCustomObject]@{ Letra = $env:SystemDrive; LivreGB = 0; TotalGB = 0 }
    }
    return $lista
}

# quanto o LibertyTube precisa: ~3 GB de programa + espaco pros videos
$EspacoMinimoGB = 15

$script:discos = Discos-Fixos
foreach ($d in $script:discos) {
    $comboDisco.Items.Add(("{0}  —  {1} GB livres de {2} GB" -f $d.Letra, $d.LivreGB, $d.TotalGB)) | Out-Null
}

# sugere o disco do Windows se ele tiver folga; senao, o mais vazio
$sugerido = 0
$doWindows = 0
for ($i = 0; $i -lt $script:discos.Count; $i++) {
    if ($script:discos[$i].Letra -eq $env:SystemDrive) { $doWindows = $i }
}
if ($script:discos[$doWindows].LivreGB -ge $EspacoMinimoGB) {
    $sugerido = $doWindows
} else {
    $maior = -1
    for ($i = 0; $i -lt $script:discos.Count; $i++) {
        if ($script:discos[$i].LivreGB -gt $maior) { $maior = $script:discos[$i].LivreGB; $sugerido = $i }
    }
}
if ($comboDisco.Items.Count -gt 0) { $comboDisco.SelectedIndex = $sugerido }

# ---- onde cada coisa vai parar, conforme o disco escolhido ----
function Aplicar-Disco {
    if ($comboDisco.SelectedIndex -lt 0) { return }
    $disco = $script:discos[$comboDisco.SelectedIndex]

    if ($disco.Letra -eq $env:SystemDrive) {
        # no disco do Windows continua exatamente como sempre foi, pra não
        # quebrar quem já tem o LibertyTube instalado
        $script:Destino = Join-Path $env:LOCALAPPDATA "LibertyTube"
        $script:PastaVideos = Join-Path ([Environment]::GetFolderPath("MyDocuments")) "LibertyTube"
    } else {
        $script:Destino = Join-Path ($disco.Letra + "\") "LibertyTube"
        $script:PastaVideos = Join-Path ($disco.Letra + "\") "LibertyTube\videos"
    }
    $script:PastaApp    = Join-Path $script:Destino "app"
    $script:PastaPython = Join-Path $script:Destino "python"
    $script:PastaFfmpeg = Join-Path $script:Destino "ffmpeg"
    $script:LogFile     = Join-Path $script:Destino "instalacao.log"

    if ($disco.LivreGB -lt $EspacoMinimoGB) {
        $lblDisco.Text = "Atenção: só $($disco.LivreGB) GB livres — o ideal é ter $EspacoMinimoGB GB ou mais."
        $lblDisco.ForeColor = Cor $CorPerigo
    } else {
        $lblDisco.Text = "Programa em $($script:Destino)  ·  vídeos em $($script:PastaVideos)"
        $lblDisco.ForeColor = Cor $CorMuted
    }
}

$comboDisco.Add_SelectedIndexChanged({ Aplicar-Disco })
Aplicar-Disco

# ---- cartao com as etapas ----
$cartaoEtapas = New-Object System.Windows.Forms.Panel
$cartaoEtapas.Size = New-Object System.Drawing.Size(584, 214)
$cartaoEtapas.Location = New-Object System.Drawing.Point(28, 270)
$cartaoEtapas.BackColor = Cor $CorFundo
Bufferizar $cartaoEtapas
$cartaoEtapas.Add_Paint({
    param($s, $e)
    Suavizar $e.Graphics
    $caminho = Caminho-Arredondado 0 0 ($s.Width - 1) ($s.Height - 1) 10
    $pincel = New-Object System.Drawing.SolidBrush((Cor $CorCard))
    $e.Graphics.FillPath($pincel, $caminho)
    $caneta = New-Object System.Drawing.Pen((Cor $CorBorda), 1)
    $e.Graphics.DrawPath($caneta, $caminho)
    $pincel.Dispose(); $caneta.Dispose(); $caminho.Dispose()
})
$form.Controls.Add($cartaoEtapas)

$NomesEtapas = @(
    "Python 3.11 (privado, não mexe no seu sistema)",
    "Componentes do app (yt-dlp, Pillow, OpenCV)",
    "IA de transcrição (a parte mais demorada)",
    "FFmpeg (o motor de vídeo)",
    "Arquivos do LibertyTube",
    "Atalhos na área de trabalho"
)

$script:marcadores = @()
$script:rotulosEtapa = @()
for ($i = 0; $i -lt $NomesEtapas.Count; $i++) {
    $y = 16 + $i * 31
    $marcador = Novo-Texto $cartaoEtapas "○" 18 $y 26 26 11 $regular $CorMuted "MiddleCenter"
    $texto = Novo-Texto $cartaoEtapas $NomesEtapas[$i] 48 $y 520 26 9 $regular $CorMuted "MiddleLeft"
    $script:marcadores += $marcador
    $script:rotulosEtapa += $texto
}

function Marcar-Etapa($numero) {
    # numero e 1..6; tudo antes vira "feito", o atual vira "fazendo"
    for ($i = 0; $i -lt $script:marcadores.Count; $i++) {
        if ($i -lt ($numero - 1)) {
            $script:marcadores[$i].Text = "✓"
            $script:marcadores[$i].ForeColor = Cor $CorSucesso
            $script:rotulosEtapa[$i].ForeColor = Cor $CorTexto2
            $script:rotulosEtapa[$i].Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Regular)
        } elseif ($i -eq ($numero - 1)) {
            $script:marcadores[$i].Text = "●"
            $script:marcadores[$i].ForeColor = Cor $CorPrimaria
            $script:rotulosEtapa[$i].ForeColor = Cor $CorTexto
            $script:rotulosEtapa[$i].Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
        } else {
            $script:marcadores[$i].Text = "○"
            $script:marcadores[$i].ForeColor = Cor $CorMuted
            $script:rotulosEtapa[$i].ForeColor = Cor $CorMuted
            $script:rotulosEtapa[$i].Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Regular)
        }
    }
}

# ---- cartao do progresso ----
$cartaoProgresso = New-Object System.Windows.Forms.Panel
$cartaoProgresso.Size = New-Object System.Drawing.Size(584, 112)
$cartaoProgresso.Location = New-Object System.Drawing.Point(28, 496)
$cartaoProgresso.BackColor = Cor $CorFundo
Bufferizar $cartaoProgresso
$cartaoProgresso.Add_Paint({
    param($s, $e)
    Suavizar $e.Graphics
    $caminho = Caminho-Arredondado 0 0 ($s.Width - 1) ($s.Height - 1) 10
    $pincel = New-Object System.Drawing.SolidBrush((Cor $CorCard))
    $e.Graphics.FillPath($pincel, $caminho)
    $caneta = New-Object System.Drawing.Pen((Cor $CorBorda), 1)
    $e.Graphics.DrawPath($caneta, $caminho)
    $pincel.Dispose(); $caneta.Dispose(); $caminho.Dispose()
})
$form.Controls.Add($cartaoProgresso)

$lblStatus  = Novo-Texto $cartaoProgresso "Pronto para instalar." 20 14 300 26 10 $negrito $CorTexto "MiddleLeft"
$lblEta     = Novo-Texto $cartaoProgresso "" 320 17 170 20 8 $regular $CorTexto2 "MiddleRight"
$lblPct     = Novo-Texto $cartaoProgresso "" 494 10 70 30 15 $negrito $CorPrimaria "MiddleRight"

$script:pct = 0
$script:fase = 0.0
$script:corBarra = $CorPrimaria

$barra = New-Object System.Windows.Forms.Panel
$barra.Size = New-Object System.Drawing.Size(544, 12)
$barra.Location = New-Object System.Drawing.Point(20, 52)
$barra.BackColor = Cor $CorCard
Bufferizar $barra
$barra.Add_Paint({
    param($s, $e)
    Suavizar $e.Graphics
    $altura = $s.Height
    $trilho = Caminho-Arredondado 0 0 ($s.Width - 1) ($altura - 1) ($altura / 2)
    $pincelTrilho = New-Object System.Drawing.SolidBrush((Cor "#232B3B"))
    $e.Graphics.FillPath($pincelTrilho, $trilho)
    $pincelTrilho.Dispose(); $trilho.Dispose()

    $largura = [int](($s.Width - 1) * $script:pct / 100.0)
    if ($largura -lt $altura -and $script:pct -gt 0) { $largura = $altura }
    if ($largura -gt 0) {
        $cheio = Caminho-Arredondado 0 0 $largura ($altura - 1) ($altura / 2)
        $pincel = New-Object System.Drawing.SolidBrush((Cor $script:corBarra))
        $e.Graphics.FillPath($pincel, $cheio)
        $pincel.Dispose(); $cheio.Dispose()

        # brilho que desliza dentro da parte cheia: e o que mostra que o
        # instalador esta VIVO mesmo quando a porcentagem nao muda
        if ($script:instalando -and $largura -gt 24) {
            $x = [int](($largura + 60) * $script:fase) - 60
            $recorte = New-Object System.Drawing.Region(
                (Caminho-Arredondado 0 0 $largura ($altura - 1) ($altura / 2)))
            $e.Graphics.Clip = $recorte
            $brilho = New-Object System.Drawing.SolidBrush(
                [System.Drawing.Color]::FromArgb(70, 255, 255, 255))
            $e.Graphics.FillRectangle($brilho, $x, 0, 60, $altura)
            $brilho.Dispose()
            $e.Graphics.ResetClip()
        }
    }
})
$cartaoProgresso.Controls.Add($barra)

$lblDetalhe = Novo-Texto $cartaoProgresso "" 20 76 380 20 8 $regular $CorMuted "MiddleLeft"
$lblTempo   = Novo-Texto $cartaoProgresso "" 404 76 160 20 8 $regular $CorMuted "MiddleRight"

# ---- botao grande (desenhado, com hover) ----
$script:textoBotao = "INSTALAR AGORA"
$script:corBotao = $CorPrimaria
$script:botaoLigado = $true
$script:hoverBotao = $false

$botao = New-Object System.Windows.Forms.Panel
$botao.Size = New-Object System.Drawing.Size(300, 52)
$botao.Location = New-Object System.Drawing.Point(170, 628)
$botao.BackColor = Cor $CorFundo
$botao.Cursor = [System.Windows.Forms.Cursors]::Hand
Bufferizar $botao
$botao.Add_Paint({
    param($s, $e)
    Suavizar $e.Graphics
    $cor = Cor $script:corBotao
    if (-not $script:botaoLigado) {
        $cor = [System.Drawing.Color]::FromArgb(255, 42, 35, 80)
    } elseif ($script:hoverBotao) {
        $cor = [System.Drawing.Color]::FromArgb(255,
            [Math]::Min(255, $cor.R + 25), [Math]::Min(255, $cor.G + 25),
            [Math]::Min(255, $cor.B + 25))
    }
    $caminho = Caminho-Arredondado 0 0 ($s.Width - 1) ($s.Height - 1) 12
    $pincel = New-Object System.Drawing.SolidBrush($cor)
    $e.Graphics.FillPath($pincel, $caminho)
    $pincel.Dispose(); $caminho.Dispose()

    $fonte = New-Object System.Drawing.Font("Segoe UI", 11.5, [System.Drawing.FontStyle]::Bold)
    $corTexto = [System.Drawing.Color]::White
    if (-not $script:botaoLigado) { $corTexto = Cor $CorTexto2 }
    $formato = New-Object System.Drawing.StringFormat
    $formato.Alignment = "Center"
    $formato.LineAlignment = "Center"
    $pincelTexto = New-Object System.Drawing.SolidBrush($corTexto)
    $e.Graphics.DrawString($script:textoBotao, $fonte, $pincelTexto,
        (New-Object System.Drawing.RectangleF(0, 0, $s.Width, $s.Height)), $formato)
    $pincelTexto.Dispose(); $fonte.Dispose()
})
$botao.Add_MouseEnter({ $script:hoverBotao = $true; $botao.Invalidate() })
$botao.Add_MouseLeave({ $script:hoverBotao = $false; $botao.Invalidate() })
$form.Controls.Add($botao)

$lblRodape = Novo-Texto $form "O LibertyTube fica na pasta escolhida acima  ·  não mexe em nada do seu Windows" 28 694 584 20 8 $regular "#3A4255" "MiddleCenter"

# ---- relogio: tempo decorrido e quanto falta ----
$script:inicioInstalacao = $null
$script:eta = $null

$relogio = New-Object System.Windows.Forms.Timer
$relogio.Interval = 50
$relogio.Add_Tick({
    $script:fase = $script:fase + 0.03
    if ($script:fase -gt 1) { $script:fase = 0 }
    $barra.Invalidate()

    if ($script:inicioInstalacao -ne $null) {
        $gasto = ((Get-Date) - $script:inicioInstalacao).TotalSeconds
        $lblTempo.Text = "rodando há " + (Tempo-Humano $gasto)
        if ($script:eta -ne $null) {
            $script:eta = [Math]::Max(0, $script:eta - 0.05)
            $lblEta.Text = "faltam ~" + (Tempo-Humano $script:eta)
        }
    }
})

# ---------------- Ajudantes ----------------
function Escrever-Log($texto) {
    try {
        New-Item -ItemType Directory -Path $Destino -Force | Out-Null
        Add-Content -Path $LogFile -Value "[$(Get-Date -Format 'dd/MM/yyyy HH:mm:ss')] $texto"
    } catch {}
}

function Atualizar-Janela {
    if (-not $Silencioso) {
        [System.Windows.Forms.Application]::DoEvents()
    }
}

function Definir-Pct($pct) {
    $script:pct = [Math]::Max(0, [Math]::Min(100, $pct))
    if ($Silencioso) { return }
    $lblPct.Text = "$([int]$script:pct)%"
    $barra.Invalidate()
    # estimativa de quanto falta, no mesmo estilo do app
    if ($script:inicioInstalacao -ne $null -and $script:pct -gt 3) {
        $gasto = ((Get-Date) - $script:inicioInstalacao).TotalSeconds
        if ($gasto -gt 8) {
            $estimativa = $gasto * (100 - $script:pct) / $script:pct
            if ($script:eta -eq $null) {
                $script:eta = $estimativa
            } else {
                $script:eta = ($script:eta * 0.7) + ($estimativa * 0.3)
            }
        }
    }
}

function Status($texto, $pct, $detalhe, $etapa = 0) {
    $lblStatus.Text = $texto
    $lblDetalhe.Text = $detalhe
    Definir-Pct $pct
    if ($etapa -gt 0 -and -not $Silencioso) { Marcar-Etapa $etapa }
    if (-not $Silencioso) {
        Atualizar-Janela
    } else {
        if ($detalhe) {
            Write-Host "  [$([int]$pct)%] $texto ($detalhe)"
        } else {
            Write-Host "  [$([int]$pct)%] $texto"
        }
    }
    Escrever-Log "$texto $detalhe"
}

function Detalhe($texto) {
    $lblDetalhe.Text = $texto
    Atualizar-Janela
}

function Baixar($urls, $arquivo, $nome, $pctIni, $pctFim) {
    $marcador = "$arquivo.ok"
    if ((Test-Path $arquivo) -and (Test-Path $marcador)) {
        Escrever-Log "$nome ja estava baixado."
        return
    }

    $parcial = "$arquivo.parcial"
    $ultimoErro = ""

    foreach ($url in $urls) {
        $fs = $null; $stream = $null; $resp = $null
        try {
            Detalhe "Conectando…"

            $req = [System.Net.HttpWebRequest]::Create($url)
            $req.UserAgent = "LibertyTube-Installer"
            $req.Timeout = 60000
            $req.ReadWriteTimeout = 60000
            $req.AllowAutoRedirect = $true

            $resp = $req.GetResponse()
            $total = $resp.ContentLength
            $stream = $resp.GetResponseStream()
            $fs = [System.IO.File]::Create($parcial)

            # Le em pedacos e devolve o controle pra janela entre um pedaco
            # e outro -> a interface nao congela.
            $buffer = New-Object byte[] 262144
            $lido = 0
            $ultimoRefresh = Get-Date
            $inicio = Get-Date

            while (($n = $stream.Read($buffer, 0, $buffer.Length)) -gt 0) {
                $fs.Write($buffer, 0, $n)
                $lido += $n
                if (((Get-Date) - $ultimoRefresh).TotalMilliseconds -gt 250) {
                    $mb = [Math]::Round($lido / 1MB, 1)
                    $seg = [Math]::Max(1, ((Get-Date) - $inicio).TotalSeconds)
                    $vel = [Math]::Round(($lido / 1MB) / $seg, 1)
                    if ($total -gt 0) {
                        $frac = $lido / $total
                        $mbTot = [Math]::Round($total / 1MB, 1)
                        $lblDetalhe.Text = "$nome  $mb MB de $mbTot MB   ($vel MB/s)"
                        Definir-Pct ($pctIni + ($pctFim - $pctIni) * $frac)
                    } else {
                        $lblDetalhe.Text = "$nome  $mb MB baixados   ($vel MB/s)"
                    }
                    Atualizar-Janela
                    $ultimoRefresh = Get-Date
                }
            }

            $fs.Close(); $fs = $null
            $stream.Close(); $stream = $null
            $resp.Close(); $resp = $null

            $tamFinal = (Get-Item $parcial).Length
            if ($total -gt 0 -and $tamFinal -lt $total) { throw "Download incompleto ($tamFinal de $total bytes)." }
            if ($tamFinal -lt 100000) { throw "Arquivo baixado pequeno demais ($tamFinal bytes)." }

            Move-Item $parcial $arquivo -Force
            Set-Content -Path $marcador -Value "ok" -Encoding ASCII
            Escrever-Log "$nome baixado: $tamFinal bytes"
            return
        }
        catch {
            $ultimoErro = $_.Exception.Message
            Escrever-Log "Falhou em $url -> $ultimoErro"
            foreach ($o in @($fs, $stream, $resp)) { if ($o) { try { $o.Close() } catch {} } }
            if (Test-Path $parcial) { Remove-Item $parcial -Force -ErrorAction SilentlyContinue }
            Detalhe "Tentando outro servidor…"
        }
    }

    throw "Nao consegui baixar o $nome.`n`nUltimo erro: $ultimoErro`n`nConfira sua internet e rode o instalador de novo."
}

function Rodar($exe, $argumentos, $etapa) {
    Escrever-Log "Executando: $exe $argumentos"

    # A saida vai pra ARQUIVO, nunca pra um cano (pipe): cano tem buffer de
    # 4 KB e o pip congela esperando alguem esvaziar.
    $outFile = Join-Path $PastaTemp "saida_$([Guid]::NewGuid().ToString('N').Substring(0,6)).log"
    $errFile = "$outFile.err"

    $proc = Start-Process -FilePath $exe -ArgumentList $argumentos -NoNewWindow -PassThru `
            -RedirectStandardOutput $outFile -RedirectStandardError $errFile

    # Sem guardar o Handle, o ExitCode volta vazio depois que o processo sai.
    try { $null = $proc.Handle } catch {}

    $inicio = Get-Date
    $limiteMin = 45

    while (-not $proc.HasExited) {
        try {
            $ultima = Get-Content $outFile -Tail 1 -ErrorAction SilentlyContinue
            if ($ultima) {
                $txt = ([string]$ultima).Trim()
                if ($txt.Length -gt 62) { $txt = $txt.Substring(0, 62) + "..." }
                $lblDetalhe.Text = $txt
            }
        } catch {}
        Atualizar-Janela
        Start-Sleep -Milliseconds 250
        if (((Get-Date) - $inicio).TotalMinutes -gt $limiteMin) {
            try { $proc.Kill() } catch {}
            throw "A etapa '$etapa' passou de $limiteMin minutos e foi cancelada.`nRode o instalador de novo: ele continua de onde parou."
        }
    }

    $saida = ""
    foreach ($f in @($outFile, $errFile)) {
        if (Test-Path $f) { $saida += (Get-Content $f -Raw -ErrorAction SilentlyContinue) }
    }
    Escrever-Log $saida
    try { $proc.WaitForExit() } catch {}

    $codigo = $null
    try { $codigo = $proc.ExitCode } catch {}
    if ($null -ne $codigo -and $codigo -ne 0) {
        $trecho = $saida
        if ($trecho.Length -gt 600) { $trecho = $trecho.Substring($trecho.Length - 600) }
        throw "Falha na etapa '$etapa' (codigo $codigo).`n`n$trecho"
    }
    if ($null -eq $codigo) { Escrever-Log "Aviso: codigo de saida indisponivel em '$etapa'; seguindo." }
}

function Salvar-PastaDeVideos($pasta) {
    <#
      O app le a pasta dos videos das preferencias
      (%LOCALAPPDATA%\LibertyTube\preferencias.json, chave "pasta_projetos").
      O instalador so escreve essa chave; se o cliente ja tiver escolhido
      uma pasta antes, a dele e mantida.
    #>
    try {
        $configDir = Join-Path $env:LOCALAPPDATA "LibertyTube"
        New-Item -ItemType Directory -Path $configDir -Force | Out-Null
        $arquivo = Join-Path $configDir "preferencias.json"

        $prefs = @{}
        if (Test-Path $arquivo) {
            try {
                $lido = Get-Content $arquivo -Raw -Encoding UTF8 | ConvertFrom-Json
                foreach ($p in $lido.PSObject.Properties) { $prefs[$p.Name] = $p.Value }
            } catch { $prefs = @{} }
        }
        if ($prefs.ContainsKey("pasta_projetos") -and $prefs["pasta_projetos"]) {
            Escrever-Log "Pasta de videos ja escolhida antes: $($prefs['pasta_projetos'])"
            return
        }
        $prefs["pasta_projetos"] = $pasta
        ($prefs | ConvertTo-Json -Depth 5) |
            Out-File $arquivo -Encoding utf8 -Force
        Escrever-Log "Pasta de videos definida: $pasta"
    } catch {
        Escrever-Log "Aviso: nao consegui salvar a pasta de videos ($($_.Exception.Message))"
    }
}

function Criar-Atalho($caminhoLnk, $alvo, $argumentos, $pastaTrabalho, $icone, $descricao) {
    $shell = New-Object -ComObject WScript.Shell
    $lnk = $shell.CreateShortcut($caminhoLnk)
    $lnk.TargetPath = $alvo
    $lnk.Arguments = $argumentos
    $lnk.WorkingDirectory = $pastaTrabalho
    $lnk.Description = $descricao
    if (Test-Path $icone) { $lnk.IconLocation = $icone }
    $lnk.Save()
}

# ---------------- Instalacao ----------------
$script:instalado = $false
$script:pythonwExe = ""
$script:alvoPy = ""

function Abrir-LibertyTube {
    if ((Test-Path $script:pythonwExe) -and (Test-Path $script:alvoPy)) {
        Start-Process -FilePath $script:pythonwExe -ArgumentList "`"$script:alvoPy`"" `
                      -WorkingDirectory (Split-Path -Parent $script:alvoPy)
    }
}

function Executar-Instalacao {
    $script:inicioInstalacao = Get-Date
    $script:instalando = $true
    if (-not $Silencioso) { $relogio.Start() }
    try {
        if (-not (Test-Path $PastaSrc)) {
            throw "A pasta 'src' nao foi encontrada ao lado do instalador.`nExtraia o ZIP INTEIRO antes de instalar (nao rode de dentro do zip)."
        }

        # disco cheio antes de comecar: melhor avisar do que baixar 600 MB
        # e morrer no meio deixando pedaco de instalacao pra tras
        $letra = (Split-Path -Qualifier $Destino)
        try {
            $info = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$letra'"
            $livre = [math]::Round($info.FreeSpace / 1GB, 1)
            if ($livre -lt 4) {
                throw ("O disco $letra tem só $livre GB livres e a instalação precisa de uns 4 GB.`n`n" +
                       "Libere espaço ou escolha outro disco na lista 'Em qual disco instalar?'.")
            }
            Escrever-Log "Disco $letra com $livre GB livres."
        } catch [System.Management.Automation.RuntimeException] { throw }
          catch { Escrever-Log "Nao consegui medir o espaco do disco; seguindo." }

        New-Item -ItemType Directory -Path $Destino   -Force | Out-Null
        New-Item -ItemType Directory -Path $PastaTemp -Force | Out-Null
        Escrever-Log "=== Instalando o LibertyTube $Versao em $Destino ==="

        # ---- 1. Python privado do LibertyTube ----
        $pythonExe  = Join-Path $PastaPython "python.exe"
        $pythonwExe = Join-Path $PastaPython "pythonw.exe"

        if (-not (Test-Path $pythonExe)) {
            Status "Baixando o Python…" 5 "cerca de 25 MB" 1
            $instPy = Join-Path $PastaTemp "python-setup.exe"
            Baixar $PythonUrls $instPy "Python" 5 11

            Status "Instalando o Python…" 12 "só pro LibertyTube; não mexe no seu sistema" 1
            Rodar $instPy "/quiet TargetDir=`"$PastaPython`" InstallAllUsers=0 PrependPath=0 Include_launcher=0 Include_test=0 Include_doc=0 Include_tcltk=1 Shortcuts=0 AssociateFiles=0" "instalar Python"
        } else {
            Status "Python já configurado." 12 "" 1
        }
        if (-not (Test-Path $pythonExe)) { throw "O Python nao foi instalado corretamente em $PastaPython" }

        # ---- 2. Dependencias ----
        Status "Preparando o gerenciador de pacotes…" 18 "" 2
        Rodar $pythonExe "-m pip install --upgrade pip --no-warn-script-location --disable-pip-version-check --no-input --progress-bar off --timeout 60 --retries 5" "atualizar pip"

        Status "Instalando os componentes do app…" 25 "yt-dlp, Pillow e OpenCV" 2
        Rodar $pythonExe "-m pip install --upgrade yt-dlp pillow opencv-python-headless --no-warn-script-location --disable-pip-version-check --no-input --progress-bar off --timeout 60 --retries 5" "instalar yt-dlp, Pillow e OpenCV"

        Status "Instalando a IA de transcrição…" 35 "faster-whisper: ~400 MB, a etapa mais demorada" 3
        Rodar $pythonExe "-m pip install faster-whisper --no-warn-script-location --disable-pip-version-check --no-input --progress-bar off --timeout 60 --retries 5" "instalar faster-whisper"

        # ---- 3. FFmpeg ----
        New-Item -ItemType Directory -Path $PastaFfmpeg -Force | Out-Null
        $ffmpegDestino = Join-Path $PastaFfmpeg "ffmpeg.exe"
        if (-not (Test-Path $ffmpegDestino)) {
            Status "Baixando o FFmpeg…" 55 "motor de vídeo, cerca de 80 MB" 4
            $zipFf = Join-Path $PastaTemp "ffmpeg.zip"
            Baixar $FfmpegUrls $zipFf "FFmpeg" 55 62

            Status "Extraindo o FFmpeg…" 64 "" 4
            # So precisamos de dois arquivos de dentro do zip; extrair os
            # 80 MB inteiros demora e congela a janela.
            Add-Type -AssemblyName System.IO.Compression.FileSystem
            $zip = [System.IO.Compression.ZipFile]::OpenRead($zipFf)
            try {
                foreach ($nome in @("ffmpeg.exe", "ffprobe.exe")) {
                    $entrada = $zip.Entries | Where-Object { $_.Name -eq $nome } | Select-Object -First 1
                    if (-not $entrada) { throw "Nao encontrei o $nome dentro do pacote do FFmpeg." }
                    Detalhe "Extraindo $nome…"
                    [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entrada, (Join-Path $PastaFfmpeg $nome), $true)
                    Escrever-Log "Extraido: $nome"
                }
            } finally { $zip.Dispose() }
        } else {
            Status "FFmpeg já configurado." 62 "" 4
        }

        # ---- 4. Arquivos do LibertyTube ----
        Status "Instalando o LibertyTube…" 75 "copiando os arquivos do app" 5
        if (Test-Path $PastaApp) { Remove-Item $PastaApp -Recurse -Force -ErrorAction SilentlyContinue }
        New-Item -ItemType Directory -Path $PastaApp -Force | Out-Null
        Copy-Item -Path (Join-Path $PastaSrc "*")    -Destination $PastaApp -Recurse -Force
        New-Item -ItemType Directory -Path (Join-Path $PastaApp "assets") -Force | Out-Null
        Copy-Item -Path (Join-Path $PastaAssets "*") -Destination (Join-Path $PastaApp "assets") -Recurse -Force

        # Configuracao publica do backend: URL e chave anonima. Sessao,
        # senha e qualquer chave administrativa nunca entram no instalador.
        $backendModelo = Join-Path $PastaAssets "backend.json"
        $backendDestino = Join-Path $Destino "backend.json"
        if ((Test-Path $backendModelo) -and (-not (Test-Path $backendDestino))) {
            Copy-Item -Path $backendModelo -Destination $backendDestino -Force
            Escrever-Log "Configuracao publica do Supabase instalada."
        }

        # pasta dos videos, no disco que o cliente escolheu
        $pastaProjetos = $script:PastaVideos
        New-Item -ItemType Directory -Path (Join-Path $pastaProjetos "projetos") -Force | Out-Null
        Salvar-PastaDeVideos $pastaProjetos

        # ---- 5. Atalhos ----
        Status "Criando os atalhos…" 92 "área de trabalho e menu iniciar" 6
        $script:alvoPy = Join-Path $PastaApp "wintube.py"
        $script:pythonwExe = $pythonwExe
$iconeApp = Join-Path $PastaApp "assets\libertytube.ico"

        $areaTrabalho = [Environment]::GetFolderPath("Desktop")
Criar-Atalho (Join-Path $areaTrabalho "LibertyTube.lnk") $pythonwExe "`"$($script:alvoPy)`"" $PastaApp $iconeApp "LibertyTube - cortes automaticos pra YouTube, TikTok e Reels"

        $menuIniciar = Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs"
        New-Item -ItemType Directory -Path $menuIniciar -Force | Out-Null
Criar-Atalho (Join-Path $menuIniciar "LibertyTube.lnk") $pythonwExe "`"$($script:alvoPy)`"" $PastaApp $iconeApp "LibertyTube"

        $script:instalando = $false
        $script:eta = $null
         Status "Tudo pronto!" 100 "o LibertyTube já está na sua área de trabalho"
        Escrever-Log "=== Instalacao concluida ==="

        if (-not $Silencioso) {
            Marcar-Etapa 7                      # 7 = todas concluidas
            $relogio.Stop()
            $gasto = Tempo-Humano ((Get-Date) - $script:inicioInstalacao).TotalSeconds
            $lblTempo.Text = "instalado em $gasto"
            $lblTitulo.Text = "LibertyTube instalado!"
            $lblInfo.Text  = "O atalho já está na sua área de trabalho e no menu iniciar."
            $lblInfo2.Text = "Entre com o email e a senha da sua conta LibertyTube."
            $script:corBarra = $CorSucesso
            $lblPct.ForeColor = Cor $CorSucesso
            $barra.Invalidate()
            $script:textoBotao = "ABRIR O LIBERTYTUBE"
            $script:corBotao = $CorSucesso
            $script:botaoLigado = $true
            $botao.Invalidate()
        }
        $script:instalado = $true

        Remove-Item $PastaTemp -Recurse -Force -ErrorAction SilentlyContinue
        if ($Silencioso) {
            Write-Host ""
            Write-Host "LibertyTube instalado em: $PastaApp" -ForegroundColor Green
            Write-Host "Atalho: area de trabalho e menu iniciar"
        }
    }
    catch {
        $mensagem = $_.Exception.Message
        $script:instalando = $false
        Escrever-Log "ERRO: $mensagem"
        if (-not $Silencioso) { $relogio.Stop() }
        $lblStatus.Text = "Não consegui terminar a instalação."
        $lblDetalhe.Text = "Os detalhes estão em instalacao.log"
        $lblTempo.Text = ""
        $script:corBarra = $CorPerigo
        $lblPct.ForeColor = Cor $CorPerigo
        $barra.Invalidate()
        $script:textoBotao = "TENTAR DE NOVO"
        $script:corBotao = $CorPerigo
        $script:botaoLigado = $true
        $botao.Invalidate()
        if ($Silencioso) {
            Write-Host "ERRO: $mensagem" -ForegroundColor Red
            Write-Host "Log completo: $LogFile"
        } else {
            [System.Windows.Forms.MessageBox]::Show(
                "$mensagem`n`nO log completo esta em:`n$LogFile",
                "LibertyTube - erro na instalacao", "OK", "Error") | Out-Null
        }
    }
}

$botao.Add_Click({
    if (-not $script:botaoLigado) { return }
    if ($script:instalado) { Abrir-LibertyTube; $form.Close(); return }
    $script:botaoLigado = $false
    $script:textoBotao = "INSTALANDO…"
    $botao.Invalidate()
    Atualizar-Janela
    Executar-Instalacao
})

# Esc fecha (quando nao esta instalando)
$form.Add_KeyDown({
    param($s, $e)
    if ($e.KeyCode -eq "Escape" -and -not $script:instalando) { $form.Close() }
})

if ($Silencioso) {
    Write-Host "Instalando o LibertyTube $Versao (modo silencioso)..." -ForegroundColor Cyan
    Executar-Instalacao
    if (-not $script:instalado) { exit 1 }
    exit 0
} else {
    [void]$form.ShowDialog()
}
