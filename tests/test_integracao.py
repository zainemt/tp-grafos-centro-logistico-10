"""Testes da integração da API com o código real das Duplas 1 e 2.

Conferem de onde vêm os dados, se os algoritmos são os reais e se a aba Desempenho
mede o código real (e não os dados de exemplo).

    python -m unittest discover tests -v
"""
import os
import tempfile
import unittest
from unittest.mock import patch

from src import grafo as nucleo_grafo
from src.api import app as api
from src.api import desempenho
from src.api import mock as dados_de_exemplo
from src.api.contrato import validar_desempenho


class TestFonteDosDados(unittest.TestCase):
    def test_sem_a_base_usa_os_dados_de_exemplo(self):
        funcao, rotulo = api.escolher_fonte_dos_dados(os.path.join("nao", "existe", "vertices.csv"))
        self.assertEqual(rotulo, "mock")
        self.assertIs(funcao, dados_de_exemplo.gerar_grafo)

    def test_com_a_base_usa_a_leitura_real(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = os.path.join(pasta, "vertices.csv")
            open(arquivo, "w", encoding="utf-8").close()
            funcao, rotulo = api.escolher_fonte_dos_dados(arquivo)
        self.assertEqual(rotulo, "real")
        self.assertIs(funcao, nucleo_grafo.carregar_grafo)

    def test_pasta_com_o_mesmo_nome_nao_conta_como_base(self):
        with tempfile.TemporaryDirectory() as pasta:
            funcao, rotulo = api.escolher_fonte_dos_dados(pasta)  # é uma pasta, não um arquivo
        self.assertEqual(rotulo, "mock")

    def test_os_algoritmos_sao_os_reais(self):
        self.assertEqual(api.FONTE_ALGORITMOS, "real")
        self.assertTrue(api.calcular_rotas.__module__.startswith("src.algoritmos"))

    def test_rotulo_da_api_acompanha_a_origem_do_grafo(self):
        cliente = api.app.test_client()
        estado = api.app.extensions["rotagrafo_auth"]
        usuarios = estado.usuarios
        self.addCleanup(lambda: setattr(estado, "usuarios", usuarios))
        estado.usuarios = {**usuarios, "integracao@teste": {"nome": "Integração", "hash": "x"}}
        with cliente.session_transaction() as sessao:
            sessao["email"] = "integracao@teste"
        self.assertEqual(cliente.get("/api/grafo").get_json()["fonte"], api.FONTE)


class TestDesempenhoReal(unittest.TestCase):
    def test_a_api_usa_o_benchmark_real(self):
        self.assertIs(api.medir_desempenho, desempenho.medir_desempenho)

    def test_formato_do_contrato(self):
        resultado = desempenho.medir_desempenho([3, 5])
        self.assertEqual(validar_desempenho(resultado), [])
        self.assertEqual([s["nome"] for s in resultado["series"]],
                         ["Vizinho mais próximo", "Clarke-Wright", "Clarke-Wright + 2-opt"])
        for serie in resultado["series"]:
            self.assertEqual([p["n"] for p in serie["pontos"]], [3, 5])

    def test_mede_o_calcular_rotas_real_em_grafos_do_tamanho_pedido(self):
        chamadas = []

        def falso(grafo, veiculos, capacidade, algoritmo, usar_2opt):
            chamadas.append((len(grafo["vertices"]), algoritmo, usar_2opt))

        with patch.object(desempenho, "calcular_rotas", falso):
            desempenho.medir_desempenho([4, 6])
        # depósito + n clientes; as 3 configurações; 3 repetições por ser grafo pequeno
        for n in (4, 6):
            for alg, opt in (("nn", False), ("clarke_wright", False), ("clarke_wright", True)):
                self.assertEqual(chamadas.count((n + 1, alg, opt)), 3, (n, alg, opt))

    def test_menos_repeticoes_em_grafos_grandes(self):
        self.assertEqual(desempenho.repeticoes_para(10), 3)
        self.assertEqual(desempenho.repeticoes_para(50), 3)
        self.assertEqual(desempenho.repeticoes_para(51), 1)
        self.assertEqual(desempenho.repeticoes_para(200), 1)


if __name__ == "__main__":
    unittest.main()
