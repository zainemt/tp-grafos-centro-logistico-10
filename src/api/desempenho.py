"""Benchmark da aba Desempenho: mede o tempo do calcular_rotas REAL (Duplas 1 e 2).

Os grafos de cada tamanho vêm do gerador de instâncias da Dupla 1 (src/grafo/gerador.py),
com a semente igual ao tamanho, então a medição é repetível. O formato devolvido é o de
GET /api/desempenho, validado por src/api/contrato.validar_desempenho.

A comparação do Dijkstra com o NetworkX (exigida no enunciado) não fica aqui: a aplicação
não pode usar a biblioteca. Ela é feita à parte, para o relatório, em
benchmark/comparar_dijkstra.py (metodologia em benchmark/README.md).
"""
import time

from src.algoritmos import calcular_rotas
from src.grafo.gerador import gerar_grafo

CAPACIDADE = 150
# (nome da série, algoritmo, usar_2opt)
CONFIGURACOES = [
    ("Vizinho mais próximo", "nn", False),
    ("Clarke-Wright", "clarke_wright", False),
    ("Clarke-Wright + 2-opt", "clarke_wright", True),
]


def repeticoes_para(n_clientes):
    """Em grafos pequenos o tempo é de milissegundos e oscila, então vale o melhor de 3.
    Nos grandes cada execução leva segundos, e repetir só deixaria a tela esperando mais."""
    return 3 if n_clientes <= 50 else 1


def medir_desempenho(tamanhos):
    """Contrato de GET /api/desempenho: uma série por configuração, com o melhor tempo (ms) por tamanho."""
    series = [{"nome": nome, "pontos": []} for nome, _, _ in CONFIGURACOES]
    for n in tamanhos:
        grafo = gerar_grafo(n, semente=n).para_contrato()
        for serie, (_, algoritmo, usar_2opt) in zip(series, CONFIGURACOES):
            melhor = float("inf")
            for _ in range(repeticoes_para(n)):
                inicio = time.perf_counter()
                calcular_rotas(grafo, n, CAPACIDADE, algoritmo, usar_2opt)  # uma frota com um veículo por cliente
                melhor = min(melhor, time.perf_counter() - inicio)
            serie["pontos"].append({"n": n, "ms": round(melhor * 1000, 3)})
    return {"series": series}
