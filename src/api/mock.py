"""Dados de EXEMPLO (mock) para o front-end funcionar antes da integração.

Este arquivo é temporário: quando as Duplas 1 e 2 entregarem o código real,
a API passa a usar src/grafo e src/algoritmos. As funções aqui definem o
FORMATO (contrato) que o código real deve devolver.
"""
import math
import random
import time

VELOCIDADE_KMH = 30      # velocidade média urbana usada para estimar o tempo
TEMPO_SERVICO_MIN = 10   # minutos parado em cada entrega
INICIO_EXPEDIENTE = 8 * 60  # 08:00, em minutos desde 00:00


def _haversine_km(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (a["lat"], a["lon"], b["lat"], b["lon"]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def gerar_grafo(n_clientes=20, semente=42):
    """Contrato de GET /api/grafo."""
    rnd = random.Random(semente)
    deposito = {"id": 0, "nome": "Centro de Distribuição", "lat": -19.9227, "lon": -43.9451,
                "demanda": 0, "janela": [0, 24 * 60], "prioridade": 0, "deposito": True}
    vertices = [deposito]
    for i in range(1, n_clientes + 1):
        inicio = rnd.choice([8, 9, 10, 11, 13, 14]) * 60
        vertices.append({
            "id": i,
            "nome": f"Cliente {i}",
            "lat": deposito["lat"] + rnd.uniform(-0.06, 0.06),
            "lon": deposito["lon"] + rnd.uniform(-0.07, 0.07),
            "demanda": rnd.randint(5, 30),
            "janela": [inicio, inicio + rnd.choice([120, 180, 240])],  # minutos desde 00:00
            "prioridade": rnd.choice([1, 1, 2, 2, 3]),  # 3 = mais urgente
            "deposito": False,
        })
    # grafo completo (cada par de pontos ligado por uma aresta)
    arestas = []
    for i, u in enumerate(vertices):
        for v in vertices[i + 1:]:
            d = _haversine_km(u, v) * 1.3  # fator de correção para ruas
            arestas.append({"u": u["id"], "v": v["id"],
                            "distancia": round(d, 3),
                            "tempo": round(d / VELOCIDADE_KMH * 60, 2)})
    return {"vertices": vertices, "arestas": arestas}


def calcular_rotas(grafo, veiculos, capacidade, algoritmo, usar_2opt):
    """Contrato de POST /api/rotas.

    NÃO é o algoritmo do trabalho: é uma heurística simples (varredura por
    ângulo) só para gerar rotas plausíveis e testar a interface.
    """
    vs = {v["id"]: v for v in grafo["vertices"]}
    dist = {}
    for a in grafo["arestas"]:
        dist[(a["u"], a["v"])] = dist[(a["v"], a["u"])] = a
    dep = next(v for v in grafo["vertices"] if v["deposito"])
    clientes = [v for v in grafo["vertices"] if not v["deposito"]]

    # agrupa por ângulo em relação ao depósito, respeitando a capacidade
    clientes.sort(key=lambda c: math.atan2(c["lat"] - dep["lat"], c["lon"] - dep["lon"]))
    grupos, atual, carga = [], [], 0
    for c in clientes:
        if carga + c["demanda"] > capacidade and atual:
            grupos.append(atual)
            atual, carga = [], 0
        atual.append(c)
        carga += c["demanda"]
    if atual:
        grupos.append(atual)

    # ordem dentro de cada rota varia com as opções, só para a tela mudar
    for g in grupos:
        if algoritmo == "nn":
            g.sort(key=lambda c: c["id"])
        if usar_2opt:
            ordem, pos = [], dep
            restantes = g[:]
            while restantes:
                prox = min(restantes, key=lambda c: dist[(pos["id"], c["id"])]["distancia"])
                ordem.append(prox)
                restantes.remove(prox)
                pos = prox
            g[:] = ordem

    rotas, nao_atendidos = [], []
    if len(grupos) > veiculos:
        for g in grupos[veiculos:]:
            nao_atendidos += [c["id"] for c in g]
        grupos = grupos[:veiculos]

    total_d = total_t = atrasos = 0
    for k, g in enumerate(grupos, start=1):
        paradas = [dep["id"]] + [c["id"] for c in g] + [dep["id"]]
        d = t = 0.0
        relogio = INICIO_EXPEDIENTE
        chegadas = []
        for a, b in zip(paradas, paradas[1:]):
            aresta = dist[(a, b)]
            d += aresta["distancia"]
            t += aresta["tempo"]
            relogio += aresta["tempo"]
            if b != dep["id"]:
                ini, fim = vs[b]["janela"]
                chegada = relogio
                inicio = max(chegada, ini)  # espera a janela abrir
                atrasado = inicio > fim
                atrasos += atrasado
                relogio = inicio + TEMPO_SERVICO_MIN
                t += TEMPO_SERVICO_MIN
                chegadas.append({"id": b, "chegada": round(chegada, 1), "inicio": round(inicio, 1),
                                 "fim": round(relogio, 1), "atrasado": atrasado})
        carga = sum(c["demanda"] for c in g)
        rotas.append({"veiculo": k, "paradas": paradas, "chegadas": chegadas,
                      "saida": INICIO_EXPEDIENTE, "retorno": round(relogio, 1),
                      "distancia": round(d, 2), "tempo": round(t, 1), "carga": carga,
                      "ocupacao": round(carga / capacidade, 3)})
        total_d += d
        total_t += t

    return {
        "rotas": rotas,
        "nao_atendidos": nao_atendidos,
        "metricas": {"distancia_total": round(total_d, 2), "tempo_total": round(total_t, 1),
                     "veiculos_usados": len(rotas), "atrasos": atrasos},
    }


def medir_desempenho(tamanhos, repeticoes=3):
    """Contrato de GET /api/desempenho.

    Mede o tempo (em ms) de cada algoritmo para grafos de vários tamanhos.
    Aqui mede só a heurística de exemplo; a Dupla 2 troca pelos algoritmos
    reais e a Dupla 1 acrescenta as séries de comparação com o NetworkX
    (ex.: "Dijkstra (nosso)" e "Dijkstra (NetworkX)").
    """
    configs = [("Vizinho mais próximo", "nn", False), ("Clarke-Wright", "clarke_wright", False),
               ("Clarke-Wright + 2-opt", "clarke_wright", True)]
    series = [{"nome": nome, "pontos": []} for nome, _, _ in configs]
    for n in tamanhos:
        grafo = gerar_grafo(n_clientes=n, semente=n)
        for serie, (_, alg, opt) in zip(series, configs):
            melhor = float("inf")
            for _ in range(repeticoes):
                inicio = time.perf_counter()
                calcular_rotas(grafo, veiculos=n, capacidade=150, algoritmo=alg, usar_2opt=opt)
                melhor = min(melhor, time.perf_counter() - inicio)
            serie["pontos"].append({"n": n, "ms": round(melhor * 1000, 3)})
    return {"series": series}
