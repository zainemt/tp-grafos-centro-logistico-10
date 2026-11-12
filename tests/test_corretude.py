"""Testes de corretude: vão além do formato (test_contrato.py) e conferem se os
números devolvidos por calcular_rotas fazem sentido no grafo.

Rodam contra as funções que a API estiver usando (mock hoje; código real das
Duplas 1 e 2 depois da integração). As instâncias de teste são geradas por
mock.gerar_grafo só como gerador de cenários: qualquer calcular_rotas que siga
o contrato precisa funcionar com elas.

Os testes da classe TestQualidade só fazem sentido para os algoritmos reais e
são pulados enquanto FONTE == "mock".

    python -m unittest discover tests -v
"""
import heapq
import itertools
import unittest

from src.api import app as api
from src.api import mock

TOL = 0.05        # tolerância de arredondamento por trecho, em km
TOL_T = 0.11      # tolerância por trecho, em min (horários vêm arredondados a 0,1 min)
INSTANCIAS = [(8, 1), (15, 7), (20, 42), (30, 3)]  # (n_clientes, semente)
CENARIOS = [
    {"veiculos": 3, "capacidade": 150},
    {"veiculos": 5, "capacidade": 80},
    {"veiculos": 1, "capacidade": 100},    # frota insuficiente
    {"veiculos": 10, "capacidade": 1000},  # folga total
]


# ---------------------------------------------------------------------------
# Referências independentes do código das duplas
# ---------------------------------------------------------------------------
def adjacencia(grafo, peso):
    adj = {v["id"]: [] for v in grafo["vertices"]}
    for a in grafo["arestas"]:
        adj[a["u"]].append((a["v"], a[peso]))
        adj[a["v"]].append((a["u"], a[peso]))
    return adj


def caminhos_minimos(grafo, peso):
    """Dijkstra de referência a partir de cada vértice: {origem: {destino: custo}}."""
    adj = adjacencia(grafo, peso)
    todos = {}
    for origem in adj:
        dist = {origem: 0.0}
        fila = [(0.0, origem)]
        while fila:
            d, u = heapq.heappop(fila)
            if d > dist[u]:
                continue
            for v, w in adj[u]:
                if d + w < dist.get(v, float("inf")):
                    dist[v] = d + w
                    heapq.heappush(fila, (dist[v], v))
        todos[origem] = dist
    return todos


def floyd_warshall(grafo, peso):
    """Segunda referência, por outro método, para conferir a primeira."""
    ids = [v["id"] for v in grafo["vertices"]]
    inf = float("inf")
    d = {u: {v: (0.0 if u == v else inf) for v in ids} for u in ids}
    for a in grafo["arestas"]:
        w = min(d[a["u"]][a["v"]], a[peso])
        d[a["u"]][a["v"]] = d[a["v"]][a["u"]] = w
    for k in ids:
        for i in ids:
            for j in ids:
                if d[i][k] + d[k][j] < d[i][j]:
                    d[i][j] = d[i][k] + d[k][j]
    return d


def deposito_de(grafo):
    return next(v["id"] for v in grafo["vertices"] if v["deposito"])


def tour_otimo(clientes, deposito, dist):
    """Menor ciclo depósito -> todos os clientes -> depósito, por força bruta."""
    melhor = float("inf")
    for perm in itertools.permutations(clientes):
        caminho = (deposito, *perm, deposito)
        melhor = min(melhor, sum(dist[a][b] for a, b in zip(caminho, caminho[1:])))
    return melhor


