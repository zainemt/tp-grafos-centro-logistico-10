"""Monta a base do RotaGrafo (dados/vertices.csv e dados/arestas.csv) a partir de dados reais.

Fontes:
  - Olist VRP Benchmark (NVIDIA, base pública de e-commerce da Olist): os pedidos de
    São Paulo viram os CLIENTES (posição e volume do pedido) e um vendedor vira o DEPÓSITO.
    https://github.com/NVlabs/olist-vrp-benchmark
  - OpenStreetMap (API Overpass): as RUAS da região, com sentido (mão única) e
    velocidade máxima. https://www.openstreetmap.org/copyright

Resultado: um ÚNICO grafo, que é o mapa do local.
  vértices = depósito + clientes + esquinas (cruzamentos e pontas de rua);
  arestas  = trechos de rua entre duas esquinas, com distância (km), tempo (min), nome
             da rua e o desenho do trecho; rua de mão única vira arco num sentido só.
O depósito e cada cliente são ligados à esquina (ou ponto de rua) mais próxima por um
trecho curto de "acesso". O custo entre duas paradas passa a ser o caminho mínimo pelas
ruas (Dijkstra), e a rota desenhada no mapa segue o traçado das ruas.

Uso (na raiz do repositório):
    python -m src.grafo.preparar_base
    python -m src.grafo.preparar_base --clientes 40 --raio-km 1.2 --semente 7
Os downloads ficam em dados/brutos/ (fora do git) e são reaproveitados; --baixar-de-novo
força baixar outra vez. Só usa a biblioteca padrão do Python.
"""
import argparse
import csv
import io
import json
import math
import os
import random
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import Counter, deque

if __package__ in (None, ""):  # permite rodar também como arquivo solto
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.grafo.dados import ARQUIVO_ARESTAS, ARQUIVO_VERTICES, PASTA_DADOS, ler_grafo  # noqa: E402
from src.grafo.gerador import sortear_janela_e_prioridade  # noqa: E402

PASTA_BRUTOS = os.path.join(PASTA_DADOS, "brutos")
ARQUIVO_INFO = os.path.join(PASTA_DADOS, "base_info.json")

URL_OLIST_ZIP = "https://media.githubusercontent.com/media/NVlabs/olist-vrp-benchmark/main/coordinates.zip"
ARQUIVOS_OLIST = ("coordinates_sao_paulo_test.csv", "sellers_sao_paulo.csv")
SERVIDORES_OVERPASS = ("https://overpass-api.de/api/interpreter",
                       "https://overpass.private.coffee/api/interpreter",
                       "https://overpass.kumi.systems/api/interpreter")
AGENTE = "RotaGrafo-tp-grafos/1.0 (trabalho academico de Teoria dos Grafos)"

# Vias por onde um veículo de entrega pode passar (sem calçadas, ciclovias, estacionamentos...).
TIPOS_DE_VIA = ("motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential",
                "living_street", "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link")
# Velocidade máxima (km/h) quando a via não informa "maxspeed" no OSM.
VELOCIDADE_PADRAO = {"motorway": 90, "trunk": 60, "primary": 50, "secondary": 50, "tertiary": 40,
                     "unclassified": 40, "residential": 30, "living_street": 20}
VELOCIDADE_LINK = 30
# Vias onde não dá para parar e entregar: o acesso de depósito/clientes nunca é ligado a elas.
SEM_PARADA = ("motorway", "trunk", "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link")
FATOR_TRANSITO = 0.6         # velocidade média = 60% da máxima (trânsito, semáforos, conversões)
VELOCIDADE_ACESSO_KMH = 15   # trecho curto entre a rua e a porta do cliente/depósito
LIMITE_ACESSO_KM = 0.25      # cliente a mais que isso da rua mais próxima é descartado
MARGEM_KM = 0.4              # ruas além do raio dos clientes, para os caminhos não ficarem presos na borda
PRIMEIRO_ID_ESQUINA = 1001


