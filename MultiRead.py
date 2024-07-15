import cv2
import numpy as np
import pyautogui
import matplotlib.pyplot as plt
import time
from datetime import datetime
import matplotlib.dates as mdates
from matplotlib.widgets import Slider
import json
from matplotlib.widgets import Button

# Configuração inicial
desconsiderar_primeiro_digito = True
desconsiderar_segundo_digito = False


# Definições iniciais
threshold_d1 = 40
threshold_d2 = 60   
threshold_d3 = 60
threshold_d4 = 60

offset_d1 = 105
offset_d2 = offset_d1 * 2
offset_d3 = offset_d1 * 3
offsety_d1 = 1
offsety_d2 = offsety_d1 * 2
offsety_d3 = offsety_d1 * 3
origem_x = 1429
origem_y = 511
zoom = 0.972
digitos_por_tempo = []
tempos = []

achatado = 0.05

# Configuração para modo interativo e criação das figuras
plt.ion()
fig, (ax, ax_digitos) = plt.subplots(2, 1, figsize=(9, 6))
fig_sliders = plt.figure(figsize=(5, 3))  # Figura para os sliders
plt.subplots_adjust(left=0.25, bottom=0.4)

# Sliders
ax_slider_zoom = fig_sliders.add_axes([0.25, 0.9, 0.65, 0.03], label="Zoom")
ax_slider_origem_x = fig_sliders.add_axes([0.25, 0.8, 0.65, 0.03], label="Origem Y")
ax_slider_origem_y = fig_sliders.add_axes([0.25, 0.7, 0.65, 0.03], label="Origem X")
ax_slider_brilho = fig_sliders.add_axes([0.25, 0.6, 0.65, 0.03], label="Brilho")
ax_slider_contraste = fig_sliders.add_axes([0.25, 0.5, 0.65, 0.03], label="Contraste")
slider_brilho = Slider(ax_slider_brilho, 'Brilho', -100, 100, valinit=0)
slider_contraste = Slider(ax_slider_contraste, 'Contraste', 0.5, 3.0, valinit=1.0)

# Variáveis globais para brilho e contraste
brilho = 0
contraste = 1.0

inicio = False



# Função para iniciar o processo
def iniciar(event):
    global inicio
    inicio = not inicio
    print("Processo iniciado.")
    
def salvar_configuracoes():
    configuracoes = {
        'origem_x': origem_x,
        'origem_y': origem_y,
        'zoom': zoom,
    }
    with open('configuracoes.json', 'w') as arquivo:
        json.dump(configuracoes, arquivo)

def carregar_configuracoes():
    try:
        with open('configuracoes.json', 'r') as arquivo:
            configuracoes = json.load(arquivo)
            return configuracoes
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            'origem_x': 1257,  # Valor padrão
            'origem_y': 500,   # Valor padrão
            'zoom': 1.015,     # Valor padrão
        }

def exportar_dados_para_txt(tempos, digitos_por_tempo, nome_arquivo="dados_digitos.txt"):
    with open(nome_arquivo, "w") as arquivo:
        for tempo, digito in zip(tempos, digitos_por_tempo):
            # Formatação manual de datetime.timedelta para HH:MM:SS
            total_seconds = int(tempo.total_seconds())
            horas = total_seconds // 3600
            minutos = (total_seconds % 3600) // 60
            segundos = total_seconds % 60
            data_hora_formatada = f"{horas:02}:{minutos:02}:{segundos:02}"
            
            linha = f"{data_hora_formatada}, {digito}\n"
            arquivo.write(linha)
    print(f"Dados exportados para {nome_arquivo} com sucesso.")

    # Fecha todas as figuras exceto a que mostra os dígitos identificados com o tempo
    plt.close(fig)
    plt.close(fig_sliders)

def calcular_luminosidade_ponto(img, ponto):
    altura, largura = img.shape
    x, y = int(ponto[0]), int(ponto[1])
    if 0 <= x < largura and 0 <= y < altura:
        rgb = img[y, x]
        return np.mean(rgb)
    else:
        return 0

