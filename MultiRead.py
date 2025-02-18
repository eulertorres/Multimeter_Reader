import cv2
import numpy as np
import pyautogui
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button, CheckButtons
from datetime import datetime
import json
import time

# ================= Configurações Iniciais =================
# Parâmetros para captura da tela (região onde o display aparece)
origem_x = 1429
origem_y = 511
zoom = 0.972  # fator de escala

# Parâmetros para thresholds (pode ser ajustado via slider se necessário)
threshold_template = {"0": 100, "1": 100, "2": 100, "3": 100}

# Parâmetros de ajuste de imagem
brilho = 0
contraste = 1.0

# Listas para armazenar os dígitos identificados e os tempos
digitos_por_tempo = []
tempos = []

# Flags de medição e tracking
medicao_ativa = False
tracking_ativo = False

# ================= Variáveis de Tracking pelo Quadrado do Display =================
# Variáveis para selecionar a região do display (bounding box)
selecionando_borda = False
tracking_bbox_points = []  # pontos clicados pelo usuário (4 pontos)
tracking_bbox = None       # [x, y, w, h]
tracking_template = None   # imagem (em gray) do display extraída da região definida

# ================= Templates dos Dígitos =================
# Cada template: lista de 7 pontos na ordem (a,b,c,d,e,f,g)
template_d0 = []
template_d1 = []
template_d2 = []
template_d3 = []

# ================= Variáveis para ignorar dígitos =================
# dicionário para controle: se True, o dígito é ignorado (não lido)
ignore_digits = {"0": False, "1": False, "2": False, "3": False}

# ================= Funções de Configuração (Salvar/Carregar) =================
CONFIG_FILE = 'configuracoes.json'

def salvar_configuracoes():
    """Salva os parâmetros de captura e os templates atuais no JSON."""
    configuracoes = {
        'origem_x': origem_x,
        'origem_y': origem_y,
        'zoom': zoom,
        'template_d0': template_d0,
        'template_d1': template_d1,
        'template_d2': template_d2,
        'template_d3': template_d3
    }
    with open(CONFIG_FILE, 'w') as arquivo:
        json.dump(configuracoes, arquivo)
    print("Configurações salvas.")

def carregar_configuracoes():
    """Carrega os parâmetros e templates do arquivo JSON; se não existir, usa valores padrão."""
    global origem_x, origem_y, zoom, template_d0, template_d1, template_d2, template_d3
    try:
        with open(CONFIG_FILE, 'r') as arquivo:
            config = json.load(arquivo)
            origem_x = config.get('origem_x', origem_x)
            origem_y = config.get('origem_y', origem_y)
            zoom = config.get('zoom', zoom)
            template_d0[:] = config.get('template_d0', [])
            template_d1[:] = config.get('template_d1', [])
            template_d2[:] = config.get('template_d2', [])
            template_d3[:] = config.get('template_d3', [])
            print("Configurações carregadas.")
            return config
    except (FileNotFoundError, json.JSONDecodeError):
        print("Arquivo de configuração não encontrado. Usando valores padrão.")
        return {}

def restaurar_templates():
    """Restaura os templates para os valores salvos no JSON."""
    config = carregar_configuracoes()
    global template_d0, template_d1, template_d2, template_d3
    template_d0[:] = config.get('template_d0', [])
    template_d1[:] = config.get('template_d1', [])
    template_d2[:] = config.get('template_d2', [])
    template_d3[:] = config.get('template_d3', [])
    print("Templates restaurados para os valores salvos.")

# Carrega configurações (se existirem)
carregar_configuracoes()

# ================= Funções Auxiliares =================
def exportar_dados_para_txt(tempos, digitos_por_tempo, nome_arquivo="dados_digitos.txt"):
    with open(nome_arquivo, "w") as arquivo:
        for tempo, digito in zip(tempos, digitos_por_tempo):
            total_seconds = int(tempo.total_seconds())
            horas = total_seconds // 3600
            minutos = (total_seconds % 3600) // 60
            segundos = total_seconds % 60
            linha = f"{horas:02}:{minutos:02}:{segundos:02}, {digito}\n"
            arquivo.write(linha)
    print(f"Dados exportados para {nome_arquivo} com sucesso.")

