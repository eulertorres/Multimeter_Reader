import cv2
import numpy as np
import pyautogui
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import time
from datetime import datetime
import json
from matplotlib.widgets import Slider, Button

# ================= Configurações Iniciais =================
# Parâmetros para offsets caso não se utilize posicionamento manual para os demais dígitos
offset_d1 = 105
offset_d2 = offset_d1 * 2
offset_d3 = offset_d1 * 3
offsety_d1 = 1
offsety_d2 = offsety_d1 * 2
offsety_d3 = offsety_d1 * 3

# Parâmetros para captura da tela
origem_x = 1429
origem_y = 511
zoom = 0.972

# Thresholds para identificação (ajuste conforme necessário)
threshold_template = {"0": 100, "1": 100, "2": 100, "3": 100}

# Listas para armazenar os dígitos identificados e os tempos
digitos_por_tempo = []
tempos = []

# Parâmetros de ajuste de imagem
brilho = 0
contraste = 1.0

# Flag para controle da medição
inicio = False

# ================= Templates dos Dígitos =================
# Cada template é uma lista de 7 pontos (ordem: a, b, c, d, e, f, g)
template_d0 = []
template_d1 = []
template_d2 = []
template_d3 = []

# Flags para controle do posicionamento dos templates
posicionando = {"0": False, "1": False, "2": False, "3": False}

# Flag para ignorar dígitos: "nenhum", "d3" ou "d2_d3"
ignorar = "nenhum"

# ================= Funções Auxiliares =================
def salvar_configuracoes():
    configuracoes = {'origem_x': origem_x, 'origem_y': origem_y, 'zoom': zoom}
    with open('configuracoes.json', 'w') as arquivo:
        json.dump(configuracoes, arquivo)

def carregar_configuracoes():
    try:
        with open('configuracoes.json', 'r') as arquivo:
            return json.load(arquivo)
    except (FileNotFoundError, json.JSONDecodeError):
        return {'origem_x': 1257, 'origem_y': 500, 'zoom': 1.015}

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
    nova_img = np.clip(contraste * img + brilho, 0, 255)
    return nova_img.astype(np.uint8)

def tratar_imagem(img, brilho=0, contraste=1.0):
    img_ajustada = ajustar_brilho_contraste(img, brilho, contraste)
    img_gray = cv2.cvtColor(img_ajustada, cv2.COLOR_BGR2GRAY)
    img_blur = cv2.GaussianBlur(img_gray, (5, 5), 0)
    img_eq = cv2.equalizeHist(img_blur)
    return img_eq

def calcular_luminosidade_ponto(img, ponto):
    altura, largura = img.shape[:2]
    x, y = int(ponto[0]), int(ponto[1])
    if 0 <= x < largura and 0 <= y < altura:
        if len(img.shape) == 3:
            return np.mean(img[y, x])
        else:
            return img[y, x]
    return 0

def identificar_digito(segmentos_str):
    mapa = {
        '1111110': 0, '0110000': 1, '1101101': 2, '1111001': 3,
        '0110011': 4, '1011011': 5, '1011111': 6, '1110000': 7,
        '1111111': 8, '1111011': 9,
    }
    return mapa.get(segmentos_str, '?')

def calcular_digito(img, template, threshold):
    segmentos_ativos = []
    for ponto in template:
        # Calcula o valor de cinza no ponto e compara com o threshold
        lum = calcular_luminosidade_ponto(img, ponto)
        segmentos_ativos.append(lum < threshold)
    return ''.join(['1' if seg else '0' for seg in segmentos_ativos])

# ================= Interface Unificada =================
# Cria uma figura unificada usando GridSpec para dividir a área de preview e os controles
fig = plt.figure(figsize=(12, 8))
gs = gridspec.GridSpec(2, 1, height_ratios=[4, 1])
ax_preview = fig.add_subplot(gs[0])
ax_preview.set_title("Preview e Medição")
# Área dos controles abaixo será definida por botões e sliders usando fig.add_axes()

# Sliders e botões serão posicionados na parte inferior
# Exemplo de posicionamento:
slider_origem_x_ax = fig.add_axes([0.05, 0.15, 0.2, 0.04])
slider_origem_y_ax = fig.add_axes([0.05, 0.10, 0.2, 0.04])
slider_zoom_ax      = fig.add_axes([0.05, 0.05, 0.2, 0.04])
slider_brilho_ax    = fig.add_axes([0.30, 0.15, 0.2, 0.04])
slider_contraste_ax = fig.add_axes([0.30, 0.10, 0.2, 0.04])

button_start_ax     = fig.add_axes([0.60, 0.10, 0.15, 0.08])
button_ignore_ax    = fig.add_axes([0.77, 0.10, 0.20, 0.08])