# ---------------------------------------------------------------------------
class TestGrafo(unittest.TestCase):
    def setUp(self):
        self.grafo = api.carregar_grafo()

    def test_conexo_a_partir_do_deposito(self):
        alcancaveis = caminhos_minimos(self.grafo, "distancia")[deposito_de(self.grafo)]
        ids = {v["id"] for v in self.grafo["vertices"]}
        self.assertEqual(ids - alcancaveis.keys(), set(), "vértices inalcançáveis a partir do depósito")

    def test_sem_laços_nem_arestas_repetidas(self):
        vistas = set()
        for a in self.grafo["arestas"]:
            self.assertNotEqual(a["u"], a["v"], f"laço no vértice {a['u']}")
            par = frozenset((a["u"], a["v"]))
            self.assertNotIn(par, vistas, f"aresta repetida {a['u']}-{a['v']}")
            vistas.add(par)

    def test_referencias_de_caminho_minimo_concordam(self):
        """Garante que a referência usada nos outros testes está certa."""
        g = mock.gerar_grafo(n_clientes=12, semente=5)
        # remove arestas para o grafo deixar de ser completo e o Dijkstra ter trabalho
        g["arestas"] = [a for a in g["arestas"] if (a["u"] + a["v"]) % 3 != 0 or 0 in (a["u"], a["v"])]
        dj, fw = caminhos_minimos(g, "distancia"), floyd_warshall(g, "distancia")
        for u in dj:
            for v in dj[u]:
                self.assertAlmostEqual(dj[u][v], fw[u][v], places=6)


class _BaseRotas(unittest.TestCase):
    """Roda calcular_rotas em várias instâncias e cenários e entrega cada resultado."""

    def resultados(self):
        for n, semente in INSTANCIAS:
            grafo = mock.gerar_grafo(n_clientes=n, semente=semente)
            dist = caminhos_minimos(grafo, "distancia")
            tempo = caminhos_minimos(grafo, "tempo")
            for c in CENARIOS:
                for alg in api.ALGORITMOS:
                    for opt in (False, True):
                        res = api.calcular_rotas(grafo, c["veiculos"], c["capacidade"], alg, opt)
                        rotulo = dict(n=n, semente=semente, algoritmo=alg, usar_2opt=opt, **c)
                        yield rotulo, grafo, dist, tempo, c, res


class TestRotas(_BaseRotas):
    def test_distancia_da_rota_bate_com_caminhos_minimos(self):
        """A distância de cada rota é a soma dos menores caminhos entre paradas consecutivas."""
        for rotulo, _, dist, _, _, res in self.resultados():
            for r in res["rotas"]:
                with self.subTest(**rotulo, veiculo=r["veiculo"]):
                    p = r["paradas"]
                    esperado = sum(dist[a][b] for a, b in zip(p, p[1:]))
                    self.assertAlmostEqual(r["distancia"], esperado, delta=TOL * len(p))

    def test_horarios_respeitam_tempo_minimo_de_viagem(self):
        """Nenhum veículo chega antes do que o menor caminho em tempo permite."""
        for rotulo, _, _, tempo, _, res in self.resultados():
            for r in res["rotas"]:
                with self.subTest(**rotulo, veiculo=r["veiculo"]):
                    p, relogio = r["paradas"], r["saida"]
                    for (a, b), c in zip(zip(p, p[1:]), r["chegadas"]):
                        self.assertGreaterEqual(c["chegada"], relogio + tempo[a][b] - TOL_T)
                        relogio = c["fim"]
                    self.assertGreaterEqual(r["retorno"], relogio + tempo[p[-2]][p[-1]] - TOL_T)

    def test_janelas_de_tempo(self):
        """Espera a janela abrir, não espera à toa e marca 'atrasado' corretamente."""
        for rotulo, grafo, _, _, _, res in self.resultados():
            vs = {v["id"]: v for v in grafo["vertices"]}
            for r in res["rotas"]:
                for c in r["chegadas"]:
                    with self.subTest(**rotulo, veiculo=r["veiculo"], cliente=c["id"]):
                        ini, fim = vs[c["id"]]["janela"]
                        self.assertGreaterEqual(c["inicio"], ini - TOL_T, "entrega antes da janela abrir")
                        self.assertAlmostEqual(c["inicio"], max(c["chegada"], ini), delta=TOL_T,
                                               msg="veículo esperou sem necessidade")
                        self.assertEqual(c["atrasado"], c["inicio"] > fim + 1e-9)

    def test_metricas_somam_as_rotas(self):
        for rotulo, _, _, _, c, res in self.resultados():
            with self.subTest(**rotulo):
                rotas, m = res["rotas"], res["metricas"]
                self.assertAlmostEqual(m["distancia_total"], sum(r["distancia"] for r in rotas),
                                       delta=TOL * max(1, len(rotas)))
                self.assertAlmostEqual(m["tempo_total"], sum(r["tempo"] for r in rotas),
                                       delta=TOL_T * max(1, len(rotas)))
                self.assertEqual(m["veiculos_usados"], len(rotas))
                self.assertEqual(m["atrasos"], sum(ch["atrasado"] for r in rotas for ch in r["chegadas"]))
                for r in rotas:
                    self.assertAlmostEqual(r["ocupacao"], r["carga"] / c["capacidade"], delta=0.001)

    def test_sem_rotas_vazias(self):
        for rotulo, _, _, _, _, res in self.resultados():
            for r in res["rotas"]:
                with self.subTest(**rotulo, veiculo=r["veiculo"]):
                    self.assertGreater(len(r["paradas"]), 2, "veículo saiu e voltou sem entregar nada")

    def test_frota_com_folga_atende_todos(self):
        for rotulo, grafo, _, _, c, res in self.resultados():
            demandas = [v["demanda"] for v in grafo["vertices"] if not v["deposito"]]
            folga = c["veiculos"] >= len(demandas) and max(demandas) <= c["capacidade"]
            if folga:
                with self.subTest(**rotulo):
                    self.assertEqual(res["nao_atendidos"], [], "sobrou cliente com frota de sobra")

    def test_nao_e_melhor_que_o_otimo(self):
        """Em instâncias pequenas, nenhuma solução pode ser mais curta que o ótimo da força bruta.

        Com um único veículo de capacidade infinita, qualquer rota válida é um ciclo
        hamiltoniano. Se a distância informada ficar abaixo do ótimo, ela está errada.
        """
        for n, semente in [(5, 1), (6, 2), (7, 3)]:
            grafo = mock.gerar_grafo(n_clientes=n, semente=semente)
            dist = caminhos_minimos(grafo, "distancia")
            dep = deposito_de(grafo)
            clientes = [v["id"] for v in grafo["vertices"] if not v["deposito"]]
            otimo = tour_otimo(clientes, dep, dist)
            for alg in api.ALGORITMOS:
                for opt in (False, True):
                    with self.subTest(n=n, algoritmo=alg, usar_2opt=opt):
                        res = api.calcular_rotas(grafo, 1, 10**6, alg, opt)
                        self.assertEqual(res["nao_atendidos"], [])
                        self.assertGreaterEqual(res["metricas"]["distancia_total"], otimo - TOL * (n + 1))


