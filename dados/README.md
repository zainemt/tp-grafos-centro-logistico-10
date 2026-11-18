# Dados

Base de dados lida por `src/grafo/dados.py` (`carregar_grafo()`), que monta o grafo no formato de `GET /api/grafo` e o valida com `src/api/contrato.py` (`validar_grafo`).

## O mapa: um único grafo

`vertices.csv` e `arestas.csv` formam **um só grafo, que é o mapa do local** (centro de São Paulo, em volta da Bela Vista):

- **vértices**: o depósito (1), os clientes (30) e as **esquinas** (1.519): cruzamentos e pontas de rua do OpenStreetMap;
- **arestas**: os trechos de rua entre duas esquinas, com distância, tempo, nome da rua e o desenho do trecho. Rua de **mão única** é um arco num sentido só (1.906 de 2.408 trechos);
- o depósito e cada cliente são ligados à rua mais próxima por um trecho de **acesso** (mediana de 39 m, no máximo 250 m).

Os algoritmos usam o **caminho mínimo pelas ruas** entre as paradas (Dijkstra, `matriz_custos`), e o mapa da interface desenha as rotas e os caminhões seguindo esse caminho (`src/grafo/mapa.py`). Com mão única, ir de A até B pode custar diferente de voltar de B até A.

Contagens, parâmetros e a data dos dados do OSM ficam em `base_info.json`.

## Origem e tratamento

| Dado | Fonte | Licença |
|---|---|---|
| Clientes (posição e volume do pedido) e depósito (posição de um vendedor) | [Olist VRP Benchmark](https://github.com/NVlabs/olist-vrp-benchmark) (NVIDIA), feito a partir da [base pública de e-commerce da Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce): `coordinates_sao_paulo_test.csv` e `sellers_sao_paulo.csv` | CC BY-NC-SA 4.0 |
| Ruas, sentido (mão única) e velocidade máxima | [OpenStreetMap](https://www.openstreetmap.org/copyright), baixado pela API Overpass | © OpenStreetMap contributors, ODbL 1.0 |

Tratamento (`src/grafo/preparar_base.py`):
1. **Depósito:** o vendedor da Olist com mais pedidos num raio de 1,5 km (CEP 01314, Bela Vista).
2. **Clientes:** 30 pedidos sorteados (semente 42) entre os 178 do raio, sem posições repetidas. **Demanda** = volume do pedido em litros, arredondado para cima (a Olist já corta em 100 L). A capacidade de 160 L por veículo é a mesma usada no benchmark da NVIDIA.
3. **Janela de tempo e prioridade** não existem na Olist: são **sorteadas** (mesma regra de `src/grafo/gerador.py`).
4. **Ruas:** vias por onde passa um carro (sem calçadas, ciclovias, estacionamentos ou vias privadas), num quadrado que cobre o raio dos clientes mais 400 m.
5. **Tempo** de cada trecho = distância ÷ (60% da velocidade máxima da via). Sem `maxspeed` no OSM, usa um padrão por tipo de via (residencial 30 km/h, terciária 40, primária 50...). O acesso usa 15 km/h.
6. **Conexão:** fica só a parte das ruas em que dá para ir **e voltar** do depósito (componente fortemente conexa), para nenhum cliente ficar preso numa rua sem saída de mão única. Depósito e clientes só se ligam a ruas onde dá para parar (não a vias expressas nem a alças de acesso).
7. **Simplificação:** os pontos intermediários de cada rua viram a `geometria` do trecho; sobram como vértices só as esquinas.

Os dados de pessoas não entram na base: dos pedidos, ficam só a posição (que a própria Olist já sorteia dentro da área do CEP) e o volume.

### Como gerar de novo

```bash
python -m src.grafo.preparar_base
```

Opções: `--clientes 40`, `--raio-km 1.2`, `--semente 7` e `--baixar-de-novo`. Os downloads ficam em `dados/brutos/` (fora do git) e são reaproveitados. Do `coordinates.zip` da Olist (~1 GB) o script baixa só os dois CSV usados (~1 MB). Só usa a biblioteca padrão do Python.

> **Mac com Python do python.org:** se aparecer `CERTIFICATE_VERIFY_FAILED`, rode uma vez o *Install Certificates.command* (pasta Aplicativos → Python 3.x). O script já tenta usar os certificados do sistema sozinho.

## `vertices.csv` (obrigatório)

Um vértice por linha: o depósito, os clientes e as esquinas. Separador vírgula, UTF-8 (com ou sem BOM do Excel).

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | inteiro | único |
| `nome` | texto | não vazio |
| `lat`, `lon` | real | graus decimais (−90 a 90 / −180 a 180) |
| `demanda` | inteiro | ≥ 0; o depósito tem 0 |
| `janela_inicio`, `janela_fim` | `HH:MM` ou minutos desde 00:00 | entre 00:00 e 24:00, início ≤ fim |
| `prioridade` | inteiro | clientes: 1 (baixa), 2 ou 3 (alta); depósito e esquinas usam 0 |
| `deposito` | `1`/`0` (ou sim/não) | exatamente **um** vértice com `1` |
| `tipo` (opcional) | `deposito`, `cliente` ou `esquina` | tem que combinar com `deposito`; esquina tem demanda 0. Sem a coluna, `deposito=1` é o depósito e o resto é cliente |

## `arestas.csv` (opcional, na mesma pasta de `vertices.csv`)

| Coluna | Tipo | Regra |
|---|---|---|
| `u`, `v` | inteiro | ids existentes em `vertices.csv`, `u ≠ v`, sem repetir o mesmo sentido |
| `distancia` | real | km, ≥ 0 |
| `tempo` | real | minutos, ≥ 0 |
| `mao_unica` (opcional) | `1`/`0` | `1`: vale só de `u` para `v`; `0` ou vazio: vale nos dois sentidos |
| `nome` (opcional) | texto | nome da rua (só para o mapa) |
| `geometria` (opcional) | `lat lon;lat lon;...` | pontos intermediários do desenho do trecho, de `u` para `v` (só para o mapa) |

**Sem `arestas.csv`**, o grafo é completo: cada par de vértices ganha uma aresta com a distância em linha reta (haversine) × 1,3 (correção para ruas) e o tempo a 30 km/h, as mesmas regras dos dados de exemplo da API.

Com `arestas.csv`, todos os vértices precisam ser alcançáveis a partir do depósito e, se houver mão única, também precisam ter caminho de volta até ele. Os algoritmos usam o custo entre paradas calculado pelo Dijkstra (`src/grafo/dijkstra.py`, `matriz_custos`).

## Erros

Qualquer problema levanta `ErroDados` com **todos** os erros encontrados, indicando arquivo e linha (ex.: `vertices.csv, linha 7: demanda negativa`). Depois da integração em `src/api/app.py`, a API não sobe com uma base inválida.

## Outros arquivos desta pasta

`base_info.json` registra as fontes, os parâmetros e as contagens da última geração da base. `brutos/` guarda os downloads (fora do git).

`usuarios.json` (e `usuarios.local.json`, fora do git) são do login (Dupla 3, `src/api/auth.py`) e não fazem parte da base do grafo.