def update(val):
    global origem_x, origem_y, zoom, brilho, contraste
    origem_x = int(slider_origem_x.val)
    origem_y = int(slider_origem_y.val)
    zoom = slider_zoom.val
    brilho = slider_brilho.val
    contraste = slider_contraste.val
    salvar_configuracoes()

def identificar_digito(segmentos_str):
    segmentos_para_numero = {
        '1111110': 0,
        '0110000': 1,
        '1101101': 2,
        '1111001': 3,
        '0110011': 4,
        '1011011': 5,
        '1011111': 6,
        '1110000': 7,
        '1111111': 8,
        '1111011': 9,
    }
    return segmentos_para_numero.get(segmentos_str, '?')

def tratar_imagem(img, brilho=0, contraste=1.0):
    img_ajustada = ajustar_brilho_contraste(img, brilho, contraste)
    img_gray = cv2.cvtColor(img_ajustada, cv2.COLOR_BGR2GRAY)
    img_blur = cv2.GaussianBlur(img_gray, (5, 5), 0)
    img_eq = cv2.equalizeHist(img_blur)
    return img_eq

def ajustar_brilho_contraste(img, brilho=0, contraste=1.0):
    nova_img = np.clip(contraste * img + brilho, 0, 255)
    return nova_img.astype(np.uint8)

def update_template(ax, img, current_time):
    global zoom, origem_x, origem_y, threshold_d1, threshold_d2, threshold_d3, threshold_d4, desconsiderar_primeiro_digito, desconsiderar_segundo_digito

    def desenhar(x_offset, y_offset, zoom, threshold):
        pontos_base = [
            ((48 + x_offset) / zoom, (65 + y_offset) / zoom),  # Segmento a
            ((78 + x_offset) / zoom, (118 + y_offset) / zoom), # Segmento b
            ((69 + x_offset) / zoom, (189 + y_offset) / zoom), # Segmento c
            ((38 + x_offset) / zoom, (240 + y_offset) / zoom), # Segmento d
            ((12+ x_offset) / zoom, (189 + y_offset) / zoom), # Segmento e
            ((18 + x_offset) / zoom, (103 + y_offset) / zoom), # Segmento f
            ((43 + x_offset) / zoom, (152 + y_offset) / zoom), # Segmento g
        ]

        for ponto in pontos_base:
            ax.plot(ponto[0], ponto[1], 'ro', markersize=5)
            #luminosidade = calcular_luminosidade_ponto(img, ponto)
            #ax.text(ponto[0], ponto[1], f'{luminosidade:.0f}', color='yellow', fontsize=10)
            
    if not desconsiderar_primeiro_digito:
        d1_segs = desenhar(0, 0, zoom, threshold_d1)

    if not desconsiderar_segundo_digito or not desconsiderar_primeiro_digito:
        d2_segs = desenhar(offset_d1, offsety_d1, zoom, threshold_d2)

    d3_segs = desenhar(offset_d2, offsety_d2, zoom, threshold_d3)
    d4_segs = desenhar(offset_d3, offsety_d3, zoom, threshold_d4)

    plt.draw()

def calcular_digito(img, x_offset, y_offset, zoom, threshold):
    pontos_base = [
        ((48 + x_offset) / zoom, (65 + y_offset) / zoom),  # Segmento a
        ((78 + x_offset) / zoom, (118 + y_offset) / zoom), # Segmento b
        ((69 + x_offset) / zoom, (189 + y_offset) / zoom), # Segmento c
        ((38 + x_offset) / zoom, (240 + y_offset) / zoom), # Segmento d
        ((12+ x_offset) / zoom, (189 + y_offset) / zoom), # Segmento e
        ((18 + x_offset) / zoom, (103 + y_offset) / zoom), # Segmento f
        ((43 + x_offset) / zoom, (152 + y_offset) / zoom), # Segmento g
    ]
    segmentos_ativos = []
    for ponto in pontos_base:
        ax.plot(ponto[0], ponto[1], 'ro', markersize=5)
        luminosidade = calcular_luminosidade_ponto(img, ponto)
        ax.text(ponto[0], ponto[1], f'{luminosidade:.0f}', color='yellow', fontsize=10)
        segmentos_ativos.append(luminosidade < threshold)
    segmentos_str = ''.join(['1' if seg else '0' for seg in segmentos_ativos])
    return segmentos_str 

