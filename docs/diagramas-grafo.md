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
e cada aresta carregam. `dijkstra` e `dados` são módulos de funções, representados como `«módulo»`.

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
```

**Decisões que o diagrama mostra**
- **Lista de adjacência** (`_adj`): cada vértice aponta para os vizinhos e os pesos da aresta. A mesma
  estrutura `Pesos` é compartilhada pelos dois sentidos, já que a aresta não tem direção.
- **Dois pesos por aresta** (`distancia` em km e `tempo` em min): o Dijkstra e a matriz de custos
  escolhem qual usar pelo parâmetro `peso`.
- **Exatamente um depósito**: a propriedade `deposito` falha se houver zero ou mais de um.
- **Conversão pelo contrato** (`de_contrato` / `para_contrato`): o grafo entra e sai da API no mesmo
  formato JSON, então as outras duplas não dependem da classe por dentro.
