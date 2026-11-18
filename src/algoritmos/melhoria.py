"""Melhoria local de rotas: 2-opt."""


def dois_opt(rota, deposito, dist):
    caminho = [deposito] + rota + [deposito]
    melhorou = True

    while melhorou:
        melhorou = False

        for i in range(1, len(caminho)-2):
            for j in range(i+1, len(caminho)-1):

                antes = caminho[i-1]
                primeiro = caminho[i]
                ultimo = caminho[j]
                depois = caminho[j+1]

                atual = dist[antes][primeiro] + dist[ultimo][depois]
                nova = dist[antes][ultimo] + dist[primeiro][depois]

                if nova < atual:
                    caminho[i:j+1] = caminho[i:j+1][::-1]
                    melhorou = True

    return caminho[1:-1]
