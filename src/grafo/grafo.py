"""Classe Grafo: grafo ponderado em lista de adjacência (sem NetworkX).

Por padrão é NÃO direcionado: é o grafo logístico (vértices = depósito e clientes,
com os atributos do contrato: id, nome, lat, lon, demanda, janela, prioridade, deposito).
Com Grafo(direcionado=True) vira o grafo viário: vértices = esquinas, arcos = trechos
de rua num sentido só (ruas de mão única).
Cada aresta (ou arco) tem dois pesos: distância (km) e tempo (min).

O formato de troca com a API e com a Dupla 2 é o dicionário de GET /api/grafo
({"vertices": [...], "arestas": [...]}), validado por src/api/contrato.py:
use Grafo.de_contrato(dicionario) e grafo.para_contrato() para converter.
Esse formato só existe para o grafo não direcionado.
"""

PESOS = ("distancia", "tempo")


class Grafo:
    def __init__(self, direcionado=False):
        self.direcionado = direcionado
        self._vertices = {}   # id -> dicionário de atributos
        self._adj = {}        # id -> {vizinho: {"distancia": km, "tempo": min}}
        self._num_arestas = 0

    # ------------------------------------------------------------------ vértices
    def adicionar_vertice(self, vertice):
        """Recebe um dicionário com os campos do contrato; o id não pode se repetir."""
        vid = vertice["id"]
        if vid in self._vertices:
            raise ValueError(f"id de vértice repetido: {vid}")
        self._vertices[vid] = dict(vertice)
        self._adj[vid] = {}

    def vertice(self, vid):
        return self._vertices[vid]

    def __contains__(self, vid):
        return vid in self._vertices

    def ids(self):
        return list(self._vertices)

    @property
    def num_vertices(self):
        return len(self._vertices)

    @property
    def deposito(self):
        """Id do depósito (o contrato exige exatamente um)."""
        depositos = [i for i, v in self._vertices.items() if v.get("deposito")]
        if len(depositos) != 1:
            raise ValueError(f"deve haver exatamente 1 depósito (há {len(depositos)})")
        return depositos[0]

    def clientes(self):
        return [i for i, v in self._vertices.items() if not v.get("deposito")]

    # ------------------------------------------------------------------- arestas
    def adicionar_aresta(self, u, v, distancia, tempo):
        """Aresta u-v (ou arco u->v, se direcionado).

        Recusa laços, repetições, vértices inexistentes e pesos negativos. No grafo
        direcionado, u->v e v->u são arcos diferentes (cada um pode ter o seu peso).
        """
        if u == v:
            raise ValueError(f"laço no vértice {u}")
        if u not in self._vertices or v not in self._vertices:
            raise ValueError(f"aresta {u}-{v} liga vértice inexistente")
        if v in self._adj[u]:
            raise ValueError(f"aresta repetida {u}-{v}")
        if distancia < 0 or tempo < 0:
            raise ValueError(f"aresta {u}-{v} com peso negativo")
        pesos = {"distancia": distancia, "tempo": tempo}
        self._adj[u][v] = pesos
        if not self.direcionado:
            self._adj[v][u] = pesos
        self._num_arestas += 1

    def vizinhos(self, u, peso="distancia"):
        """Lista de (vizinho, custo) de u segundo o peso escolhido ('distancia' ou 'tempo')."""
        if peso not in PESOS:
            raise ValueError(f"peso inválido: {peso}; use um de {PESOS}")
        return [(v, p[peso]) for v, p in self._adj[u].items()]

    def aresta(self, u, v):
        """Pesos da aresta u-v ({'distancia', 'tempo'}) ou None se não existir."""
        return self._adj.get(u, {}).get(v)

    @property
    def num_arestas(self):
        return self._num_arestas

    def arestas(self):
        """Cada aresta uma única vez, como (u, v, distancia, tempo). No direcionado, cada arco u->v."""
        vistas = set()
        for u, viz in self._adj.items():
            for v, p in viz.items():
                if self.direcionado:
                    yield u, v, p["distancia"], p["tempo"]
                    continue
                par = frozenset((u, v))
                if par not in vistas:
                    vistas.add(par)
                    yield u, v, p["distancia"], p["tempo"]

    def invertido(self):
        """Cópia com todos os arcos ao contrário (v->u no lugar de u->v).

        Um Dijkstra no grafo invertido, a partir de x, dá o custo de cada vértice ATÉ x.
        No grafo não direcionado, a cópia é igual ao original.
        """
        g = Grafo(self.direcionado)
        for v in self._vertices.values():
            g.adicionar_vertice(v)
        for u, v, d, t in self.arestas():
            if self.direcionado:
                g.adicionar_aresta(v, u, d, t)
            else:
                g.adicionar_aresta(u, v, d, t)
        return g

    # ----------------------------------------------------------------- conversão
    def para_contrato(self):
        """Dicionário no formato de GET /api/grafo (só para o grafo não direcionado)."""
        if self.direcionado:
            raise ValueError("o grafo direcionado (viário) não segue o contrato da API")
        return {
            "vertices": [dict(v) for v in self._vertices.values()],
            "arestas": [{"u": u, "v": v, "distancia": d, "tempo": t} for u, v, d, t in self.arestas()],
        }

    @classmethod
    def de_contrato(cls, dados):
        """Monta o Grafo a partir do dicionário de GET /api/grafo (o que calcular_rotas recebe)."""
        g = cls()
        for v in dados["vertices"]:
            g.adicionar_vertice(v)
        for a in dados["arestas"]:
            g.adicionar_aresta(a["u"], a["v"], a["distancia"], a["tempo"])
        return g

    def __repr__(self):
        tipo = "arcos" if self.direcionado else "arestas"
        return f"Grafo({self.num_vertices} vértices, {self.num_arestas} {tipo})"
