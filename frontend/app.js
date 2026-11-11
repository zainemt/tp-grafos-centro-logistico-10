// Front-end do RotaGrafo: consome a API (src/api/app.py) e desenha no mapa.
// Depende apenas do contrato da API (ver README), não do código interno das outras duplas.

const CORES = ["#2563eb", "#dc2626", "#16a34a", "#9333ea", "#ea580c", "#0891b2", "#ca8a04", "#db2777"];
const PRIORIDADE = { 1: "baixa", 2: "média", 3: "alta" };
const LIMITE_ARESTAS = 3000; // acima disso o desenho das arestas fica lento

const $ = (id) => document.getElementById(id);
const mapa = L.map("mapa");
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "&copy; OpenStreetMap",
  maxZoom: 19,
}).addTo(mapa);

let grafo = null;
let vertices = {};          // id -> vértice
let algoritmos = {};
let ultimoResultado = null; // { config, resultado } da última execução
const camadaArestas = L.layerGroup();
const camadaRotas = L.layerGroup().addTo(mapa);
const camadaPontos = L.layerGroup().addTo(mapa);
let linhasRotas = [];       // polylines, na mesma ordem de ultimoResultado.resultado.rotas

const hhmm = (min) => `${String(Math.floor(min / 60)).padStart(2, "0")}:${String(Math.round(min % 60)).padStart(2, "0")}`;

async function api(caminho, corpo) {
  const resp = await fetch(caminho, corpo
    ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) }
    : undefined);
  const json = await resp.json();
  if (!resp.ok) throw new Error(json.erro || `Erro ${resp.status}`);
  return json;
}

function mostrarErro(msg) {
  $("erro").textContent = msg || "";
  $("erro").hidden = !msg;
}

// ---------------------------------------------------------------- grafo base

function icone(v, cor) {
  const cls = v.deposito ? "marcador deposito" : "marcador";
  const texto = v.deposito ? "🏭" : v.id;
  return L.divIcon({
    className: "",
    html: `<div class="${cls}" style="${v.deposito ? "" : `background:${cor}`}">${texto}</div>`,
    iconSize: v.deposito ? [30, 30] : [22, 22],
    iconAnchor: v.deposito ? [15, 15] : [11, 11],
  });
}

function popup(v, chegada) {
  if (v.deposito) return `<b>${v.nome}</b>`;
  let html = `<b>${v.nome}</b><br>Demanda: ${v.demanda}<br>Janela: ${hhmm(v.janela[0])}–${hhmm(v.janela[1])}<br>Prioridade: ${PRIORIDADE[v.prioridade] || v.prioridade}`;
  if (chegada) {
    html += `<br>Chegada: <span class="${chegada.atrasado ? "atrasado" : ""}">${hhmm(chegada.chegada)}${chegada.atrasado ? " (atrasado)" : ""}</span>`;
  }
  return html;
}

function desenharPontos(corPorVertice = {}, chegadas = {}) {
  camadaPontos.clearLayers();
  for (const v of grafo.vertices) {
    L.marker([v.lat, v.lon], { icon: icone(v, corPorVertice[v.id] || "#9aa5b1"), zIndexOffset: v.deposito ? 1000 : 0 })
      .bindPopup(popup(v, chegadas[v.id]))
      .addTo(camadaPontos);
  }
}

function desenharArestas() {
  camadaArestas.clearLayers();
  for (const a of grafo.arestas.slice(0, LIMITE_ARESTAS)) {
    const u = vertices[a.u], v = vertices[a.v];
    L.polyline([[u.lat, u.lon], [v.lat, v.lon]], { color: "#64748b", weight: 1, opacity: 0.25 })
      .bindTooltip(`${a.u} ↔ ${a.v}: ${a.distancia} km, ${a.tempo} min`, { sticky: true })
      .addTo(camadaArestas);
  }
}

function mostrarResumo() {
  const clientes = grafo.vertices.filter((v) => !v.deposito);
  const demandaTotal = clientes.reduce((s, v) => s + v.demanda, 0);
  const urgentes = clientes.filter((v) => v.prioridade === 3).length;
  $("resumo").innerHTML = [
    [grafo.vertices.length, "Vértices"],
    [grafo.arestas.length, "Arestas"],
    [demandaTotal, "Demanda total"],
    [urgentes, "Prioridade alta"],
  ].map(([valor, nome]) => `<div class="metrica"><b>${valor}</b><span>${nome}</span></div>`).join("");
  atualizarDica();
}

