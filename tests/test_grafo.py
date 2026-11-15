"""Testes da Dupla 1: classe Grafo, Dijkstra, leitura da base (CSV) e benchmark.

Não dependem do Flask: rodam direto sobre src/grafo, src/api/contrato.py e,
como consumidor provisório, mock.calcular_rotas (stub da Dupla 2).

    python -m unittest tests.test_grafo -v
"""
import unittest

from src.api.contrato import validar_grafo
from src.grafo import Grafo, caminho, dijkstra, matriz_custos


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

    def test_matriz_aceita_dicionario_do_contrato(self):
        d = grafo_pequeno().para_contrato()
        m = matriz_custos(d, "distancia")
        self.assertEqual(m[3][0], 4)
        self.assertEqual(m, matriz_custos(Grafo.de_contrato(d)))


if __name__ == "__main__":
    unittest.main()