# ------------------------------------------------------------------ utilidades
def _contexto_ssl():
    """Verificação SSL normal. O Python do python.org no macOS vem sem certificados até rodar
    'Install Certificates.command'; nesse caso, usa os certificados do próprio sistema."""
    ctx = ssl.create_default_context()
    if not ctx.get_ca_certs() and os.path.isfile("/etc/ssl/cert.pem"):
        ctx.load_verify_locations("/etc/ssl/cert.pem")
    return ctx


SSL = _contexto_ssl()


def _abrir(req, timeout=120):
    return urllib.request.urlopen(req, timeout=timeout, context=SSL)


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def _log(msg):
    print(msg, flush=True)


# ------------------------------------------------------------------ Olist
class _ZipRemoto(io.RawIOBase):
    """Arquivo remoto lido por pedaços (HTTP Range): o zip da Olist tem ~1 GB, quase tudo
    matrizes de distância que não usamos; assim baixamos só os CSV necessários (~1 MB)."""

    def __init__(self, url):
        self.url, self.pos, self.baixado = url, 0, 0
        with _abrir(urllib.request.Request(url, method="HEAD", headers={"User-Agent": AGENTE})) as r:
            self.tamanho = int(r.headers["Content-Length"])

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, deslocamento, de_onde=0):
        self.pos = {0: deslocamento, 1: self.pos + deslocamento, 2: self.tamanho + deslocamento}[de_onde]
        return self.pos

    def readinto(self, buffer):
        n = min(len(buffer), self.tamanho - self.pos)
        if n <= 0:
            return 0
        req = urllib.request.Request(self.url, headers={"User-Agent": AGENTE,
                                                        "Range": f"bytes={self.pos}-{self.pos + n - 1}"})
        with _abrir(req) as r:
            if r.status != 206:
                raise IOError(f"o servidor não aceitou download parcial (HTTP {r.status})")
            dados = r.read()
        buffer[:len(dados)] = dados
        self.pos += len(dados)
        self.baixado += len(dados)
        return len(dados)


def baixar_olist(baixar_de_novo=False):
    os.makedirs(PASTA_BRUTOS, exist_ok=True)
    faltando = [a for a in ARQUIVOS_OLIST if baixar_de_novo or not os.path.isfile(os.path.join(PASTA_BRUTOS, a))]
    if not faltando:
        _log("Olist: usando os arquivos já baixados em dados/brutos/")
        return
    _log(f"Olist: baixando {', '.join(faltando)} de dentro do coordinates.zip ...")
    remoto = _ZipRemoto(URL_OLIST_ZIP)
    with zipfile.ZipFile(io.BufferedReader(remoto, buffer_size=1 << 20)) as z:
        for nome in faltando:
            with z.open(nome) as origem, open(os.path.join(PASTA_BRUTOS, nome), "wb") as destino:
                destino.write(origem.read())
    _log(f"Olist: {remoto.baixado / 1e6:.1f} MB baixados (de {remoto.tamanho / 1e9:.1f} GB do zip)")


