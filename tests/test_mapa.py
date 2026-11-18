"""Testes do mapa único (Dupla 1): depósito + clientes + esquinas num grafo só, com ruas de mão única.

Não dependem do Flask nem da internet: usam um mapa pequeno montado à mão.

    python -m unittest tests.test_mapa -v
"""
import os
import tempfile
import unittest

from src.algoritmos.melhoria import dois_opt
from src.api.contrato import validar_grafo, validar_rotas
from src.grafo import ErroDados, Grafo, carregar_grafo, ler_grafo, matriz_custos
from src.grafo.mapa import Trajetos


def mapa_pequeno():
    """Quarteirão com mão única: esquinas 101 -> 102 -> 103 -> 104 -> 101 (sentido horário).

        cliente 1 --- 102 ---> 103 --- cliente 2
                       ^        |
                       |        v
        depósito 0 -- 101 <--- 104

    Ir de 101 a 104 exige dar a volta (101 -> 102 -> 103 -> 104).
    """
    vertices = [
        {"id": 0, "nome": "CD", "lat": -23.5500, "lon": -46.6400, "demanda": 0, "janela": [0, 1440],
         "prioridade": 0, "deposito": True, "tipo": "deposito"},
        {"id": 1, "nome": "Cliente 1", "lat": -23.5480, "lon": -46.6400, "demanda": 5, "janela": [480, 720],
         "prioridade": 2, "deposito": False, "tipo": "cliente"},
        {"id": 2, "nome": "Cliente 2", "lat": -23.5480, "lon": -46.6370, "demanda": 7, "janela": [480, 720],
         "prioridade": 1, "deposito": False, "tipo": "cliente"},
    ]
    for i, (lat, lon) in {101: (-23.5500, -46.6390), 102: (-23.5480, -46.6390),
                          103: (-23.5480, -46.6380), 104: (-23.5500, -46.6380)}.items():
        vertices.append({"id": i, "nome": f"Esquina {i}", "lat": lat, "lon": lon, "demanda": 0,
                         "janela": [0, 1440], "prioridade": 0, "deposito": False, "tipo": "esquina"})
    arestas = [
        {"u": 101, "v": 102, "distancia": 0.2, "tempo": 1, "mao_unica": True, "nome": "Rua A",
         "geometria": [[-23.5490, -46.6390]]},
        {"u": 102, "v": 103, "distancia": 0.1, "tempo": 1, "mao_unica": True, "nome": "Rua B"},
        {"u": 103, "v": 104, "distancia": 0.2, "tempo": 1, "mao_unica": True, "nome": "Rua C"},
        {"u": 104, "v": 101, "distancia": 0.1, "tempo": 1, "mao_unica": True, "nome": "Rua D"},
        {"u": 0, "v": 101, "distancia": 0.1, "tempo": 1, "nome": "acesso"},
        {"u": 1, "v": 102, "distancia": 0.1, "tempo": 1, "nome": "acesso"},
        {"u": 2, "v": 103, "distancia": 0.15, "tempo": 1, "nome": "acesso"},
    ]
    return {"vertices": vertices, "arestas": arestas}


class TestMapaUnico(unittest.TestCase):
    def setUp(self):
        self.dados = mapa_pequeno()
        self.g = Grafo.de_contrato(self.dados)

    def test_contrato_valido_e_direcionado(self):
        self.assertEqual(validar_grafo(self.dados), [])
        self.assertTrue(self.g.direcionado)
        self.assertEqual(self.g.num_arestas, 4 + 2 * 3)      # 4 arcos de mão única + 3 acessos de mão dupla

    def test_esquina_nao_e_cliente(self):
        self.assertEqual(self.g.deposito, 0)
        self.assertEqual(sorted(self.g.clientes()), [1, 2])
        self.assertEqual(sorted(self.g.paradas()), [0, 1, 2])
        self.assertEqual(self.g.tipo(101), "esquina")

    def test_matriz_so_entre_paradas_e_assimetrica(self):
        dist = matriz_custos(self.g, "distancia")
        self.assertEqual(set(dist), {0, 1, 2})
        self.assertEqual(set(dist[0]), {0, 1, 2})
        # 1 -> 2: 1-102-103-2 (0,1+0,1+0,15); 2 -> 1: 2-103-104-101-102-1, dando a volta na quadra
        self.assertAlmostEqual(dist[1][2], 0.35)
        self.assertAlmostEqual(dist[2][1], 0.15 + 0.2 + 0.1 + 0.2 + 0.1)

    def test_ida_e_volta_pelo_contrato_mantem_nome_e_geometria(self):
        d = self.g.para_contrato()
        self.assertEqual(Grafo.de_contrato(d).para_contrato(), d)
        a = next(x for x in d["arestas"] if (x["u"], x["v"]) == (101, 102))
        self.assertEqual((a["nome"], a["geometria"], a["mao_unica"]), ("Rua A", [[-23.549, -46.639]], True))

    def test_trajeto_segue_as_ruas_e_a_mao_unica(self):
        t = Trajetos(self.dados)
        self.assertEqual(t.vertices(2, 1), [2, 103, 104, 101, 102, 1])
        pontos = t.pontos(0, 1)                               # 0 -> 101 -> (geometria) -> 102 -> 1
        self.assertEqual(pontos[0], [-23.55, -46.64])
        self.assertIn([-23.549, -46.639], pontos)
        self.assertEqual(pontos[-1], [-23.548, -46.64])
        self.assertEqual(len(t.da_rota([0, 1, 2, 0])), 3)    # um trecho por perna

    def test_rota_nao_pode_parar_em_esquina(self):
        res = {"rotas": [{"veiculo": 1, "paradas": [0, 101, 1, 2, 0], "chegadas": [], "saida": 480,
                          "retorno": 500, "distancia": 1, "tempo": 20, "carga": 12, "ocupacao": 0.1}],
               "nao_atendidos": [], "metricas": {"distancia_total": 1, "tempo_total": 20,
                                                 "veiculos_usados": 1, "atrasos": 0}}
        self.assertTrue(any("não são clientes" in e for e in validar_rotas(self.dados, res, 1, 100)))


