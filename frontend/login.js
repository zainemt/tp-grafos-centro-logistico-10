"use strict";

const $ = (id) => document.getElementById(id);

const form = $("form-login");
const campoEmail = $("email");
const campoSenha = $("senha");
const botaoOlho = $("btn-olho");
const campoManter = $("manter");
const botaoEntrar = $("btn-entrar");
const rotuloEntrar = botaoEntrar.querySelector(".rotulo");
const caixaErro = $("erro-login").querySelector(".erro");

function mostrarErro(mensagem) {
  caixaErro.querySelector("span").textContent = mensagem;
  caixaErro.hidden = false;
  // reinicia a animação de "tremer" quando o erro se repete
  caixaErro.style.animation = "none";
  void caixaErro.offsetWidth;
  caixaErro.style.animation = "";
}

function esconderErro() {
  caixaErro.hidden = true;
  caixaErro.querySelector("span").textContent = "";
}

function travar(travado) {
  botaoEntrar.disabled = travado;
  botaoEntrar.classList.toggle("carregando", travado);
  botaoEntrar.setAttribute("aria-busy", String(travado));
  rotuloEntrar.textContent = travado ? "Entrando..." : "Entrar";
}

botaoOlho.addEventListener("click", () => {
  const mostrar = campoSenha.type === "password";
  campoSenha.type = mostrar ? "text" : "password";
  botaoOlho.setAttribute("aria-pressed", String(mostrar));
  botaoOlho.setAttribute("aria-label", mostrar ? "Ocultar senha" : "Mostrar senha");
  campoSenha.focus();
});

form.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  if (botaoEntrar.disabled) return;
  esconderErro();

  const email = campoEmail.value.trim();
  const senha = campoSenha.value;
  if (!email) { mostrarErro("Informe o seu e-mail."); campoEmail.focus(); return; }
  if (!/^[^\s@]+@[^\s@]+$/.test(email)) { mostrarErro("Digite um e-mail válido."); campoEmail.focus(); return; }
  if (!senha) { mostrarErro("Informe a sua senha."); campoSenha.focus(); return; }

  travar(true);
  try {
    const resposta = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, senha, manter: campoManter.checked }),
    });
    const corpo = await resposta.json().catch(() => ({}));
    if (resposta.ok) {
      location.replace("/");
      return; // mantém o botão travado até a página trocar
    }
    mostrarErro(corpo.erro || `Erro ${resposta.status}`);
    if (resposta.status === 401) { campoSenha.select(); }
  } catch {
    mostrarErro("Não foi possível conectar ao servidor.");
  }
  travar(false);
});

[campoEmail, campoSenha].forEach((campo) => campo.addEventListener("input", esconderErro));

campoEmail.focus({ preventScroll: true });
