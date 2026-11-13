"""Estrutura do grafo e leitura de dados — responsabilidade da Dupla 1 (sem NetworkX).

  - grafo.py       classe Grafo (lista de adjacência; vértices = depósito/clientes;
                   arestas = distância em km e tempo em min)

A fazer: leitura de dados/*.csv (carregar_grafo, no formato de GET /api/grafo)
e Dijkstra para a matriz de distâncias/tempos.
"""
from src.grafo.grafo import Grafo

__all__ = ["Grafo"]
