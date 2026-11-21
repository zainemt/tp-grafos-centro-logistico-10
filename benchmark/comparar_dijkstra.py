"""Comparação do nosso Dijkstra (src/grafo/dijkstra.py) com o do NetworkX.

O NetworkX entra SÓ aqui, como referência externa: a aplicação (src/) não o importa,
e um teste (tests/test_benchmark_networkx.py) garante isso. A metodologia completa
está em benchmark/README.md.

Executar a partir da raiz do repositório:
    .venv/bin/pip install -r benchmark/requirements.txt
    .venv/bin/python -m benchmark.comparar_dijkstra            # completo (~7 min num Apple M4)
    .venv/bin/python -m benchmark.comparar_dijkstra --rapido   # instâncias pequenas

Saídas:
    benchmark/resultados/dijkstra_networkx.csv   todas as medições (uma linha por medição)
    benchmark/resultados/dijkstra_networkx.md    resumo legível + ambiente da execução
    relatorio/tabelas/dijkstra-networkx.tex      tabela para o relatório (\\input)
    relatorio/figuras/dijkstra-networkx.tex      gráfico pgfplots para o relatório (\\input)
"""
import argparse
import csv
import gc
import json
import math
import os
import platform
import random
import statistics
import subprocess
import sys
import time
from datetime import datetime

import networkx as nx

from src.grafo.dados import carregar_grafo
from src.grafo.dijkstra import caminho, dijkstra, matriz_custos
from src.grafo.gerador import gerar_grafo
from src.grafo.grafo import Grafo

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PASTA_RESULTADOS = os.path.join(RAIZ, "benchmark", "resultados")
PASTA_RELATORIO = os.path.join(RAIZ, "relatorio")

PESOS = ("distancia", "tempo")
SEMENTE = 42
TOLERANCIA = 1e-9           # diferença aceita entre custos (só arredondamento de ponto flutuante)
ALVOS_POR_ORIGEM = 200      # destinos sorteados por origem para conferir o caminho reconstruído

# Famílias de instâncias (ver README): o mapa real, grades (malha viária esparsa, E ~ 2V)
# e grafos completos (densos, E ~ V^2/2, como na leitura sem arestas.csv).
LADOS_GRADE = (25, 50, 100, 200, 300)
CLIENTES_COMPLETO = (50, 100, 200, 400, 800)
LADOS_GRADE_RAPIDO = (10, 20)
CLIENTES_COMPLETO_RAPIDO = (10, 20)


# ----------------------------------------------------------------------------- instâncias
def mapa_sp():
    """O mapa real usado pela aplicação (dados/*.csv): direcionado, com ruas de mão única."""
    return Grafo.de_contrato(carregar_grafo())


def grade(lado, semente=SEMENTE):
    """Malha viária sintética lado x lado (quarteirões de ~100 m), não direcionada.

    Distância de cada trecho entre 80 e 150 m e velocidade de 20, 30 ou 40 km/h, sorteadas
    pela semente. Serve para medir o crescimento do tempo em grafos esparsos como o de ruas.
    """
    rnd = random.Random(semente * 1_000_003 + lado)
    g = Grafo()
    for i in range(lado * lado):
        g.adicionar_vertice({"id": i, "tipo": "deposito" if i == 0 else "esquina", "deposito": i == 0,
                             "lat": 0.0, "lon": 0.0})
    for linha in range(lado):
        for coluna in range(lado):
            u = linha * lado + coluna
            vizinhos = []
            if coluna + 1 < lado:
                vizinhos.append(u + 1)
            if linha + 1 < lado:
                vizinhos.append(u + lado)
            for v in vizinhos:
                km = rnd.uniform(0.08, 0.15)
                g.adicionar_aresta(u, v, round(km, 4), round(km / rnd.choice((20, 30, 40)) * 60, 4))
    return g


def completo(n_clientes):
    """Grafo completo do gerador da Dupla 1 (depósito + n clientes), semente = n."""
    return gerar_grafo(n_clientes, semente=n_clientes)