function atualizarDica() {
  const demandaTotal = grafo.vertices.reduce((s, v) => s + v.demanda, 0);
  const capTotal = Number($("veiculos").value) * Number($("capacidade").value);
  const minVeic = Math.ceil(demandaTotal / Math.max(1, Number($("capacidade").value)));
  $("dica").textContent = capTotal >= demandaTotal
    ? `Capacidade da frota: ${capTotal} (sobra ${capTotal - demandaTotal}). Mínimo teórico: ${minVeic} veículo(s).`
    : `⚠ Capacidade da frota (${capTotal}) menor que a demanda (${demandaTotal}). Use ao menos ${minVeic} veículo(s).`;
}

// ---------------------------------------------------------------- resultado

function tabelaParadas(r) {
  if (!r.chegadas || !r.chegadas.length) return "";
  const linhas = r.chegadas.map((c, i) => {
    const v = vertices[c.id];
    return `<tr><td>${i + 1}. ${v.nome}</td><td>${hhmm(v.janela[0])}–${hhmm(v.janela[1])}</td>
      <td class="${c.atrasado ? "atrasado" : ""}">${hhmm(c.chegada)}</td><td>${PRIORIDADE[v.prioridade] || v.prioridade}</td></tr>`;
  }).join("");
  return `<details><summary>Ver entregas</summary><div class="tabela-wrap"><table>
    <tr><th>Parada</th><th>Janela</th><th>Chegada</th><th>Prior.</th></tr>${linhas}</table></div></details>`;
}

function focarRota(i) {
  document.querySelectorAll(".rota").forEach((el, j) => el.classList.toggle("foco", i === j));
  linhasRotas.forEach((l, j) => l.setStyle({ opacity: i === j ? 1 : 0.15, weight: i === j ? 6 : 4 }));
  if (linhasRotas[i]) mapa.fitBounds(linhasRotas[i].getBounds().pad(0.2));
}

function limparFoco() {
  document.querySelectorAll(".rota").forEach((el) => el.classList.remove("foco"));
  linhasRotas.forEach((l) => l.setStyle({ opacity: 0.85, weight: 4 }));
}

function desenharResultado(res) {
  camadaRotas.clearLayers();
  linhasRotas = [];
  const corPorVertice = {};
  const chegadas = {};
  const lista = $("lista-rotas");
  lista.innerHTML = "";

  res.rotas.forEach((r, i) => {
    const cor = CORES[i % CORES.length];
    const coords = r.paradas.map((id) => [vertices[id].lat, vertices[id].lon]);
    const linha = L.polyline(coords, { color: cor, weight: 4, opacity: 0.85 })
      .bindTooltip(`Veículo ${r.veiculo}`)
      .on("click", () => focarRota(i))
      .addTo(camadaRotas);
    linhasRotas.push(linha);
    r.paradas.forEach((id) => { if (!vertices[id].deposito) corPorVertice[id] = cor; });
    (r.chegadas || []).forEach((c) => { chegadas[c.id] = c; });

    const atrasos = (r.chegadas || []).filter((c) => c.atrasado).length;
    const div = document.createElement("div");
    div.className = "rota";
    div.style.borderColor = cor;
    div.innerHTML = `
      <h3 title="Clique para destacar no mapa">Veículo ${r.veiculo}</h3>
      <small>${r.paradas.length - 2} entregas · ${r.distancia} km · ${r.tempo} min${atrasos ? ` · <span class="atrasado">${atrasos} atraso(s)</span>` : ""}</small>
      <div><small>Carga ${r.carga} (${Math.round(r.ocupacao * 100)}%)</small></div>
      <div class="barra"><div style="width:${Math.min(100, r.ocupacao * 100)}%;background:${cor}"></div></div>
      <small>${r.paradas.join(" → ")}</small>
      ${tabelaParadas(r)}`;
    div.querySelector("h3").addEventListener("click", () => focarRota(i));
    lista.appendChild(div);
  });

  desenharPontos(corPorVertice, chegadas);

  const m = res.metricas;
  $("metricas").innerHTML = [
    [m.distancia_total + " km", "Distância total"],
    [m.tempo_total + " min", "Tempo total"],
    [m.veiculos_usados, "Veículos usados"],
    [m.atrasos, "Entregas atrasadas"],
    [res.tempo_execucao_ms + " ms", "Tempo de execução"],
  ].map(([valor, nome]) => `<div class="metrica"><b>${valor}</b><span>${nome}</span></div>`).join("");

  const na = res.nao_atendidos || [];
  $("nao-atendidos").hidden = na.length === 0;
  $("nao-atendidos").textContent = `Frota insuficiente: ${na.length} cliente(s) sem atendimento (${na.join(", ")}).`;
  $("sec-metricas").hidden = false;
}

