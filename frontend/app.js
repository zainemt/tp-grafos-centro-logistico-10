// Front-end do RotaGrafo: consome a API (src/api/app.py) e desenha os resultados.
// Depende apenas do contrato da API (ver README), não do código interno das outras duplas.
//
// Organização do arquivo:
//   1. utilidades e estado        5. simulação (animação dos veículos)
//   2. grafo base no mapa         6. linha do tempo (Gantt)
//   3. cálculo das rotas          7. comparação e desempenho
//   4. foco em uma rota           8. guia de uso (tour) e inicialização

// =====================================================================
// 1. Utilidades e estado
// =====================================================================

// Paleta categórica validada (daltonismo e contraste), sempre na mesma ordem.
// Do 9º veículo em diante usa cinza; o número do veículo continua identificando.
const PALETA = [
  { cor: "#2a78d6", texto: "#fff" },
  { cor: "#eb6834", texto: "#fff" },
  { cor: "#1baf7a", texto: "#111827" },
  { cor: "#eda100", texto: "#111827" },
  { cor: "#e87ba4", texto: "#111827" },
  { cor: "#008300", texto: "#fff" },
  { cor: "#6250d6", texto: "#fff" },
  { cor: "#e34948", texto: "#fff" },
];
const COR_OUTROS = { cor: "#7b8794", texto: "#fff" };
const COR_CRITICO = "#b42318";
const PRIORIDADE = { 1: "baixa", 2: "média", 3: "alta" };
const LIMITE_ARESTAS = 3000;

const $ = (id) => document.getElementById(id);
const corDaRota = (i) => PALETA[i] || COR_OUTROS;
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const hhmm = (min) => {
  const m = Math.floor(min);
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
};
const armazenamento = {
  ler(k) { try { return localStorage.getItem(k); } catch { return null; } },
  gravar(k, v) { try { localStorage.setItem(k, v); } catch { /* sem armazenamento: tudo bem */ } },
};

const estado = {
  grafo: null,
  vertices: {},          // id -> vértice
  algoritmos: {},
  config: null,
  resultado: null,
  linhasRotas: [],       // polylines, na ordem de resultado.rotas
  marcadores: {},        // id do cliente -> marker
  statusIcone: {},       // id do cliente -> último status desenhado (evita redesenho)
  rotaDoCliente: {},     // id do cliente -> índice da rota
  chegadaDoCliente: {},  // id do cliente -> objeto de chegada
  // simulação
  agendas: [],           // por rota: lista de segmentos {tipo, t0, t1, ...}
  caminhoes: [],
  tMin: 0, tMax: 1, t: 0,
  modo: "estatico",      // "estatico" | "simulando"
  tocando: false,
  ultimoQuadro: 0,
  focoRota: null,
};

async function api(caminho, corpo) {
  const resp = await fetch(caminho, corpo
    ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) }
    : undefined);
  const json = await resp.json();
  if (!resp.ok) throw new Error(json.erro || `Erro ${resp.status}`);
  return json;
}

async function comBotoesTravados(idErro, fn) {
  const botoes = document.querySelectorAll("#painel button:not(.ajuda):not([role=tab])");
  botoes.forEach((b) => (b.disabled = true));
  $(idErro).hidden = true;
  try { return await fn(); }
  catch (e) { $(idErro).textContent = e.message; $(idErro).hidden = false; }
  finally { botoes.forEach((b) => (b.disabled = false)); }
}

function mostrarAba(nome) {
  document.querySelectorAll(".abas button").forEach((b) => b.classList.toggle("ativa", b.dataset.aba === nome));
  document.querySelectorAll(".aba").forEach((el) => (el.hidden = el.id !== `aba-${nome}`));
  requestAnimationFrame(() => { if (nome === "desempenho" && estado.desempenho) desenharDesempenho(); });
}

// =====================================================================
// 2. Grafo base no mapa
// =====================================================================

const mapa = L.map("mapa", { zoomControl: true });
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "&copy; OpenStreetMap",
  maxZoom: 19,
}).addTo(mapa);
const camadaArestas = L.layerGroup();
const camadaRotas = L.layerGroup().addTo(mapa);
const camadaPontos = L.layerGroup().addTo(mapa);
const camadaCaminhoes = L.layerGroup();

function iconeCliente(v, paleta, status = "normal") {
  if (v.deposito) {
    return L.divIcon({ className: "", html: `<div class="marcador deposito">🏭</div>`, iconSize: [30, 30], iconAnchor: [15, 15] });
  }
  const texto = status === "entregue" ? "✓" : status === "atraso" ? "!" : v.id;
  const estilo = status === "pendente"
    ? `border-color:${paleta.cor};color:#111827`
    : `background:${paleta.cor};color:${paleta.texto}`;
  return L.divIcon({
    className: "",
    html: `<div class="marcador ${status}" style="${estilo}">${texto}</div>`,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  });
}

function textoPopup(v) {
  if (v.deposito) return `<b>${esc(v.nome)}</b><br>Ponto de partida e chegada de todos os veículos.`;
  const c = estado.chegadaDoCliente[v.id];
  const i = estado.rotaDoCliente[v.id];
  let html = `<b>${esc(v.nome)}</b><br>Demanda: ${v.demanda}<br>Janela: ${hhmm(v.janela[0])}–${hhmm(v.janela[1])}<br>Prioridade: ${PRIORIDADE[v.prioridade] || v.prioridade}`;
  if (i !== undefined) html += `<br>Veículo: ${estado.resultado.rotas[i].veiculo}`;
  if (c) {
    html += `<br>Chegada: ${hhmm(c.chegada)}`;
    if (c.inicio > c.chegada) html += ` (espera até ${hhmm(c.inicio)})`;
    html += c.atrasado ? `<br><span class="atrasado">⚠ Atendido com atraso</span>` : `<br>✓ Atendido no prazo`;
  }
  return html;
}

