"""API Flask do RotaGrafo — liga o grafo (Dupla 1) e os algoritmos (Dupla 2) ao front-end.

Executar a partir da raiz do repositório:
    python src/api/app.py
e abrir http://localhost:5000
"""
import os
import sys
import time

from flask import Flask, jsonify, request, send_from_directory

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, RAIZ)

from src.algoritmos import calcular_rotas, ALGORITMOS  # noqa: E402
from src.api import mock  # noqa: E402
from src.api.auth import registrar_auth  # noqa: E402
from src.api.desempenho import medir_desempenho  # noqa: E402
from src.grafo import carregar_grafo as carregar_grafo_real  # noqa: E402
from src.grafo.dados import ARQUIVO_VERTICES  # noqa: E402
from src.grafo.mapa import Trajetos  # noqa: E402

# ---------------------------------------------------------------------------
# PONTO DE INTEGRAÇÃO
#   calcular_rotas    -> algoritmos reais da Dupla 2 (src/algoritmos)
#   medir_desempenho  -> benchmark do calcular_rotas real (src/api/desempenho.py);
#                        a Dupla 1 acrescenta a série do NetworkX
#   carregar_grafo    -> a base real da Dupla 1 (dados/*.csv, o mapa de SP gerado por
#                        python -m src.grafo.preparar_base) quando ela existir;
#                        enquanto não existir, os dados de exemplo (src/api/mock.py)
#
# FONTE            diz de onde vêm os DADOS ("real" ou "mock"); com "mock" a tela mostra o
#                  selo "dados de exemplo". Muda sozinha quando dados/vertices.csv é criado.
# FONTE_ALGORITMOS diz se os algoritmos são os reais; os testes de qualidade dependem dela.
# ---------------------------------------------------------------------------
FONTE_ALGORITMOS = "real"


def escolher_fonte_dos_dados(arquivo_vertices=ARQUIVO_VERTICES):
    """Devolve (função que carrega o grafo, rótulo da fonte).

    Com dados/vertices.csv, usa a leitura real (e uma base inválida impede a API de subir,
    com a lista de problemas). Sem ele, usa os dados de exemplo.
    """
    if os.path.isfile(arquivo_vertices):
        return carregar_grafo_real, "real"
    return mock.gerar_grafo, "mock"


carregar_grafo, FONTE = escolher_fonte_dos_dados()

TAMANHOS_PADRAO = [10, 25, 50, 100, 200]
TAMANHO_MAXIMO = 500

app = Flask(__name__, static_folder=os.path.join(
    RAIZ, "frontend"), static_url_path="")
registrar_auth(app)
_grafo = carregar_grafo()
_trajetos = Trajetos(_grafo)   # desenho de cada rota pelas ruas (caminhos mínimos)


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/grafo")
def api_grafo():
    return jsonify({**_grafo, "fonte": FONTE})


@app.get("/api/algoritmos")
def api_algoritmos():
    return jsonify(ALGORITMOS)


@app.post("/api/rotas")
def api_rotas():
    dados = request.get_json(silent=True) or {}
    try:
        veiculos = int(dados.get("veiculos", 3))
        capacidade = int(dados.get("capacidade", 100))
    except (TypeError, ValueError):
        return jsonify({"erro": "veiculos e capacidade devem ser números inteiros"}), 400
    algoritmo = dados.get("algoritmo", "clarke_wright")
    usar_2opt = bool(dados.get("usar_2opt", True))

    if veiculos < 1 or capacidade < 1:
        return jsonify({"erro": "veiculos e capacidade devem ser maiores que zero"}), 400
    if algoritmo not in ALGORITMOS:
        return jsonify({"erro": f"algoritmo inválido; use um de {list(ALGORITMOS)}"}), 400

    inicio = time.perf_counter()
    resultado = calcular_rotas(
        _grafo, veiculos, capacidade, algoritmo, usar_2opt)
    resultado["tempo_execucao_ms"] = round(
        (time.perf_counter() - inicio) * 1000, 3)
    for rota in resultado["rotas"]:
        # um trecho de pontos [lat, lon] por perna da rota, seguindo as ruas
        rota["trajetos"] = _trajetos.da_rota(rota["paradas"])
    resultado["fonte"] = FONTE
    return jsonify(resultado)


@app.get("/api/desempenho")
def api_desempenho():
    bruto = request.args.get("tamanhos")
    try:
        tamanhos = sorted({int(x) for x in bruto.split(",")}
                          ) if bruto else TAMANHOS_PADRAO
    except ValueError:
        return jsonify({"erro": "tamanhos deve ser uma lista de inteiros, ex.: 10,50,100"}), 400
    if not tamanhos or tamanhos[0] < 2 or tamanhos[-1] > TAMANHO_MAXIMO:
        return jsonify({"erro": f"use tamanhos entre 2 e {TAMANHO_MAXIMO}"}), 400
    resultado = medir_desempenho(tamanhos)
    resultado["fonte"] = "sintetico"  # mede grafos gerados por semente, não a base de dados
    return jsonify(resultado)


if __name__ == "__main__":
    app.run(debug=True)
