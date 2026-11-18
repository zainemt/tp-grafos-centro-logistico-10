"""Validação do contrato entre as duplas.

Qualquer implementação de carregar_grafo (Dupla 1) e calcular_rotas (Dupla 2)
precisa passar por estas checagens para funcionar com a API e o front-end.
Cada função devolve uma lista de problemas (vazia = tudo certo).

O grafo é o mapa do local: além do depósito e dos clientes, pode ter vértices
"tipo": "esquina" (só passagem) e arestas "mao_unica": true (valem só de u para v).
Campos opcionais das arestas, para o mapa: "nome" (da rua) e "geometria"
(pontos [lat, lon] do desenho do trecho, de u para v).
"""

CAMPOS_VERTICE = {"id", "nome", "lat", "lon", "demanda", "janela", "prioridade", "deposito"}
CAMPOS_ARESTA = {"u", "v", "distancia", "tempo"}
CAMPOS_ROTA = {"veiculo", "paradas", "chegadas", "saida", "retorno", "distancia", "tempo", "carga", "ocupacao"}
CAMPOS_CHEGADA = {"id", "chegada", "inicio", "fim", "atrasado"}
CAMPOS_METRICAS = {"distancia_total", "tempo_total", "veiculos_usados", "atrasos"}
TIPOS = {"deposito", "cliente", "esquina"}


def tipo_do_vertice(v):
    """Igual a src/grafo/grafo.py: sem 'tipo', deposito=True é o depósito e o resto é cliente."""
    return v.get("tipo") or ("deposito" if v.get("deposito") else "cliente")


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
        if "tipo" in v:
            if v["tipo"] not in TIPOS:
                erros.append(f"tipo inválido no vértice {v['id']}: {v['tipo']!r} (use {sorted(TIPOS)})")
            elif (v["tipo"] == "deposito") != bool(v["deposito"]):
                erros.append(f"vértice {v['id']}: tipo {v['tipo']!r} não combina com deposito={v['deposito']}")
            elif v["tipo"] == "esquina" and v["demanda"] != 0:
                erros.append(f"esquina {v['id']} com demanda (só clientes têm demanda)")
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
        elif not isinstance(a.get("mao_unica", False), bool):
            erros.append(f"aresta {a['u']}-{a['v']}: mao_unica deve ser true/false")
        elif "geometria" in a and not all(isinstance(p, (list, tuple)) and len(p) == 2 for p in a["geometria"]):
            erros.append(f"aresta {a['u']}-{a['v']}: geometria deve ser uma lista de [lat, lon]")
    return erros


def validar_rotas(grafo, resultado, veiculos, capacidade):
    erros = []
    vs = {v["id"]: v for v in grafo["vertices"]}
    deposito = next(v["id"] for v in grafo["vertices"] if v["deposito"])
    clientes = {i for i, v in vs.items() if tipo_do_vertice(v) == "cliente"}

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
        fora = [i for i in meio if i not in clientes]
        if fora:
            erros.append(f"rota {r['veiculo']} para em vértices que não são clientes: {fora}")
        visitados += meio
        carga = sum(vs[i]["demanda"] for i in meio if i in vs)
        if carga > capacidade:
            erros.append(f"rota {r['veiculo']} excede a capacidade ({carga} > {capacidade})")
        if carga != r["carga"]:
            erros.append(f"rota {r['veiculo']}: carga informada {r['carga']} != soma das demandas {carga}")
        erros += _validar_horarios(r, meio)

    if len(visitados) != len(set(visitados)):
        erros.append("algum cliente foi visitado mais de uma vez")
    cobertos = set(visitados) | set(resultado["nao_atendidos"])
    if cobertos != clientes:
        erros.append(f"clientes nem roteados nem em nao_atendidos: {sorted(clientes - cobertos)}")
    return erros


def _validar_horarios(rota, clientes_da_rota):
    """Horários em minutos desde 00:00, em ordem: saida <= chegada <= inicio <= fim <= ... <= retorno."""
    erros = []
    ch = rota["chegadas"]
    for c in ch:
        faltando = CAMPOS_CHEGADA - c.keys()
        if faltando:
            return [f"rota {rota['veiculo']}: chegada {c.get('id')} sem os campos {sorted(faltando)}"]
    if [c["id"] for c in ch] != clientes_da_rota:
        erros.append(f"rota {rota['veiculo']}: 'chegadas' fora da ordem das paradas")
    relogio = rota["saida"]
    for c in ch:
        if not (relogio <= c["chegada"] <= c["inicio"] <= c["fim"]):
            erros.append(f"rota {rota['veiculo']}: horários fora de ordem no cliente {c['id']}")
        relogio = c["fim"]
    if rota["retorno"] < relogio:
        erros.append(f"rota {rota['veiculo']}: retorno antes da última entrega")
    return erros


def validar_desempenho(resultado):
    erros = []
    series = resultado.get("series")
    if not series:
        return ["desempenho sem 'series'"]
    for s in series:
        if "nome" not in s or "pontos" not in s:
            erros.append(f"série sem 'nome' ou 'pontos': {s}")
            continue
        for p in s["pontos"]:
            if "n" not in p or "ms" not in p:
                erros.append(f"série {s['nome']}: ponto sem 'n' ou 'ms'")
            elif p["ms"] < 0:
                erros.append(f"série {s['nome']}: tempo negativo")
    return erros