function desenharPontos() {
  camadaPontos.clearLayers();
  estado.marcadores = {};
  estado.statusIcone = {};
  for (const v of estado.grafo.vertices) {
    const i = estado.rotaDoCliente[v.id];
    const paleta = i === undefined ? { cor: "#9aa5b1", texto: "#fff" } : corDaRota(i);
    const m = L.marker([v.lat, v.lon], { icon: iconeCliente(v, paleta), zIndexOffset: v.deposito ? 1000 : 0 })
      .bindPopup(() => textoPopup(v))
      .addTo(camadaPontos);
    estado.marcadores[v.id] = m;
    estado.statusIcone[v.id] = "normal";
  }
}

function atualizarIconeCliente(id, status) {
  if (estado.statusIcone[id] === status) return;
  estado.statusIcone[id] = status;
  estado.marcadores[id].setIcon(iconeCliente(estado.vertices[id], corDaRota(estado.rotaDoCliente[id]), status));
}

function desenharArestas() {
  camadaArestas.clearLayers();
  for (const a of estado.grafo.arestas.slice(0, LIMITE_ARESTAS)) {
    const u = estado.vertices[a.u], v = estado.vertices[a.v];
    L.polyline([[u.lat, u.lon], [v.lat, v.lon]], { color: "#64748b", weight: 1, opacity: 0.25 })
      .bindTooltip(`${a.u} ↔ ${a.v}: ${a.distancia} km, ${a.tempo} min`, { sticky: true })
      .addTo(camadaArestas);
  }
}

function mostrarResumo() {
  const clientes = estado.grafo.vertices.filter((v) => !v.deposito);
  const demandaTotal = clientes.reduce((s, v) => s + v.demanda, 0);
  $("resumo").innerHTML = [
    [estado.grafo.vertices.length, "Vértices"],
    [estado.grafo.arestas.length, "Arestas"],
    [demandaTotal, "Demanda total"],
    [clientes.filter((v) => v.prioridade === 3).length, "Prioridade alta"],
  ].map(([valor, nome]) => `<div class="metrica"><b>${valor}</b><span>${nome}</span></div>`).join("");
  atualizarDica();
}

function atualizarDica() {
  if (!estado.grafo) return;
  const demandaTotal = estado.grafo.vertices.reduce((s, v) => s + v.demanda, 0);
  const cap = Math.max(1, Number($("capacidade").value));
  const capTotal = Number($("veiculos").value) * cap;
  const minVeic = Math.ceil(demandaTotal / cap);
  $("dica").textContent = capTotal >= demandaTotal
    ? `Capacidade da frota: ${capTotal} (sobra ${capTotal - demandaTotal}). Mínimo teórico: ${minVeic} veículo(s).`
    : `⚠ Capacidade da frota (${capTotal}) menor que a demanda (${demandaTotal}). Use ao menos ${minVeic} veículo(s).`;
}

function adicionarLegendaMapa() {
  const legenda = L.control({ position: "bottomleft" });
  legenda.onAdd = () => {
    const div = L.DomUtil.create("div", "legenda-mapa");
    div.innerHTML = `
      <b>Legenda</b>
      <div class="item"><div class="marcador deposito" style="width:22px;height:22px;font-size:11px">🏭</div>Depósito</div>
      <div class="item"><div class="marcador" style="background:${PALETA[0].cor}">7</div>Cliente (cor = veículo)</div>
      <div class="item"><div class="marcador pendente" style="border-color:${PALETA[0].cor};color:#111827">7</div>Aguardando entrega</div>
      <div class="item"><div class="marcador" style="background:${PALETA[0].cor}">✓</div>Entregue no prazo</div>
      <div class="item"><div class="marcador atraso">!</div>Entregue com atraso</div>
      <div class="item"><span style="font-size:16px">🚚</span>Veículo (na simulação)</div>`;
    L.DomEvent.disableClickPropagation(div);
    return div;
  };
  legenda.addTo(mapa);
}

// =====================================================================
// 3. Cálculo das rotas
// =====================================================================

function lerConfig() {
  return {
    veiculos: Number($("veiculos").value),
    capacidade: Number($("capacidade").value),
    algoritmo: $("algoritmo").value,
    usar_2opt: $("usar2opt").checked,
  };
}

async function calcularRotas() {
  return comBotoesTravados("erro", async () => {
    const config = lerConfig();
    const resultado = await api("/api/rotas", config);
    estado.config = config;
    estado.resultado = resultado;
    desenharResultado();
  });
}