def ajustar_brilho_contraste(img, brilho=0, contraste=1.0):
    nova = np.clip(contraste * img + brilho, 0, 255)
    return nova.astype(np.uint8)

def tratar_imagem(img, brilho=0, contraste=1.0):
    img_ajustada = ajustar_brilho_contraste(img, brilho, contraste)
    img_gray = cv2.cvtColor(img_ajustada, cv2.COLOR_BGR2GRAY)
    img_blur = cv2.GaussianBlur(img_gray, (5, 5), 0)
    img_eq = cv2.equalizeHist(img_blur)
    return img_eq

def calcular_luminosidade_ponto(img, ponto):
    h, w = img.shape[:2]
    x, y = int(ponto[0]), int(ponto[1])
    if 0 <= x < w and 0 <= y < h:
        return np.mean(img[y, x]) if len(img.shape)==3 else img[y, x]
    return 0

def identificar_digito(segmentos_str):
    mapa = {
        '1111110': 0, '0110000': 1, '1101101': 2,
        '1111001': 3, '0110011': 4, '1011011': 5,
        '1011111': 6, '1110000': 7, '1111111': 8,
        '1111011': 9,
    }
    return mapa.get(segmentos_str, '?')

def calcular_digito(img, template, threshold):
    ativos = []
    for ponto in template:
        lum = calcular_luminosidade_ponto(img, ponto)
        ativos.append(lum < threshold)
    return ''.join(['1' if a else '0' for a in ativos])

def desenhar_template(ax, template, cor='r', thresh=100, img_gray=None):
    if template:
        xs, ys = zip(*template)
        ax.plot(xs, ys, color=cor, marker='o', linestyle='-', markersize=6)
        if img_gray is not None:
            for (x, y) in template:
                val = calcular_luminosidade_ponto(img_gray, (x, y))
                ax.text(x, y, f"{val:.0f}", color=cor, fontsize=8, alpha=0.7)

# ================= Interface Unificada (Preview + Controles) =================
# Cria uma janela menor (por exemplo, 8x6 polegadas)
fig = plt.figure(figsize=(8,6))

# Área de preview (parte superior)
ax_preview = fig.add_axes([0.05, 0.35, 0.9, 0.6])
ax_preview.set_title("Preview da Captura")

# Sliders (na parte inferior esquerda)
ax_slider_zoom      = fig.add_axes([0.05, 0.28, 0.3, 0.03])
ax_slider_origem_x  = fig.add_axes([0.05, 0.24, 0.3, 0.03])
ax_slider_origem_y  = fig.add_axes([0.05, 0.20, 0.3, 0.03])
ax_slider_brilho    = fig.add_axes([0.05, 0.16, 0.3, 0.03])
ax_slider_contraste = fig.add_axes([0.05, 0.12, 0.3, 0.03])

slider_zoom      = Slider(ax_slider_zoom, 'Zoom', 0.5, 4.0, valinit=zoom)
slider_origem_x  = Slider(ax_slider_origem_x, 'Origem X', 950, 1920, valinit=origem_x)
slider_origem_y  = Slider(ax_slider_origem_y, 'Origem Y', 0, 900, valinit=origem_y)
slider_brilho    = Slider(ax_slider_brilho, 'Brilho', -100, 100, valinit=brilho)
slider_contraste = Slider(ax_slider_contraste, 'Contraste', 0.5, 3.0, valinit=contraste)

# Botões de ação (parte inferior central e direita)
ax_bt_start     = fig.add_axes([0.4, 0.20, 0.15, 0.06])
button_start    = Button(ax_bt_start, 'Iniciar/Parar')

ax_bt_tracking  = fig.add_axes([0.4, 0.12, 0.15, 0.06])
button_tracking = Button(ax_bt_tracking, 'Tracking: Off')

ax_bt_borda = fig.add_axes([0.4, 0.04, 0.15, 0.06])
button_borda = Button(ax_bt_borda, 'Selecionar Borda')

