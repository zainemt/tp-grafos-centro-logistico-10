"""Testes de contrato: rodam contra as funções que a API estiver usando
(mock hoje; código real das Duplas 1 e 2 depois da integração).

    python -m unittest discover tests -v
"""
import unittest

from src.api import app as api
from src.api.contrato import validar_desempenho, validar_grafo, validar_rotas

CENARIOS = [
    {"veiculos": 3, "capacidade": 150},
    {"veiculos": 5, "capacidade": 80},
    {"veiculos": 1, "capacidade": 100},   # frota insuficiente
    {"veiculos": 10, "capacidade": 1000},  # folga total
]


class TestGrafo(unittest.TestCase):
    def test_formato_do_grafo(self):
        self.assertEqual(validar_grafo(api.carregar_grafo()), [])


class TestRotas(unittest.TestCase):
    def setUp(self):
        self.grafo = api.carregar_grafo()

    def test_todas_as_combinacoes(self):
        for c in CENARIOS:
            for alg in api.ALGORITMOS:
                for opt in (False, True):
                    with self.subTest(**c, algoritmo=alg, usar_2opt=opt):
                        res = api.calcular_rotas(self.grafo, c["veiculos"], c["capacidade"], alg, opt)
                        self.assertEqual(validar_rotas(self.grafo, res, c["veiculos"], c["capacidade"]), [])


class TestDesempenho(unittest.TestCase):
    def test_formato(self):
        self.assertEqual(validar_desempenho(api.medir_desempenho([5, 10])), [])


class TestApi(unittest.TestCase):
    def setUp(self):
        self.cliente = api.app.test_client()
        # As rotas exigem login; este teste verifica o contrato, não a autenticação.
        estado = api.app.extensions["rotagrafo_auth"]
        usuarios_originais = estado.usuarios
        self.addCleanup(lambda: setattr(estado, "usuarios", usuarios_originais))
        estado.usuarios = {**usuarios_originais, "contrato@teste": {"nome": "Contrato", "hash": "x"}}
        with self.cliente.session_transaction() as sessao:
            sessao["email"] = "contrato@teste"

    def test_pagina_e_grafo(self):
        for caminho in ("/", "/app.js", "/style.css", "/api/grafo"):
            with self.subTest(caminho=caminho):
                resp = self.cliente.get(caminho)
                self.assertEqual(resp.status_code, 200)
                resp.close()

    def test_rotas_ok(self):
        r = self.cliente.post("/api/rotas", json={"veiculos": 3, "capacidade": 150,
                                                  "algoritmo": "clarke_wright", "usar_2opt": True})
        self.assertEqual(r.status_code, 200)
        self.assertIn("tempo_execucao_ms", r.get_json())

    def test_desempenho(self):
        self.assertEqual(self.cliente.get("/api/desempenho?tamanhos=5,10").status_code, 200)
        for q in ("abc", "1", "9999"):
            with self.subTest(tamanhos=q):
                self.assertEqual(self.cliente.get(f"/api/desempenho?tamanhos={q}").status_code, 400)

    def test_entradas_invalidas(self):
        for corpo in ({"algoritmo": "x"}, {"veiculos": 0}, {"capacidade": "abc"}):
            with self.subTest(corpo=corpo):
                self.assertEqual(self.cliente.post("/api/rotas", json=corpo).status_code, 400)


if __name__ == "__main__":
    unittest.main()