def ler_olist():
    with open(os.path.join(PASTA_BRUTOS, ARQUIVOS_OLIST[0]), encoding="utf-8") as f:
        pedidos = [{"lat": float(r["geolocation_lat"]), "lon": float(r["geolocation_lng"]),
                    "volume": float(r["volume_clipped"])} for r in csv.DictReader(f)]
    vendedores = {}
    with open(os.path.join(PASTA_BRUTOS, ARQUIVOS_OLIST[1]), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            vendedores[r["seller_id"]] = {"lat": float(r["geolocation_lat"]), "lon": float(r["geolocation_lng"]),
                                          "cep": f"{int(float(r['seller_zip_code_prefix'])):05d}"}
    return pedidos, vendedores


def _perto(lat0, lon0, raio_km):
    """Teste rápido de distância (aproximação plana, boa para poucos km)."""
    k = math.cos(math.radians(lat0))
    r2 = (raio_km / 111.32) ** 2
    return lambda lat, lon: (lat - lat0) ** 2 + ((lon - lon0) * k) ** 2 <= r2


def escolher_deposito(pedidos, vendedores, raio_km):
    """O vendedor com mais pedidos no raio (desempate: menor CEP) vira o centro de distribuição."""
    melhor = None
    for vid in sorted(vendedores, key=lambda i: (vendedores[i]["cep"], i)):
        v = vendedores[vid]
        perto = _perto(v["lat"], v["lon"], raio_km)
        n = sum(1 for p in pedidos if perto(p["lat"], p["lon"]))
        if melhor is None or n > melhor[0]:
            melhor = (n, v)
    return melhor[1]


# ------------------------------------------------------------------ OpenStreetMap
def caixa(lat, lon, raio_km):
    dlat = raio_km / 111.32
    dlon = raio_km / (111.32 * math.cos(math.radians(lat)))
    return (round(lat - dlat, 5), round(lon - dlon, 5), round(lat + dlat, 5), round(lon + dlon, 5))


def baixar_ruas(bbox, baixar_de_novo=False):
    os.makedirs(PASTA_BRUTOS, exist_ok=True)
    arquivo = os.path.join(PASTA_BRUTOS, "osm_ruas_{}_{}_{}_{}.json".format(*bbox))
    if os.path.isfile(arquivo) and not baixar_de_novo:
        _log("OpenStreetMap: usando o arquivo já baixado em dados/brutos/")
        with open(arquivo, encoding="utf-8") as f:
            return json.load(f)
    s, w, n, e = bbox
    consulta = (f'[out:json][timeout:120];\n'
                f'way["highway"~"^({"|".join(TIPOS_DE_VIA)})$"]["access"!~"^(private|no)$"]'
                f'["area"!="yes"]({s},{w},{n},{e});\n(._;>;);\nout body;')
    erros = []
    for tentativa in range(2):
        for url in SERVIDORES_OVERPASS:
            _log(f"OpenStreetMap: baixando as ruas da região em {urllib.parse.urlparse(url).netloc} ...")
            req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": consulta}).encode(),
                                         headers={"User-Agent": AGENTE})
            try:
                with _abrir(req, timeout=180) as r:
                    bruto = r.read()
                dados = json.loads(bruto)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as ex:
                erros.append(f"{url}: {ex}")
                continue
            with open(arquivo, "wb") as f:
                f.write(bruto)
            _log(f"OpenStreetMap: {len(bruto) / 1e6:.1f} MB")
            return dados
        time.sleep(10 * (tentativa + 1))
    raise RuntimeError("não foi possível baixar as ruas do OpenStreetMap:\n  " + "\n  ".join(erros))


def _velocidade(tags):
    bruto = (tags.get("maxspeed") or "").split(";")[0].strip()
    try:
        kmh = float(bruto.split()[0])
        if "mph" in bruto:
            kmh *= 1.609
        if kmh > 0:
            return kmh
    except (ValueError, IndexError):
        pass
    tipo = tags.get("highway", "")
    return VELOCIDADE_LINK if tipo.endswith("_link") else VELOCIDADE_PADRAO.get(tipo, 30)


def _sentido(tags):
    """+1 = só no sentido do desenho da via; -1 = só no contrário; 0 = mão dupla."""
    oneway = (tags.get("oneway") or "").lower()
    if oneway in ("yes", "true", "1"):
        return 1
    if oneway == "-1":
        return -1
    if oneway == "no":
        return 0
    if tags.get("junction") in ("roundabout", "circular") or tags.get("highway") in ("motorway", "motorway_link"):
        return 1
    return 0


def rede_de_ruas(osm):
    """Grafo direcionado nó a nó do OSM: {no: {vizinho: (km, min, nome)}} e posições {no: (lat, lon)}."""
    pos = {e["id"]: (e["lat"], e["lon"]) for e in osm["elements"] if e["type"] == "node"}
    arcos = {}
    for via in (e for e in osm["elements"] if e["type"] == "way"):
        tags = via.get("tags", {})
        nos = [n for n in via["nodes"] if n in pos]
        sentido, kmh = _sentido(tags), _velocidade(tags) * FATOR_TRANSITO
        nome = tags.get("name") or tags.get("ref") or ""
        for a, b in zip(nos, nos[1:]):
            if a == b:
                continue
            km = haversine_km(*pos[a], *pos[b])
            trecho = (km, km / kmh * 60, nome)
            if sentido >= 0:
                arcos.setdefault(a, {})[b] = min(trecho, arcos.get(a, {}).get(b, trecho))
            if sentido <= 0:
                arcos.setdefault(b, {})[a] = min(trecho, arcos.get(b, {}).get(a, trecho))
    return arcos, pos