class TestLeituraDoMapa(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def arquivo(self, nome, texto):
        caminho = os.path.join(self._tmp.name, nome)
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(texto)
        return caminho

    V = ("id,nome,lat,lon,demanda,janela_inicio,janela_fim,prioridade,deposito,tipo\n"
         "0,CD,-23.55,-46.64,0,00:00,24:00,0,1,deposito\n"
         "1,Cliente,-23.548,-46.64,5,08:00,12:00,2,0,cliente\n"
         "101,R. A × R. B,-23.55,-46.639,0,00:00,24:00,0,0,esquina\n")

    def test_colunas_do_mapa(self):
        v = self.arquivo("vertices.csv", self.V)
        a = self.arquivo("arestas.csv", "u,v,distancia,tempo,mao_unica,nome,geometria\n"
                                        "0,101,0.1,1,0,acesso,\n"
                                        "101,1,0.3,2,1,\"Rua A, trecho 1\",-23.549 -46.6395;-23.5485 -46.6398\n"
                                        "1,0,0.2,1,1,Rua B,\n")
        g = ler_grafo(v, a)
        self.assertTrue(g.direcionado)
        self.assertEqual(g.clientes(), [1])
        self.assertEqual(g.info_aresta(101, 1), {"nome": "Rua A, trecho 1",
                                                 "geometria": [[-23.549, -46.6395], [-23.5485, -46.6398]]})
        self.assertIsNone(g.aresta(1, 101))                   # mão única
        self.assertEqual(validar_grafo(carregar_grafo(v, a)), [])

    def test_sem_caminho_de_volta(self):
        v = self.arquivo("vertices.csv", self.V)
        a = self.arquivo("arestas.csv", "u,v,distancia,tempo,mao_unica\n0,101,0.1,1,1\n101,1,0.3,2,1\n")
        with self.assertRaises(ErroDados) as ctx:
            ler_grafo(v, a)
        self.assertIn("sem caminho de volta", "\n".join(ctx.exception.problemas))

    def test_esquina_com_demanda_e_tipo_invalido(self):
        v = self.arquivo("vertices.csv", self.V + "102,X,-23.55,-46.63,4,00:00,24:00,0,0,esquina\n"
                                                  "103,Y,-23.55,-46.63,0,00:00,24:00,0,0,praça\n")
        with self.assertRaises(ErroDados) as ctx:
            ler_grafo(v, self.arquivo("arestas.csv", "u,v,distancia,tempo\n0,1,1,1\n"))
        texto = "\n".join(ctx.exception.problemas)
        self.assertIn("esquina deve ter demanda 0", texto)
        self.assertIn("tipo inválido", texto)


class TestDoisOptAssimetrico(unittest.TestCase):
    def test_termina_e_nunca_piora_com_mao_unica(self):
        """Com dist[a][b] != dist[b][a] o 2-opt clássico (só as pontas) podia nunca terminar."""
        import random
        rnd = random.Random(3)
        n = 12
        dist = {a: {b: (0 if a == b else rnd.uniform(1, 10)) for b in range(n)} for a in range(n)}

        def custo(rota):
            c = [0] + rota + [0]
            return sum(dist[a][b] for a, b in zip(c, c[1:]))

        for _ in range(20):
            rota = list(range(1, n))
            rnd.shuffle(rota)
            nova = dois_opt(rota, 0, dist)
            self.assertEqual(sorted(nova), sorted(rota))
            self.assertLessEqual(custo(nova), custo(rota) + 1e-9)


if __name__ == "__main__":
    unittest.main()
