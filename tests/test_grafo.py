"""Testes da Dupla 1: classe Grafo, Dijkstra, leitura da base (CSV) e benchmark.

Não dependem do Flask: rodam direto sobre src/grafo, src/api/contrato.py e,
como consumidor provisório, mock.calcular_rotas (stub da Dupla 2).

    python -m unittest tests.test_grafo -v
"""
import os
import tempfile
import unittest

from src.api.contrato import validar_grafo
from src.grafo import ErroDados, Grafo, caminho, dijkstra, ler_grafo, matriz_custos
from src.grafo.gerador import gerar_grafo, gerar_vertices

CABECALHO_V = "id,nome,lat,lon,demanda,janela_inicio,janela_fim,prioridade,deposito\n"
DEPOSITO_CSV = "0,CD,-19.92,-43.94,0,00:00,24:00,0,1\n"


def _vertice(i, deposito=False):
    return {"id": i, "nome": f"V{i}", "lat": -19.9 + i / 100, "lon": -43.9, "demanda": 0 if deposito else 10,
            "janela": [480, 600], "prioridade": 0 if deposito else 1, "deposito": deposito}


def grafo_pequeno():
    """0-1 (1), 1-2 (2), 0-2 (10), 2-3 (1), 4 isolado: o caminho 0->2 bom passa por 1."""
    g = Grafo()
    g.adicionar_vertice(_vertice(0, deposito=True))
    for i in range(1, 5):
        g.adicionar_vertice(_vertice(i))
    for u, v, d in [(0, 1, 1), (1, 2, 2), (0, 2, 10), (2, 3, 1)]:
        g.adicionar_aresta(u, v, d, d * 2)
    return g


def bellman_ford(grafo, origem, peso):
    """Referência independente do Dijkstra."""
    custo = {origem: 0.0}
    for _ in range(grafo.num_vertices - 1):
        for u, v, d, t in grafo.arestas():
            w = d if peso == "distancia" else t
            for a, b in ((u, v), (v, u)):
                if a in custo and custo[a] + w < custo.get(b, float("inf")):
                    custo[b] = custo[a] + w
    return custo


class TestGrafo(unittest.TestCase):
    def test_estrutura(self):
        g = grafo_pequeno()
        self.assertEqual((g.num_vertices, g.num_arestas), (5, 4))
        self.assertEqual(g.deposito, 0)
        self.assertEqual(sorted(g.clientes()), [1, 2, 3, 4])
        self.assertEqual(sorted(g.vizinhos(2)), [(0, 10), (1, 2), (3, 1)])
        self.assertEqual(sorted(g.vizinhos(2, "tempo")), [(0, 20), (1, 4), (3, 2)])
        self.assertEqual(g.aresta(1, 0), {"distancia": 1, "tempo": 2})
        self.assertIsNone(g.aresta(0, 3))

    def test_recusa_entradas_invalidas(self):
        g = grafo_pequeno()
        casos = [lambda: g.adicionar_vertice(_vertice(1)),         # id repetido
                 lambda: g.adicionar_aresta(1, 1, 1, 1),           # laço
                 lambda: g.adicionar_aresta(1, 0, 1, 1),           # repetida (não direcionado)
                 lambda: g.adicionar_aresta(1, 99, 1, 1),          # vértice inexistente
                 lambda: g.adicionar_aresta(1, 3, -1, 1),          # peso negativo
                 lambda: g.vizinhos(1, "custo")]                   # peso inválido
        for i, caso in enumerate(casos):
            with self.subTest(caso=i):
                self.assertRaises(ValueError, caso)

    def test_ida_e_volta_pelo_contrato(self):
        g = grafo_pequeno()
        d = g.para_contrato()
        self.assertEqual(validar_grafo(d), [])
        self.assertEqual(Grafo.de_contrato(d).para_contrato(), d)

    def test_dois_depositos(self):
        g = grafo_pequeno()
        g.adicionar_vertice(_vertice(9, deposito=True))
        with self.assertRaises(ValueError):
            g.deposito


class TestDijkstra(unittest.TestCase):
    def test_caminho_minimo(self):
        custo, anterior = dijkstra(grafo_pequeno(), 0)
        self.assertEqual(custo, {0: 0, 1: 1, 2: 3, 3: 4})   # 4 é inalcançável e fica de fora
        self.assertEqual(caminho(anterior, 0, 3), [0, 1, 2, 3])
        self.assertEqual(caminho(anterior, 0, 0), [0])
        self.assertEqual(caminho(anterior, 0, 4), [])

    def test_peso_tempo_e_origem_inexistente(self):
        self.assertEqual(dijkstra(grafo_pequeno(), 0, "tempo")[0][3], 8)
        self.assertRaises(KeyError, dijkstra, grafo_pequeno(), 42)

    def test_confere_com_bellman_ford(self):
        g = gerar_grafo(15, semente=3)
        esparso = Grafo()   # tira arestas para o grafo deixar de ser completo
        for i in g.ids():
            esparso.adicionar_vertice(g.vertice(i))
        for u, v, d, t in g.arestas():
            if (u + v) % 3 != 0 or 0 in (u, v):
                esparso.adicionar_aresta(u, v, d, t)
        for peso in ("distancia", "tempo"):
            for origem in esparso.ids():
                with self.subTest(peso=peso, origem=origem):
                    nosso, ref = dijkstra(esparso, origem, peso)[0], bellman_ford(esparso, origem, peso)
                    self.assertEqual(nosso.keys(), ref.keys())
                    for v in ref:
                        self.assertAlmostEqual(nosso[v], ref[v], places=9)

    def test_matriz_aceita_dicionario_do_contrato(self):
        d = grafo_pequeno().para_contrato()
        m = matriz_custos(d, "distancia")
        self.assertEqual(m[3][0], 4)
        self.assertEqual(m, matriz_custos(Grafo.de_contrato(d)))


