"""Estrutura do grafo e leitura de dados — responsabilidade da Dupla 1 (sem NetworkX).

  - grafo.py       classe Grafo (lista de adjacência; vértices = depósito/clientes;
                   arestas = distância em km e tempo em min)
  - dijkstra.py    Dijkstra com heap e matriz de custos entre todos os pares

A fazer: leitura de dados/*.csv (carregar_grafo, no formato de GET /api/grafo).

Uso pela Dupla 2 (dentro de calcular_rotas):
    dist = matriz_custos(grafo, "distancia");  tempo = matriz_custos(grafo, "tempo")
"""
from src.grafo.dijkstra import caminho, dijkstra, matriz_custos
from src.grafo.grafo import Grafo

__all__ = ["Grafo", "dijkstra", "caminho", "matriz_custos"]