# Botões para posicionar os templates dos dígitos (lado direito)
ax_bt_d0 = fig.add_axes([0.6, 0.20, 0.12, 0.06])
ax_bt_d1 = fig.add_axes([0.73, 0.20, 0.12, 0.06])
ax_bt_d2 = fig.add_axes([0.6, 0.12, 0.12, 0.06])
ax_bt_d3 = fig.add_axes([0.73, 0.12, 0.12, 0.06])
button_d0 = Button(ax_bt_d0, 'Posicionar D0')
button_d1 = Button(ax_bt_d1, 'Posicionar D1')
button_d2 = Button(ax_bt_d2, 'Posicionar D2')
button_d3 = Button(ax_bt_d3, 'Posicionar D3')

# Caixa de seleção para ignorar dígitos (lado direito inferior)
ax_ignore = fig.add_axes([0.6, 0.04, 0.25, 0.12])
check_labels = ["Ignorar D0", "Ignorar D1", "Ignorar D2", "Ignorar D3"]
check_status = [ignore_digits["0"], ignore_digits["1"], ignore_digits["2"], ignore_digits["3"]]
check_ignore = CheckButtons(ax_ignore, check_labels, check_status)

def ignore_callback(label):
    # Atualiza o dicionário global ignore_digits conforme a caixa marcada/desmarcada
    if label == "Ignorar D0":
        ignore_digits["0"] = not ignore_digits["0"]
    elif label == "Ignorar D1":
        ignore_digits["1"] = not ignore_digits["1"]
    elif label == "Ignorar D2":
        ignore_digits["2"] = not ignore_digits["2"]
    elif label == "Ignorar D3":
        ignore_digits["3"] = not ignore_digits["3"]
    print("Ignore digits:", ignore_digits)
check_ignore.on_clicked(ignore_callback)

# ================= Atualização dos Parâmetros via Sliders =================
def update_params(val):
    global origem_x, origem_y, zoom, brilho, contraste
    origem_x = int(slider_origem_x.val)
    origem_y = int(slider_origem_y.val)
    zoom = slider_zoom.val
    brilho = slider_brilho.val
    contraste = slider_contraste.val
    salvar_configuracoes()
slider_zoom.on_changed(update_params)
slider_origem_x.on_changed(update_params)
slider_origem_y.on_changed(update_params)
slider_brilho.on_changed(update_params)
slider_contraste.on_changed(update_params)

# ================= Função de Captura =================
def capturar():
    largura = int(430 / zoom)
    altura  = int(300 / zoom)
    img = np.array(pyautogui.screenshot(region=(origem_x, origem_y, largura, altura)))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return img

# ================= Função de Identificação e Exibição =================
def identificar_e_exibir(current_time, frame_processado, frame_gray):
    # Para cada dígito, se não estiver ignorado, lê-o; caso contrário, exibe "-" como placeholder
    resultado = []
    # Dígito 0
    if ignore_digits["0"]:
        resultado.append("-")
    else:
        if len(template_d0) == 7:
            seg = calcular_digito(frame_processado, template_d0, threshold_template["0"])
            resultado.append(str(identificar_digito(seg)))
        else:
            resultado.append("?")
    # Dígito 1
    if ignore_digits["1"]:
        resultado.append("-")
    else:
        if len(template_d1) == 7:
            seg = calcular_digito(frame_processado, template_d1, threshold_template["1"])
            resultado.append(str(identificar_digito(seg)))
        else:
            resultado.append("?")
    # Dígito 2
    if ignore_digits["2"]:
        resultado.append("-")
    else:
        if len(template_d2) == 7:
            seg = calcular_digito(frame_processado, template_d2, threshold_template["2"])
            resultado.append(str(identificar_digito(seg)))
        else:
            resultado.append("?")
    # Dígito 3
    if ignore_digits["3"]:
        resultado.append("-")
    else:
        if len(template_d3) == 7:
            seg = calcular_digito(frame_processado, template_d3, threshold_template["3"])
            resultado.append(str(identificar_digito(seg)))
        else:
            resultado.append("?")
    ax_preview.set_title("Dígitos: " + " ".join(resultado))
    # Se nenhum dígito lido for "?" (erro), então concatena os dígitos não ignorados e registra
    if "?" not in resultado:
        # Concatena somente os dígitos que não são ignorados (ignorados serão pulados)
        numero = "".join([d for d in resultado if d != "-"])
        if numero != "":
            digitos_por_tempo.append(int(numero))
            tempos.append(current_time)

