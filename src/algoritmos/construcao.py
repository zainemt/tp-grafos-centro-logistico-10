"""Heurísticas construtivas de rotas: vizinho mais próximo (e, depois, Clarke-Wright)."""


def vizinho_mais_proximo(clientes, deposito, dist, demanda, capacidade, veiculos, prioridade):

    nao_atendidos = [
        cliente for cliente in clientes if demanda[cliente] > capacidade]
    pendentes = [
        cliente for cliente in clientes if demanda[cliente] <= capacidade]
    viagens = []

    # enquanto tiver cliente pendente e tiver menos viagens que veiculos
    while pendentes and len(viagens) < veiculos:

        atual = deposito
        carga = 0
        rota = []

        while True:

            candidatos = [
                cliente for cliente in pendentes if demanda[cliente] + carga <= capacidade]
            if not candidatos:
                viagens.append(rota)
                break
            proximo = min(candidatos, key=lambda cliente: (
                dist[atual][cliente]/prioridade[cliente]))
            atual = proximo
            pendentes.remove(atual)
            rota.append(atual)
            carga += demanda[atual]

    return viagens, pendentes+nao_atendidos


def calcular_economias(clientes, deposito, dist):
    economias = []

    for a in range(len(clientes)):
        for b in range(a+1, len(clientes)):
            i = clientes[a]
            j = clientes[b]
            ganho = dist[deposito][i] + dist[deposito][j] - dist[i][j]
            economias.append((ganho, i, j))

    return sorted(economias, reverse=True)


def clarke_wright(clientes, deposito, dist, demanda, capacidade, veiculos, prioridade):

    nao_atendidos = [
        cliente for cliente in clientes if demanda[cliente] > capacidade]
    pendentes = [
        cliente for cliente in clientes if demanda[cliente] <= capacidade]

    rotas = [[c] for c in pendentes]

    economias = calcular_economias(pendentes, deposito, dist)

    for ganho, i, j in economias:
        if ganho <= 0:
            break
        rota_i = next(r for r in rotas if i in r)
        rota_j = next(r for r in rotas if j in r)
        if rota_i is rota_j:
            continue

        if sum(demanda[c] for c in rota_i) + sum(demanda[c] for c in rota_j) > capacidade:
            continue

        if i != rota_i[0] and i != rota_i[-1] or j != rota_j[0] and j != rota_j[-1]:
            continue

        if i != rota_i[-1]:
            rota_i.reverse()

        if j != rota_j[0]:
            rota_j.reverse()

        rota_i.extend(rota_j)
        rotas.remove(rota_j)

    ordenadas = sorted(rotas, key=lambda r: sum(
        prioridade[p] for p in r), reverse=True)
    viagens = ordenadas[:veiculos]

    for rota in ordenadas[veiculos:]:
        nao_atendidos.extend(rota)

    return viagens, nao_atendidos