def pontos_de_parada(osm):
    """Pontos de rua onde um veículo pode parar (fora de vias expressas e alças de acesso)."""
    bons = set()
    for via in (e for e in osm["elements"] if e["type"] == "way"):
        if via.get("tags", {}).get("highway") not in SEM_PARADA:
            bons.update(via["nodes"])
    return bons


def _alcancaveis(adj, origem):
    vistos, fila = {origem}, deque([origem])
    while fila:
        u = fila.popleft()
        for v in adj.get(u, ()):
            if v not in vistos:
                vistos.add(v)
                fila.append(v)
    return vistos


def componente_forte(arcos, origem):
    """Nós que vão E voltam de 'origem' (componente fortemente conexa): assim todo cliente
    consegue ser alcançado a partir do depósito e voltar a ele, mesmo com mão única."""
    reverso = {}
    for u, viz in arcos.items():
        for v in viz:
            reverso.setdefault(v, set()).add(u)
    return _alcancaveis(arcos, origem) & _alcancaveis(reverso, origem)


def mais_proximo(lat, lon, candidatos, pos):
    no = min(candidatos, key=lambda n: (pos[n][0] - lat) ** 2 + ((pos[n][1] - lon) * math.cos(math.radians(lat))) ** 2)
    return no, haversine_km(lat, lon, *pos[no])


def simplificar(arcos, pos, manter):
    """Junta os pontos intermediários de cada rua: sobram só as esquinas (cruzamentos, pontas
    de rua, mudanças de sentido) e os pontos em 'manter'. Cada trecho entre duas esquinas
    vira um arco com a soma das distâncias/tempos e o desenho do caminho em 'geometria'."""
    entrada = {}
    for u, viz in arcos.items():
        for v in viz:
            entrada.setdefault(v, set()).add(u)

    def passagem(x):  # ponto que só continua a rua (não é esquina)
        saem, chegam = set(arcos.get(x, ())), entrada.get(x, set())
        return (x not in manter and len(saem | chegam) == 2 and len(saem) == len(chegam) >= 1
                and all(len(saem - {p}) == 1 for p in chegam))

    esquinas = {x for x in set(arcos) | set(entrada) if not passagem(x)}
    trechos = {}
    for u in esquinas:
        for primeiro in arcos.get(u, ()):
            km, minutos, nomes, geo = 0.0, 0.0, Counter(), []
            ant, x = u, primeiro
            while True:
                d, t, nome = arcos[ant][x]
                km, minutos = km + d, minutos + t
                if nome:
                    nomes[nome] += d
                if x in esquinas:
                    break
                geo.append([round(pos[x][0], 6), round(pos[x][1], 6)])
                ant, x = x, next(iter(set(arcos[x]) - {ant}))
            if x == u:
                continue  # volta para a mesma esquina (retorno em U): não serve para rotas
            nome = nomes.most_common(1)[0][0] if nomes else ""
            if (u, x) not in trechos or km < trechos[(u, x)][0]:
                trechos[(u, x)] = (km, minutos, nome, geo)
    return esquinas, trechos


def nomes_das_esquinas(osm, esquinas):
    ruas = {}
    for via in (e for e in osm["elements"] if e["type"] == "way"):
        nome = via.get("tags", {}).get("name")
        if nome:
            for n in via["nodes"]:
                if n in esquinas and nome not in ruas.setdefault(n, []):
                    ruas[n].append(nome)
    return {n: " × ".join(sorted(ruas.get(n, []))[:2]) for n in esquinas}


