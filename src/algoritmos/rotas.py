from src.grafo import Grafo, matriz_custos
from .melhoria import dois_opt
from .construcao import vizinho_mais_proximo


INICIO_EXPEDIENTE = 480
TEMPO_SERVICO = 10
ALGORITMOS = {"nn": "Vizinho mais próximo"}


def calcular_horarios(rota, deposito, dist, tempo, janela, inicio_expediente, tempo_servico):
    relogio = inicio_expediente
    caminho = [deposito] + rota + [deposito]
    distancia = 0
    chegadas = []

    for origem, destino in zip(caminho, caminho[1:]):
        distancia += dist[origem][destino]
        chegada = relogio + tempo[origem][destino]

        if destino == deposito:
            retorno = chegada
        else:
            if chegada < janela[destino][0]:
                inicio = janela[destino][0]
            else:
                inicio = chegada

            fim = inicio + tempo_servico
            atrasado = inicio > janela[destino][1]

            chegadas.append({"id": destino, "chegada": round(chegada, 1),
                            "inicio": round(inicio, 1), "fim": round(fim, 1), "atrasado": atrasado})
            relogio = fim

    tempo_rota = round(retorno - inicio_expediente, 1)
    distancia = round(distancia, 2)

    return caminho, chegadas, retorno, distancia, tempo_rota


def _montar_solucao(clientes, deposito, dist, tempo, demanda, prioridade, janela, capacidade, veiculos, inicio_expediente, tempo_servico, usar_2opt):

    viagens, nao_atendidos = vizinho_mais_proximo(
        clientes, deposito, dist, demanda, capacidade, veiculos, prioridade)

    if usar_2opt:
        viagens = [dois_opt(rota, deposito, dist) for rota in viagens]

    rotas = []

    for i, rota in enumerate(viagens, start=1):
        caminho, chegadas, retorno, distancia, tempo_rota = calcular_horarios(
            rota, deposito, dist, tempo, janela, inicio_expediente, tempo_servico)

        carga = sum(demanda[c] for c in rota)
        ocupacao = round(carga/capacidade, 3)

        rotas.append({"veiculo": i, "paradas": caminho, "chegadas": chegadas, "saida": inicio_expediente,
                     "retorno": retorno, "distancia": distancia, "tempo": tempo_rota, "carga": carga, "ocupacao": ocupacao})

    distancia_total = round(sum(d["distancia"] for d in rotas), 2)
    tempo_total = round(sum(t["tempo"] for t in rotas), 1)
    veiculos_usados = len(rotas)
    atrasos = sum(cliente["atrasado"]
                  for rota in rotas for cliente in rota["chegadas"])
    metricas = {"distancia_total": distancia_total, "tempo_total": tempo_total,
                "veiculos_usados": veiculos_usados, "atrasos": atrasos}

    return {"rotas": rotas, "nao_atendidos": nao_atendidos, "metricas": metricas}


def calcular_rotas(grafo, veiculos, capacidade, algoritmo, usar_2opt):
    if algoritmo not in ALGORITMOS:
        raise ValueError("Algoritmo Nao Implementado")

    g = Grafo.de_contrato(grafo)

    deposito = g.deposito
    clientes = g.clientes()
    demanda = {cli: g.vertice(cli)["demanda"] for cli in clientes}
    prioridade = {cli: g.vertice(cli)["prioridade"] for cli in clientes}
    janela = {cli: g.vertice(cli)["janela"] for cli in clientes}
    dist = matriz_custos(g, "distancia")
    tempo = matriz_custos(g, "tempo")

    return _montar_solucao(clientes, deposito, dist, tempo, demanda, prioridade, janela, capacidade, veiculos, INICIO_EXPEDIENTE, TEMPO_SERVICO, usar_2opt)
