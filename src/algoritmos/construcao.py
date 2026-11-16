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