# Botões para posicionar templates dos dígitos (0 a 3)
button_template0_ax = fig.add_axes([0.60, 0.01, 0.1, 0.06])
button_template1_ax = fig.add_axes([0.71, 0.01, 0.1, 0.06])
button_template2_ax = fig.add_axes([0.82, 0.01, 0.1, 0.06])
button_template3_ax = fig.add_axes([0.93, 0.01, 0.1, 0.06])

# Criação dos sliders
slider_origem_x = Slider(slider_origem_x_ax, 'Origem X', 950, 1920, valinit=origem_x)
slider_origem_y = Slider(slider_origem_y_ax, 'Origem Y', 0, 900, valinit=origem_y)
slider_zoom = Slider(slider_zoom_ax, 'Zoom', 0.5, 4.0, valinit=zoom)
slider_brilho = Slider(slider_brilho_ax, 'Brilho', -100, 100, valinit=brilho)
slider_contraste = Slider(slider_contraste_ax, 'Contraste', 0.5, 3.0, valinit=contraste)

# Criação dos botões
button_start = Button(button_start_ax, 'Iniciar')
button_ignore = Button(button_ignore_ax, 'Ignorar: Nenhum')
button_template0 = Button(button_template0_ax, 'Dígito 0')
button_template1 = Button(button_template1_ax, 'Dígito 1')
button_template2 = Button(button_template2_ax, 'Dígito 2')
button_template3 = Button(button_template3_ax, 'Dígito 3')

def update_sliders(val):
    global origem_x, origem_y, zoom, brilho, contraste
    origem_x = int(slider_origem_x.val)
    origem_y = int(slider_origem_y.val)
    zoom = slider_zoom.val
    brilho = slider_brilho.val
    contraste = slider_contraste.val
    salvar_configuracoes()

slider_origem_x.on_changed(update_sliders)
slider_origem_y.on_changed(update_sliders)
slider_zoom.on_changed(update_sliders)
slider_brilho.on_changed(update_sliders)
slider_contraste.on_changed(update_sliders)

def toggle_medicao(event):
    global inicio, time_zero
    inicio = not inicio
    if inicio:
        button_start.label.set_text("Parar")
        print("Medição iniciada.")
        time_zero = datetime.now()
    else:
        button_start.label.set_text("Iniciar")
        exportar_dados_para_txt(tempos, digitos_por_tempo)
        # Exibe o gráfico dos resultados
        plt.figure()
        plt.plot([t.total_seconds() for t in tempos], digitos_por_tempo, 'bo-')
        plt.xlabel('Tempo (s)')
        plt.ylabel('Dígito')
        plt.title('Medição dos dígitos')
        plt.show()
        print("Medição parada.")
button_start.on_clicked(toggle_medicao)

def alternar_ignorar(event):
    global ignorar
    if ignorar == "nenhum":
        ignorar = "d3"
        button_ignore.label.set_text("Ignorar: Dígito 3")
    elif ignorar == "d3":
        ignorar = "d2_d3"
        button_ignore.label.set_text("Ignorar: Dígitos 2 e 3")
    else:
        ignorar = "nenhum"
        button_ignore.label.set_text("Ignorar: Nenhum")
    print("Opção de ignorar:", ignorar)
button_ignore.on_clicked(alternar_ignorar)

def ativar_template(digito):
    def func(event):
        global template_d0, template_d1, template_d2, template_d3
        posicionando[str(digito)] = True
        # Reinicia o template para o dígito selecionado
        if digito == 0:
            template_d0.clear()
        elif digito == 1:
            template_d1.clear()
        elif digito == 2:
            template_d2.clear()
        elif digito == 3:
            template_d3.clear()
        print(f"Posicionando dígito {digito}: Clique nos 7 pontos na ordem (a,b,c,d,e,f,g).")
    return func

button_template0.on_clicked(ativar_template(0))
button_template1.on_clicked(ativar_template(1))
button_template2.on_clicked(ativar_template(2))
button_template3.on_clicked(ativar_template(3))