def identificar(ax, img, current_time):
    global zoom, origem_x, origem_y, threshold_d1, threshold_d2, threshold_d3, threshold_d4, desconsiderar_primeiro_digito, desconsiderar_segundo_digito

    digitos_identificados = []
    if not desconsiderar_primeiro_digito:
        d1_segs = calcular_digito(img, 0, 0, zoom, threshold_d1)
        digitos_identificados.append(identificar_digito(d1_segs))

    if not desconsiderar_segundo_digito or not desconsiderar_primeiro_digito:
        d2_segs = calcular_digito(img, offset_d1, offsety_d1, zoom, threshold_d2)
        digitos_identificados.append(identificar_digito(d2_segs))

    d3_segs = calcular_digito(img, offset_d2, offsety_d2, zoom, threshold_d3)
    d4_segs = calcular_digito(img, offset_d3, offsety_d3, zoom, threshold_d4)
    digitos_identificados.extend([identificar_digito(d3_segs), identificar_digito(d4_segs)])

    if '?' not in digitos_identificados:
        digitos_juntos = int(''.join(map(str, digitos_identificados)))
        digitos_por_tempo.append(digitos_juntos)
        tempos.append(current_time)
    else:
        digitos_por_tempo.append(0)
        tempos.append(current_time)

    tempos_em_segundos = [tempo.total_seconds() for tempo in tempos]
    ax_digitos.clear()
    ax_digitos.plot(tempos_em_segundos, digitos_por_tempo, 'bo-')
    plt.xticks(rotation=45)
    #ax_digitos.autofmt_xdate()
    #plt.xlabel('Tempo (s)')
    #plt.ylabel('Dígitos Identificados')
    plt.draw()

def capturar(ax):
    global origem_x, origem_y, zoom, brilho, contraste
    largura_captura = int(430 / zoom)
    altura_captura = int(300 / zoom)
    img = np.array(pyautogui.screenshot(region=(origem_x, origem_y, largura_captura, altura_captura)))
    img = img[:, :, ::-1]
    if inicio:
        img_tratada = tratar_imagem(img, brilho, contraste)
        ax.clear()
        ax.imshow(img_tratada, cmap='gray')
        ax.set_title('Captura de tela atualizada')
    else:
        ax.clear()
        ax.imshow(img, cmap='gray')
        ax.set_title('Captura de tela inicial')
    return img_tratada if inicio else img

def tratar_offsets(arquivo_entrada, arquivo_saida, thr):
    with open(arquivo_entrada, 'r') as entrada:
        linhas = entrada.readlines()
    
    temperaturas = []
    for linha in linhas:
        partes = linha.strip().split(', ')
        data_hora = partes[0]
        temperatura = int(partes[1])
        temperaturas.append((data_hora, temperatura))
    
    # Remover as últimas linhas com o mesmo valor
    while temperaturas and temperaturas[-1][1] == temperaturas[-2][1]:
        temperaturas.pop()
    
    temperaturas_tratadas = []  # Lista para armazenar as temperaturas tratadas
    
    for i in range(2, len(temperaturas)):
        temp_atual = temperaturas[i][1]
        temp_anterior = temperaturas[i-1][1]
        
        # Verifica se a mudança é maior que o threshold
        if abs(temp_atual - temp_anterior) > thr:
            # Calcula a média dos dois valores anteriores válidos
            media = (temperaturas[i-2][1] + temperaturas[i-1][1]) // 2
            temperaturas[i] = (temperaturas[i][0], media)
    
    with open(arquivo_saida, 'w') as saida:
        for data_hora, temperatura in temperaturas:
            saida.write(f'{data_hora}, {temperatura}\n')
            temperaturas_tratadas.append(temperatura)  # Adiciona a temperatura tratada à lista
    # Plotando o gráfico dos resultados finais
    plt.figure(figsize=(10, 5))  # Define o tamanho do gráfico
    plt.plot(temperaturas_tratadas, marker='o', linestyle='-', color='b')  # Plota as temperaturas tratadas
    plt.title("Temperaturas Tratadas")
    plt.xlabel("Contagem dos Pontos")
    plt.ylabel("Temperatura")
    plt.grid(True)  # Adiciona uma grade ao gráfico para melhor visualização
    plt.show()  # Exibe o gráfico

    # Pausa o programa até que uma tecla seja pressionada no console
    input("Pressione qualquer tecla para continuar...")


