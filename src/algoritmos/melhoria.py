"""Melhoria local de rotas: 2-opt."""

from .construcao import _atrasos_rota


def dois_opt(rota, deposito, dist, tempo=None, janela=None, inicio_expediente=480, tempo_servico=10):
    caminho = [deposito] + rota + [deposito]
    melhorou = True

    while melhorou:
        melhorou = False

        for i in range(1, len(caminho)-2):
            for j in range(i+1, len(caminho)-1):
                trecho = caminho[i - 1:j + 2]
                invertido = [trecho[0]] + trecho[1:-1][::-1] + [trecho[-1]]
                atual = sum(dist[a][b] for a, b in zip(trecho, trecho[1:]))
                nova = sum(dist[a][b]
                           for a, b in zip(invertido, invertido[1:]))

                if nova < atual - 1e-9:
                    novo_caminho = caminho[:i - 1] + \
                        invertido + caminho[j + 2:]
                    if tempo is not None and janela is not None:
                        if _atrasos_rota(novo_caminho[1:-1], deposito, tempo, janela, inicio_expediente, tempo_servico) > \
                           _atrasos_rota(caminho[1:-1], deposito, tempo, janela, inicio_expediente, tempo_servico):
                            continue

                    caminho = novo_caminho
                    melhorou = True

    return caminho[1:-1]
