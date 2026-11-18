"""Melhoria local de rotas: 2-opt."""


def dois_opt(rota, deposito, dist):
    caminho = [deposito] + rota + [deposito]
    melhorou = True

    while melhorou:
        melhorou = False

        for i in range(1, len(caminho)-2):
            for j in range(i+1, len(caminho)-1):

                # Custo real do trecho antes e depois de inverter caminho[i..j].
                # Com ruas de mão única, dist[a][b] != dist[b][a]: inverter o trecho muda
                # também os arcos de dentro, então não basta olhar as duas pontas
                # (isso fazia o laço nunca terminar). Com custos simétricos, a decisão
                # é a mesma da fórmula clássica.
                trecho = caminho[i-1:j+2]
                invertido = [trecho[0]] + trecho[1:-1][::-1] + [trecho[-1]]
                atual = sum(dist[a][b] for a, b in zip(trecho, trecho[1:]))
                nova = sum(dist[a][b] for a, b in zip(invertido, invertido[1:]))

                if nova < atual - 1e-9:
                    caminho[i-1:j+2] = invertido
                    melhorou = True

    return caminho[1:-1]
