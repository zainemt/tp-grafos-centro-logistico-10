# Benchmark: nosso Dijkstra × NetworkX

Compara o Dijkstra implementado do zero em [`src/grafo/dijkstra.py`](../src/grafo/dijkstra.py) com o da biblioteca [NetworkX](https://networkx.org/). A comparação verifica duas coisas: se os resultados são iguais (corretude) e quanto tempo cada um leva (desempenho).

> **O NetworkX só é usado aqui.** A aplicação (`src/`) não o importa e ele não está em `requirements.txt`. O teste `tests/test_benchmark_networkx.py` falha se algum arquivo de `src/` passar a importá-lo.

## Como rodar

Na raiz do repositório, com o `.venv` do projeto:

```bash
.venv/bin/pip install -r benchmark/requirements.txt
.venv/bin/python -m benchmark.comparar_dijkstra
```

| Opção | Efeito |
|---|---|
| *(nenhuma)* | todas as instâncias; cerca de 7 min num Apple M4 |
| `--rapido` | só instâncias pequenas, para conferir se roda (segundos) |
| `--repeticoes N` / `--origens N` / `--pontos N` | execuções medidas (5), origens sorteadas (10), pontos da matriz nas instâncias sintéticas (30) |
| `--saida PASTA` | grava tudo em outra pasta, sem mexer no relatório |
| `--so-saidas` | não mede de novo: refaz a tabela, o gráfico e o resumo a partir do CSV já gravado |

O programa termina com código 1 se encontrar qualquer divergência de resultado.

### Saídas

| Arquivo | Conteúdo |
|---|---|
| `benchmark/resultados/dijkstra_networkx.csv` | todas as medições: instância, peso, operação, implementação, V, E, arcos, mediana/mínimo/máximo em ms, divergências |
| `benchmark/resultados/dijkstra_networkx.md` | as mesmas medições em tabelas legíveis |
| `benchmark/resultados/ambiente.json` | data, versões do Python e do NetworkX, sistema e processador da execução |
| `relatorio/tabelas/dijkstra-networkx.tex` | tabela do relatório (`\input{tabelas/dijkstra-networkx}`) |
| `relatorio/figuras/dijkstra-networkx.tex` | gráfico pgfplots do relatório (`\input{figuras/dijkstra-networkx}`) |

## Metodologia

### 1. Mesma entrada para os dois

Cada instância é montada uma vez como `Grafo`, a nossa classe. Ela é copiada para o NetworkX pela função `para_networkx`:
- o grafo vira `nx.DiGraph` se for direcionado e `nx.Graph` se não for;
- os ids são os mesmos;
- os arcos são os mesmos, com os dois pesos (`distancia` e `tempo`) como atributos.

O teste `test_conversao_preserva_o_grafo` confere que a cópia tem os mesmos vértices, as mesmas arestas e os mesmos pesos. O teste `test_mapa_real_mao_unica_preservada` confere que as ruas de mão única não ganham o sentido contrário.

A conversão fica **fora** do tempo medido. As duas implementações recebem a estrutura já montada, como acontece na aplicação, que monta o grafo uma vez na subida da API. O tempo da conversão fica registrado no CSV (`conversao_networkx_ms`), só como informação.

### 2. Instâncias

| Família | O que é | Tamanhos | Por quê |
|---|---|---|---|
| **Mapa de SP** | a base real da aplicação (`dados/*.csv`): ruas do OpenStreetMap, 1 550 vértices, 2 910 arcos, com mão única | 1 | é o grafo em que o Dijkstra roda de verdade |
| **Grade** | malha de lado × lado esquinas, quarteirões de 80 a 150 m, velocidades de 20/30/40 km/h sorteadas (semente 42) | 25² a 300² (625 a 90 000 vértices) | grafo esparso como o de ruas (E ≈ 2V), em tamanhos crescentes, para ver como o tempo cresce |
| **Completo** | grafo completo do gerador da Dupla 1 (`src/grafo/gerador.py`, semente = n), a regra usada quando não há `arestas.csv` | n = 50 a 800 clientes | grafo denso (E ≈ V²/2): o outro extremo |

Todas as instâncias são reprodutíveis: as mesmas sementes geram os mesmos grafos, as mesmas origens e os mesmos pontos.

### 3. Operações medidas

Cada operação é medida com os dois pesos, `distancia` e `tempo`:

| Operação | Nosso | NetworkX | Observação |
|---|---|---|---|
| **Uma origem** (10 origens sorteadas) | `dijkstra(grafo, s, peso)` | `nx.dijkstra_predecessor_and_distance(G, s, weight=peso)` | as duas devolvem custos **e** predecessores: é a comparação equivalente |
| **Matriz entre P pontos** | `matriz_custos(grafo, peso, pontos)` | `nx.single_source_dijkstra_path_length` a partir de cada ponto, filtrado para os P pontos | é o uso real na aplicação. No mapa de SP, os pontos são as 31 paradas (depósito e clientes); nas outras instâncias, 30 vértices sorteados |

Na matriz, a função do NetworkX devolve **só** as distâncias. A nossa também guarda os predecessores, ou seja, faz um pouco mais de trabalho. A comparação nessa operação é, portanto, levemente favorável ao NetworkX.

### 4. Corretude (antes de medir)

Para cada instância, peso e origem, a função `conferir_uma_origem` verifica três coisas:
1. **o mesmo conjunto de vértices alcançáveis** nas duas implementações;
2. **o mesmo custo mínimo para cada vértice**, com tolerância de 10⁻⁹. A tolerância cobre só o arredondamento de ponto flutuante, já que somas em ordens diferentes podem diferir no último dígito;
3. **um caminho coerente com o custo**: para até 200 destinos sorteados, o caminho reconstruído pelo nosso `anterior` vai da origem ao destino, e a soma dos pesos das suas arestas é igual ao custo do NetworkX.

A matriz também é comparada célula a célula (`conferir_matriz`).

Quando dois caminhos diferentes têm o mesmo custo, cada biblioteca pode escolher um. Por isso o teste compara o **custo** do caminho, e não a sequência de vértices.

Os testes `test_a_conferencia_detecta_um_custo_errado` e `test_a_conferencia_detecta_alcance_diferente` estragam de propósito o grafo do NetworkX e conferem que a verificação acusa a diferença. Sem eles, "zero divergências" poderia significar apenas que a verificação nunca acusa nada.

### 5. Protocolo de medição

- O relógio é `time.perf_counter_ns()`.
- Antes de medir, cada caso roda 1 vez como aquecimento. Depois roda 5 vezes, e o resultado é a **mediana**. Mínimo e máximo também ficam no CSV.
- O coletor de lixo fica desligado durante cada execução medida, como faz o módulo `timeit`. Isso evita que uma coleta caia por acaso no tempo de uma das implementações.
- As duas implementações recebem exatamente as mesmas origens e os mesmos pontos.
- O tempo por origem é o tempo total das 10 origens dividido por 10.
- A coluna **c** divide o tempo por origem por (V + arcos)·log₂V. Se o tempo cresce como O((V + E) log V), a complexidade do Dijkstra com heap binário, c fica aproximadamente constante entre instâncias de tamanhos diferentes.

### 6. Limites desta comparação

- Uma única máquina, com o computador em uso normal. Medições em Python oscilam de uma execução para outra (no CSV, o máximo pode passar da mediana em 10 a 50%). Por isso a análise usa a mediana e olha a tendência entre tamanhos, e não um valor isolado.
- O NetworkX é uma biblioteca genérica: aceita função de peso, várias origens, `cutoff`, `target` e listas de predecessores para empates. Parte da diferença de tempo vem desse custo de generalidade, e não de um algoritmo melhor. As duas implementações usam o mesmo algoritmo: Dijkstra com heap binário (`heapq`).
- Os números valem para as versões registradas em `ambiente.json`. Outra versão do Python ou do NetworkX pode mudar as proporções.

## Resultados da última execução

Os números completos estão em [`resultados/dijkstra_networkx.md`](resultados/dijkstra_networkx.md). Em resumo:
- **Corretude:** nenhuma divergência em nenhuma das 11 instâncias, nos dois pesos e nas duas operações.
- **Uma origem:** o nosso foi de 1,1 a 1,2 vez mais rápido nos grafos esparsos (mapa de SP e grades) e de 1,5 a 1,7 vez nos completos.
- **Matriz:** a diferença cai para entre 0,9 e 1,7 vez, porque aqui o NetworkX devolve só as distâncias (veja o item 3). Em 2 dos 22 casos, o NetworkX ficou à frente.
- **Crescimento:** c ficou entre 13 e 26 ns em instâncias de 51 a 90 000 vértices, compatível com O((V + E) log V).