def instancias(rapido=False):
    """[(família, nome, função que monta o Grafo)] na ordem em que são medidas."""
    lados = LADOS_GRADE_RAPIDO if rapido else LADOS_GRADE
    clientes = CLIENTES_COMPLETO_RAPIDO if rapido else CLIENTES_COMPLETO
    lista = [("mapa", "Mapa de SP (real)", mapa_sp)]
    lista += [("grade", f"Grade {lado}x{lado}", lambda lado=lado: grade(lado)) for lado in lados]
    lista += [("completo", f"Completo n={n}", lambda n=n: completo(n)) for n in clientes]
    return lista


# ----------------------------------------------------------------------------- conversão
def para_networkx(grafo):
    """Mesmo grafo no NetworkX: mesmos ids, mesmos arcos e os dois pesos como atributos."""
    G = nx.DiGraph() if grafo.direcionado else nx.Graph()
    G.add_nodes_from(grafo.ids())
    for u, v, d, t in grafo.arestas():
        G.add_edge(u, v, distancia=d, tempo=t)
    return G


def num_arcos(grafo):
    """Entradas na lista de adjacência: o 'E' que o Dijkstra percorre (2E no não direcionado)."""
    return sum(len(grafo.vizinhos(u)) for u in grafo.ids())


# ----------------------------------------------------------------------------- operações
# Cada operação recebe a estrutura já montada; a montagem fica fora do tempo medido.
def nosso_uma_origem(grafo, origens, peso):
    return [dijkstra(grafo, s, peso) for s in origens]


def nx_uma_origem(G, origens, peso):
    # mesma saída do nosso: custos e predecessores (o NetworkX devolve listas de predecessores)
    return [nx.dijkstra_predecessor_and_distance(G, s, weight=peso) for s in origens]


def nosso_matriz(grafo, pontos, peso):
    return matriz_custos(grafo, peso, pontos)


def nx_matriz(G, pontos, peso):
    matriz = {}
    for u in pontos:
        custo = nx.single_source_dijkstra_path_length(G, u, weight=peso)
        matriz[u] = {v: custo[v] for v in pontos if v in custo}
    return matriz


# ----------------------------------------------------------------------------- corretude
def _iguais(a, b):
    return math.isclose(a, b, rel_tol=TOLERANCIA, abs_tol=TOLERANCIA)


def conferir_uma_origem(grafo, G, origem, peso, rnd):
    """Divergências entre os dois resultados a partir de uma origem (lista vazia = iguais).

    Confere (1) o mesmo conjunto de vértices alcançáveis, (2) o mesmo custo mínimo para
    cada um e (3) que o caminho reconstruído pelo nosso 'anterior' tem exatamente o custo
    informado (num subconjunto sorteado de destinos).
    """
    custo, anterior = dijkstra(grafo, origem, peso)
    _, custo_nx = nx.dijkstra_predecessor_and_distance(G, origem, weight=peso)
    problemas = []
    if set(custo) != set(custo_nx):
        problemas.append(f"origem {origem}: alcançáveis diferentes "
                         f"({len(custo)} no nosso, {len(custo_nx)} no NetworkX)")
    for v in custo.keys() & custo_nx.keys():
        if not _iguais(custo[v], custo_nx[v]):
            problemas.append(f"origem {origem} -> {v}: {custo[v]} x {custo_nx[v]} ({peso})")
    destinos = sorted(custo)
    for v in rnd.sample(destinos, min(ALVOS_POR_ORIGEM, len(destinos))):
        seq = caminho(anterior, origem, v)
        soma = sum(grafo.aresta(a, b)[peso] for a, b in zip(seq, seq[1:]))
        if not seq or seq[0] != origem or seq[-1] != v or not _iguais(soma, custo_nx[v]):
            problemas.append(f"origem {origem} -> {v}: caminho reconstruído custa {soma}, "
                             f"esperado {custo_nx[v]} ({peso})")
    return problemas


