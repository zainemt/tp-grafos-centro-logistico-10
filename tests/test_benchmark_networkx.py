"""Testes da comparação Dijkstra x NetworkX (benchmark/comparar_dijkstra.py).

O primeiro teste roda sempre: garante que a aplicação (src/) não usa o NetworkX, que só
pode servir de referência no benchmark. Os demais precisam do NetworkX instalado
(pip install -r benchmark/requirements.txt) e são pulados sem ele.

    python -m unittest tests.test_benchmark_networkx -v
"""
import ast
import csv
import importlib.util
import os
import random
import tempfile
import unittest

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEM_NETWORKX = importlib.util.find_spec("networkx") is not None


def modulos_importados(arquivo):
    with open(arquivo, encoding="utf-8") as f:
        arvore = ast.parse(f.read(), filename=arquivo)
    nomes = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            nomes.update(a.name.split(".")[0] for a in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module:
            nomes.add(no.module.split(".")[0])
    return nomes


class TestAplicacaoSemNetworkX(unittest.TestCase):
    def test_src_nao_importa_networkx(self):
        culpados = []
        for pasta, _, arquivos in os.walk(os.path.join(RAIZ, "src")):
            for nome in arquivos:
                if nome.endswith(".py") and "networkx" in modulos_importados(os.path.join(pasta, nome)):
                    culpados.append(os.path.relpath(os.path.join(pasta, nome), RAIZ))
        self.assertEqual(culpados, [], "o NetworkX só pode ser usado em benchmark/")

    def test_networkx_fora_das_dependencias_da_aplicacao(self):
        with open(os.path.join(RAIZ, "requirements.txt"), encoding="utf-8") as f:
            self.assertNotIn("networkx", f.read().lower())


@unittest.skipUnless(TEM_NETWORKX, "NetworkX não instalado (pip install -r benchmark/requirements.txt)")
class TestComparacao(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from benchmark import comparar_dijkstra as cd
        cls.cd = cd
        cls.mapa = cd.mapa_sp()

    def test_conversao_preserva_o_grafo(self):
        for grafo in (self.mapa, self.cd.grade(5), self.cd.completo(6)):
            G = self.cd.para_networkx(grafo)
            self.assertEqual(G.is_directed(), grafo.direcionado)
            self.assertEqual(G.number_of_nodes(), grafo.num_vertices)
            self.assertEqual(G.number_of_edges(), grafo.num_arestas)
            for u, v, d, t in grafo.arestas():
                self.assertEqual((G[u][v]["distancia"], G[u][v]["tempo"]), (d, t))

    def test_mapa_real_mao_unica_preservada(self):
        G = self.cd.para_networkx(self.mapa)
        unicas = [(u, v) for u, v, _, _ in self.mapa.arestas() if self.mapa.aresta(v, u) is None]
        self.assertTrue(unicas)
        for u, v in unicas[:50]:
            self.assertFalse(G.has_edge(v, u), (u, v))

    def test_mesmos_custos_no_mapa_real(self):
        G = self.cd.para_networkx(self.mapa)
        rnd = random.Random(1)
        for origem in self.mapa.paradas()[:5]:
            for peso in self.cd.PESOS:
                self.assertEqual(self.cd.conferir_uma_origem(self.mapa, G, origem, peso, rnd), [])

    def test_mesma_matriz_no_mapa_real(self):
        G = self.cd.para_networkx(self.mapa)
        pontos = self.mapa.paradas()
        for peso in self.cd.PESOS:
            self.assertEqual(self.cd.conferir_matriz(self.cd.nosso_matriz(self.mapa, pontos, peso),
                                                     self.cd.nx_matriz(G, pontos, peso)), [])

    def test_a_conferencia_detecta_um_custo_errado(self):
        """Se a conferência nunca acusasse nada, o 'zero divergências' não provaria nada."""
        grafo = self.cd.grade(4)
        G = self.cd.para_networkx(grafo)
        G[0][1]["distancia"] += 1.0   # estraga um peso só do lado do NetworkX
        problemas = self.cd.conferir_uma_origem(grafo, G, 0, "distancia", random.Random(1))
        self.assertTrue(problemas)

    def test_a_conferencia_detecta_alcance_diferente(self):
        grafo = self.cd.grade(3)
        G = self.cd.para_networkx(grafo)
        G.add_node(999)
        G.add_edge(0, 999, distancia=1.0, tempo=1.0)
        problemas = self.cd.conferir_uma_origem(grafo, G, 0, "distancia", random.Random(1))
        self.assertTrue(any("alcançáveis" in p for p in problemas))

    def test_grade_tem_o_tamanho_pedido(self):
        g = self.cd.grade(7)
        self.assertEqual(g.num_vertices, 49)
        self.assertEqual(g.num_arestas, 2 * 7 * 6)
        self.assertEqual(self.cd.num_arcos(g), 2 * g.num_arestas)

    def test_execucao_rapida_gera_os_arquivos(self):
        linhas = self.cd.executar(rapido=True, repeticoes=1, n_origens=2, n_pontos=3, mostrar=lambda *_: None)
        self.assertTrue(all(linha["divergencias"] == 0 for linha in linhas))
        # instâncias x 2 pesos x 2 operações x 2 implementações
        self.assertEqual(len(linhas), len(self.cd.instancias(rapido=True)) * 8)
        with tempfile.TemporaryDirectory() as pasta:
            arquivos = self.cd.gravar(linhas, 1, pasta, pasta)
            for arquivo in arquivos:
                self.assertTrue(os.path.getsize(arquivo) > 0, arquivo)
            with open(arquivos[0], encoding="utf-8") as f:
                self.assertEqual(len(list(csv.DictReader(f))), len(linhas))
            with open(arquivos[2], encoding="utf-8") as f:
                self.assertIn("\\label{tab:dijkstra-networkx}", f.read())


if __name__ == "__main__":
    unittest.main()
