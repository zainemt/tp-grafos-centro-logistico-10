"""Leitura da base de dados (dados/*.csv) e montagem do grafo no formato do contrato.

Ponto de integração com a API: carregar_grafo() substitui mock.gerar_grafo em
src/api/app.py. O resultado passa por src/api/contrato.validar_grafo antes de
ser devolvido; se algo estiver errado, levanta ErroDados com a lista de problemas.

Formato dos arquivos: ver dados/README.md.
"""
import csv
import math
import os

from src.api.contrato import validar_grafo
from src.grafo.dijkstra import dijkstra
from src.grafo.grafo import Grafo

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PASTA_DADOS = os.path.join(RAIZ, "dados")
ARQUIVO_VERTICES = os.path.join(PASTA_DADOS, "vertices.csv")
ARQUIVO_ARESTAS = os.path.join(PASTA_DADOS, "arestas.csv")

COLUNAS_VERTICES = ("id", "nome", "lat", "lon", "demanda", "janela_inicio", "janela_fim", "prioridade", "deposito")
COLUNAS_ARESTAS = ("u", "v", "distancia", "tempo")

# Usados só quando não há arestas.csv: o grafo vira completo, com a distância em
# linha reta (haversine) corrigida para ruas e o tempo a uma velocidade média urbana.
FATOR_RUAS = 1.3
VELOCIDADE_KMH = 30
MINUTOS_DIA = 24 * 60
PRIORIDADES_CLIENTE = {1, 2, 3}  # 1 = baixa, 3 = alta (o depósito usa 0)
VERDADEIRO = {"1", "true", "sim", "s", "yes", "y"}
FALSO = {"0", "false", "nao", "não", "n", "no", ""}


class ErroDados(ValueError):
    """Base de dados inválida. `problemas` traz uma mensagem por erro encontrado."""

    def __init__(self, problemas):
        self.problemas = list(problemas)
        super().__init__("base de dados inválida:\n  - " + "\n  - ".join(self.problemas))


# ---------------------------------------------------------------- conversões
def _inteiro(texto, campo):
    try:
        valor = float(texto.replace(",", "."))
    except (AttributeError, ValueError):
        raise ValueError(f"{campo} não é número: {texto!r}") from None
    if not valor.is_integer():
        raise ValueError(f"{campo} deve ser inteiro: {texto!r}")
    return int(valor)


def _real(texto, campo):
    try:
        valor = float(texto.replace(",", "."))
    except (AttributeError, ValueError):
        raise ValueError(f"{campo} não é número: {texto!r}") from None
    if not math.isfinite(valor):
        raise ValueError(f"{campo} não é número finito: {texto!r}")
    return valor


def _horario(texto, campo):
    """'HH:MM' ou minutos desde 00:00 -> minutos desde 00:00."""
    texto = (texto or "").strip()
    if ":" in texto:
        h, _, m = texto.partition(":")
        try:
            hh, mm = int(h), int(m)
        except ValueError:
            raise ValueError(f"{campo} inválido: {texto!r} (use HH:MM)") from None
        if not (0 <= mm < 60):
            raise ValueError(f"{campo} inválido: {texto!r}")
        minutos = hh * 60 + mm
    else:
        minutos = _inteiro(texto, campo)
    if not (0 <= minutos <= MINUTOS_DIA):
        raise ValueError(f"{campo} fora do dia (00:00 a 24:00): {texto!r}")
    return minutos


def _booleano(texto, campo):
    t = (texto or "").strip().lower()
    if t in VERDADEIRO:
        return True
    if t in FALSO:
        return False
    raise ValueError(f"{campo} deve ser 1/0 (ou sim/não): {texto!r}")