def conferir_matriz(m_nossa, m_nx):
    problemas = []
    for u in m_nx:
        if set(m_nossa.get(u, {})) != set(m_nx[u]):
            problemas.append(f"matriz: linha {u} com destinos diferentes")
            continue
        for v, c in m_nx[u].items():
            if not _iguais(m_nossa[u][v], c):
                problemas.append(f"matriz[{u}][{v}]: {m_nossa[u][v]} x {c}")
    return problemas


# ----------------------------------------------------------------------------- medição
def cronometrar(funcao, repeticoes):
    """Tempos (ms) de `repeticoes` execuções, depois de 1 execução de aquecimento.

    O coletor de lixo fica desligado durante cada execução (como no módulo timeit), para
    que uma coleta não caia por acaso no tempo de uma das implementações.
    """
    funcao()  # aquecimento: caches do interpretador e alocações iniciais
    tempos = []
    for _ in range(repeticoes):
        gc.collect()
        gc.disable()
        try:
            inicio = time.perf_counter_ns()
            funcao()
            tempos.append((time.perf_counter_ns() - inicio) / 1e6)
        finally:
            gc.enable()
    return tempos


def medir_instancia(familia, nome, grafo, repeticoes, n_origens, n_pontos, semente=SEMENTE):
    """Linhas de resultado de uma instância (uma por peso x operação x implementação)."""
    inicio = time.perf_counter()
    G = para_networkx(grafo)
    conversao_ms = (time.perf_counter() - inicio) * 1000

    rnd = random.Random(semente)
    ids = sorted(grafo.ids())
    origens = rnd.sample(ids, min(n_origens, len(ids)))
    # matriz: no mapa real, as paradas de verdade (depósito + clientes); nas outras, pontos sorteados
    pontos = grafo.paradas() if familia == "mapa" else rnd.sample(ids, min(n_pontos, len(ids)))

    base = {"familia": familia, "instancia": nome, "direcionado": grafo.direcionado,
            "vertices": grafo.num_vertices, "arestas": grafo.num_arestas, "arcos": num_arcos(grafo),
            "conversao_networkx_ms": round(conversao_ms, 3)}
    linhas = []
    for peso in PESOS:
        divergencias = []
        for s in origens:
            divergencias += conferir_uma_origem(grafo, G, s, peso, rnd)
        operacoes = [
            ("uma_origem", len(origens),
             lambda: nosso_uma_origem(grafo, origens, peso), lambda: nx_uma_origem(G, origens, peso)),
            ("matriz", len(pontos),
             lambda: nosso_matriz(grafo, pontos, peso), lambda: nx_matriz(G, pontos, peso)),
        ]
        divergencias += conferir_matriz(nosso_matriz(grafo, pontos, peso), nx_matriz(G, pontos, peso))
        for operacao, quantidade, f_nosso, f_nx in operacoes:
            for implementacao, funcao in (("nosso", f_nosso), ("networkx", f_nx)):
                tempos = cronometrar(funcao, repeticoes)
                linhas.append({**base, "peso": peso, "operacao": operacao, "implementacao": implementacao,
                               "origens": quantidade, "repeticoes": repeticoes,
                               "mediana_ms": round(statistics.median(tempos), 3),
                               "minimo_ms": round(min(tempos), 3),
                               "maximo_ms": round(max(tempos), 3),
                               "divergencias": len(divergencias)})
        for problema in divergencias[:5]:
            print("  DIVERGÊNCIA:", problema, file=sys.stderr)
    return linhas


def executar(rapido=False, repeticoes=5, n_origens=10, n_pontos=30, mostrar=print):
    linhas = []
    for familia, nome, montar in instancias(rapido):
        grafo = montar()
        mostrar(f"{nome}: V={grafo.num_vertices}, E={grafo.num_arestas} ...")
        novas = medir_instancia(familia, nome, grafo, repeticoes, n_origens, n_pontos)
        linhas += novas
        for linha in novas:
            if linha["peso"] == "distancia" and linha["operacao"] == "uma_origem":
                mostrar(f"    {linha['implementacao']:>8}: {por_origem(linha):9.3f} ms por origem")
    return linhas


