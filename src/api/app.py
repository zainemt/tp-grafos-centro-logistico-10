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

from src.api import mock  # noqa: E402
from src.api.auth import registrar_auth  # noqa: E402

# ---------------------------------------------------------------------------
# PONTO DE INTEGRAÇÃO
# Quando o código real estiver pronto, troque estas funções:
#   carregar_grafo    -> função da Dupla 1 (src/grafo)
#   calcular_rotas    -> função da Dupla 2 (src/algoritmos)
#   medir_desempenho  -> benchmark das Duplas 1 e 2 (inclui a comparação com NetworkX)
# e mude FONTE para "real".
# ---------------------------------------------------------------------------
carregar_grafo = mock.gerar_grafo
calcular_rotas = mock.calcular_rotas
medir_desempenho = mock.medir_desempenho
FONTE = "mock"

TAMANHOS_PADRAO = [10, 25, 50, 100, 200]
TAMANHO_MAXIMO = 500

ALGORITMOS = {"nn": "Vizinho mais próximo", "clarke_wright": "Clarke-Wright"}

app = Flask(__name__, static_folder=os.path.join(RAIZ, "frontend"), static_url_path="")
registrar_auth(app)
_grafo = carregar_grafo()


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
    resultado = calcular_rotas(_grafo, veiculos, capacidade, algoritmo, usar_2opt)
    resultado["tempo_execucao_ms"] = round((time.perf_counter() - inicio) * 1000, 3)
    resultado["fonte"] = FONTE
    return jsonify(resultado)


@app.get("/api/desempenho")
def api_desempenho():
    bruto = request.args.get("tamanhos")
    try:
        tamanhos = sorted({int(x) for x in bruto.split(",")}) if bruto else TAMANHOS_PADRAO
    except ValueError:
        return jsonify({"erro": "tamanhos deve ser uma lista de inteiros, ex.: 10,50,100"}), 400
    if not tamanhos or tamanhos[0] < 2 or tamanhos[-1] > TAMANHO_MAXIMO:
        return jsonify({"erro": f"use tamanhos entre 2 e {TAMANHO_MAXIMO}"}), 400
    resultado = medir_desempenho(tamanhos)
    resultado["fonte"] = FONTE
    return jsonify(resultado)


if __name__ == "__main__":
    app.run(debug=True)
