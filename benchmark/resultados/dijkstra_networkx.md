# Dijkstra: nossa implementação x NetworkX

Gerado por `python -m benchmark.comparar_dijkstra` em 18/11/2026 15:48. Python 3.15.2, NetworkX 3.7, Apple M4 (macOS-26.6.2).
Tempos: mediana de 5 execuções após 1 de aquecimento. Metodologia em `benchmark/README.md`.

## Dijkstra a partir de uma origem (ms por origem)

| Instância | Peso | V | arcos | P | Nosso | NetworkX | NetworkX / nosso | Divergências |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Mapa de SP (real) | distancia | 1550 | 2910 | 10 | 1.217 | 1.370 | 1.13 | 0 |
| Mapa de SP (real) | tempo | 1550 | 2910 | 10 | 1.442 | 1.501 | 1.04 | 0 |
| Grade 25x25 | distancia | 625 | 2400 | 10 | 0.634 | 0.756 | 1.19 | 0 |
| Grade 25x25 | tempo | 625 | 2400 | 10 | 0.638 | 0.771 | 1.21 | 0 |
| Grade 50x50 | distancia | 2500 | 9800 | 10 | 2.947 | 3.413 | 1.16 | 0 |
| Grade 50x50 | tempo | 2500 | 9800 | 10 | 2.999 | 3.582 | 1.19 | 0 |
| Grade 100x100 | distancia | 10000 | 39600 | 10 | 12.804 | 15.896 | 1.24 | 0 |
| Grade 100x100 | tempo | 10000 | 39600 | 10 | 14.207 | 16.558 | 1.17 | 0 |
| Grade 200x200 | distancia | 40000 | 159200 | 10 | 59.250 | 66.236 | 1.12 | 0 |
| Grade 200x200 | tempo | 40000 | 159200 | 10 | 49.201 | 56.423 | 1.15 | 0 |
| Grade 300x300 | distancia | 90000 | 358800 | 10 | 111.846 | 131.626 | 1.18 | 0 |
| Grade 300x300 | tempo | 90000 | 358800 | 10 | 168.887 | 172.540 | 1.02 | 0 |
| Completo n=50 | distancia | 51 | 2550 | 10 | 0.344 | 0.507 | 1.48 | 0 |
| Completo n=50 | tempo | 51 | 2550 | 10 | 0.266 | 0.417 | 1.57 | 0 |
| Completo n=100 | distancia | 101 | 10100 | 10 | 1.022 | 1.619 | 1.58 | 0 |
| Completo n=100 | tempo | 101 | 10100 | 10 | 0.996 | 1.580 | 1.59 | 0 |
| Completo n=200 | distancia | 201 | 40200 | 10 | 4.129 | 6.587 | 1.60 | 0 |
| Completo n=200 | tempo | 201 | 40200 | 10 | 4.031 | 6.552 | 1.63 | 0 |
| Completo n=400 | distancia | 401 | 160400 | 10 | 21.905 | 34.368 | 1.57 | 0 |
| Completo n=400 | tempo | 401 | 160400 | 10 | 20.256 | 29.856 | 1.47 | 0 |
| Completo n=800 | distancia | 801 | 640800 | 10 | 106.105 | 180.105 | 1.70 | 0 |
| Completo n=800 | tempo | 801 | 640800 | 10 | 97.594 | 174.263 | 1.79 | 0 |

## Matriz de custos entre P pontos (ms por matriz)

| Instância | Peso | V | arcos | P | Nosso | NetworkX | NetworkX / nosso | Divergências |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Mapa de SP (real) | distancia | 1550 | 2910 | 31 | 39.327 | 43.497 | 1.11 | 0 |
| Mapa de SP (real) | tempo | 1550 | 2910 | 31 | 40.224 | 37.083 | 0.92 | 0 |
| Grade 25x25 | distancia | 625 | 2400 | 30 | 19.619 | 20.493 | 1.04 | 0 |
| Grade 25x25 | tempo | 625 | 2400 | 30 | 18.666 | 26.543 | 1.42 | 0 |
| Grade 50x50 | distancia | 2500 | 9800 | 30 | 86.506 | 93.823 | 1.08 | 0 |
| Grade 50x50 | tempo | 2500 | 9800 | 30 | 94.705 | 95.308 | 1.01 | 0 |
| Grade 100x100 | distancia | 10000 | 39600 | 30 | 369.268 | 441.397 | 1.20 | 0 |
| Grade 100x100 | tempo | 10000 | 39600 | 30 | 401.587 | 427.437 | 1.06 | 0 |
| Grade 200x200 | distancia | 40000 | 159200 | 30 | 1664.279 | 1552.020 | 0.93 | 0 |
| Grade 200x200 | tempo | 40000 | 159200 | 30 | 1493.426 | 1540.011 | 1.03 | 0 |
| Grade 300x300 | distancia | 90000 | 358800 | 30 | 3788.842 | 4082.830 | 1.08 | 0 |
| Grade 300x300 | tempo | 90000 | 358800 | 30 | 4109.028 | 4321.534 | 1.05 | 0 |
| Completo n=50 | distancia | 51 | 2550 | 30 | 9.685 | 13.435 | 1.39 | 0 |
| Completo n=50 | tempo | 51 | 2550 | 30 | 7.977 | 12.154 | 1.52 | 0 |
| Completo n=100 | distancia | 101 | 10100 | 30 | 33.281 | 44.196 | 1.33 | 0 |
| Completo n=100 | tempo | 101 | 10100 | 30 | 30.772 | 44.242 | 1.44 | 0 |
| Completo n=200 | distancia | 201 | 40200 | 30 | 137.977 | 189.162 | 1.37 | 0 |
| Completo n=200 | tempo | 201 | 40200 | 30 | 122.903 | 181.559 | 1.48 | 0 |
| Completo n=400 | distancia | 401 | 160400 | 30 | 619.944 | 882.957 | 1.42 | 0 |
| Completo n=400 | tempo | 401 | 160400 | 30 | 617.759 | 938.020 | 1.52 | 0 |
| Completo n=800 | distancia | 801 | 640800 | 30 | 2955.099 | 4998.512 | 1.69 | 0 |
| Completo n=800 | tempo | 801 | 640800 | 30 | 2895.108 | 5019.125 | 1.73 | 0 |