def _haversine_km(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (a["lat"], a["lon"], b["lat"], b["lon"]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


# ------------------------------------------------------------------- leitura
def _ler_csv(caminho, colunas):
    if not os.path.isfile(caminho):
        raise ErroDados([f"arquivo não encontrado: {caminho}"])
    with open(caminho, encoding="utf-8-sig", newline="") as f:  # utf-8-sig: aceita CSV salvo pelo Excel
        leitor = csv.DictReader(f)
        cabecalho = [c.strip() for c in (leitor.fieldnames or [])]
        faltando = [c for c in colunas if c not in cabecalho]
        if faltando:
            raise ErroDados([f"{os.path.basename(caminho)}: faltam as colunas {faltando}"])
        leitor.fieldnames = cabecalho
        # linha 1 = cabeçalho, então o primeiro registro é a linha 2
        return [(n, linha) for n, linha in enumerate(leitor, start=2)
                if any((valor or "").strip() for valor in linha.values() if isinstance(valor, str))]


def _vertice(linha):
    vertice = {
        "id": _inteiro(linha["id"], "id"),
        "nome": (linha["nome"] or "").strip(),
        "lat": _real(linha["lat"], "lat"),
        "lon": _real(linha["lon"], "lon"),
        "demanda": _inteiro(linha["demanda"], "demanda"),
        "janela": [_horario(linha["janela_inicio"], "janela_inicio"), _horario(linha["janela_fim"], "janela_fim")],
        "prioridade": _inteiro(linha["prioridade"], "prioridade"),
        "deposito": _booleano(linha["deposito"], "deposito"),
    }
    problemas = []
    if not vertice["nome"]:
        problemas.append("nome vazio")
    if not (-90 <= vertice["lat"] <= 90) or not (-180 <= vertice["lon"] <= 180):
        problemas.append(f"coordenada fora do intervalo: ({vertice['lat']}, {vertice['lon']})")
    if vertice["demanda"] < 0:
        problemas.append("demanda negativa")
    if vertice["janela"][0] > vertice["janela"][1]:
        problemas.append(f"janela começa depois de terminar: {linha['janela_inicio']}-{linha['janela_fim']}")
    if vertice["deposito"]:
        if vertice["demanda"] != 0:
            problemas.append("depósito deve ter demanda 0")
    elif vertice["prioridade"] not in PRIORIDADES_CLIENTE:
        problemas.append(f"prioridade deve ser 1, 2 ou 3: {vertice['prioridade']}")
    if problemas:
        raise ValueError("; ".join(problemas))
    return vertice


def _aresta(linha):
    a = {"u": _inteiro(linha["u"], "u"), "v": _inteiro(linha["v"], "v"),
         "distancia": _real(linha["distancia"], "distancia"), "tempo": _real(linha["tempo"], "tempo")}
    if a["distancia"] < 0 or a["tempo"] < 0:
        raise ValueError("peso negativo")
    return a


def _arestas_completas(vertices):
    """Uma aresta para cada par de vértices (grafo completo)."""
    arestas = []
    for i, u in enumerate(vertices):
        for v in vertices[i + 1:]:
            d = _haversine_km(u, v) * FATOR_RUAS
            arestas.append({"u": u["id"], "v": v["id"], "distancia": round(d, 3),
                            "tempo": round(d / VELOCIDADE_KMH * 60, 2)})
    return arestas


def ler_grafo(caminho_vertices=None, caminho_arestas=None):
    """Lê os CSV e devolve um Grafo validado.

    caminho_arestas=None usa o arestas.csv da mesma pasta do arquivo de vértices, se existir;
    senão monta o grafo completo.
    Levanta ErroDados listando todos os problemas encontrados (não para no primeiro).
    """
    caminho_vertices = caminho_vertices or ARQUIVO_VERTICES
    if caminho_arestas is None:
        vizinho = os.path.join(os.path.dirname(os.path.abspath(caminho_vertices)), os.path.basename(ARQUIVO_ARESTAS))
        if os.path.isfile(vizinho):
            caminho_arestas = vizinho

    problemas, vertices = [], []
    nome_v = os.path.basename(caminho_vertices)
    for n, linha in _ler_csv(caminho_vertices, COLUNAS_VERTICES):
        try:
            vertices.append(_vertice(linha))
        except ValueError as e:
            problemas.append(f"{nome_v}, linha {n}: {e}")

    if caminho_arestas:
        arestas, nome_a = [], os.path.basename(caminho_arestas)
        for n, linha in _ler_csv(caminho_arestas, COLUNAS_ARESTAS):
            try:
                arestas.append(_aresta(linha))
            except ValueError as e:
                problemas.append(f"{nome_a}, linha {n}: {e}")
    else:
        arestas = _arestas_completas(vertices)
    if problemas:
        raise ErroDados(problemas)

    dados = {"vertices": vertices, "arestas": arestas}
    problemas = validar_grafo(dados)  # mesmas checagens que a API e os testes de contrato fazem
    if problemas:
        raise ErroDados(problemas)

    grafo = Grafo()
    for v in vertices:
        grafo.adicionar_vertice(v)
    for a in arestas:
        try:
            grafo.adicionar_aresta(a["u"], a["v"], a["distancia"], a["tempo"])
        except ValueError as e:  # laço ou aresta repetida
            problemas.append(str(e))
    alcancaveis = dijkstra(grafo, grafo.deposito)[0] if not problemas else {}
    inalcancaveis = sorted(set(grafo.ids()) - alcancaveis.keys()) if not problemas else []
    if inalcancaveis:
        problemas.append(f"vértices inalcançáveis a partir do depósito: {inalcancaveis}")
    if problemas:
        raise ErroDados(problemas)
    return grafo


def carregar_grafo(caminho_vertices=None, caminho_arestas=None):
    """Função da Dupla 1 para a API: o grafo no formato de GET /api/grafo.

    Sem argumentos lê dados/vertices.csv (e dados/arestas.csv, se existir),
    como a API chama em src/api/app.py: `_grafo = carregar_grafo()`.
    """
    return ler_grafo(caminho_vertices, caminho_arestas).para_contrato()
