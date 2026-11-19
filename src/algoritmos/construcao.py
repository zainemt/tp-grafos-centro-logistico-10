"""Heurísticas construtivas de rotas: vizinho mais próximo e Clarke-Wright."""


def _atrasos_rota(rota, deposito, tempo, janela, inicio_expediente, tempo_servico):
    relogio = inicio_expediente
    atual = deposito
    atrasos = 0

    for c in rota:
        inicio = max(relogio + tempo[atual][c], janela[c][0])
        if round(inicio, 1) > janela[c][1]:
            atrasos += 1
        relogio = inicio + tempo_servico
        atual = c

    return atrasos


def vizinho_mais_proximo(
    clientes, deposito, dist, tempo, demanda, capacidade,
    veiculos, prioridade, janela, inicio_expediente, tempo_servico
):
    nao_atendidos = [c for c in clientes if demanda[c] > capacidade]
    pendentes = [c for c in clientes if demanda[c] <= capacidade]
    viagens = []

    while pendentes and len(viagens) < veiculos:
        atual = deposito
        carga = 0
        relogio = inicio_expediente
        rota = []

        while True:
            candidatos = [
                c for c in pendentes if demanda[c] + carga <= capacidade]
            if not candidatos:
                viagens.append(rota)
                break

            def custo(c):
                inicio = max(relogio + tempo[atual][c], janela[c][0])
                atraso = max(0, inicio - janela[c][1])
                return (atraso > 0, inicio, dist[atual][c] / prioridade[c])

            proximo = min(candidatos, key=custo)
            inicio = max(relogio + tempo[atual][proximo], janela[proximo][0])

            # Se vai atrasar e ainda há veículos livres na frota, fecha esta rota
            if round(inicio, 1) > janela[proximo][1] and rota and len(viagens) + 1 < veiculos:
                viagens.append(rota)
                break

            relogio = inicio + tempo_servico
            atual = proximo
            pendentes.remove(atual)
            rota.append(atual)
            carga += demanda[atual]

    return viagens, pendentes + nao_atendidos


def calcular_economias(clientes, deposito, dist):
    economias = []

    for a in range(len(clientes)):
        for b in range(a + 1, len(clientes)):
            i = clientes[a]
            j = clientes[b]
            ganho = dist[deposito][i] + dist[deposito][j] - dist[i][j]
            economias.append((ganho, i, j))

    return sorted(economias, reverse=True)


def clarke_wright(clientes, deposito, dist, tempo, demanda, capacidade, veiculos, prioridade, janela, inicio_expediente, tempo_servico):

    nao_atendidos = [
        cliente for cliente in clientes if demanda[cliente] > capacidade]
    pendentes = [
        cliente for cliente in clientes if demanda[cliente] <= capacidade]

    rotas = [[c] for c in pendentes]

    economias = calcular_economias(pendentes, deposito, dist)

    for exigir_sem_atraso in (True, False):
        if not exigir_sem_atraso and len(rotas) <= veiculos:
            break

        for ganho, i, j in economias:
            if ganho <= 0:
                break
            rota_i = next(r for r in rotas if i in r)
            rota_j = next(r for r in rotas if j in r)
            if rota_i is rota_j:
                continue
            if sum(demanda[c] for c in rota_i) + sum(demanda[c] for c in rota_j) > capacidade:
                continue
            if (i != rota_i[0] and i != rota_i[-1]) or (j != rota_j[0] and j != rota_j[-1]):
                continue

            cand_i = rota_i if i == rota_i[-1] else list(reversed(rota_i))
            cand_j = rota_j if j == rota_j[0] else list(reversed(rota_j))

            opcao1 = cand_i + cand_j
            opcao2 = cand_j + cand_i
            atrasos1 = _atrasos_rota(
                opcao1, deposito, tempo, janela, inicio_expediente, tempo_servico)
            atrasos2 = _atrasos_rota(
                opcao2, deposito, tempo, janela, inicio_expediente, tempo_servico)

            combinada, atrasos_comb = (
                opcao1, atrasos1) if atrasos1 <= atrasos2 else (opcao2, atrasos2)

            if exigir_sem_atraso and len(rotas) > veiculos and atrasos_comb > 0:
                continue

            rota_i[:] = combinada
            rotas.remove(rota_j)

    ordenadas = sorted(rotas, key=lambda r: sum(
        prioridade[p] for p in r), reverse=True)
    viagens = ordenadas[:veiculos]

    sobras = [c for rota in ordenadas[veiculos:] for c in rota]
    sobras.sort(key=lambda c: (-prioridade[c], janela[c][1]))

    for cliente in sobras:
        melhor = None
        for r_idx, rota in enumerate(viagens):
            if sum(demanda[x] for x in rota) + demanda[cliente] > capacidade:
                continue
            dist_antes = sum(dist[a][b] for a, b in zip(
                [deposito] + rota, rota + [deposito]))
            for pos in range(len(rota) + 1):
                cand = rota[:pos] + [cliente] + rota[pos:]
                atrasos = _atrasos_rota(
                    cand, deposito, tempo, janela, inicio_expediente, tempo_servico)
                dist_depois = sum(dist[a][b] for a, b in zip(
                    [deposito] + cand, cand + [deposito]))
                score = (atrasos, dist_depois - dist_antes)
                if melhor is None or score < melhor[0]:
                    melhor = (score, r_idx, cand)

        if melhor is not None:
            viagens[melhor[1]] = melhor[2]
        else:
            nao_atendidos.append(cliente)

    return viagens, nao_atendidos