#Início do programa -----------------------------------------------------------------------------------------------------------------

#Recupera configurações anteriores
configuracoes = carregar_configuracoes()
origem_x = configuracoes['origem_x']
origem_y = configuracoes['origem_y']
zoom = configuracoes['zoom']

#Cria os sliders
slider_origem_x = Slider(ax_slider_origem_x, 'Origem X', 950, 1920, valinit=origem_x)
slider_origem_y = Slider(ax_slider_origem_y, 'Origem Y', 0, 900, valinit=origem_y)
slider_zoom = Slider(ax_slider_zoom, 'Zoom', 0.5, 4.0, valinit=zoom)

slider_origem_x.on_changed(update)
slider_origem_y.on_changed(update)
slider_zoom.on_changed(update)
slider_brilho.on_changed(update)
slider_contraste.on_changed(update)

# Adicionando o botão
ax_button = fig_sliders.add_axes([0.25, 0.4, 0.5, 0.1])  # Ajuste a posição e tamanho conforme necessário
button = Button(ax_button, 'Iniciar/Parar')
button.on_clicked(iniciar)

time_zero = datetime.now()

while inicio == False:
    current_time = datetime.now() - time_zero
    update_template(ax, capturar(ax), current_time)
    
    # Formatação do tempo para minutos, segundos e milissegundos
    #total_seconds = current_time.total_seconds()
    #minutes = int(total_seconds // 60)
    #seconds = int(total_seconds % 60)
    #milliseconds = int((total_seconds % 1) * 1000)
    
    #ax.set_title(f'Atualizado em: {minutes:02}:{seconds:02}:{milliseconds:03}')
    
    fig.canvas.draw()
    fig.canvas.flush_events()
    plt.pause(0.01)  # Pequena pausa para atualização
    
d3_segs = '0000000'
d4_segs = '0000000'
print("Coloque o vídeo no final, usando o VLC")

while d3_segs != '1111111':
    d3_segs = calcular_digito(capturar(ax), offset_d2, offsety_d2, zoom, threshold_d3)
    #d4_segs = calcular_digito(capturar(ax), offset_d3, offsety_d3, zoom, threshold_d4)
    #print(d3_segs)
    time.sleep(0.1)

print("Inicie o vídeo")
while d3_segs == '1111111':
    d3_segs = calcular_digito(capturar(ax), offset_d2, offsety_d2, zoom, threshold_d3)
    #d4_segs = calcular_digito(capturar(ax), offset_d3, offsety_d3, zoom, threshold_d4)
    #print(d3_segs)
    time.sleep(0.1)

#fig_digitos, ax_digitos = plt.subplots()  # Plotagem dos dígitos ao longo do tempo
#ax_digitos.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))

while inicio:
    current_time = datetime.now() - time_zero
    identificar(ax, capturar(ax), current_time)
    fig.canvas.draw()
    fig.canvas.flush_events()
    plt.pause(0.01)  # Pequena pausa para atualização

exportar_dados_para_txt(tempos, digitos_por_tempo)
print('Acabou :D Agora bora filtrar essa beleza')
    
arquivo_entrada = 'dados_digitos.txt'
arquivo_saida = 'temperaturas_corrigidas.txt'
tratar_offsets(arquivo_entrada, arquivo_saida, 9)
#tratar_offsets(arquivo_entrada, arquivo_saida, 3)
