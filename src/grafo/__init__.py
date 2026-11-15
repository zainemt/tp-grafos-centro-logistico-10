"""Estrutura do grafo e leitura de dados — responsabilidade da Dupla 1 (sem NetworkX).

  - grafo.py       classe Grafo (lista de adjacência; vértices = depósito/clientes;
                   arestas = distância em km e tempo em min)
  - dados.py       leitura de dados/vertices.csv (+ dados/arestas.csv opcional) e
                   carregar_grafo(), no formato de GET /api/grafo
  - dijkstra.py    Dijkstra com heap e matriz de custos entre todos os pares

Uso pela API (src/api/app.py):  carregar_grafo = grafo.carregar_grafo
Uso pela Dupla 2 (dentro de calcular_rotas):
    dist = matriz_custos(grafo, "distancia");  tempo = matriz_custos(grafo, "tempo")
"""
from src.grafo.dados import ErroDados, carregar_grafo, ler_grafo
from src.grafo.dijkstra import caminho, dijkstra, matriz_custos
from src.grafo.grafo import Grafo

__all__ = ["Grafo", "ErroDados", "carregar_grafo", "ler_grafo", "dijkstra", "caminho", "matriz_custos"]