@unittest.skipIf(api.FONTE == "mock", "só vale para os algoritmos reais (FONTE = 'real')")
class TestQualidade(_BaseRotas):
    def test_2opt_nunca_piora(self):
        """Com o mesmo algoritmo e a mesma frota, ligar o 2-opt não aumenta a distância."""
        for n, semente in INSTANCIAS:
            grafo = mock.gerar_grafo(n_clientes=n, semente=semente)
            for c in CENARIOS:
                for alg in api.ALGORITMOS:
                    with self.subTest(n=n, semente=semente, algoritmo=alg, **c):
                        sem = api.calcular_rotas(grafo, c["veiculos"], c["capacidade"], alg, False)
                        com = api.calcular_rotas(grafo, c["veiculos"], c["capacidade"], alg, True)
                        if sem["nao_atendidos"] == com["nao_atendidos"]:
                            self.assertLessEqual(com["metricas"]["distancia_total"],
                                                 sem["metricas"]["distancia_total"] + TOL)

    def test_proximo_do_otimo_em_instancias_pequenas(self):
        """Clarke-Wright + 2-opt deve ficar a no máximo 25% do ótimo com 1 veículo."""
        for n, semente in [(5, 1), (6, 2), (7, 3)]:
            grafo = mock.gerar_grafo(n_clientes=n, semente=semente)
            dist = caminhos_minimos(grafo, "distancia")
            clientes = [v["id"] for v in grafo["vertices"] if not v["deposito"]]
            otimo = tour_otimo(clientes, deposito_de(grafo), dist)
            with self.subTest(n=n):
                res = api.calcular_rotas(grafo, 1, 10**6, "clarke_wright", True)
                self.assertLessEqual(res["metricas"]["distancia_total"], otimo * 1.25)


if __name__ == "__main__":
    unittest.main()
