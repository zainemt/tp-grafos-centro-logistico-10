"""Validação do contrato entre as duplas.

Qualquer implementação de carregar_grafo (Dupla 1) e calcular_rotas (Dupla 2)
precisa passar por estas checagens para funcionar com a API e o front-end.
Cada função devolve uma lista de problemas (vazia = tudo certo).
"""

CAMPOS_VERTICE = {"id", "nome", "lat", "lon", "demanda", "janela", "prioridade", "deposito"}
CAMPOS_ARESTA = {"u", "v", "distancia", "tempo"}
CAMPOS_ROTA = {"veiculo", "paradas", "chegadas", "distancia", "tempo", "carga", "ocupacao"}
CAMPOS_METRICAS = {"distancia_total", "tempo_total", "veiculos_usados", "atrasos"}


def validar_grafo(grafo):
    erros = []
    vertices = grafo.get("vertices", [])
    arestas = grafo.get("arestas", [])
    if not vertices:
        return ["grafo sem vértices"]
    ids = set()
    for v in vertices:
        faltando = CAMPOS_VERTICE - v.keys()
        if faltando:
            erros.append(f"vértice {v.get('id')} sem os campos {sorted(faltando)}")
            continue
        if v["id"] in ids:
            erros.append(f"id de vértice repetido: {v['id']}")
        ids.add(v["id"])
        if len(v["janela"]) != 2 or v["janela"][0] > v["janela"][1]:
            erros.append(f"janela inválida no vértice {v['id']}: {v['janela']}")
        if v["demanda"] < 0:
            erros.append(f"demanda negativa no vértice {v['id']}")
    depositos = [v for v in vertices if v.get("deposito")]
    if len(depositos) != 1:
        erros.append(f"deve haver exatamente 1 depósito (há {len(depositos)})")
    for a in arestas:
        faltando = CAMPOS_ARESTA - a.keys()
        if faltando:
            erros.append(f"aresta {a} sem os campos {sorted(faltando)}")
        elif a["u"] not in ids or a["v"] not in ids:
            erros.append(f"aresta {a['u']}-{a['v']} liga vértice inexistente")
        elif a["distancia"] < 0 or a["tempo"] < 0:
            erros.append(f"aresta {a['u']}-{a['v']} com peso negativo")
    return erros


def validar_rotas(grafo, resultado, veiculos, capacidade):
    erros = []
    vs = {v["id"]: v for v in grafo["vertices"]}
    deposito = next(v["id"] for v in grafo["vertices"] if v["deposito"])
    clientes = {i for i, v in vs.items() if not v["deposito"]}

    for chave in ("rotas", "nao_atendidos", "metricas"):
        if chave not in resultado:
            erros.append(f"resultado sem a chave '{chave}'")
    if erros:
        return erros

    faltando = CAMPOS_METRICAS - resultado["metricas"].keys()
    if faltando:
        erros.append(f"métricas sem os campos {sorted(faltando)}")
    if len(resultado["rotas"]) > veiculos:
        erros.append(f"{len(resultado['rotas'])} rotas para apenas {veiculos} veículos")

    visitados = []
    for r in resultado["rotas"]:
        faltando = CAMPOS_ROTA - r.keys()
        if faltando:
            erros.append(f"rota {r.get('veiculo')} sem os campos {sorted(faltando)}")
            continue
        p = r["paradas"]
        if len(p) < 2 or p[0] != deposito or p[-1] != deposito:
            erros.append(f"rota {r['veiculo']} deve começar e terminar no depósito")
        meio = p[1:-1]
        visitados += meio
        carga = sum(vs[i]["demanda"] for i in meio if i in vs)
        if carga > capacidade:
            erros.append(f"rota {r['veiculo']} excede a capacidade ({carga} > {capacidade})")
        if carga != r["carga"]:
            erros.append(f"rota {r['veiculo']}: carga informada {r['carga']} != soma das demandas {carga}")

    if len(visitados) != len(set(visitados)):
        erros.append("algum cliente foi visitado mais de uma vez")
    cobertos = set(visitados) | set(resultado["nao_atendidos"])
    if cobertos != clientes:
        erros.append(f"clientes nem roteados nem em nao_atendidos: {sorted(clientes - cobertos)}")
    return erros
