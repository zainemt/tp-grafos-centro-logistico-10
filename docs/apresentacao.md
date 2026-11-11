# Roteiro da apresentação e do vídeo

Regras do enunciado: **todos os membros participam**. A apresentação presencial tem **10 min**, com slides. O vídeo tem **entre 12 e 18 min** e mostra só o funcionamento e as features feitas por cada aluno.

---

## 1. Apresentação presencial: 10 min, 12 slides

| # | Slide | Quem apresenta | Tempo |
|---|---|---|---|
| 1 | Capa: RotaGrafo, nomes, tema 10 | Dupla 3 | 0:15 |
| 2 | O problema: centro logístico, frota limitada, capacidade, janelas de tempo e prioridade | Dupla 3 | 0:45 |
| 3 | Por que é um problema de grafos: o VRP, por que é NP-difícil e por que usamos heurísticas | Dupla 3 | 0:45 |
| 4 | Modelagem: G = (V, E), atributos dos vértices e pesos das arestas | Dupla 1 | 1:00 |
| 5 | Diagrama UML de classes | Dupla 1 | 0:45 |
| 6 | Base de dados: origem e tratamento | Dupla 1 | 0:30 |
| 7 | Dijkstra e a matriz de distâncias | Dupla 1 | 0:30 |
| 8 | Vizinho Mais Próximo × Clarke-Wright: ideia e complexidade | Dupla 2 | 1:15 |
| 9 | 2-opt: ideia, com uma figura de cruzamento desfeito | Dupla 2 | 0:45 |
| 10 | Arquitetura (núcleo, API, front) e **demo ao vivo** | Dupla 3 | 2:00 |
| 11 | Resultados: tabela comparativa, ganho do 2-opt e comparação com o NetworkX | Duplas 1 e 2 | 1:00 |
| 12 | Limitações e conclusão | Dupla 2 | 0:30 |

**Demo ao vivo (slide 10), passo a passo:**
1. Abrir o sistema e mostrar o cenário e as arestas do grafo.
2. Calcular com 3 veículos, usando Clarke-Wright + 2-opt.
3. Apertar **▶ Simular o dia** e deixar os caminhões andarem por uns 10 s. Mostrar os ✓ e os **!** aparecendo e o cursor andando na linha do tempo.
4. Passar o mouse numa entrega atrasada da linha do tempo para mostrar a janela de tempo.
5. Reduzir para 1 veículo e mostrar o aviso de frota insuficiente.
6. Na aba Comparação, mostrar a tabela e o gráfico.

> **Plano B:** grave a demo antes. Se a internet cair, o mapa de fundo não carrega.

---

## 2. Vídeo: 12 a 18 min (alvo: 15 min)

Foco no **funcionamento** e em **quem fez cada feature**. Cada pessoa grava o próprio trecho, de preferência com tela e voz.

| Bloco | Quem | Duração | O que mostrar |
|---|---|---|---|
| Abertura | Filipe | 1:00 | Problema, objetivo e visão geral da ferramenta rodando |
| Estrutura do grafo | Zaine | 2:30 | Classe do grafo no código, operações principais, por que lista de adjacência |
| Dados e Dijkstra | Bruna | 2:30 | Leitura da base, montagem do grafo, Dijkstra e a matriz de distâncias, comparação com o NetworkX |
| Construção de rotas | Kethellen | 2:30 | Vizinho Mais Próximo e Clarke-Wright no código, tratamento de capacidade, janela e prioridade |
| Melhoria e métricas | Rafael | 2:30 | 2-opt, métricas, experimentos e ganhos |
| Interface | Filipe | 2:30 | Guia de uso, mapa, rotas, **simulação do dia**, **linha do tempo**, comparação e exportação |
| API e integração | Vitor | 2:00 | Rotas da API, contrato JSON, testes de contrato rodando, **aba Desempenho**, diagramas UML da arquitetura |
| Encerramento | Vitor | 0:30 | Resultados principais e limitações |

> Ajustem os blocos ao que cada um fez de fato. O vídeo precisa bater com a tabela de responsabilidades do relatório.

**Dicas de gravação:**
- Use OBS Studio (gratuito) ou a gravação de tela do Windows (Win + Alt + R).
- Use zoom no navegador (Ctrl +) e no editor para o código ficar legível.
- Grave por blocos e junte no final (Clipchamp, que já vem no Windows, ou CapCut).
- Confira a duração total antes de enviar: precisa ficar **entre 12 e 18 min**.

---

## 3. Checklist de entrega (22/11)

- [ ] Código no Git com commits de **todos** os membros
- [ ] Relatório SBC com **12 a 15 páginas**: .tex e PDF
- [ ] Tabela de responsabilidades no relatório
- [ ] Slides
- [ ] Vídeo de 12 a 18 min
- [ ] .zip com o código-fonte, o .tex e o PDF
- [ ] **Cada um** dos 6 enviou o .zip no Canvas