# ----------------------------------------------------------------------------- saídas
def por_origem(linha):
    return linha["mediana_ms"] / linha["origens"]


def constante(linha):
    """Tempo por origem dividido por (V + arcos) log2 V, em ns: se o crescimento segue
    O((V + E) log V), este número fica aproximadamente constante entre as instâncias."""
    v = linha["vertices"]
    return por_origem(linha) * 1e6 / ((v + linha["arcos"]) * math.log2(v))


def ambiente():
    cpu = platform.processor() or platform.machine()
    if sys.platform == "darwin":
        try:
            cpu = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True,
                                 text=True, check=True).stdout.strip() or cpu
        except (OSError, subprocess.CalledProcessError):
            pass
    return {"data": datetime.now().strftime("%d/%m/%Y %H:%M"), "python": platform.python_version(),
            "networkx": nx.__version__, "sistema": platform.platform(terse=True), "processador": cpu}


def resumo(linhas):
    """{(instância, peso, operação): {'nosso': linha, 'networkx': linha}} na ordem de medição."""
    pares = {}
    for linha in linhas:
        pares.setdefault((linha["instancia"], linha["peso"], linha["operacao"]), {})[linha["implementacao"]] = linha
    return pares


def gravar_csv(linhas, arquivo):
    with open(arquivo, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=list(linhas[0]))
        escritor.writeheader()
        escritor.writerows(linhas)