# ================= Modo de Posicionamento dos Templates =================
def ativar_template(digito):
    def func(event):
        global posicionando
        posicionando[str(digito)] = True
        if digito == 0:
            template_d0.clear()
        elif digito == 1:
            template_d1.clear()
        elif digito == 2:
            template_d2.clear()
        elif digito == 3:
            template_d3.clear()
        print(f"Posicionando dígito {digito}: clique nos 7 pontos (ordem a, b, c, d, e, f, g).")
    return func
button_d0.on_clicked(ativar_template(0))
button_d1.on_clicked(ativar_template(1))
button_d2.on_clicked(ativar_template(2))
button_d3.on_clicked(ativar_template(3))

# ================= Botão para Selecionar Borda do Display (para tracking) =================
def selecionar_borda(event):
    global selecionando_borda, tracking_bbox_points, tracking_bbox, tracking_template
    selecionando_borda = True
    tracking_bbox_points = []
    print("Selecione 4 pontos que definem as bordas do display (em ordem arbitrária).")
button_borda.on_clicked(selecionar_borda)

# ================= Toggle de Tracking Automático =================
def toggle_tracking(event):
    global tracking_ativo, tracking_template, tracking_bbox
    tracking_ativo = not tracking_ativo
    if tracking_ativo:
        button_tracking.label.set_text("Tracking: On")
        frame = capturar()
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        if tracking_bbox is not None:
            x, y, w, h = tracking_bbox
            tracking_template = frame_gray[y:y+h, x:x+w].copy()
        else:
            # Se a região de tracking não foi definida, usa o centro do frame
            h, w = frame_gray.shape
            tracking_bbox = (w//4, h//4, w//2, h//2)
            tracking_template = frame_gray[tracking_bbox[1]:tracking_bbox[1]+tracking_bbox[3],
                                            tracking_bbox[0]:tracking_bbox[0]+tracking_bbox[2]].copy()
        print("Tracking ativado.")
    else:
        button_tracking.label.set_text("Tracking: Off")
        tracking_template = None
        print("Tracking desativado.")
button_tracking.on_clicked(toggle_tracking)

# ================= Captura de Cliques na Área de Preview =================
def on_click(event):
    global selecionando_borda, tracking_bbox_points
    if event.inaxes != ax_preview:
        return
    pt = (event.xdata, event.ydata)
    # Se estiver selecionando a região de borda para tracking:
    if selecionando_borda:
        tracking_bbox_points.append(pt)
        ax_preview.plot(pt[0], pt[1], 'mo', markersize=8)
        fig.canvas.draw()
        print(f"Ponto para borda: ({pt[0]:.1f}, {pt[1]:.1f})")
        if len(tracking_bbox_points) == 4:
            # Calcula a bounding box: mínimo x, mínimo y, largura e altura
            xs = [p[0] for p in tracking_bbox_points]
            ys = [p[1] for p in tracking_bbox_points]
            x_min, y_min = min(xs), min(ys)
            x_max, y_max = max(xs), max(ys)
            tracking_bbox = (int(x_min), int(y_min), int(x_max - x_min), int(y_max - y_min))
            selecionando_borda = False
            print("Região de tracking definida:", tracking_bbox)
    else:
        # Se não estiver selecionando a borda, verifica se algum template está em modo de posicionamento
        for dig in posicionando:
            if posicionando[dig]:
                if dig == "0":
                    template_d0.append(pt)
                    ax_preview.plot(pt[0], pt[1], 'ro', markersize=6)
                    print(f"D0 - Ponto {len(template_d0)}: ({pt[0]:.1f}, {pt[1]:.1f})")
                    if len(template_d0) == 7:
                        posicionando["0"] = False
                        print("Template completo para D0.")
                        salvar_configuracoes()
                elif dig == "1":
                    template_d1.append(pt)
                    ax_preview.plot(pt[0], pt[1], 'go', markersize=6)
                    print(f"D1 - Ponto {len(template_d1)}: ({pt[0]:.1f}, {pt[1]:.1f})")
                    if len(template_d1) == 7:
                        posicionando["1"] = False
                        print("Template completo para D1.")
                        salvar_configuracoes()
                elif dig == "2":
                    template_d2.append(pt)
                    ax_preview.plot(pt[0], pt[1], 'bo', markersize=6)
                    print(f"D2 - Ponto {len(template_d2)}: ({pt[0]:.1f}, {pt[1]:.1f})")
                    if len(template_d2) == 7:
                        posicionando["2"] = False
                        print("Template completo para D2.")
                        salvar_configuracoes()
                elif dig == "3":
                    template_d3.append(pt)
                    ax_preview.plot(pt[0], pt[1], 'co', markersize=6)
                    print(f"D3 - Ponto {len(template_d3)}: ({pt[0]:.1f}, {pt[1]:.1f})")
                    if len(template_d3) == 7:
                        posicionando["3"] = False
                        print("Template completo para D3.")
                        salvar_configuracoes()
                fig.canvas.draw()
                break
fig.canvas.mpl_connect('button_press_event', on_click)

# ================= Botão Iniciar/Parar =================
time_zero = None
def iniciar_parar(event):
    global medicao_ativa, time_zero, digitos_por_tempo, tempos
    medicao_ativa = not medicao_ativa
    if medicao_ativa:
        time_zero = datetime.now()
        digitos_por_tempo.clear()
        tempos.clear()
        button_start.label.set_text("Parar")
        print("Medição iniciada.")
    else:
        exportar_dados_para_txt(tempos, digitos_por_tempo)
        print("Dados salvos em dados_digitos.txt")
        # Exibe o gráfico dos dígitos medidos
        plt.figure()
        plt.plot([t.total_seconds() for t in tempos], digitos_por_tempo, 'bo-')
        plt.xlabel('Tempo (s)')
        plt.ylabel('Número lido (concatenação dos dígitos não ignorados)')
        plt.title('Medição dos dígitos')
        plt.show()
        restaurar_templates()
        button_start.label.set_text("Iniciar/Parar")
        print("Templates restaurados para os valores originais.")
button_start.on_clicked(iniciar_parar)

# ================= Loop Principal =================
while True:
    frame = capturar()
    frame_processado = tratar_imagem(frame, brilho, contraste)
    frame_gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
    
    # Se o tracking estiver ativo e a região de bounding box foi definida, usa template matching
    if tracking_ativo and tracking_bbox is not None and tracking_template is not None:
        # Procura a melhor correspondência da região template na imagem atual
        res = cv2.matchTemplate(frame_gray, tracking_template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        # Calcula deslocamento (dx, dy) entre a posição atual da bbox e a nova posição
        x_old, y_old, w, h = tracking_bbox
        dx = max_loc[0] - x_old
        dy = max_loc[1] - y_old
        # Atualiza a bounding box e o template
        tracking_bbox = (max_loc[0], max_loc[1], w, h)
        tracking_template = frame_gray[max_loc[1]:max_loc[1]+h, max_loc[0]:max_loc[0]+w].copy()
        # Atualiza todos os templates (dígitos) somando o deslocamento detectado
        def atualizar_template(template):
            return [(p[0] + dx, p[1] + dy) for p in template]
        if template_d0: template_d0 = atualizar_template(template_d0)
        if template_d1: template_d1 = atualizar_template(template_d1)
        if template_d2: template_d2 = atualizar_template(template_d2)
        if template_d3: template_d3 = atualizar_template(template_d3)
    
    ax_preview.cla()
    ax_preview.imshow(frame_processado, cmap='gray')
    
    # Desenha os templates com seus valores de cinza (de forma sutil)
    desenhar_template(ax_preview, template_d0, cor='r', thresh=threshold_template["0"], img_gray=frame_processado)
    desenhar_template(ax_preview, template_d1, cor='g', thresh=threshold_template["1"], img_gray=frame_processado)
    desenhar_template(ax_preview, template_d2, cor='b', thresh=threshold_template["2"], img_gray=frame_processado)
    desenhar_template(ax_preview, template_d3, cor='c', thresh=threshold_template["3"], img_gray=frame_processado)
    
    if medicao_ativa:
        current_time = datetime.now() - time_zero
        identificar_e_exibir(current_time, frame_processado, frame_gray)
    
    fig.canvas.draw_idle()
    plt.pause(0.03)  # aproximadamente 30 FPS