function desenharResultado() {
  const res = estado.resultado;
  pararSimulacao();
  estado.focoRota = null;
  estado.rotaDoCliente = {};
  estado.chegadaDoCliente = {};
  res.rotas.forEach((r, i) => {
    r.paradas.forEach((id) => { if (!estado.vertices[id].deposito) estado.rotaDoCliente[id] = i; });
    r.chegadas.forEach((c) => { estado.chegadaDoCliente[c.id] = c; });
  });

  camadaRotas.clearLayers();
  estado.linhasRotas = res.rotas.map((r, i) => {
    const coords = r.paradas.map((id) => [estado.vertices[id].lat, estado.vertices[id].lon]);
    return L.polyline(coords, { color: corDaRota(i).cor, weight: 4, opacity: 0.85 })
      .bindTooltip(`Veículo ${r.veiculo}`, { sticky: true })
      .on("click", (e) => { L.DomEvent.stopPropagation(e); focarRota(i); })
      .addTo(camadaRotas);
  });
  desenharPontos();

  // cartões
  const lista = $("lista-rotas");
  lista.innerHTML = "";
  res.rotas.forEach((r, i) => {
    const paleta = corDaRota(i);
    const atrasos = r.chegadas.filter((c) => c.atrasado).length;
    const linhas = r.chegadas.map((c, k) => {
      const v = estado.vertices[c.id];
      return `<tr><td>${k + 1}. ${esc(v.nome)}</td><td>${hhmm(v.janela[0])}–${hhmm(v.janela[1])}</td>
        <td class="${c.atrasado ? "atrasado" : ""}">${hhmm(c.inicio)}${c.atrasado ? " ⚠" : ""}</td><td>${PRIORIDADE[v.prioridade] || v.prioridade}</td></tr>`;
    }).join("");
    const div = document.createElement("div");
    div.className = "rota";
    div.style.borderColor = paleta.cor;
    div.innerHTML = `
      <h3 title="Clique para destacar no mapa">Veículo ${r.veiculo}</h3>
      <small>${r.paradas.length - 2} entregas · ${r.distancia} km · ${r.tempo} min · ${hhmm(r.saida)}–${hhmm(r.retorno)}${atrasos ? ` · <span class="atrasado">${atrasos} atraso(s)</span>` : ""}</small>
      <div><small>Carga ${r.carga} (${Math.round(r.ocupacao * 100)}%)</small></div>
      <div class="barra"><div style="width:0;background:${paleta.cor}"></div></div>
      <details><summary>Ver entregas</summary><div class="tabela-wrap"><table>
        <tr><th>Parada</th><th>Janela</th><th>Atendido</th><th>Prior.</th></tr>${linhas}</table></div></details>`;
    div.querySelector("h3").addEventListener("click", () => focarRota(i));
    lista.appendChild(div);
    requestAnimationFrame(() => { div.querySelector(".barra div").style.width = `${Math.min(100, r.ocupacao * 100)}%`; });
  });

  const m = res.metricas;
  $("metricas").innerHTML = [
    [`${m.distancia_total} km`, "Distância total"],
    [`${m.tempo_total} min`, "Tempo total"],
    [m.veiculos_usados, "Veículos usados"],
    [m.atrasos, "Entregas atrasadas"],
    [`${res.tempo_execucao_ms} ms`, "Tempo de execução"],
  ].map(([valor, nome]) => `<div class="metrica"><b>${valor}</b><span>${nome}</span></div>`).join("");

  const na = res.nao_atendidos || [];
  $("nao-atendidos").hidden = na.length === 0;
  $("nao-atendidos").textContent = `Frota insuficiente: ${na.length} cliente(s) sem atendimento (${na.join(", ")}).`;
  $("sec-metricas").hidden = false;

  prepararSimulacao();
  $("player").hidden = res.rotas.length === 0;
  $("linha-tempo").hidden = res.rotas.length === 0;
  mapa.invalidateSize();
  desenharGantt();
}

