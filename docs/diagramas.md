# Diagramas UML: arquitetura e interface (Dupla 3)

Os diagramas estão em [Mermaid](https://mermaid.js.org/), que o GitHub desenha sozinho ao abrir este arquivo.

**Para gerar as figuras do relatório:**
1. Cole o bloco em https://mermaid.live.
2. Clique em *Actions → PNG* (ou SVG).
3. Salve em `relatorio/figuras/` com o nome indicado em cada seção.

Os diagramas da **modelagem do grafo** (classes do grafo, casos de uso, atividades) são responsabilidade da Dupla 1.

---

## 1. Diagrama de componentes
Arquivo da figura: `figuras/uml-componentes.png`

```mermaid
flowchart TB
    subgraph Navegador["Navegador (cliente)"]
        LG["Login e cadastro<br/>login.* · registrar.*"]
        UI["Interface web<br/>index.html · style.css · app.js"]
        LF["Leaflet<br/>(mapa)"]
        LG -- "sessão criada" --> UI
        UI --> LF
    end

    subgraph Servidor["Servidor Python"]
        AU["Autenticação e sessão<br/>src/api/auth.py"]
        API["API REST (Flask)<br/>src/api/app.py"]
        CT["Validador do contrato<br/>src/api/contrato.py"]
        subgraph Nucleo["Núcleo de grafos"]
            G["Grafo + leitura de dados + Dijkstra<br/>src/grafo (Dupla 1)"]
            A["Vizinho mais próximo · Clarke-Wright · 2-opt<br/>src/algoritmos (Dupla 2)"]
        end
        AU -- "protege /api/*" --> API
        API --> G
        API --> A
        A --> G
        CT -. testes .-> API
    end

    D[("Base de dados<br/>dados/*.csv")]
    U[("Usuários<br/>dados/usuarios.json")]
    OSM["OpenStreetMap<br/>(imagens do mapa)"]

    LG -- "POST /api/auth/login<br/>POST /api/auth/registrar" --> AU
    UI -- "HTTP / JSON<br/>GET /api/grafo · POST /api/rotas<br/>GET /api/desempenho" --> API
    AU --> U
    G --> D
    LF --> OSM
```

---

## 1b. Arquitetura em camadas
Arquivo da figura: `figuras/arquitetura.png`

```mermaid
flowchart LR
    C1["<b>1 · Interface web</b><br/>HTML · CSS · JavaScript<br/><br/>mapa (Leaflet)<br/>simulação e linha do tempo<br/>comparação e desempenho"]
    C2["<b>2 · API REST (Flask)</b><br/><br/>autenticação e sessão<br/>validação da entrada<br/>contrato JSON"]
    C3["<b>3 · Núcleo de grafos</b><br/>Python, sem bibliotecas de grafos<br/><br/>grafo + Dijkstra<br/>Vizinho mais próximo<br/>Clarke-Wright · 2-opt"]
    C1 -- "HTTP / JSON" --> C2
    C2 -- "chamadas<br/>de função" --> C3
```

---

## 2. Diagrama de sequência: calcular rotas
Arquivo da figura: `figuras/uml-sequencia.png`

```mermaid
sequenceDiagram
    actor U as Usuário
    participant F as Interface (app.js)
    participant API as API Flask
    participant G as Grafo (Dupla 1)
    participant A as Algoritmos (Dupla 2)

    Note over F,API: Ao abrir a página
    F->>API: GET /api/grafo
    API->>G: carregar_grafo()
    G-->>API: vértices e arestas
    API-->>F: JSON do grafo
    F->>F: desenha depósito, clientes e arestas no mapa

    Note over U,A: Cálculo das rotas
    U->>F: define frota, capacidade, algoritmo e 2-opt
    U->>F: clica em "Calcular rotas"
    F->>API: POST /api/rotas {veiculos, capacidade, algoritmo, usar_2opt}
    API->>API: valida a entrada
    alt entrada inválida
        API-->>F: 400 {erro}
        F-->>U: mostra a mensagem de erro
    else entrada válida
        API->>A: calcular_rotas(grafo, ...)
        A->>G: distâncias e tempos (Dijkstra)
        G-->>A: matriz de custos
        A-->>API: rotas, horários e métricas
        API-->>F: JSON das rotas + tempo de execução
        F->>F: desenha as rotas, os cartões e a linha do tempo
        F-->>U: mostra o resultado
    end
```

---

## 3. Diagrama de estados: simulação do dia
Arquivo da figura: `figuras/uml-estados-simulacao.png`

```mermaid
stateDiagram-v2
    [*] --> SemRotas
    SemRotas --> VisaoGeral: calcular rotas
    VisaoGeral --> Tocando: ▶ play / espaço
    VisaoGeral --> Pausado: arrastar a barra de horário
    Tocando --> Pausado: ⏸ pausa
    Tocando --> Pausado: fim do expediente
    Pausado --> Tocando: ▶ play
    Pausado --> Pausado: arrastar a barra
    Tocando --> VisaoGeral: ⟲ reiniciar
    Pausado --> VisaoGeral: ⟲ reiniciar
    VisaoGeral --> VisaoGeral: recalcular rotas
    Tocando --> VisaoGeral: recalcular rotas
    Pausado --> VisaoGeral: recalcular rotas
```

Estado de cada cliente durante a simulação:

```mermaid
stateDiagram-v2
    [*] --> Aguardando
    Aguardando --> EmAtendimento: veículo chega
    EmAtendimento --> EntregueNoPrazo: fim da entrega, início dentro da janela
    EmAtendimento --> EntregueComAtraso: fim da entrega, início após a janela
    EntregueNoPrazo --> [*]
    EntregueComAtraso --> [*]
```

---

## 4. Diagrama de casos de uso da interface
Arquivo da figura: `figuras/uml-casos-uso-interface.png`

O Mermaid não tem um tipo próprio para casos de uso, por isso o diagrama abaixo é uma aproximação. Se a Dupla 1 já fizer o diagrama de casos de uso oficial (no draw.io, por exemplo), basta incluir estes casos nele.

```mermaid
flowchart LR
    U(("👤 Planejador<br/>logístico"))
    U --> C1(["Visualizar o grafo no mapa"])
    U --> C2(["Configurar a frota"])
    U --> C3(["Calcular rotas"])
    U --> C4(["Inspecionar uma rota"])
    U --> C5(["Simular o dia"])
    U --> C6(["Comparar algoritmos"])
    U --> C7(["Medir desempenho"])
    U --> C8(["Exportar resultado"])
    U --> C9(["Consultar o guia de uso"])
    C3 -. include .-> C2
    C5 -. include .-> C3
    C4 -. extend .-> C3
```
