# Diagramas UML: modelagem do grafo (Dupla 1)

Os diagramas estão em [Mermaid](https://mermaid.js.org/), que o GitHub desenha sozinho ao abrir este arquivo.
Para gerar as figuras do relatório, siga as instruções de [diagramas.md](diagramas.md) (mermaid.live → *Actions → PNG*)
ou, com Node instalado, rode na raiz do repositório:

```bash
npx -p @mermaid-js/mermaid-cli mmdc -i docs/diagramas-grafo.md -o relatorio/figuras/uml-classes.png -w 1600 -s 2 -b white
```

---

## 1. Diagrama de classes
Arquivo da figura: `figuras/uml-classes.png`

O núcleo é a classe `Grafo` (`src/grafo/grafo.py`), que guarda o grafo não direcionado e ponderado em
lista de adjacência. `Vertice` e `Pesos` não são classes no código: são dicionários com os campos do
contrato da API (`src/api/contrato.py`). Aparecem aqui como `«estrutura»` para mostrar o que cada vértice
e cada aresta carregam. `dijkstra`, `dados` e `gerador` são módulos de funções, representados como `«módulo»`. O `gerador` cria
instâncias sintéticas (reprodutíveis pela semente) só para os testes e o benchmark; a base do sistema vem de `dados/`.

```mermaid
classDiagram
    direction TB

    class Grafo {
        -_vertices : dict[int, Vertice]
        -_adj : dict[int, dict[int, Pesos]]
        -_num_arestas : int
        +num_vertices : int
        +num_arestas : int
        +deposito : int
        +adicionar_vertice(vertice: Vertice) None
        +adicionar_aresta(u: int, v: int, distancia: float, tempo: float) None
        +vertice(vid: int) Vertice
        +ids() list[int]
        +clientes() list[int]
        +vizinhos(u: int, peso: str) list[tuple]
        +aresta(u: int, v: int) Pesos
        +arestas() Iterator[tuple]
        +para_contrato() dict
        +de_contrato(dados: dict)$ Grafo
    }

    class Vertice {
        <<estrutura>>
        +id : int
        +nome : str
        +lat : float
        +lon : float
        +demanda : int
        +janela : list[int]
        +prioridade : int
        +deposito : bool
    }

    class Pesos {
        <<estrutura>>
        +distancia : float
        +tempo : float
    }

    class dijkstra {
        <<módulo>>
        +INFINITO : float
        +dijkstra(grafo, origem: int, peso: str) tuple[dict, dict]
        +caminho(anterior: dict, origem: int, destino: int) list[int]
        +matriz_custos(grafo, peso: str) dict[int, dict]
    }

    class dados {
        <<módulo>>
        +FATOR_RUAS : float = 1.3
        +VELOCIDADE_KMH : int = 30
        +ler_grafo(caminho_vertices, caminho_arestas) Grafo
        +carregar_grafo(caminho_vertices, caminho_arestas) dict
        -_ler_csv(caminho, colunas) list
        -_vertice(linha) Vertice
        -_aresta(linha) dict
        -_arestas_completas(vertices) list
        -_haversine_km(a, b) float
    }

    class gerador {
        <<módulo>>
        +DEPOSITO : Vertice
        +SEMENTE_PADRAO : int = 10
        +gerar_grafo(n_clientes: int, semente: int) Grafo
        +gerar_vertices(n_clientes: int, semente: int) list[Vertice]
        +sortear_janela_e_prioridade(rnd: Random) tuple[list, int]
    }

    class ErroDados {
        +problemas : list[str]
    }

    class ValueError {
        <<Python>>
    }

    class contrato {
        <<módulo · API>>
        +validar_grafo(grafo: dict) list[str]
    }

    Grafo "1" *-- "1..*" Vertice : vértices
    Grafo "1" *-- "0..*" Pesos : arestas (u, v)
    ErroDados --|> ValueError
    dijkstra ..> Grafo : percorre
    dados ..> Grafo : cria
    dados ..> dijkstra : alcançabilidade
    dados ..> contrato : valida
    dados ..> ErroDados : lança
    gerador ..> Grafo : cria
    gerador ..> dados : arestas completas
```

**Decisões que o diagrama mostra**
- **Lista de adjacência** (`_adj`): cada vértice aponta para os vizinhos e os pesos da aresta. A mesma
  estrutura `Pesos` é compartilhada pelos dois sentidos, já que a aresta não tem direção.
- **Dois pesos por aresta** (`distancia` em km e `tempo` em min): o Dijkstra e a matriz de custos
  escolhem qual usar pelo parâmetro `peso`.
- **Exatamente um depósito**: a propriedade `deposito` falha se houver zero ou mais de um.
- **Conversão pelo contrato** (`de_contrato` / `para_contrato`): o grafo entra e sai da API no mesmo
  formato JSON, então as outras duplas não dependem da classe por dentro.

---

## 2. Diagrama de atividades: cálculo de rotas (domínio do problema)
Arquivo da figura: `figuras/uml-atividades-rotas.png`

Este diagrama mostra o fluxo de dados do problema modelado (CVRPTW), da leitura do grafo até a
solução final — complementar ao diagrama de classes (estrutura estática) e ao diagrama de sequência
da interface (`diagramas.md`, que mostra a troca de mensagens entre API e front, não o algoritmo em si).

Desenhado na horizontal, em duas faixas (preparação dos dados e cálculo das rotas), para
ocupar pouca altura no relatório.

```mermaid
flowchart TB
    subgraph PREP["1 · Preparar os dados"]
        direction LR
        A([Início]) --> B[Ler vértices e<br/>arestas do CSV] --> C{Base<br/>válida?}
        C -- sim --> D[Montar Grafo<br/>lista de adjacência] --> E[Dijkstra a partir de<br/>cada parada: matriz<br/>de distância e tempo] --> F[Separar clientes<br/>com demanda > Q<br/>como não atendidos]
        C -- não --> C1[Listar todos os erros<br/>por arquivo e linha] --> Z([Fim: API<br/>não sobe])
    end
    subgraph ROTAS["2 · Calcular as rotas"]
        direction LR
        G{Algoritmo<br/>escolhido} -- Vizinho Mais Próximo --> H1[Rotas gulosas: cliente<br/>mais próximo sem atraso]
        G -- Clarke-Wright --> H2[Calcular economias e<br/>juntar rotas até a frota]
        H1 --> I{Usar<br/>2-opt?}
        H2 --> I
        I -- sim --> J[Trocar arestas enquanto<br/>reduzir a distância<br/>sem piorar atrasos] --> K
        I -- não --> K[Calcular horários:<br/>chegada, início,<br/>fim, atrasado]
        K --> L[Somar métricas:<br/>distância, tempo,<br/>atrasos] --> M([Fim: rotas, não<br/>atendidos e métricas])
    end
    PREP --> ROTAS
```

**Decisões que o diagrama mostra**
- A validação (`ErroDados`) acontece **antes** de montar o grafo, e lista todos os problemas de uma
  vez (não para no primeiro erro) — é o que o teste `test_registros_invalidos_listados_todos` cobra.
- A matriz de custos (Dijkstra) é calculada **uma única vez**, antes de escolher o algoritmo: as
  heurísticas de construção e o 2-opt trabalham só sobre essa matriz entre paradas, nunca sobre o
  grafo viário completo de novo.
- O 2-opt é condicional e vem **depois** da construção, nunca embutido nela — é por isso que a
  interface pode ligar e desligar o 2-opt sem trocar o algoritmo de construção.
