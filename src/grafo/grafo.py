"""Classe Grafo: grafo ponderado em lista de adjacência (sem NetworkX).

Um único grafo representa o mapa do local. Cada vértice tem um tipo:
  - "deposito": o centro de distribuição (exatamente um);
  - "cliente":  ponto de entrega (demanda, janela de tempo, prioridade);
  - "esquina":  cruzamento ou ponta de rua do OpenStreetMap (só serve de passagem).
Sem o campo "tipo", vale o padrão antigo: deposito=True é o depósito, o resto é cliente.

Cada aresta é um trecho de rua com dois pesos, distância (km) e tempo (min), e,
opcionalmente, o nome da rua e a geometria (pontos intermediários [lat, lon] do
desenho da rua, no sentido u -> v).

Por padrão o grafo é NÃO direcionado. Com Grafo(direcionado=True), cada arco u->v
vale num sentido só (ruas de mão única); rua de mão dupla vira dois arcos.

O formato de troca com a API e com a Dupla 2 é o dicionário de GET /api/grafo
({"vertices": [...], "arestas": [...]}), validado por src/api/contrato.py:
use Grafo.de_contrato(dicionario) e grafo.para_contrato() para converter.
No contrato, uma aresta com "mao_unica": true vale só de u para v; as demais valem
nos dois sentidos.
"""

PESOS = ("distancia", "tempo")
TIPOS = ("deposito", "cliente", "esquina")


def tipo_do_vertice(vertice):
    """Tipo do vértice ('deposito', 'cliente' ou 'esquina'), com o padrão para dados sem 'tipo'."""
    return vertice.get("tipo") or ("deposito" if vertice.get("deposito") else "cliente")


def _invertida(geometria):
    return [list(p) for p in reversed(geometria)] if geometria else geometria


class Grafo:
    def __init__(self, direcionado=False):
        self.direcionado = direcionado
        self._vertices = {}   # id -> dicionário de atributos
        self._adj = {}        # id -> {vizinho: {"distancia": km, "tempo": min}}
        self._info = {}       # (u, v) -> {"nome": ..., "geometria": [...]} (opcional, para o mapa)
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

    def tipo(self, vid):
        return tipo_do_vertice(self._vertices[vid])

    def clientes(self):
        """Ids dos clientes (não inclui o depósito nem as esquinas)."""
        return [i for i, v in self._vertices.items() if tipo_do_vertice(v) == "cliente"]

    def paradas(self):
        """Ids dos vértices onde um veículo pode parar: o depósito e os clientes (sem as esquinas)."""
        return [i for i, v in self._vertices.items() if tipo_do_vertice(v) != "esquina"]

    # ------------------------------------------------------------------- arestas
    def adicionar_aresta(self, u, v, distancia, tempo, nome=None, geometria=None):
        """Aresta u-v (ou arco u->v, se direcionado).

        Recusa laços, repetições, vértices inexistentes e pesos negativos. No grafo
        direcionado, u->v e v->u são arcos diferentes (cada um pode ter o seu peso).
        nome e geometria são opcionais e só servem para desenhar o trecho no mapa.
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
        if nome or geometria:
            self._info[(u, v)] = {"nome": nome, "geometria": geometria}
            if not self.direcionado:
                self._info[(v, u)] = {"nome": nome, "geometria": _invertida(geometria)}

    def vizinhos(self, u, peso="distancia"):
        """Lista de (vizinho, custo) de u segundo o peso escolhido ('distancia' ou 'tempo')."""
        if peso not in PESOS:
            raise ValueError(f"peso inválido: {peso}; use um de {PESOS}")
        return [(v, p[peso]) for v, p in self._adj[u].items()]

    def aresta(self, u, v):
        """Pesos da aresta u-v ({'distancia', 'tempo'}) ou None se não existir."""
        return self._adj.get(u, {}).get(v)

    def info_aresta(self, u, v):
        """Nome da rua e geometria do trecho u->v (pontos intermediários, no sentido u->v)."""
        return self._info.get((u, v), {"nome": None, "geometria": None})

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
            info = self.info_aresta(u, v)
            if self.direcionado:
                g.adicionar_aresta(v, u, d, t, info["nome"], _invertida(info["geometria"]))
            else:
                g.adicionar_aresta(u, v, d, t, info["nome"], info["geometria"])
        return g

    # ----------------------------------------------------------------- conversão
    def _aresta_contrato(self, u, v, d, t, mao_unica=False):
        a = {"u": u, "v": v, "distancia": d, "tempo": t}
        if mao_unica:
            a["mao_unica"] = True
        info = self.info_aresta(u, v)
        if info["nome"]:
            a["nome"] = info["nome"]
        if info["geometria"]:
            a["geometria"] = info["geometria"]
        return a

    def para_contrato(self):
        """Dicionário no formato de GET /api/grafo.

        No grafo direcionado, um par de arcos u->v e v->u iguais (mesmos pesos, mesmo
        desenho) vira uma aresta de mão dupla; um arco sem par igual vira "mao_unica": true.
        """
        arestas = []
        if not self.direcionado:
            arestas = [self._aresta_contrato(u, v, d, t) for u, v, d, t in self.arestas()]
        else:
            emitidos = set()
            for u, v, d, t in self.arestas():
                if (u, v) in emitidos:
                    continue
                volta = self.aresta(v, u)
                mao_dupla = (volta == {"distancia": d, "tempo": t} and
                             self.info_aresta(v, u)["geometria"] == _invertida(self.info_aresta(u, v)["geometria"]))
                arestas.append(self._aresta_contrato(u, v, d, t, mao_unica=not mao_dupla))
                emitidos.add((u, v))
                if mao_dupla:
                    emitidos.add((v, u))
        return {"vertices": [dict(v) for v in self._vertices.values()], "arestas": arestas}

    @classmethod
    def de_contrato(cls, dados):
        """Monta o Grafo a partir do dicionário de GET /api/grafo (o que calcular_rotas recebe).

        Se alguma aresta tiver "mao_unica": true, o grafo é direcionado e cada aresta de
        mão dupla vira dois arcos (ida e volta).
        """
        direcionado = any(a.get("mao_unica") for a in dados["arestas"])
        g = cls(direcionado=direcionado)
        for v in dados["vertices"]:
            g.adicionar_vertice(v)
        for a in dados["arestas"]:
            nome, geo = a.get("nome"), a.get("geometria")
            g.adicionar_aresta(a["u"], a["v"], a["distancia"], a["tempo"], nome, geo)
            if direcionado and not a.get("mao_unica"):
                g.adicionar_aresta(a["v"], a["u"], a["distancia"], a["tempo"], nome, _invertida(geo))
        return g

    def __repr__(self):
        tipo = "arcos" if self.direcionado else "arestas"
        return f"Grafo({self.num_vertices} vértices, {self.num_arestas} {tipo})"
