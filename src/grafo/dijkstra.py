"""Dijkstra com heap binário e matriz de custos (caminhos mínimos entre todos os pares).

Complexidade: O((V + E) log V) por origem; a matriz roda uma vez por vértice.
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


def matriz_custos(grafo, peso="distancia"):
    """Custo mínimo entre todos os pares: {origem: {destino: custo}}.

    É a "matriz de distâncias/tempos" que os algoritmos de roteirização (Dupla 2)
    usam para saber o custo de ir de uma parada à próxima.
    """
    g = _como_grafo(grafo)
    return {u: dijkstra(g, u, peso)[0] for u in g.ids()}
