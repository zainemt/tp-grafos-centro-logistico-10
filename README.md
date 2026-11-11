# 🚚 RotaGrafo

Ferramenta de roteamento e carga de veículos em centros logísticos, baseada em grafos.

Trabalho prático de **Teoria dos Grafos**, tema 10.

## 📌 Sobre

O sistema representa a rede de entregas como um grafo ponderado: os vértices são o depósito e os pontos de entrega, e as arestas carregam a distância e o tempo entre eles. A partir dos pedidos e da frota disponível, ele calcula rotas otimizadas que respeitam a **capacidade dos veículos**, as **janelas de tempo** e a **prioridade** das entregas. O resultado é exibido em uma interface com mapa.

## 🧠 Algoritmos

- **Dijkstra:** menor caminho entre os pontos
- **Clarke-Wright / vizinho mais próximo:** construção das rotas
- **2-opt:** melhoria das rotas

> O grafo é implementado do zero. O NetworkX é usado apenas na comparação de desempenho.

## 🛠️ Tecnologias

Python · API (Flask/FastAPI) · Front-end com mapa (Leaflet) · LaTeX (SBC)

## 🚀 Como executar

```bash
git clone https://github.com/zainemt/tp-grafos-centro-logistico-10.git
cd tp-grafos-centro-logistico-10
python -m venv .venv
.venv\Scripts\activate        # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
python src/api/app.py
```

Depois, abra http://localhost:5000.

> Enquanto o grafo e os algoritmos reais não estiverem prontos, a API usa dados de exemplo (`src/api/mock.py`). O ponto de integração fica no topo de `src/api/app.py`.

### Testes de contrato

```bash
python -m unittest discover tests -v
```

Os testes conferem se o grafo e as rotas devolvidos estão no formato que a API e o front esperam, e se as rotas respeitam as regras básicas: começam e terminam no depósito, não passam da capacidade e não repetem nem esquecem clientes. **Rode esses testes antes de integrar o seu código.**

## 📁 Estrutura

```
src/grafo/        Dupla 1: classe do grafo, leitura dos dados e Dijkstra
src/algoritmos/   Dupla 2: vizinho mais próximo, Clarke-Wright, 2-opt e métricas
src/api/          Dupla 3: API Flask (app.py), validador do contrato (contrato.py) e dados de exemplo (mock.py)
frontend/         Dupla 3: interface com mapa (Leaflet)
tests/            testes de contrato
dados/            base de dados (CSV)
relatorio/        relatório LaTeX (template SBC): main.tex e referencias.bib
docs/             roteiro da apresentação, do vídeo e checklist de entrega
```

## 🔌 Contrato da API

| Rota | Retorno |
|---|---|
| `GET /api/grafo` | `{vertices: [{id, nome, lat, lon, demanda, janela:[ini,fim], prioridade, deposito}], arestas: [{u, v, distancia, tempo}]}` |
| `GET /api/algoritmos` | `{"nn": "Vizinho mais próximo", "clarke_wright": "Clarke-Wright"}` |
| `POST /api/rotas` | recebe `{veiculos, capacidade, algoritmo, usar_2opt}` e devolve `{rotas: [{veiculo, paradas, chegadas, distancia, tempo, carga, ocupacao}], nao_atendidos, metricas: {distancia_total, tempo_total, veiculos_usados, atrasos}, tempo_execucao_ms}` |

As janelas de tempo são dadas em minutos desde 00:00, as distâncias em km e os tempos em minutos.

## 👥 Equipe

| Dupla | Responsabilidade | Integrantes |
|---|---|---|
| 1 | Estrutura do grafo e dados | Zaine e Bruna |
| 2 | Algoritmos de roteirização | Kethellen e Rafael |
| 3 | Front-end, relatório e apoio | Filipe e Vitor |