# Função para capturar cliques na área de preview e registrar pontos para o template em posicionamento
def on_click(event):
    if event.inaxes != ax_preview:
        return
    for dig in posicionando:
        if posicionando[dig]:
            ponto = (event.xdata, event.ydata)
            if dig == "0":
                template_d0.append(ponto)
                ax_preview.plot(event.xdata, event.ydata, 'ro', markersize=8)
                print(f"Dígito 0 - Ponto {len(template_d0)}: ({event.xdata:.1f}, {event.ydata:.1f})")
                if len(template_d0) == 7:
                    posicionando["0"] = False
                    print("Template completo para dígito 0.")
            elif dig == "1":
                template_d1.append(ponto)
                ax_preview.plot(event.xdata, event.ydata, 'go', markersize=8)
                print(f"Dígito 1 - Ponto {len(template_d1)}: ({event.xdata:.1f}, {event.ydata:.1f})")
                if len(template_d1) == 7:
                    posicionando["1"] = False
                    print("Template completo para dígito 1.")
            elif dig == "2":
                template_d2.append(ponto)
                ax_preview.plot(event.xdata, event.ydata, 'bo', markersize=8)
                print(f"Dígito 2 - Ponto {len(template_d2)}: ({event.xdata:.1f}, {event.ydata:.1f})")
                if len(template_d2) == 7:
                    posicionando["2"] = False
                    print("Template completo para dígito 2.")
            elif dig == "3":
                template_d3.append(ponto)
                ax_preview.plot(event.xdata, event.ydata, 'co', markersize=8)
                print(f"Dígito 3 - Ponto {len(template_d3)}: ({event.xdata:.1f}, {event.ydata:.1f})")
                if len(template_d3) == 7:
                    posicionando["3"] = False
                    print("Template completo para dígito 3.")
            fig.canvas.draw()
            break

fig.canvas.mpl_connect('button_press_event', on_click)

# ================= Função de Captura e Processamento =================
def capturar():
    global origem_x, origem_y, zoom, brilho, contraste
    largura = int(430 / zoom)
    altura = int(300 / zoom)
    img = np.array(pyautogui.screenshot(region=(origem_x, origem_y, largura, altura)))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    if inicio:
        return tratar_imagem(img, brilho, contraste)
    return img

def identificar(img, current_time):
    global template_d0, template_d1, template_d2, template_d3, ignorar
    digitos_identificados = []
    # Dígito 0
    if template_d0 and len(template_d0) == 7:
        seg0 = calcular_digito(img, template_d0, threshold_template["0"])
        dig0 = identificar_digito(seg0)
    else:
        dig0 = '?'
    digitos_identificados.append(dig0)
    
    # Dígito 1
    if template_d1 and len(template_d1) == 7:
        seg1 = calcular_digito(img, template_d1, threshold_template["1"])
        dig1 = identificar_digito(seg1)
    else:
        dig1 = '?'
    digitos_identificados.append(dig1)
    
    # Dígito 2 (verifica opção de ignorar)
    if ignorar == "d2_d3":
        digitos_identificados.append('?')
    else:
        if template_d2 and len(template_d2) == 7:
            seg2 = calcular_digito(img, template_d2, threshold_template["2"])
            dig2 = identificar_digito(seg2)
        else:
            dig2 = '?'
        digitos_identificados.append(dig2)
    
    # Dígito 3 (verifica opção de ignorar)
    if ignorar in ["d3", "d2_d3"]:
        digitos_identificados.append('?')
    else:
        if template_d3 and len(template_d3) == 7:
            seg3 = calcular_digito(img, template_d3, threshold_template["3"])
            dig3 = identificar_digito(seg3)
        else:
            dig3 = '?'
        digitos_identificados.append(dig3)
    
    # Armazena os dígitos se nenhum estiver com erro
    if '?' not in digitos_identificados:
        digitos_juntos = int(''.join(map(str, digitos_identificados)))
        digitos_por_tempo.append(digitos_juntos)
        tempos.append(current_time)
    else:
        digitos_por_tempo.append(0)
        tempos.append(current_time)
    
    ax_preview.set_title("Dígitos: " + " ".join(map(str, digitos_identificados)))

# ================= Loop Principal de Atualização =================
# Atualização contínua da área de preview
while True:
    img = capturar()
    ax_preview.clear()
    ax_preview.imshow(img, cmap='gray')
    
    # Desenha os templates (se definidos) com os valores de cinza próximos a cada ponto
    def desenhar_template(template, cor):
        if template and len(template) > 0:
            xs, ys = zip(*template)
            ax_preview.plot(xs, ys, marker='o', linestyle='-', color=cor, markersize=8)
            # Mostra o valor de cinza de cada ponto (em fonte pequena)
            for (x, y) in template:
                val = calcular_luminosidade_ponto(img, (x, y))
                ax_preview.text(x, y, f"{val:.0f}", color=cor, fontsize=7, ha='left', va='bottom', alpha=0.7)
    desenhar_template(template_d0, 'r')
    desenhar_template(template_d1, 'g')
    desenhar_template(template_d2, 'b')
    desenhar_template(template_d3, 'c')
    
    # Se estiver medindo, processa e identifica os dígitos
    if inicio:
        current_time = datetime.now() - time_zero
        identificar(img, current_time)
    
    fig.canvas.draw_idle()
    plt.pause(0.02)