def gravar_markdown(linhas, amb, arquivo, repeticoes):
    partes = [
        "# Dijkstra: nossa implementação x NetworkX",
        "",
        f"Gerado por `python -m benchmark.comparar_dijkstra` em {amb['data']}. "
        f"Python {amb['python']}, NetworkX {amb['networkx']}, {amb['processador']} ({amb['sistema']}).",
        f"Tempos: mediana de {repeticoes} execuções após 1 de aquecimento. Metodologia em `benchmark/README.md`.",
        "",
    ]
    for operacao, titulo in (("uma_origem", "Dijkstra a partir de uma origem (ms por origem)"),
                             ("matriz", "Matriz de custos entre P pontos (ms por matriz)")):
        partes += [f"## {titulo}", "",
                   "| Instância | Peso | V | arcos | P | Nosso | NetworkX | NetworkX / nosso | Divergências |",
                   "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
        for (inst, peso, op), par in resumo(linhas).items():
            if op != operacao:
                continue
            a, b = par["nosso"], par["networkx"]
            ta, tb = (por_origem(a), por_origem(b)) if op == "uma_origem" else (a["mediana_ms"], b["mediana_ms"])
            partes.append(f"| {inst} | {peso} | {a['vertices']} | {a['arcos']} | {a['origens']} | {ta:.3f} | "
                          f"{tb:.3f} | {tb / ta:.2f} | {a['divergencias']} |")
        partes.append("")
    with open(arquivo, "w", encoding="utf-8") as f:
        f.write("\n".join(partes))


def _num(x, casas=2):
    """Número no formato do relatório (vírgula decimal, separador de milhar fino)."""
    texto = f"{x:,.{casas}f}".replace(",", "X").replace(".", "{,}").replace("X", "\\,")
    return texto


def gravar_tabela_tex(linhas, amb, arquivo, repeticoes):
    corpo = []
    familia_anterior = None
    pares = resumo(linhas)
    for (inst, peso, op), par in pares.items():
        if peso != "distancia" or op != "uma_origem":
            continue
        a, b = par["nosso"], par["networkx"]
        if familia_anterior and a["familia"] != familia_anterior:
            corpo.append("\\midrule")
        familia_anterior = a["familia"]
        ta, tb = por_origem(a), por_origem(b)
        # divergências de toda a instância: os dois pesos, as duas operações
        divergencias = sum(pares[(inst, p, "uma_origem")]["nosso"]["divergencias"] for p in PESOS)
        corpo.append(f"{inst} & {_num(a['vertices'], 0)} & {_num(a['arcos'], 0)} & {_num(ta, 3)} & "
                     f"{_num(tb, 3)} & {_num(tb / ta)} & {_num(constante(a), 1)} & {divergencias} \\\\")
    texto = "\n".join([
        f"% Gerado por benchmark/comparar_dijkstra.py em {amb['data']} — não editar à mão.",
        "\\begin{table}[ht]",
        "\\centering",
        "\\caption{Dijkstra a partir de uma origem (peso: distância): mediana do tempo por origem, em ms; "
        "$c$ = tempo do nosso / $((|V| + \\text{arcos}) \\log_2 |V|)$, em ns; "
        "Diverg.\\ = custos diferentes do NetworkX (os dois pesos). "
        f"Python {amb['python']}, NetworkX {amb['networkx']}, {amb['processador']}; "
        f"mediana de {repeticoes} execuções.}}",
        "\\label{tab:dijkstra-networkx}",
        "\\begin{tabular}{lrrrrrrr}",
        "\\toprule",
        "Instância & $|V|$ & arcos & Nosso & NetworkX & NX/nosso & $c$ (ns) & Diverg. \\\\",
        "\\midrule",
        *corpo,
        "\\bottomrule",
        "\\end{tabular}",
        "\\end{table}",
        "",
    ])
    with open(arquivo, "w", encoding="utf-8") as f:
        f.write(texto)


def gravar_figura_tex(linhas, amb, arquivo):
    """Gráfico log-log: tempo por origem x (V + arcos), nas grades e nos grafos completos."""
    pares = resumo(linhas)
    series = []
    estilos = {("grade", "nosso"): "blue, mark=*", ("grade", "networkx"): "red, mark=square*",
               ("completo", "nosso"): "blue, dashed, mark=o", ("completo", "networkx"): "red, dashed, mark=square"}
    rotulos = {("grade", "nosso"): "Nosso (grade)", ("grade", "networkx"): "NetworkX (grade)",
               ("completo", "nosso"): "Nosso (completo)", ("completo", "networkx"): "NetworkX (completo)"}
    for familia in ("grade", "completo"):
        for impl in ("nosso", "networkx"):
            pontos = [(p[impl]["vertices"] + p[impl]["arcos"], por_origem(p[impl]))
                      for (_, peso, op), p in pares.items()
                      if peso == "distancia" and op == "uma_origem" and p[impl]["familia"] == familia]
            if not pontos:
                continue
            coords = " ".join(f"({x},{y:.4f})" for x, y in pontos)
            series += [f"\\addplot[{estilos[(familia, impl)]}] coordinates {{{coords}}};",
                       f"\\addlegendentry{{{rotulos[(familia, impl)]}}}"]
    texto = "\n".join([
        f"% Gerado por benchmark/comparar_dijkstra.py em {amb['data']} — não editar à mão.",
        "% Requer no preâmbulo: \\usepackage{pgfplots} e \\pgfplotsset{compat=1.18}",
        "\\begin{tikzpicture}",
        "\\begin{loglogaxis}[width=.85\\textwidth, height=6.5cm,",
        "  xlabel={$|V| + |\\text{arcos}|$}, ylabel={tempo por origem (ms)},",
        "  legend pos=north west, legend style={font=\\footnotesize}, grid=major]",
        *series,
        "\\end{loglogaxis}",
        "\\end{tikzpicture}",
        "",
    ])
    with open(arquivo, "w", encoding="utf-8") as f:
        f.write(texto)


NUMERICOS = {"vertices": int, "arestas": int, "arcos": int, "origens": int, "repeticoes": int,
             "divergencias": int, "conversao_networkx_ms": float, "mediana_ms": float,
             "minimo_ms": float, "maximo_ms": float}


def ler_resultados(pasta_resultados=PASTA_RESULTADOS):
    """Linhas e ambiente de uma execução já gravada (para refazer as saídas sem medir de novo)."""
    with open(os.path.join(pasta_resultados, "dijkstra_networkx.csv"), encoding="utf-8") as f:
        linhas = [{k: NUMERICOS.get(k, str)(v) if k != "direcionado" else v == "True" for k, v in r.items()}
                  for r in csv.DictReader(f)]
    with open(os.path.join(pasta_resultados, "ambiente.json"), encoding="utf-8") as f:
        return linhas, json.load(f)


def gravar(linhas, repeticoes, pasta_resultados=PASTA_RESULTADOS, pasta_relatorio=PASTA_RELATORIO, amb=None):
    amb = amb or ambiente()
    os.makedirs(pasta_resultados, exist_ok=True)
    os.makedirs(os.path.join(pasta_relatorio, "tabelas"), exist_ok=True)
    os.makedirs(os.path.join(pasta_relatorio, "figuras"), exist_ok=True)
    arquivos = [os.path.join(pasta_resultados, "dijkstra_networkx.csv"),
                os.path.join(pasta_resultados, "dijkstra_networkx.md"),
                os.path.join(pasta_relatorio, "tabelas", "dijkstra-networkx.tex"),
                os.path.join(pasta_relatorio, "figuras", "dijkstra-networkx.tex")]
    gravar_csv(linhas, arquivos[0])
    with open(os.path.join(pasta_resultados, "ambiente.json"), "w", encoding="utf-8") as f:
        json.dump(amb, f, ensure_ascii=False, indent=2)
    gravar_markdown(linhas, amb, arquivos[1], repeticoes)
    gravar_tabela_tex(linhas, amb, arquivos[2], repeticoes)
    gravar_figura_tex(linhas, amb, arquivos[3])
    return arquivos


def main(argv=None):
    p = argparse.ArgumentParser(description="Compara o nosso Dijkstra com o do NetworkX (só benchmark).")
    p.add_argument("--rapido", action="store_true", help="só instâncias pequenas (para conferir se roda)")
    p.add_argument("--repeticoes", type=int, default=5, help="execuções medidas por caso (padrão 5)")
    p.add_argument("--origens", type=int, default=10, help="origens sorteadas por instância (padrão 10)")
    p.add_argument("--pontos", type=int, default=30, help="pontos da matriz nas instâncias sintéticas (padrão 30)")
    p.add_argument("--saida", help="pasta para os resultados (padrão: benchmark/resultados e relatorio/)")
    p.add_argument("--so-saidas", action="store_true",
                   help="não mede: refaz tabela, gráfico e resumo a partir do CSV já gravado")
    args = p.parse_args(argv)

    if args.so_saidas:
        linhas, amb = ler_resultados(args.saida or PASTA_RESULTADOS)
        pastas = (args.saida, args.saida) if args.saida else (PASTA_RESULTADOS, PASTA_RELATORIO)
        arquivos = gravar(linhas, linhas[0]["repeticoes"], *pastas, amb=amb)
        print("Saídas refeitas a partir do CSV:\n  " + "\n  ".join(os.path.relpath(a, RAIZ) for a in arquivos))
        return 0

    linhas = executar(args.rapido, args.repeticoes, args.origens, args.pontos)
    if args.saida:
        arquivos = gravar(linhas, args.repeticoes, args.saida, args.saida)
    else:
        arquivos = gravar(linhas, args.repeticoes)
    total = sum(linha["divergencias"] for linha in linhas)
    print("\nDivergências de resultado:", "nenhuma" if total == 0 else "HÁ DIVERGÊNCIAS (veja acima)")
    legivel = [os.path.relpath(a, RAIZ) if a.startswith(RAIZ + os.sep) else a for a in arquivos]
    print("Arquivos gerados:\n  " + "\n  ".join(legivel))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
