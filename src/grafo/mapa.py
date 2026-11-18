"""Trajetos pelas ruas: transforma as paradas de uma rota no desenho do caminho no mapa.

Os algoritmos de roteirização (Dupla 2) devolvem só a ordem das paradas
(depósito -> clientes -> depósito). Entre duas paradas seguidas, o veículo faz o
caminho mínimo pelas ruas; aqui esse caminho é refeito com o Dijkstra (a mesma
árvore de caminhos mínimos que gera a matriz de distâncias) e convertido em pontos
[lat, lon], usando a geometria de cada trecho de rua.

Uso (src/api/app.py):
    trajetos = Trajetos(grafo)               # uma vez, na subida da API
    trajetos.da_rota([0, 5, 2, 0])           # -> um trecho de pontos por perna da rota
"""
from src.grafo.dijkstra import caminho, dijkstra
from src.grafo.grafo import Grafo


class Trajetos:
    def __init__(self, grafo, peso="distancia"):
        """peso='distancia' desenha o mesmo caminho cuja distância entra nas métricas da rota."""
        self.grafo = grafo if isinstance(grafo, Grafo) else Grafo.de_contrato(grafo)
        self.peso = peso
        self._anterior = {}   # origem -> árvore de caminhos mínimos (guardada para reaproveitar)

    def vertices(self, origem, destino):
        """Ids do caminho mínimo de origem até destino, passando pelas esquinas ([] se não houver)."""
        if origem not in self._anterior:
            self._anterior[origem] = dijkstra(self.grafo, origem, self.peso)[1]
        return caminho(self._anterior[origem], origem, destino)

    def pontos(self, origem, destino):
        """Desenho do caminho mínimo como lista de [lat, lon], do primeiro ao último vértice."""
        ids = self.vertices(origem, destino)
        if not ids:
            return []
        posicao = lambda i: [self.grafo.vertice(i)["lat"], self.grafo.vertice(i)["lon"]]  # noqa: E731
        pontos = [posicao(ids[0])]
        for a, b in zip(ids, ids[1:]):
            pontos += [list(p) for p in self.grafo.info_aresta(a, b)["geometria"] or []]
            pontos.append(posicao(b))
        return pontos

    def da_rota(self, paradas):
        """Um trecho por perna: [[pontos da parada 0 até a 1], [da 1 até a 2], ...]."""
        return [self.pontos(a, b) for a, b in zip(paradas, paradas[1:])]