// ---------------------------------------------------------------- ações

function lerConfig() {
  return {
    veiculos: Number($("veiculos").value),
    capacidade: Number($("capacidade").value),
    algoritmo: $("algoritmo").value,
    usar_2opt: $("usar2opt").checked,
  };
}

async function comBotoesTravados(fn) {
  const botoes = document.querySelectorAll("button");
  botoes.forEach((b) => (b.disabled = true));
  mostrarErro("");
  try { await fn(); }
  catch (e) { mostrarErro(e.message); }
  finally { botoes.forEach((b) => (b.disabled = false)); }
}

async function calcular(ev) {
  ev.preventDefault();
  await comBotoesTravados(async () => {
    const config = lerConfig();
    const resultado = await api("/api/rotas", config);
    ultimoResultado = { config, resultado };
    desenharResultado(resultado);
  });
}

function graficoComparacao(linhas) {
  const maior = Math.max(...linhas.map((l) => l.distancia_total)) || 1;
  const melhor = Math.min(...linhas.map((l) => l.distancia_total));
  $("grafico-comparacao").innerHTML = linhas.map((l) => `
    <div class="linha ${l.distancia_total === melhor ? "melhor" : ""}">
      <span>${l.nome}</span>
      <div class="trilho"><div class="valor" style="width:${(l.distancia_total / maior) * 100}%">${l.distancia_total}</div></div>
    </div>`).join("");
}

async function comparar() {
  await comBotoesTravados(async () => {
    const base = lerConfig();
    const linhas = [];
    for (const [chave, nome] of Object.entries(algoritmos)) {
      for (const opt of [false, true]) {
        const res = await api("/api/rotas", { ...base, algoritmo: chave, usar_2opt: opt });
        linhas.push({ nome: nome + (opt ? " + 2-opt" : ""), ...res.metricas, ms: res.tempo_execucao_ms });
      }
    }
    const melhor = Math.min(...linhas.map((l) => l.distancia_total));
    $("tabela-comparacao").innerHTML =
      "<tr><th>Configuração</th><th>km</th><th>min</th><th>Veíc.</th><th>Atrasos</th><th>ms</th></tr>" +
      linhas.map((l) => `<tr class="${l.distancia_total === melhor ? "melhor" : ""}">
        <td>${l.nome}</td><td>${l.distancia_total}</td><td>${l.tempo_total}</td>
        <td>${l.veiculos_usados}</td><td>${l.atrasos}</td><td>${l.ms}</td></tr>`).join("");
    graficoComparacao(linhas);
    $("sec-comparacao").hidden = false;
  });
}

function exportar() {
  if (!ultimoResultado) return;
  const blob = new Blob([JSON.stringify({ ...ultimoResultado, gerado_em: new Date().toISOString() }, null, 2)],
    { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `rotas_${ultimoResultado.config.algoritmo}${ultimoResultado.config.usar_2opt ? "_2opt" : ""}.json`;
  a.click();
  URL.revokeObjectURL(a.href);
}

async function iniciar() {
  try {
    [grafo, algoritmos] = await Promise.all([api("/api/grafo"), api("/api/algoritmos")]);
  } catch (e) {
    mostrarErro("Não foi possível carregar o grafo: " + e.message);
    return;
  }
  vertices = Object.fromEntries(grafo.vertices.map((v) => [v.id, v]));
  $("algoritmo").innerHTML = Object.entries(algoritmos)
    .map(([k, nome]) => `<option value="${k}">${nome}</option>`).join("");
  $("fonte").hidden = grafo.fonte !== "mock";

  mostrarResumo();
  desenharArestas();
  desenharPontos();
  mapa.fitBounds(L.latLngBounds(grafo.vertices.map((v) => [v.lat, v.lon])).pad(0.1));
}

$("form-config").addEventListener("submit", calcular);
$("btn-comparar").addEventListener("click", comparar);
$("btn-exportar").addEventListener("click", exportar);
$("veiculos").addEventListener("input", () => grafo && atualizarDica());
$("capacidade").addEventListener("input", () => grafo && atualizarDica());
$("mostrar-arestas").addEventListener("change", (e) => {
  if (e.target.checked) camadaArestas.addTo(mapa); else camadaArestas.remove();
});
mapa.on("click", limparFoco);
iniciar();