function exportar() {
  if (!estado.resultado) return;
  const dados = { config: estado.config, resultado: estado.resultado, gerado_em: new Date().toISOString() };
  const blob = new Blob([JSON.stringify(dados, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `rotas_${estado.config.algoritmo}${estado.config.usar_2opt ? "_2opt" : ""}.json`;
  a.click();
  URL.revokeObjectURL(a.href);
}

// =====================================================================
// 4. Foco em uma rota
// =====================================================================

function focarRota(i) {
  estado.focoRota = i;
  document.querySelectorAll(".rota").forEach((el, j) => el.classList.toggle("foco", i === j));
  estado.linhasRotas.forEach((l, j) => l.setStyle({ opacity: i === j ? 1 : 0.15, weight: i === j ? 6 : 4 }));
  document.querySelectorAll("#gantt .linha-rota").forEach((g) => (g.style.opacity = Number(g.dataset.rota) === i ? 1 : 0.25));
  if (estado.linhasRotas[i]) mapa.fitBounds(estado.linhasRotas[i].getBounds().pad(0.2));
}

function limparFoco() {
  estado.focoRota = null;
  document.querySelectorAll(".rota").forEach((el) => el.classList.remove("foco"));
  estado.linhasRotas.forEach((l) => l.setStyle({ opacity: 0.85, weight: 4 }));
  document.querySelectorAll("#gantt .linha-rota").forEach((g) => (g.style.opacity = 1));
}

// =====================================================================
// 5. Simulação: os veículos percorrem as rotas ao longo do dia
// =====================================================================

// Cada rota vira uma agenda de segmentos: viagem (andando) ou parada (esperando/entregando).
function construirAgenda(rota) {
  const dep = rota.paradas[0];
  const segs = [];
  let t = rota.saida, pos = dep;
  for (const c of rota.chegadas) {
    segs.push({ tipo: "viagem", t0: t, t1: c.chegada, de: pos, para: c.id });
    segs.push({ tipo: "parada", t0: c.chegada, t1: c.fim, id: c.id });
    t = c.fim;
    pos = c.id;
  }
  segs.push({ tipo: "viagem", t0: t, t1: rota.retorno, de: pos, para: dep });
  return segs;
}

function posicaoEm(agenda, t) {
  const coord = (id) => [estado.vertices[id].lat, estado.vertices[id].lon];
  if (t <= agenda[0].t0) return coord(agenda[0].de);
  for (const s of agenda) {
    if (t > s.t1) continue;
    if (s.tipo === "parada") return coord(s.id);
    const f = s.t1 > s.t0 ? (t - s.t0) / (s.t1 - s.t0) : 1;
    const [a, b] = [coord(s.de), coord(s.para)];
    return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f];
  }
  return coord(agenda[agenda.length - 1].para);
}

function statusEm(c, t) {
  if (t < c.chegada) return "pendente";
  if (t < c.fim) return "atendendo";
  return c.atrasado ? "atraso" : "entregue";
}

function prepararSimulacao() {
  const rotas = estado.resultado.rotas;
  estado.agendas = rotas.map(construirAgenda);
  estado.tMin = rotas.length ? Math.min(...rotas.map((r) => r.saida)) : 0;
  estado.tMax = rotas.length ? Math.max(...rotas.map((r) => r.retorno)) : 1;
  estado.t = estado.tMin;
  camadaCaminhoes.clearLayers();
  estado.caminhoes = rotas.map((r, i) => {
    const paleta = corDaRota(i);
    const icone = L.divIcon({
      className: "",
      html: `<div class="caminhao" style="background:${paleta.cor}">🚚<small>${r.veiculo}</small></div>`,
      iconSize: [30, 30], iconAnchor: [15, 15],
    });
    return L.marker(posicaoEm(estado.agendas[i], estado.t), { icon: icone, zIndexOffset: 2000 })
      .bindTooltip(`Veículo ${r.veiculo}`)
      .addTo(camadaCaminhoes);
  });
  const slider = $("linha-relogio");
  slider.min = estado.tMin;
  slider.max = estado.tMax;
  slider.value = estado.tMin;
  $("relogio").textContent = hhmm(estado.tMin);
  $("btn-play").textContent = "▶";
}

function renderizarTempo(t) {
  estado.t = Math.max(estado.tMin, Math.min(estado.tMax, t));
  $("relogio").textContent = hhmm(estado.t);
  $("linha-relogio").value = estado.t;
  estado.caminhoes.forEach((m, i) => m.setLatLng(posicaoEm(estado.agendas[i], estado.t)));
  for (const c of Object.values(estado.chegadaDoCliente)) atualizarIconeCliente(c.id, statusEm(c, estado.t));
  moverCursorGantt(estado.t);
}

function entrarSimulacao() {
  if (estado.modo === "simulando") return;
  estado.modo = "simulando";
  camadaCaminhoes.addTo(mapa);
  renderizarTempo(estado.t);
}

function tocar() {
  if (!estado.resultado) return;
  entrarSimulacao();
  if (estado.t >= estado.tMax) estado.t = estado.tMin;
  estado.tocando = true;
  estado.ultimoQuadro = performance.now();
  $("btn-play").textContent = "⏸";
  requestAnimationFrame(quadro);
}

function pausar() {
  estado.tocando = false;
  $("btn-play").textContent = "▶";
}

function quadro(agora) {
  if (!estado.tocando) return;
  const dt = Math.min(0.1, (agora - estado.ultimoQuadro) / 1000); // evita saltos ao trocar de aba
  estado.ultimoQuadro = agora;
  renderizarTempo(estado.t + dt * Number($("velocidade").value));
  if (estado.t >= estado.tMax) { pausar(); return; }
  requestAnimationFrame(quadro);
}

// volta para a visão geral (sem caminhões, clientes com o número)
function pararSimulacao() {
  pausar();
  estado.modo = "estatico";
  camadaCaminhoes.remove();
  estado.t = estado.tMin;
  $("linha-relogio").value = estado.tMin;
  $("relogio").textContent = hhmm(estado.tMin);
  for (const id of Object.keys(estado.chegadaDoCliente)) atualizarIconeCliente(Number(id), "normal");
  moverCursorGantt(null);
}

// =====================================================================
// 6. Linha do tempo (Gantt): uma linha por veículo
// =====================================================================

const GANTT = { esq: 92, dir: 16, topo: 24, alturaLinha: 34 };

function escalaGantt(largura) {
  const ini = Math.floor(estado.tMin / 60) * 60;
  const fim = Math.max(ini + 60, Math.ceil(estado.tMax / 60) * 60);
  const x = (t) => GANTT.esq + ((Math.max(ini, Math.min(fim, t)) - ini) / (fim - ini)) * (largura - GANTT.esq - GANTT.dir);
  return { ini, fim, x };
}

function desenharGantt() {
  const caixa = $("gantt");
  const res = estado.resultado;
  if (!res || $("linha-tempo").hidden) return;
  const largura = caixa.clientWidth || 600;
  const altura = GANTT.topo + res.rotas.length * GANTT.alturaLinha + 4;
  const { ini, fim, x } = escalaGantt(largura);
  estado.escalaGantt = x;

  const horas = (fim - ini) / 60;
  const passo = horas > 12 ? 120 : 60;
  let svg = `<svg viewBox="0 0 ${largura} ${altura}" height="${altura}" role="img" aria-label="Linha do tempo das entregas por veículo">`;
  svg += `<g class="eixo">`;
  for (let t = ini; t <= fim; t += passo) {
    svg += `<line x1="${x(t)}" x2="${x(t)}" y1="${GANTT.topo - 6}" y2="${altura}"/>`;
    svg += `<text x="${x(t)}" y="${GANTT.topo - 10}" text-anchor="middle">${hhmm(t)}</text>`;
  }
  svg += `</g>`;
  svg += `<rect id="janela-hover" rx="4" visibility="hidden"/>`;

  res.rotas.forEach((r, i) => {
    const paleta = corDaRota(i);
    const y = GANTT.topo + i * GANTT.alturaLinha + GANTT.alturaLinha / 2;
    svg += `<g class="linha-rota" data-rota="${i}">`;
    svg += `<text class="rotulo-veiculo" data-rota="${i}" x="8" y="${y + 4}">Veículo ${r.veiculo}</text>`;
    for (const s of estado.agendas[i]) {
      if (s.tipo === "viagem") {
        svg += `<line x1="${x(s.t0)}" x2="${x(s.t1)}" y1="${y}" y2="${y}" stroke="${paleta.cor}" stroke-width="2"/>`;
      }
    }
    r.chegadas.forEach((c, k) => {
      if (c.inicio > c.chegada) {
        svg += `<line x1="${x(c.chegada)}" x2="${x(c.inicio)}" y1="${y}" y2="${y}" stroke="#7b8794" stroke-width="2" stroke-dasharray="3 3"/>`;
      }
      const x0 = x(c.inicio), w = Math.max(4, x(c.fim) - x0);
      const cor = c.atrasado ? COR_CRITICO : paleta.cor;
      svg += `<g class="bloco" data-rota="${i}" data-k="${k}">
        <rect x="${x0 - 2}" y="${y - 12}" width="${w + 4}" height="24" fill="transparent"/>
        <rect class="entrega" x="${x0}" y="${y - 8}" width="${w}" height="16" rx="3" fill="${cor}" stroke="#fff" stroke-width="1"/>
        ${c.atrasado && w >= 8 ? `<text x="${x0 + w / 2}" y="${y + 4}" text-anchor="middle" fill="#fff" font-size="11" font-weight="700">!</text>` : ""}
      </g>`;
    });
    svg += `</g>`;
  });
  svg += `<line id="cursor-gantt" y1="${GANTT.topo - 6}" y2="${altura}" stroke="#111827" stroke-width="2" visibility="hidden"/>`;
  svg += `</svg>`;
  caixa.innerHTML = svg;

  if (estado.focoRota !== null) focarRota(estado.focoRota);
  if (estado.modo === "simulando") moverCursorGantt(estado.t);
}

function moverCursorGantt(t) {
  const cursor = document.getElementById("cursor-gantt");
  if (!cursor || !estado.escalaGantt) return;
  if (t === null) { cursor.setAttribute("visibility", "hidden"); return; }
  const x = estado.escalaGantt(t);
  cursor.setAttribute("x1", x);
  cursor.setAttribute("x2", x);
  cursor.setAttribute("visibility", "visible");
}

function dicaGantt(ev) {
  const bloco = ev.target.closest(".bloco");
  const tip = $("tooltip");
  const janela = document.getElementById("janela-hover");
  if (!bloco) { tip.hidden = true; if (janela) janela.setAttribute("visibility", "hidden"); return; }
  const i = Number(bloco.dataset.rota);
  const r = estado.resultado.rotas[i];
  const c = r.chegadas[Number(bloco.dataset.k)];
  const v = estado.vertices[c.id];

  // destaca a janela de tempo do cliente atrás do bloco
  const x = estado.escalaGantt;
  const y = GANTT.topo + i * GANTT.alturaLinha + 3;
  janela.setAttribute("x", x(v.janela[0]));
  janela.setAttribute("width", Math.max(2, x(v.janela[1]) - x(v.janela[0])));
  janela.setAttribute("y", y);
  janela.setAttribute("height", GANTT.alturaLinha - 6);
  janela.setAttribute("fill", corDaRota(i).cor);
  janela.setAttribute("fill-opacity", "0.14");
  janela.setAttribute("stroke", corDaRota(i).cor);
  janela.setAttribute("stroke-dasharray", "4 3");
  janela.setAttribute("visibility", "visible");

  tip.innerHTML = `<b>${esc(v.nome)}</b> · Veículo ${r.veiculo}<br>
    Janela: ${hhmm(v.janela[0])}–${hhmm(v.janela[1])}<br>
    Chegada: ${hhmm(c.chegada)}${c.inicio > c.chegada ? ` · espera ${Math.round(c.inicio - c.chegada)} min` : ""}<br>
    Entrega: ${hhmm(c.inicio)}–${hhmm(c.fim)}<br>
    ${c.atrasado ? `<span class="atrasado">⚠ Atrasada (${Math.round(c.inicio - v.janela[1])} min após a janela)</span>` : "✓ No prazo"}`;
  posicionarDica(tip, $("linha-tempo"), ev);
}

function posicionarDica(tip, container, ev) {
  tip.hidden = false;
  const caixa = container.getBoundingClientRect();
  let left = ev.clientX - caixa.left + 14;
  let top = ev.clientY - caixa.top + container.scrollTop + 14;
  if (left + tip.offsetWidth > caixa.width - 8) left = ev.clientX - caixa.left - tip.offsetWidth - 14;
  if (ev.clientY + tip.offsetHeight + 20 > window.innerHeight) top -= tip.offsetHeight + 28;
  tip.style.left = `${Math.max(4, left)}px`;
  tip.style.top = `${Math.max(4, top)}px`;
}

function cliqueGantt(ev) {
  const rotulo = ev.target.closest(".rotulo-veiculo");
  const bloco = ev.target.closest(".bloco");
  const alvo = rotulo || bloco;
  if (!alvo) return;
  const i = Number(alvo.dataset.rota);
  focarRota(i);
  if (bloco) {
    const c = estado.resultado.rotas[i].chegadas[Number(bloco.dataset.k)];
    estado.marcadores[c.id].openPopup();
  }
}

// =====================================================================
// 7. Comparação e desempenho
// =====================================================================

async function comparar() {
  await comBotoesTravados("erro-comparacao", async () => {
    const base = lerConfig();
    const linhas = [];
    for (const [chave, nome] of Object.entries(estado.algoritmos)) {
      for (const opt of [false, true]) {
        const res = await api("/api/rotas", { ...base, algoritmo: chave, usar_2opt: opt });
        linhas.push({ nome: nome + (opt ? " + 2-opt" : ""), ...res.metricas, ms: res.tempo_execucao_ms });
      }
    }
    const melhor = Math.min(...linhas.map((l) => l.distancia_total));
    const maior = Math.max(...linhas.map((l) => l.distancia_total)) || 1;
    $("grafico-comparacao").innerHTML = linhas.map((l) => {
      const pct = (l.distancia_total / maior) * 100;
      const eMelhor = l.distancia_total === melhor;
      return `<div class="linha ${eMelhor ? "melhor" : ""}" title="${esc(l.nome)}: ${l.distancia_total} km">
        <span>${eMelhor ? "★ " : ""}${esc(l.nome)}</span>
        <div class="trilho"><div class="valor" style="width:0" data-largura="${pct * 0.82}"></div>
        <span class="rotulo" style="left:${pct * 0.82}%">${l.distancia_total}</span></div>
      </div>`;
    }).join("");
    requestAnimationFrame(() => document.querySelectorAll("#grafico-comparacao .valor")
      .forEach((el) => (el.style.width = `${el.dataset.largura}%`)));
    $("tabela-comparacao").innerHTML =
      "<tr><th>Configuração</th><th>km</th><th>min</th><th>Veíc.</th><th>Atrasos</th><th>ms</th></tr>" +
      linhas.map((l) => `<tr class="${l.distancia_total === melhor ? "melhor" : ""}">
        <td>${esc(l.nome)}</td><td>${l.distancia_total}</td><td>${l.tempo_total}</td>
        <td>${l.veiculos_usados}</td><td>${l.atrasos}</td><td>${l.ms}</td></tr>`).join("");
    $("sec-comparacao").hidden = false;
  });
}

async function medirDesempenho() {
  await comBotoesTravados("erro-desempenho", async () => {
    const tamanhos = $("tamanhos").value.replace(/\s+/g, "");
    estado.desempenho = await api(`/api/desempenho?tamanhos=${encodeURIComponent(tamanhos)}`);
    $("sec-desempenho").hidden = false;
    desenharDesempenho();
  });
}

function marcasEixo(max, n = 4) {
  if (!(max > 0)) return [0, 1];
  const bruto = max / n;
  const mag = 10 ** Math.floor(Math.log10(bruto));
  const passo = [1, 2, 5, 10].map((k) => k * mag).find((p) => p >= bruto);
  const marcas = [];
  for (let v = 0; v < max + passo * 1e-9; v += passo) marcas.push(Number(v.toPrecision(12)));
  if (marcas[marcas.length - 1] < max) marcas.push(Number((marcas[marcas.length - 1] + passo).toPrecision(12)));
  return marcas;
}

function desenharDesempenho() {
  const dados = estado.desempenho;
  const caixa = $("grafico-desempenho");
  if (!dados || !caixa.clientWidth) return;
  const series = dados.series;
  const largura = caixa.clientWidth, altura = 230;
  const m = { esq: 44, dir: 12, topo: 10, base: 34 };
  const ns = [...new Set(series.flatMap((s) => s.pontos.map((p) => p.n)))].sort((a, b) => a - b);
  const yMarcas = marcasEixo(Math.max(...series.flatMap((s) => s.pontos.map((p) => p.ms))));
  const yMax = yMarcas[yMarcas.length - 1];
  const nMin = ns[0], nMax = ns[ns.length - 1] === ns[0] ? ns[0] + 1 : ns[ns.length - 1];
  const x = (n) => m.esq + ((n - nMin) / (nMax - nMin)) * (largura - m.esq - m.dir);
  const y = (v) => altura - m.base - (v / yMax) * (altura - m.topo - m.base);
  const cor = (i) => corDaRota(i).cor;

  $("legenda-desempenho").innerHTML = series.map((s, i) =>
    `<span><i style="background:${cor(i)}"></i>${esc(s.nome)}</span>`).join("");

  let svg = `<svg viewBox="0 0 ${largura} ${altura}" role="img" aria-label="Tempo de execução por número de clientes">`;
  svg += `<g class="eixo">`;
  for (const v of yMarcas) {
    svg += `<line x1="${m.esq}" x2="${largura - m.dir}" y1="${y(v)}" y2="${y(v)}"/>`;
    svg += `<text x="${m.esq - 6}" y="${y(v) + 3}" text-anchor="end">${v}</text>`;
  }
  const xMarcas = ns.length <= 8 ? ns : marcasEixo(nMax, 5).filter((v) => v >= nMin);
  for (const n of xMarcas) svg += `<text x="${x(n)}" y="${altura - m.base + 14}" text-anchor="middle">${n}</text>`;
  svg += `</g>`;
  svg += `<text class="titulo-eixo" x="${(m.esq + largura - m.dir) / 2}" y="${altura - 4}" text-anchor="middle">nº de clientes</text>`;
  svg += `<text class="titulo-eixo" x="10" y="${m.topo + 4}" >ms</text>`;
  series.forEach((s, i) => {
    const pts = [...s.pontos].sort((a, b) => a.n - b.n);
    svg += `<polyline fill="none" stroke="${cor(i)}" stroke-width="2" stroke-linejoin="round" points="${pts.map((p) => `${x(p.n)},${y(p.ms)}`).join(" ")}"/>`;
    for (const p of pts) svg += `<circle cx="${x(p.n)}" cy="${y(p.ms)}" r="4" fill="${cor(i)}" stroke="#fff" stroke-width="2"/>`;
  });
  svg += `<line id="mira-desempenho" y1="${m.topo}" y2="${altura - m.base}" stroke="#52606d" stroke-width="1" visibility="hidden"/>`;
  svg += `<rect id="area-hover" x="${m.esq}" y="${m.topo}" width="${largura - m.esq - m.dir}" height="${altura - m.topo - m.base}" fill="transparent"/>`;
  svg += `</svg><div id="tooltip-desempenho" class="tooltip" hidden></div>`;
  caixa.innerHTML = svg;

  const area = document.getElementById("area-hover");
  const mira = document.getElementById("mira-desempenho");
  const tip = document.getElementById("tooltip-desempenho");
  area.addEventListener("mousemove", (ev) => {
    const svgRect = caixa.querySelector("svg").getBoundingClientRect();
    const px = ((ev.clientX - svgRect.left) / svgRect.width) * largura;
    const n = ns.reduce((a, b) => (Math.abs(x(b) - px) < Math.abs(x(a) - px) ? b : a));
    mira.setAttribute("x1", x(n));
    mira.setAttribute("x2", x(n));
    mira.setAttribute("visibility", "visible");
    const valores = series.map((s, i) => ({ nome: s.nome, cor: cor(i), p: s.pontos.find((p) => p.n === n) }))
      .filter((v) => v.p).sort((a, b) => b.p.ms - a.p.ms);
    tip.innerHTML = `<b>${n} clientes</b><br>` + valores.map((v) =>
      `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${v.cor};margin-right:6px"></span>${esc(v.nome)}: ${v.p.ms} ms`).join("<br>");
    posicionarDica(tip, caixa, ev);
  });
  area.addEventListener("mouseleave", () => { mira.setAttribute("visibility", "hidden"); tip.hidden = true; });

  $("tabela-desempenho").innerHTML =
    `<tr><th>n</th>${series.map((s) => `<th>${esc(s.nome)}</th>`).join("")}</tr>` +
    ns.map((n) => `<tr><td>${n}</td>${series.map((s) => `<td>${s.pontos.find((p) => p.n === n)?.ms ?? "–"}</td>`).join("")}</tr>`).join("");
  $("nota-networkx").hidden = series.some((s) => /networkx/i.test(s.nome));
}

// =====================================================================
// 8. Guia de uso (tour) e inicialização
// =====================================================================

const PASSOS_TOUR = [
  { titulo: "Bem-vindo ao RotaGrafo 👋",
    texto: "Este guia rápido mostra como planejar as rotas de entrega de um centro logístico. Use os botões ou as setas do teclado (Esc fecha)." },
  { alvo: "#sec-cenario", aba: "rotas", titulo: "O cenário",
    texto: "Este é o grafo carregado: o depósito e os clientes são os vértices, e as ligações entre eles são as arestas, com distância e tempo. Marque “Mostrar arestas” para vê-las no mapa." },
  { alvo: "#form-config", aba: "rotas", titulo: "Configure a frota",
    texto: "Escolha o número de veículos, a capacidade de cada um, o algoritmo que monta as rotas e se o 2-opt deve melhorar o resultado. Depois clique em “Calcular rotas”." },
  { alvo: "#mapa-wrap", titulo: "O mapa",
    texto: "Cada cor é um veículo. 🏭 é o depósito e os círculos numerados são os clientes. Clique num cliente para ver a demanda, a janela de tempo e o horário de atendimento." },
  { alvo: "#sec-metricas", aba: "rotas", titulo: "O resultado",
    texto: "Aqui ficam as métricas gerais e um cartão por veículo. Clique no nome de um veículo para destacar a rota dele e em “Ver entregas” para a lista de paradas." },
  { alvo: "#player", titulo: "Simule o dia ▶",
    texto: "Aperte play (ou a barra de espaço) para ver os veículos saindo do depósito. Os clientes ganham ✓ quando são atendidos no prazo e ! quando há atraso. Arraste a barra para ir a qualquer horário." },
  { alvo: "#linha-tempo", titulo: "Linha do tempo",
    texto: "Cada linha é um veículo ao longo do dia, com as viagens, as esperas pela abertura da janela e as entregas. Passe o mouse numa entrega para ver a janela do cliente." },
  { alvo: ".abas", titulo: "Comparação e desempenho",
    texto: "Na aba Comparação, todos os algoritmos rodam lado a lado no mesmo cenário. Na aba Desempenho, o tempo de execução é medido em grafos de tamanhos diferentes." },
  { alvo: "#btn-ajuda", titulo: "Pronto!",
    texto: "Você pode abrir este guia de novo a qualquer momento por aqui." },
];
let passoTour = -1;

async function iniciarTour() {
  if (!estado.resultado) await calcularRotas();
  pararSimulacao();
  $("tour").hidden = false;
  mostrarPassoTour(0);
}

function fecharTour() {
  $("tour").hidden = true;
  passoTour = -1;
  armazenamento.gravar("rotagrafo-tour-visto", "1");
}

function mostrarPassoTour(i) {
  if (i < 0) return;
  if (i >= PASSOS_TOUR.length) { fecharTour(); return; }
  passoTour = i;
  const p = PASSOS_TOUR[i];
  if (p.aba) mostrarAba(p.aba);
  $("tour-passo").textContent = `Passo ${i + 1} de ${PASSOS_TOUR.length}`;
  $("tour-titulo").textContent = p.titulo;
  $("tour-texto").textContent = p.texto;
  $("tour-voltar").hidden = i === 0;
  $("tour-avancar").textContent = i === PASSOS_TOUR.length - 1 ? "Concluir" : "Próximo";

  const el = p.alvo ? document.querySelector(p.alvo) : null;
  if (el && el.offsetParent !== null) el.scrollIntoView({ block: "nearest", behavior: "instant" });
  requestAnimationFrame(() => posicionarTour(el && el.offsetParent !== null ? el : null));
}

function posicionarTour(el) {
  const foco = $("tour-foco"), cartao = $("tour-cartao");
  const W = window.innerWidth, H = window.innerHeight, folga = 6, gap = 14;
  const cw = cartao.offsetWidth, ch = cartao.offsetHeight;
  if (!el) {
    Object.assign(foco.style, { left: `${W / 2}px`, top: `${H / 2}px`, width: "0px", height: "0px" });
    Object.assign(cartao.style, { left: `${(W - cw) / 2}px`, top: `${(H - ch) / 2}px` });
    return;
  }
  const r = el.getBoundingClientRect();
  const alvo = {
    left: Math.max(4, r.left - folga), top: Math.max(4, r.top - folga),
    right: Math.min(W - 4, r.right + folga), bottom: Math.min(H - 4, r.bottom + folga),
  };
  Object.assign(foco.style, {
    left: `${alvo.left}px`, top: `${alvo.top}px`,
    width: `${alvo.right - alvo.left}px`, height: `${alvo.bottom - alvo.top}px`,
  });
  let left, top;
  if (alvo.right + gap + cw < W) { left = alvo.right + gap; top = alvo.top; }               // à direita
  else if (alvo.left - gap - cw > 0) { left = alvo.left - gap - cw; top = alvo.top; }       // à esquerda
  else if (alvo.bottom + gap + ch < H) { left = alvo.left; top = alvo.bottom + gap; }        // abaixo
  else { left = alvo.left; top = alvo.top - gap - ch; }                                      // acima
  // alvo muito grande (ex.: o mapa): cartão dentro dele, no canto superior
  if (top < 0 || top + ch > H) top = Math.max(alvo.top + gap, 8);
  cartao.style.left = `${Math.min(Math.max(8, left), W - cw - 8)}px`;
  cartao.style.top = `${Math.min(Math.max(8, top), H - ch - 8)}px`;
}

async function iniciar() {
  try {
    [estado.grafo, estado.algoritmos] = await Promise.all([api("/api/grafo"), api("/api/algoritmos")]);
  } catch (e) {
    $("erro").textContent = "Não foi possível carregar o grafo: " + e.message;
    $("erro").hidden = false;
    return;
  }
  estado.vertices = Object.fromEntries(estado.grafo.vertices.map((v) => [v.id, v]));
  $("algoritmo").innerHTML = Object.entries(estado.algoritmos)
    .map(([k, nome]) => `<option value="${k}">${esc(nome)}</option>`).join("");
  $("fonte").hidden = estado.grafo.fonte !== "mock";

  mostrarResumo();
  desenharArestas();
  desenharPontos();
  adicionarLegendaMapa();
  mapa.fitBounds(L.latLngBounds(estado.grafo.vertices.map((v) => [v.lat, v.lon])).pad(0.1));

  if (!armazenamento.ler("rotagrafo-tour-visto")) iniciarTour();
}

// ------------------------------------------------------------ eventos
$("form-config").addEventListener("submit", (ev) => { ev.preventDefault(); calcularRotas(); });
$("btn-comparar").addEventListener("click", comparar);
$("btn-desempenho").addEventListener("click", medirDesempenho);
$("btn-exportar").addEventListener("click", exportar);
$("btn-ajuda").addEventListener("click", iniciarTour);
$("veiculos").addEventListener("input", atualizarDica);
$("capacidade").addEventListener("input", atualizarDica);
$("mostrar-arestas").addEventListener("change", (e) => {
  if (e.target.checked) camadaArestas.addTo(mapa); else camadaArestas.remove();
});
document.querySelectorAll(".abas button").forEach((b) => b.addEventListener("click", () => mostrarAba(b.dataset.aba)));
mapa.on("click", limparFoco);

$("btn-play").addEventListener("click", () => (estado.tocando ? pausar() : tocar()));
$("btn-reiniciar").addEventListener("click", pararSimulacao);
$("linha-relogio").addEventListener("input", (e) => { entrarSimulacao(); pausar(); renderizarTempo(Number(e.target.value)); });

$("gantt").addEventListener("mousemove", dicaGantt);
$("gantt").addEventListener("mouseleave", () => dicaGantt({ target: document.body }));
$("gantt").addEventListener("click", cliqueGantt);

$("tour-avancar").addEventListener("click", () => mostrarPassoTour(passoTour + 1));
$("tour-voltar").addEventListener("click", () => mostrarPassoTour(passoTour - 1));
$("tour-pular").addEventListener("click", fecharTour);

document.addEventListener("keydown", (e) => {
  if (!$("tour").hidden) {
    if (e.key === "ArrowRight" || e.key === "Enter") { e.preventDefault(); mostrarPassoTour(passoTour + 1); }
    else if (e.key === "ArrowLeft") mostrarPassoTour(passoTour - 1);
    else if (e.key === "Escape") fecharTour();
    return;
  }
  const digitando = ["INPUT", "SELECT", "TEXTAREA", "BUTTON"].includes(document.activeElement?.tagName);
  if (e.code === "Space" && !digitando && estado.resultado) {
    e.preventDefault();
    estado.tocando ? pausar() : tocar();
  }
});

let esperaResize;
window.addEventListener("resize", () => {
  clearTimeout(esperaResize);
  esperaResize = setTimeout(() => {
    desenharGantt();
    desenharDesempenho();
    if (!$("tour").hidden) mostrarPassoTour(passoTour);
  }, 120);
});

iniciar();
