"""Gerador de instâncias sintéticas, reprodutíveis pela semente.

Serve só para testes e para o benchmark (src/grafo/desempenho.py), que precisam
de grafos de vários tamanhos. A base de dados do sistema fica em dados/ e não é
gerada aqui.

Os pontos ficam num raio de ~7 km em torno de um centro de distribuição em
Belo Horizonte (mesma região dos dados de exemplo da API). Não são dados reais.
"""
import random

from src.grafo.dados import _arestas_completas
from src.grafo.grafo import Grafo

DEPOSITO = {"id": 0, "nome": "Centro de Distribuição", "lat": -19.9227, "lon": -43.9451,
            "demanda": 0, "janela": [0, 24 * 60], "prioridade": 0, "deposito": True}
SEMENTE_PADRAO = 10


def sortear_janela_e_prioridade(rnd):
    """Janela de tempo (minutos desde 00:00) e prioridade (1 = baixa, 3 = alta) de um cliente."""
    inicio = rnd.choice([8, 9, 10, 11, 13, 14]) * 60
    janela = [inicio, inicio + rnd.choice([120, 180, 240])]
    return janela, rnd.choice([1, 1, 2, 2, 3])


def gerar_vertices(n_clientes, semente=SEMENTE_PADRAO):
    """Depósito + n clientes com posição, demanda, janela de tempo e prioridade sorteadas."""
    rnd = random.Random(semente)
    vertices = [dict(DEPOSITO, janela=list(DEPOSITO["janela"]))]
    for i in range(1, n_clientes + 1):
        lat = round(DEPOSITO["lat"] + rnd.uniform(-0.06, 0.06), 6)
        lon = round(DEPOSITO["lon"] + rnd.uniform(-0.07, 0.07), 6)
        demanda = rnd.randint(5, 30)
        janela, prioridade = sortear_janela_e_prioridade(rnd)
        vertices.append({"id": i, "nome": f"Cliente {i:02d}", "lat": lat, "lon": lon, "demanda": demanda,
                         "janela": janela, "prioridade": prioridade, "deposito": False})
    return vertices


def gerar_grafo(n_clientes, semente=SEMENTE_PADRAO):
    """Grafo completo com n clientes (arestas pela mesma regra da leitura sem arestas.csv)."""
    vertices = gerar_vertices(n_clientes, semente)
    return Grafo.de_contrato({"vertices": vertices, "arestas": _arestas_completas(vertices)})
