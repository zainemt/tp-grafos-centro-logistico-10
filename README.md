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
git clone <url-do-repositorio>
cd RotaGrafo
pip install -r requirements.txt
python src/api/app.py
```

## 👥 Equipe

| Dupla | Responsabilidade | Integrantes |
|---|---|---|
| 1 | Estrutura do grafo e dados | Zaine e Bruna |
| 2 | Algoritmos de roteirização | Kethellen e Rafael |
| 3 | Front-end, relatório e apoio | Filipe e Vitor |