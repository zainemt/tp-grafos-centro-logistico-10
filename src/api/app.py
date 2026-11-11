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

# ---------------------------------------------------------------------------
# PONTO DE INTEGRAÇÃO
# Quando o código real estiver pronto, troque estas duas funções:
#   carregar_grafo  -> função da Dupla 1 (src/grafo)
#   calcular_rotas  -> função da Dupla 2 (src/algoritmos)
# e mude FONTE para "real".
# ---------------------------------------------------------------------------
carregar_grafo = mock.gerar_grafo
calcular_rotas = mock.calcular_rotas
FONTE = "mock"

ALGORITMOS = {"nn": "Vizinho mais próximo", "clarke_wright": "Clarke-Wright"}

app = Flask(__name__, static_folder=os.path.join(RAIZ, "frontend"), static_url_path="")
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


if __name__ == "__main__":
    app.run(debug=True)
