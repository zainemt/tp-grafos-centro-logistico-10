# 🚚 RotaGrafo

Ferramenta de roteamento e carga de veículos em centros logísticos, baseada em grafos.

Trabalho prático de **Teoria dos Grafos**, tema 10.

## 📌 Sobre

Um centro logístico (o **depósito**) precisa atender vários **clientes** usando uma frota limitada. Cada cliente tem:
- uma **demanda** (quanto de carga pede);
- uma **janela de tempo** (o horário em que aceita a entrega, por exemplo 09:00 a 11:00);
- uma **prioridade** (1 = baixa, 3 = alta).

Os veículos têm uma **capacidade** máxima de carga.

O sistema representa essa rede como um **grafo ponderado**: os vértices são o depósito e os clientes, e as arestas guardam a distância (km) e o tempo de viagem (min) entre cada par. A partir disso, ele calcula rotas que começam e terminam no depósito, não passam da capacidade dos veículos e tentam cumprir as janelas de tempo. O resultado aparece num mapa interativo.

## 🧠 Algoritmos

| Algoritmo | Para que serve |
|---|---|
| **Dijkstra** | menor caminho entre dois pontos; monta a matriz de distâncias |
| **Vizinho mais próximo** | constrói as rotas indo sempre ao cliente mais perto ainda não atendido (rápido e simples) |
| **Clarke-Wright** | constrói as rotas juntando pares de clientes que mais economizam distância (em geral, rotas melhores) |
| **2-opt** | melhora uma rota pronta desfazendo os "cruzamentos" do trajeto |

> O grafo e os algoritmos são implementados do zero. O NetworkX é usado **apenas** na comparação de desempenho.

## 🛠️ Tecnologias

Python 3 · Flask (API) · HTML, CSS e JavaScript puro · Leaflet + OpenStreetMap (mapa) · LaTeX no template SBC (relatório)

## 🚀 Como executar

**Na primeira vez:**

```bash
git clone https://github.com/zainemt/tp-grafos-centro-logistico-10.git
cd tp-grafos-centro-logistico-10
python -m venv .venv
.venv\Scripts\activate        # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
```

**Para rodar** (sempre de dentro da pasta `tp-grafos-centro-logistico-10`):

```bash
.venv\Scripts\python src\api\app.py      # Linux/Mac: .venv/bin/python src/api/app.py
```

Depois, abra **http://localhost:5000** no navegador (você será levado à tela de login, veja [Acesso](#-acesso)). Para parar o servidor, use `Ctrl + C` no terminal.

## 🔐 Acesso

O sistema exige login. Sem sessão, a página redireciona para `/login` e a API (`/api/*`) responde **401**.

**Usuário de demonstração** (só para desenvolvimento e apresentação):

| E-mail | Senha |
|---|---|
| `demo@rotagrafo.com` | `rotagrafo123` |

**Criar uma conta pela tela:** na página de login, clique em **Criar conta** (ou abra `/registrar`) e informe nome, e-mail e senha (8 a 128 caracteres). A conta é criada, você já entra logado, e ela fica em `dados/usuarios.local.json` (só com o hash da senha). Esse arquivo está no `.gitignore` e **não deve ser commitado**. O cadastro é aberto: qualquer pessoa que acesse o sistema consegue criar uma conta, com limite de 10 contas por IP por hora.

**Criar outro usuário pelo terminal** (a senha é pedida no terminal e gravada só como hash em `dados/usuarios.json`):

```bash
.venv\Scripts\python -m src.api.auth criar maria@exemplo.com "Maria Souza"
```

**Regras de segurança:**
- a sessão fica num cookie `HttpOnly`; com **Manter conectado** ela dura 30 dias, sem marcar acaba ao fechar o navegador;
- 5 tentativas erradas seguidas para o mesmo e-mail e IP bloqueiam o login por 15 minutos;
- defina a variável de ambiente `SECRET_KEY` com um valor longo e aleatório para as sessões sobreviverem a reinícios; sem ela, o servidor gera uma chave nova a cada execução e avisa no terminal;
- ao publicar com HTTPS, defina também `SESSION_COOKIE_SECURE=1`.