# ------------------------------------------------------------------ montagem
def montar_base(n_clientes, raio_km, semente, baixar_de_novo=False):
    baixar_olist(baixar_de_novo)
    pedidos, vendedores = ler_olist()
    dep = escolher_deposito(pedidos, vendedores, raio_km)
    _log(f"Depósito: vendedor Olist do CEP {dep['cep']}-xxx ({dep['lat']:.5f}, {dep['lon']:.5f})")

    perto = _perto(dep["lat"], dep["lon"], raio_km)
    vistos, candidatos = set(), []
    for p in pedidos:  # pedidos no raio, sem posições repetidas
        chave = (round(p["lat"], 6), round(p["lon"], 6))
        if perto(p["lat"], p["lon"]) and chave not in vistos:
            vistos.add(chave)
            candidatos.append(p)
    _log(f"Clientes: {len(candidatos)} pedidos a até {raio_km} km do depósito; sorteando {n_clientes}")
    if len(candidatos) < n_clientes:
        raise SystemExit(f"só há {len(candidatos)} pedidos no raio; aumente --raio-km ou diminua --clientes")

    bbox = caixa(dep["lat"], dep["lon"], raio_km + MARGEM_KM)
    osm = baixar_ruas(bbox, baixar_de_novo)
    arcos, pos = rede_de_ruas(osm)
    inicio, _ = mais_proximo(dep["lat"], dep["lon"], arcos, pos)
    forte = componente_forte(arcos, inicio)
    arcos = {u: {v: t for v, t in viz.items() if v in forte} for u, viz in arcos.items() if u in forte}
    _log(f"Ruas: {len(pos)} pontos do OSM; {len(forte)} na parte conectada (ida e volta)")

    rnd = random.Random(semente)
    rnd.shuffle(candidatos)
    onde_parar = forte & pontos_de_parada(osm)
    no_dep, d_dep = mais_proximo(dep["lat"], dep["lon"], onde_parar, pos)
    paradas = [{"id": 0, "nome": "Centro de Distribuição", "lat": round(dep["lat"], 6), "lon": round(dep["lon"], 6),
                "demanda": 0,
                "janela": [0, 24 * 60], "prioridade": 0, "deposito": True, "tipo": "deposito",
                "no": no_dep, "acesso": d_dep}]
    descartados = 0
    for p in candidatos:
        if len(paradas) > n_clientes:
            break
        no, d = mais_proximo(p["lat"], p["lon"], onde_parar, pos)
        if d > LIMITE_ACESSO_KM:
            descartados += 1
            continue
        janela, prioridade = sortear_janela_e_prioridade(rnd)
        i = len(paradas)
        paradas.append({"id": i, "nome": f"Cliente {i:02d}", "lat": round(p["lat"], 6), "lon": round(p["lon"], 6),
                        "demanda": max(1, math.ceil(p["volume"])), "janela": janela, "prioridade": prioridade,
                        "deposito": False, "tipo": "cliente", "no": no, "acesso": d})
    if descartados:
        _log(f"Clientes: {descartados} descartados (a mais de {LIMITE_ACESSO_KM * 1000:.0f} m de uma rua)")

    esquinas, trechos = simplificar(arcos, pos, manter={p["no"] for p in paradas})
    ids = {no: PRIMEIRO_ID_ESQUINA + k for k, no in enumerate(sorted(esquinas))}
    nomes = nomes_das_esquinas(osm, esquinas)

    vertices = [{k: v for k, v in p.items() if k not in ("no", "acesso")} for p in paradas]
    for no in sorted(esquinas):
        vertices.append({"id": ids[no], "nome": nomes[no] or f"Esquina {ids[no]}", "lat": round(pos[no][0], 6),
                         "lon": round(pos[no][1], 6), "demanda": 0, "janela": [0, 24 * 60], "prioridade": 0,
                         "deposito": False, "tipo": "esquina"})

    arestas = []
    for (u, v), (km, minutos, nome, geo) in sorted(trechos.items(), key=lambda kv: (ids[kv[0][0]], ids[kv[0][1]])):
        volta = trechos.get((v, u))
        mao_dupla = volta is not None and round(volta[0], 6) == round(km, 6) and volta[3] == geo[::-1]
        if mao_dupla and ids[u] > ids[v]:
            continue  # a mão dupla já entrou pelo outro sentido
        arestas.append({"u": ids[u], "v": ids[v], "distancia": round(km, 4), "tempo": round(minutos, 3),
                        "mao_unica": not mao_dupla, "nome": nome, "geometria": geo})
    for p in paradas:  # acesso: da porta até a rua, nos dois sentidos
        arestas.append({"u": p["id"], "v": ids[p["no"]], "distancia": round(p["acesso"], 4),
                        "tempo": round(p["acesso"] / VELOCIDADE_ACESSO_KMH * 60, 3),
                        "mao_unica": False, "nome": "acesso", "geometria": []})

    info = {"fontes": {"olist": "https://github.com/NVlabs/olist-vrp-benchmark (coordinates_sao_paulo_test.csv, "
                                "sellers_sao_paulo.csv) - CC BY-NC-SA 4.0",
                       "ruas": "OpenStreetMap via Overpass - © OpenStreetMap contributors, ODbL 1.0",
                       "osm_data_base": osm.get("osm3s", {}).get("timestamp_osm_base")},
            "parametros": {"clientes": n_clientes, "raio_km": raio_km, "semente": semente, "bbox": bbox,
                           "fator_transito": FATOR_TRANSITO, "velocidade_acesso_kmh": VELOCIDADE_ACESSO_KMH},
            "deposito_cep_prefixo": dep["cep"],
            "contagem": {"vertices": len(vertices), "clientes": n_clientes, "esquinas": len(esquinas),
                         "arestas": len(arestas), "mao_unica": sum(a["mao_unica"] for a in arestas)}}
    return vertices, arestas, info


