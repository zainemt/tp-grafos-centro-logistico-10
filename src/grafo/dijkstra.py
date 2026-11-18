"""Dijkstra com heap binário e matriz de custos (caminhos mínimos entre todos os pares).

Complexidade: O((V + E) log V) por origem. A matriz roda uma vez por parada
(depósito e clientes), e cada execução percorre o mapa inteiro, esquinas incluídas:
O(P (V + E) log V) para P paradas.
Aceita tanto um Grafo quanto o dicionário do contrato (o que calcular_rotas recebe).
"""
import heapq

from src.grafo.grafo import Grafo

INFINITO = float("inf")


def _como_grafo(grafo):
    return grafo if isinstance(grafo, Grafo) else Grafo.de_contrato(grafo)


def dijkstra(grafo, origem, peso="distancia"):
    """Menor custo de origem até cada vértice alcançável.

    Devolve (custo, anterior): custo = {id: custo mínimo}; anterior = {id: vértice
    anterior no caminho mínimo} (a origem não aparece em anterior). Vértices
    inalcançáveis ficam fora dos dois dicionários.
    """
    g = _como_grafo(grafo)
    if origem not in g:
        raise KeyError(f"vértice de origem inexistente: {origem}")
    custo = {origem: 0.0}
    anterior = {}
    fila = [(0.0, 0, origem)]  # (custo, desempate, vértice): o contador evita comparar ids de tipos diferentes
    contador = 1
    while fila:
        d, _, u = heapq.heappop(fila)
        if d > custo[u]:
            continue  # entrada velha da fila
        for v, w in g.vizinhos(u, peso):
            nd = d + w
            if nd < custo.get(v, INFINITO):
                custo[v] = nd
                anterior[v] = u
                heapq.heappush(fila, (nd, contador, v))
                contador += 1
    return custo, anterior


def caminho(anterior, origem, destino):
    """Reconstrói a lista de vértices do caminho mínimo; [] se o destino for inalcançável."""
    if destino == origem:
        return [origem]
    if destino not in anterior:
        return []
    seq = [destino]
    while seq[-1] != origem:
        seq.append(anterior[seq[-1]])
    return seq[::-1]


def matriz_custos(grafo, peso="distancia", pontos=None):
    """Custo mínimo entre todos os pares de pontos: {origem: {destino: custo}}.

    É a "matriz de distâncias/tempos" que os algoritmos de roteirização (Dupla 2)
    usam para saber o custo de ir de uma parada à próxima. Por padrão, os pontos são
    as paradas (depósito e clientes); as esquinas entram só como passagem, dentro
    dos caminhos mínimos. No grafo direcionado, custo[u][v] pode ser diferente de
    custo[v][u] (ruas de mão única). Pares sem caminho ficam fora da matriz.
    """
    g = _como_grafo(grafo)
    pontos = g.paradas() if pontos is None else list(pontos)
    matriz = {}
    for u in pontos:
        custo = dijkstra(g, u, peso)[0]
        matriz[u] = {v: custo[v] for v in pontos if v in custo}
    return matriz