> **Dados de exemplo:** enquanto o grafo e os algoritmos reais não estiverem prontos, a API usa dados gerados por `src/api/mock.py`, e a tela mostra o selo *dados de exemplo*. Veja [Integração](#-integração-duplas-1-e-2).

## 🖥️ A tela

```
┌──────────────────────┬─────────────────────────────────────┐
│ RotaGrafo  ❓ Ajuda   │                                     │
│ [Rotas|Comparação|   │              MAPA                   │
│        Desempenho]   │                                     │
│                      │   ▶ ⟲  08:00 ━━━━━━━━━━━  15 min/s  │  ← player da simulação
│  painel da aba       ├─────────────────────────────────────┤
│  selecionada         │         LINHA DO TEMPO              │  ← uma linha por veículo
└──────────────────────┴─────────────────────────────────────┘
```

| Parte | O que é |
|---|---|
| **❓ Ajuda** | reabre o guia interativo (ele abre sozinho na primeira visita) |
| **Aba Rotas** | cenário, configuração da frota e resultado de cada rota |
| **Aba Comparação** | roda todos os algoritmos e compara os resultados |
| **Aba Desempenho** | mede o tempo de execução dos algoritmos para grafos de vários tamanhos |
| **Mapa** | depósito, clientes e as rotas desenhadas, uma cor por veículo |
| **Player** | anima o dia de trabalho dos veículos |
| **Linha do tempo** | mostra, hora a hora, o que cada veículo está fazendo |

### Legenda do mapa

| Símbolo | Significado |
|---|---|
| 🏭 | depósito (onde todas as rotas começam e terminam) |
| círculo colorido com número | cliente (o número é o id; a cor é a do veículo que o atende) |
| linha colorida | rota de um veículo (cada veículo tem uma cor fixa) |
| círculo só com a borda | cliente aguardando a entrega (durante a simulação) |
| 🚚 | veículo em movimento (durante a simulação) |
| ✓ | cliente atendido dentro da janela de tempo |
| **!** vermelho | cliente atendido **com atraso** (depois do fim da janela) |

A mesma legenda aparece no canto inferior esquerdo do mapa.

## 📖 Como usar

### 1. Calcular as rotas (aba Rotas)
1. Em **Cenário**, veja o tamanho do grafo (vértices e arestas), a demanda total e quantos veículos são necessários no mínimo. Marque *Mostrar arestas do grafo* para ver todas as ligações no mapa.
2. Em **Configuração**, escolha:
   - **Veículos:** quantos veículos a frota tem;
   - **Capacidade:** a carga máxima de cada veículo;
   - **Algoritmo:** Vizinho mais próximo ou Clarke-Wright;
   - **2-opt:** se a melhoria das rotas deve ser aplicada.
3. Clique em **Calcular rotas**.

### 2. Ler o resultado
- **Métricas:** distância total, tempo total, veículos usados, número de atrasos e tempo de execução do algoritmo.
- **Cartões das rotas:** um por veículo, com distância, tempo, ocupação da carga (barra) e a lista de entregas com horários.
- **Clientes não atendidos:** aparecem em destaque quando a frota não dá conta de toda a demanda. Aumente os veículos ou a capacidade.
- Clique num cartão ou numa rota no mapa para **destacá-la**; as outras ficam apagadas.
- Clique num cliente no mapa para ver nome, demanda, janela de tempo, prioridade e horário de atendimento.

### 3. Simular o dia
1. Aperte **▶** (ou a **barra de espaço**). Os veículos 🚚 saem do depósito às 08:00 e percorrem as rotas enquanto o relógio corre.
2. Acompanhe os clientes mudando de estado: aguardando → em atendimento → ✓ ou **!**.
3. Use a **barra de horário** para ir direto a qualquer momento do dia e o seletor de **velocidade** (5, 15, 30 ou 60 min por segundo).
4. Aperte **⟲** para voltar à visão geral das rotas.

### 4. Ler a linha do tempo
Cada linha é um veículo. Da esquerda para a direita:
- **linha fina:** veículo viajando;
- **tracejado:** veículo esperando a janela do cliente abrir;
- **bloco:** entrega em andamento. Blocos vermelhos com **!** são entregas atrasadas.

Passe o mouse num bloco para ver o cliente, os horários e, ao fundo, a **janela de tempo** dele. Clique no bloco para localizar o cliente no mapa. Durante a simulação, um cursor vertical acompanha o relógio.

### 5. Comparar algoritmos (aba Comparação)
Clique em **Comparar algoritmos**. O sistema roda todas as combinações (cada algoritmo, com e sem 2-opt) com a mesma frota e mostra uma tabela e um gráfico de barras. A melhor configuração, a de menor distância, fica marcada com ★.

### 6. Medir o desempenho (aba Desempenho)
Digite os tamanhos de grafo (número de clientes, separados por vírgula, entre 2 e 500) e clique em **Medir desempenho**. O gráfico mostra o tempo de execução de cada algoritmo conforme o grafo cresce; passe o mouse para ver os valores. A tabela completa fica em *Ver tabela*. Esses dados servem para comparar o comportamento real com a complexidade teórica no relatório.

### 7. Exportar
Na aba Rotas, **Exportar resultado (JSON)** salva a solução calculada, para usar em tabelas e análises do relatório.

### Atalhos

| Tecla | Ação |
|---|---|
| `Espaço` | play/pausa da simulação |
| `→` / `Enter` | próximo passo do guia |
| `←` | passo anterior do guia |
| `Esc` | fecha o guia |

## 🧪 Testes

```bash
.venv\Scripts\python -m unittest discover tests -v
```

Os **testes de contrato** (`tests/test_contrato.py`) conferem se o grafo e as rotas devolvidos estão no formato que a API e o front esperam, e se as rotas respeitam as regras básicas:
- começam e terminam no depósito;
- não passam da capacidade;
- não repetem nem esquecem clientes;
- os horários estão em ordem (saída → chegada → início → fim → retorno).

Os **testes de corretude** (`tests/test_corretude.py`) vão além do formato e conferem os números com um Dijkstra de referência:
- a distância de cada rota é a soma dos caminhos mínimos entre as paradas;
- nenhum veículo chega antes do que o tempo mínimo de viagem permite;
- cada entrega começa quando o veículo chega ou quando a janela abre (o que vier depois), e `atrasado` está certo;
- as métricas somam as rotas, e com frota de sobra ninguém fica sem atendimento;
- em instâncias pequenas, nenhuma solução fica mais curta que o ótimo da força bruta.

Dois testes de qualidade (o 2-opt nunca piora; Clarke-Wright + 2-opt fica a até 25% do ótimo) só rodam quando `FONTE = "real"`.

**Rode esses testes antes de integrar o seu código.**

## 🔗 Integração (Duplas 1 e 2)

A API não depende de como o grafo e os algoritmos são feitos por dentro, só do **formato** do que eles devolvem. Para trocar os dados de exemplo pelo código real:

1. Implemente as funções em `src/grafo/` e `src/algoritmos/` devolvendo os formatos da seção [Contrato da API](#-contrato-da-api).
2. No topo de `src/api/app.py`, troque as linhas que apontam para `mock`:
   ```python
   carregar_grafo   = mock.gerar_grafo        # → função da Dupla 1
   calcular_rotas   = mock.calcular_rotas     # → função da Dupla 2
   medir_desempenho = mock.medir_desempenho  # → incluir a série do NetworkX
   FONTE = "mock"                             # → "real" (remove o selo "dados de exemplo")
   ```
3. Rode os testes de contrato. Se passarem, a interface funciona sem nenhuma mudança.

## 🔌 Contrato da API

| Rota | Retorno |
|---|---|
| `POST /api/auth/login` | recebe `{email, senha, manter}` e devolve `{usuario: {nome, email}}`; **401** `{erro}` se as credenciais forem inválidas, **429** se bloqueado por tentativas. As demais rotas abaixo exigem sessão (sem ela, **401**) |
| `POST /api/auth/registrar` | recebe `{nome, email, senha}`, cria a conta e já inicia a sessão: **201** `{usuario: {nome, email}}`; **400** `{erro, campo}` se algum campo for inválido, **409** se o e-mail já existir, **429** se passar do limite por IP |
| `POST /api/auth/logout` · `GET /api/auth/me` | encerra a sessão (204) · devolve `{nome, email}` do usuário logado |
| `GET /api/grafo` | `{vertices: [{id, nome, lat, lon, demanda, janela:[ini,fim], prioridade, deposito}], arestas: [{u, v, distancia, tempo}]}` |
| `GET /api/algoritmos` | `{"nn": "Vizinho mais próximo", "clarke_wright": "Clarke-Wright"}` |
| `POST /api/rotas` | recebe `{veiculos, capacidade, algoritmo, usar_2opt}` e devolve `{rotas: [{veiculo, paradas, chegadas, saida, retorno, distancia, tempo, carga, ocupacao}], nao_atendidos, metricas: {distancia_total, tempo_total, veiculos_usados, atrasos}, tempo_execucao_ms}` |
| `GET /api/desempenho?tamanhos=10,50,100` | `{series: [{nome, pontos: [{n, ms}]}]}`: uma série por algoritmo. A Dupla 1 acrescenta as séries do Dijkstra nosso × NetworkX |

Entradas inválidas (por exemplo, 0 veículos ou um algoritmo inexistente) devolvem **400** com `{erro: "mensagem"}`.

Detalhes de cada rota:
- `paradas`: ids dos vértices em ordem, começando e terminando no depósito.
- `chegadas`: uma entrada por cliente, na ordem das paradas, no formato `{id, chegada, inicio, fim, atrasado}`:
  - `chegada`: quando o veículo chega ao cliente;
  - `inicio`: quando a entrega começa (pode ser depois da chegada, se o veículo esperar a janela abrir);
  - `fim`: quando a entrega termina;
  - `atrasado`: `true` se `inicio` for depois do fim da janela.
- `saida`: quando o veículo sai do depósito.
- `retorno`: quando o veículo volta ao depósito.
- `carga`: soma das demandas atendidas; `ocupacao`: carga ÷ capacidade (0 a 1).

Unidades: horários em minutos desde 00:00 (ex.: 480 = 08:00), distâncias em km e tempos em minutos.

## 📄 Relatório (LaTeX)

**👉 [Ver/baixar a prévia do relatório (PDF)](relatorio/RotaGrafo-relatorio-parcial.pdf)**: versão parcial de 12/11, com 7 páginas. O GitHub abre o PDF direto no navegador; para baixar, use o botão de download no canto da visualização.

<p align="center">
  <img src="relatorio/figuras/arquitetura.png" alt="Arquitetura do RotaGrafo em três camadas" width="700">
</p>

O relatório usa o template da SBC e está em `relatorio/`:

```
relatorio/
├── main.tex                          texto do relatório
├── referencias.bib                   referências bibliográficas
├── RotaGrafo-relatorio-parcial.pdf   prévia compilada (atualizar a cada versão)
└── figuras/                          imagens usadas no relatório
    ├── arquitetura.png               Figura 1: arquitetura em três camadas
    ├── uml-componentes.png           Figura 2: diagrama de componentes
    ├── uml-sequencia.png             Figura 3: diagrama de sequência do cálculo de rotas
    ├── uml-estados-simulacao.png     Figura 4: diagrama de estados da simulação
    ├── uml-estados-cliente.png       (gerada, ainda não usada no texto)
    └── uml-casos-uso-interface.png   (gerada, ainda não usada; a Dupla 1 decide se entra)
```

### Como compilar no Overleaf

O `main.tex` depende de dois arquivos do template da SBC (`sbc-template.sty` e `sbc.bst`), que não estão no repositório. Por isso, o projeto é criado a partir do template:

1. Abra o [template SBC no Overleaf](https://www.overleaf.com/latex/templates/sbc-conferences-template/blbxwjwzdngr) e clique em **Open as Template**.
2. No **File tree**, clique em **⬆ Upload** e envie `relatorio/main.tex` e `relatorio/referencias.bib`. Quando perguntar, clique em **Overwrite**, porque o template também tem um `main.tex`.
3. Crie uma pasta chamada **`figuras`** (ícone 📁) e, com ela selecionada, envie os PNGs de `relatorio/figuras/`. **Eles precisam ficar dentro da pasta `figuras`**, senão o LaTeX não acha as imagens.
4. Clique em **Recompile**.
5. Para atualizar a prévia do repositório, baixe o PDF (ícone ⬇ ao lado do Recompile) e salve como `relatorio/RotaGrafo-relatorio-parcial.pdf`.

> Os arquivos `fig1.jpg`, `fig2.jpg`, `table.jpg` e `sbc-template.bib` são do exemplo do template e podem ficar no projeto do Overleaf. Os avisos em laranja ao lado do Recompile não impedem a compilação; hoje são as referências aos prints das telas, que ainda não existem ("Figura ??").

**Trabalho em grupo:** pelo botão **Share** do Overleaf dá para convidar os 6 membros para o mesmo projeto. No fim, copiem o `main.tex` de volta para o repositório, porque a entrega pede o `.tex` e o PDF no `.zip`.

### Como regenerar as figuras dos diagramas

Os diagramas são escritos em [Mermaid](https://mermaid.js.org/) em [docs/diagramas.md](docs/diagramas.md). Depois de editar um diagrama, gere o PNG de novo:
- **Sem instalar nada:** cole o bloco em https://mermaid.live, use *Actions → PNG* e salve em `relatorio/figuras/` com o nome indicado no `diagramas.md`.
- **Pelo terminal** (precisa do Node.js): `npx -p @mermaid-js/mermaid-cli mmdc -i diagrama.mmd -o relatorio/figuras/nome.png -s 3 -b white`. Use a escala `-s 3` para a imagem ficar nítida no PDF.

Depois, envie o PNG novo para a pasta `figuras` do Overleaf com **Overwrite** e recompile.

## 📁 Estrutura

```
src/grafo/        Dupla 1: classe do grafo, leitura dos dados e Dijkstra
src/algoritmos/   Dupla 2: vizinho mais próximo, Clarke-Wright, 2-opt e métricas
src/api/          Dupla 3: API Flask (app.py), login e sessão (auth.py), validador do contrato (contrato.py) e dados de exemplo (mock.py)
frontend/         Dupla 3: interface (index.html, style.css, app.js) e telas de login e cadastro (login.*, registrar.*, logo.svg)
tests/            testes de contrato, de corretude e de autenticação
dados/            base de dados (CSV) e usuários do login (usuarios.json; usuarios.local.json = contas criadas pela tela, fora do git)
relatorio/        relatório LaTeX (template SBC): main.tex, referencias.bib, figuras/ e a prévia em PDF
docs/             diagramas UML (diagramas.md), roteiro da apresentação e do vídeo, checklist de entrega
```

## ❓ Problemas comuns

| Problema | Solução |
|---|---|
| `O sistema não pode encontrar o caminho especificado` | o terminal está na pasta errada. Rode `cd tp-grafos-centro-logistico-10` antes |
| `No module named flask` | o ambiente virtual não foi usado. Rode com `.venv\Scripts\python` ou instale de novo com `pip install -r requirements.txt` |
| O mapa fica cinza, sem ruas | o mapa de fundo vem da internet (OpenStreetMap); confira a conexão. As rotas continuam funcionando |
| `Address already in use` / porta 5000 ocupada | já existe um servidor rodando; feche o outro terminal ou use `Ctrl + C` nele |
| Clientes não atendidos | a frota é pequena para a demanda; aumente os veículos ou a capacidade |

## 📋 Andamento e pendências

Entrega: **22/11**. Situação em 12/11:

| Item | Situação | Responsável |
|---|---|---|
| Interface web, simulação, linha do tempo, comparação, desempenho | ✅ pronto (com dados de exemplo) | Dupla 3 |
| API, contrato, login e cadastro | ✅ pronto | Dupla 3 |
| Testes de contrato, de corretude e de autenticação | ✅ prontos (51 testes) | Dupla 3 |
| Seção 4 do relatório (arquitetura, testes, acesso, interface) e diagramas UML | ✅ pronta, menos os prints | Dupla 3 |
| **Classe do grafo, leitura do CSV e Dijkstra** (`src/grafo/`) | ❌ não iniciado | **Dupla 1** |
| **Base de dados** em `dados/` + nota de origem (Kaggle) | ❌ falta | **Dupla 1** |
| **Vizinho mais próximo, Clarke-Wright e 2-opt** (`src/algoritmos/`) | ❌ não iniciado | **Dupla 2** |
| Integração (trocar o mock em `src/api/app.py`) e rodar os testes | ⏳ depende das Duplas 1 e 2 | Todos |
| Prints das telas no relatório (tirar os "Figura ??") | ⏳ depois da integração | Dupla 3 |
| Seções 2, 3 e 5 do relatório (modelagem, algoritmos, resultados + NetworkX) | ❌ vazias | Duplas 1 e 2 |
| Limitações, conclusão, nomes completos, instituição, tabela de responsabilidades | ❌ falta | Todos |
| Relatório com **12 a 15 páginas** (hoje: 7) | ⏳ | Todos |
| Slides (10 min) e vídeo (12 a 18 min) | ❌ falta | Todos, ver [docs/apresentacao.md](docs/apresentacao.md) |
| Commits de **todos** os 6 membros no Git | ⏳ hoje só 2 membros têm commits | Todos |

## 🆕 Últimas alterações (12/11)

**Testes de corretude:** `tests/test_corretude.py`, 12 testes novos
- Dijkstra de referência, conferido contra Floyd-Warshall, usado para validar os resultados de `calcular_rotas` em 4 instâncias × 4 frotas × 2 algoritmos × com e sem 2-opt.
- Conferem: grafo conexo e sem laços ou arestas repetidas; distância das rotas igual à soma dos caminhos mínimos; tempo mínimo de viagem respeitado; janelas de tempo (espera, sem espera à toa, `atrasado` correto); métricas e ocupação; ausência de rotas vazias; atendimento completo com frota de sobra; nenhuma solução abaixo do ótimo da força bruta.
- Dois testes de qualidade só rodam com `FONTE = "real"`: o 2-opt nunca piora, e Clarke-Wright + 2-opt fica a até 25% do ótimo.
- Hoje: 51 testes no total, todos passando (2 pulados enquanto a API usa o mock).

**Relatório** (`relatorio/main.tex`):
- Figura 1 (arquitetura) incluída, e Figuras 2 a 4 (componentes, sequência, estados) ativadas.
- Pacote `float` adicionado, com as figuras fixadas no lugar (`[H]`). Antes, elas iam parar depois das Referências.
- Tabela de rotas da API atualizada com `/api/desempenho`, `/api/auth/login`, `/api/auth/registrar` e `/api/auth/logout`.
- Novas subseções **4.3 Testes de corretude** e **4.4 Controle de acesso**.
- O texto agora fala em "quatro linhas" do ponto de integração, e não mais "duas".
- Login, cadastro e controle de sessão acrescentados nas atividades do Vitor, na tabela de responsabilidades.
- Prévia compilada em `relatorio/RotaGrafo-relatorio-parcial.pdf`.

**Figuras** (`relatorio/figuras/`): 6 PNGs gerados a partir de `docs/diagramas.md`, com fonte maior para ficarem legíveis no PDF.

**Diagramas** (`docs/diagramas.md`):
- Diagrama de componentes atualizado com o login (páginas de login e cadastro, `auth.py`, `usuarios.json`).
- Novo diagrama 1b, de arquitetura em camadas.

**README:** seções de testes, relatório (prévia, Overleaf e como regenerar as figuras), andamento e esta lista de alterações.

## 👥 Equipe

| Dupla | Responsabilidade | Integrantes |
|---|---|---|
| 1 | Estrutura do grafo e dados | Zaine e Bruna |
| 2 | Algoritmos de roteirização | Kethellen e Rafael |
| 3 | Front-end, relatório e apoio | Filipe e Vitor |