class TestGerador(unittest.TestCase):
    def test_mesma_semente_mesmo_resultado(self):
        self.assertEqual(gerar_vertices(10, semente=5), gerar_vertices(10, semente=5))
        self.assertNotEqual(gerar_vertices(10, semente=5), gerar_vertices(10, semente=6))

    def test_instancia_cumpre_o_contrato(self):
        g = gerar_grafo(12, semente=1)
        self.assertEqual(validar_grafo(g.para_contrato()), [])
        self.assertEqual((g.num_vertices, g.num_arestas), (13, 12 * 13 // 2))   # grafo completo
        for i in g.clientes():
            v = g.vertice(i)
            self.assertIn(v["prioridade"], (1, 2, 3))
            self.assertTrue(480 <= v["janela"][0] < v["janela"][1] <= 18 * 60)
            self.assertTrue(5 <= v["demanda"] <= 30)


class TestDados(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def arquivo(self, nome, texto, encoding="utf-8"):
        caminho = os.path.join(self._tmp.name, nome)
        with open(caminho, "w", encoding=encoding, newline="") as f:
            f.write(texto)
        return caminho

    def erros(self, *args, **kw):
        with self.assertRaises(ErroDados) as ctx:
            ler_grafo(*args, **kw)
        return "\n".join(ctx.exception.problemas)

    def test_horarios_e_bom_do_excel(self):
        v = self.arquivo("v.csv", CABECALHO_V + DEPOSITO_CSV + "1,Loja,-19.93,-43.95,7,08:30,600,3,0\n",
                         encoding="utf-8-sig")
        g = ler_grafo(v)
        self.assertEqual(g.vertice(1)["janela"], [510, 600])
        self.assertEqual(g.vertice(0)["janela"], [0, 1440])
        self.assertEqual(g.num_arestas, 1)
        self.assertEqual(validar_grafo(g.para_contrato()), [])

    def test_arquivo_inexistente(self):
        self.assertIn("não encontrado", self.erros(os.path.join(self._tmp.name, "nada.csv")))

    def test_coluna_faltando(self):
        v = self.arquivo("v.csv", "id,nome,lat,lon\n0,CD,1,1\n")
        self.assertIn("faltam as colunas", self.erros(v))

    def test_registros_invalidos_listados_todos(self):
        v = self.arquivo("v.csv", CABECALHO_V + DEPOSITO_CSV +
                         "1,A,abc,-43.9,10,08:00,10:00,1,0\n"     # lat não numérica
                         "2,B,-19.9,-43.9,-5,08:00,10:00,1,0\n"   # demanda negativa
                         "3,C,-19.9,-43.9,5,11:00,10:00,1,0\n"    # janela invertida
                         "4,D,-19.9,-43.9,5,08:00,25:00,1,0\n"    # fora do dia
                         "5,E,-19.9,-43.9,5,08:00,10:00,7,0\n"    # prioridade inválida
                         "6,,-19.9,-43.9,5,08:00,10:00,1,0\n"     # nome vazio
                         "7,G,-19.9,-43.9,5,08:00,10:00,1,talvez\n")
        texto = self.erros(v)
        for linha in range(3, 10):
            self.assertIn(f"linha {linha}:", texto)

    def test_regras_do_contrato(self):
        dois_depositos = self.arquivo("a.csv", CABECALHO_V + DEPOSITO_CSV + "1,CD2,-19.9,-43.9,0,00:00,24:00,0,1\n")
        self.assertIn("exatamente 1 depósito", self.erros(dois_depositos))
        id_repetido = self.arquivo("b.csv", CABECALHO_V + DEPOSITO_CSV + "0,X,-19.9,-43.9,5,08:00,10:00,1,0\n")
        self.assertIn("repetido", self.erros(id_repetido))

    def test_arestas_csv(self):
        v = self.arquivo("v.csv", CABECALHO_V + DEPOSITO_CSV +
                         "1,A,-19.9,-43.9,5,08:00,10:00,1,0\n2,B,-19.8,-43.9,5,08:00,10:00,1,0\n")
        ok = self.arquivo("ok.csv", "u,v,distancia,tempo\n0,1,2.5,5\n1,2,1,2\n")
        g = ler_grafo(v, ok)
        self.assertEqual(g.num_arestas, 2)
        self.assertEqual(dijkstra(g, 0)[0][2], 3.5)
        # sem informar as arestas, usa o arestas.csv da mesma pasta dos vértices
        self.arquivo("arestas.csv", "u,v,distancia,tempo\n0,1,2.5,5\n1,2,1,2\n")
        self.assertEqual(ler_grafo(v).num_arestas, 2)
        casos = {"inexistente": "u,v,distancia,tempo\n0,1,1,1\n1,9,1,1\n",
                 "negativo": "u,v,distancia,tempo\n0,1,-1,1\n1,2,1,1\n",
                 "repetida": "u,v,distancia,tempo\n0,1,1,1\n1,0,1,1\n1,2,1,1\n",
                 "inalcançáveis": "u,v,distancia,tempo\n0,1,1,1\n"}
        for esperado, texto in casos.items():
            with self.subTest(esperado=esperado):
                self.assertIn(esperado, self.erros(v, self.arquivo("a.csv", texto)))


if __name__ == "__main__":
    unittest.main()
