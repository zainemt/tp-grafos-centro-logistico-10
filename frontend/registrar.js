"use strict";

const $ = (id) => document.getElementById(id);

const form = $("form-registro");
const botaoCriar = $("btn-criar");
const rotuloCriar = botaoCriar.querySelector(".rotulo");
const caixaErro = $("erro-registro").querySelector(".erro");
const dicaSenha = $("dica-senha");

const EMAIL_VALIDO = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MIN_SENHA = 8;
const CAMPOS = ["nome", "email", "senha", "confirmar"];

function limparErroCampo(campo) {
  const aviso = $(`erro-${campo}`);
  aviso.hidden = true;
  aviso.textContent = "";
  $(campo).removeAttribute("aria-invalid");
  $(campo).closest(".vidro").classList.remove("invalido");
}

function mostrarErroCampo(campo, mensagem) {
  const aviso = $(`erro-${campo}`);
  aviso.textContent = mensagem;
  aviso.hidden = false;
  $(campo).setAttribute("aria-invalid", "true");
  $(campo).closest(".vidro").classList.add("invalido");
}

function mostrarErroGeral(mensagem) {
  caixaErro.querySelector("span").textContent = mensagem;
  caixaErro.hidden = false;
  caixaErro.style.animation = "none";
  void caixaErro.offsetWidth; // reinicia a animação quando o erro se repete
  caixaErro.style.animation = "";
}

function limparTudo() {
  CAMPOS.forEach(limparErroCampo);
  caixaErro.hidden = true;
  caixaErro.querySelector("span").textContent = "";
}

function travar(travado) {
  botaoCriar.disabled = travado;
  botaoCriar.classList.toggle("carregando", travado);
  botaoCriar.setAttribute("aria-busy", String(travado));
  rotuloCriar.textContent = travado ? "Criando conta..." : "Criar conta";
}

// Primeiro campo com problema, ou null. Mesmas regras do servidor (que é quem decide de verdade).
function validar(v) {
  if (v.nome.length < 2) return ["nome", "Informe seu nome, com pelo menos 2 caracteres."];
  if (!EMAIL_VALIDO.test(v.email)) return ["email", "Digite um e-mail válido."];
  if (v.senha.length < MIN_SENHA) return ["senha", `A senha precisa de pelo menos ${MIN_SENHA} caracteres.`];
  if (v.confirmar !== v.senha) return ["confirmar", "As senhas não são iguais."];
  return null;
}

// mostrar/ocultar senha (um botão por campo)
document.querySelectorAll(".olho").forEach((botao) => {
  botao.addEventListener("click", () => {
    const campo = $(botao.dataset.alvo);
    const mostrar = campo.type === "password";
    campo.type = mostrar ? "text" : "password";
    botao.setAttribute("aria-pressed", String(mostrar));
    botao.setAttribute("aria-label", mostrar ? "Ocultar senha" : "Mostrar senha");
    campo.focus();
  });
});

// dica de tamanho da senha: vira "ok" quando atinge o mínimo
$("senha").addEventListener("input", () => {
  const ok = $("senha").value.length >= MIN_SENHA;
  dicaSenha.classList.toggle("ok", ok);
  dicaSenha.querySelector("span").textContent = ok ? "Tamanho da senha adequado" : `Use pelo menos ${MIN_SENHA} caracteres`;
});

CAMPOS.forEach((campo) => $(campo).addEventListener("input", () => {
  limparErroCampo(campo);
  if (campo === "senha") limparErroCampo("confirmar");
  caixaErro.hidden = true;
}));

form.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  if (botaoCriar.disabled) return;
  limparTudo();

  const valores = {
    nome: $("nome").value.trim(),
    email: $("email").value.trim(),
    senha: $("senha").value,
    confirmar: $("confirmar").value,
  };
  const problema = validar(valores);
  if (problema) {
    mostrarErroCampo(problema[0], problema[1]);
    $(problema[0]).focus();
    return;
  }

  travar(true);
  try {
    const resposta = await fetch("/api/auth/registrar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nome: valores.nome, email: valores.email, senha: valores.senha }),
    });
    const corpo = await resposta.json().catch(() => ({}));
    if (resposta.ok) {
      location.replace("/");
      return; // mantém o botão travado até a página trocar
    }
    const mensagem = corpo.erro || `Erro ${resposta.status}`;
    if (corpo.campo && CAMPOS.includes(corpo.campo)) {
      mostrarErroCampo(corpo.campo, mensagem);
      $(corpo.campo).focus();
    } else {
      mostrarErroGeral(mensagem);
    }
  } catch {
    mostrarErroGeral("Não foi possível conectar ao servidor.");
  }
  travar(false);
});

$("nome").focus({ preventScroll: true });