def _hhmm(minutos):
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


def gravar(vertices, arestas, info):
    with open(ARQUIVO_VERTICES, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "nome", "lat", "lon", "demanda", "janela_inicio", "janela_fim", "prioridade", "deposito", "tipo"])
        for v in vertices:
            w.writerow([v["id"], v["nome"], v["lat"], v["lon"], v["demanda"], _hhmm(v["janela"][0]),
                        _hhmm(v["janela"][1]), v["prioridade"], int(v["deposito"]), v["tipo"]])
    with open(ARQUIVO_ARESTAS, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["u", "v", "distancia", "tempo", "mao_unica", "nome", "geometria"])
        for a in arestas:
            w.writerow([a["u"], a["v"], a["distancia"], a["tempo"], int(a["mao_unica"]), a["nome"],
                        ";".join(f"{lat} {lon}" for lat, lon in a["geometria"])])
    with open(ARQUIVO_INFO, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Gera dados/vertices.csv e dados/arestas.csv (Olist + OpenStreetMap).")
    ap.add_argument("--clientes", type=int, default=30, help="número de clientes (padrão: 30)")
    ap.add_argument("--raio-km", type=float, default=1.5, help="raio em volta do depósito (padrão: 1,5 km)")
    ap.add_argument("--semente", type=int, default=42, help="semente do sorteio dos clientes (padrão: 42)")
    ap.add_argument("--baixar-de-novo", action="store_true", help="ignora os arquivos já baixados em dados/brutos/")
    args = ap.parse_args(argv)

    vertices, arestas, info = montar_base(args.clientes, args.raio_km, args.semente, args.baixar_de_novo)
    gravar(vertices, arestas, info)
    g = ler_grafo()  # confere tudo com as mesmas regras que a API usa
    c = info["contagem"]
    _log(f"Pronto: {g} -> {c['clientes']} clientes, 1 depósito, {c['esquinas']} esquinas; "
         f"{c['mao_unica']} de {c['arestas']} arestas são de mão única.")
    _log(f"Arquivos: {os.path.relpath(ARQUIVO_VERTICES)}, {os.path.relpath(ARQUIVO_ARESTAS)}, "
         f"{os.path.relpath(ARQUIVO_INFO)}")


if __name__ == "__main__":
    main()
