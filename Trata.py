import matplotlib.pyplot as plt

def tratar_offsets(arquivo_entrada, arquivo_saida, thr):
    with open(arquivo_entrada, 'r') as entrada:
        linhas = entrada.readlines()
    
    temperaturas = []
    for linha in linhas:
        partes = linha.strip().split(', ')
        data_hora = partes[0]
        temperatura = int(partes[1])
        temperaturas.append((data_hora, temperatura))
    
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

arquivo_entrada = 'dados_digitos.txt'
arquivo_saida = 'temperaturas_corrigidas.txt'
tratar_offsets(arquivo_entrada, arquivo_saida, 22)
#tratar_offsets(arquivo_entrada, arquivo_saida, 3)
