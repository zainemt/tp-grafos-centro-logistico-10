# Dados

Base de dados lida por `src/grafo/dados.py` (`carregar_grafo()`), que monta o grafo no formato de `GET /api/grafo` e o valida com `src/api/contrato.py` (`validar_grafo`).

## Origem

Em preparação: Olist VRP Benchmark (NVIDIA, a partir da base pública da Olist no Kaggle) com distâncias e tempos calculados nas ruas do OpenStreetMap. A origem, as licenças e o tratamento serão registrados aqui junto com os arquivos.

## `vertices.csv` (obrigatório)

Um vértice por linha: o depósito e os clientes. Separador vírgula, UTF-8 (com ou sem BOM do Excel).

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | inteiro | único |
| `nome` | texto | não vazio |
| `lat`, `lon` | real | graus decimais (−90 a 90 / −180 a 180) |
| `demanda` | inteiro | ≥ 0; o depósito tem 0 |
| `janela_inicio`, `janela_fim` | `HH:MM` ou minutos desde 00:00 | entre 00:00 e 24:00, início ≤ fim |
| `prioridade` | inteiro | clientes: 1 (baixa), 2 ou 3 (alta); o depósito usa 0 |
| `deposito` | `1`/`0` (ou sim/não) | exatamente **um** vértice com `1` |

## `arestas.csv` (opcional, na mesma pasta de `vertices.csv`)

| Coluna | Tipo | Regra |
|---|---|---|
| `u`, `v` | inteiro | ids existentes em `vertices.csv`, `u ≠ v`, sem pares repetidos (a aresta não tem direção) |
| `distancia` | real | km, ≥ 0 |
| `tempo` | real | minutos, ≥ 0 |

**Sem `arestas.csv`**, o grafo é completo: cada par de vértices ganha uma aresta com a distância em linha reta (haversine) × 1,3 (correção para ruas) e o tempo a 30 km/h, as mesmas regras dos dados de exemplo da API.

Com `arestas.csv`, todos os vértices precisam ser alcançáveis a partir do depósito. Os algoritmos usam o custo entre paradas calculado pelo Dijkstra (`src/grafo/dijkstra.py`, `matriz_custos`).

## Erros

Qualquer problema levanta `ErroDados` com **todos** os erros encontrados, indicando arquivo e linha (ex.: `vertices.csv, linha 7: demanda negativa`). Depois da integração em `src/api/app.py`, a API não sobe com uma base inválida.

## Outros arquivos desta pasta

`usuarios.json` (e `usuarios.local.json`, fora do git) são do login (Dupla 3, `src/api/auth.py`) e não fazem parte da base do grafo.
