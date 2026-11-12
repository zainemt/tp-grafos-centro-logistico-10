"""Autenticação do RotaGrafo: login por sessão (cookie assinado) e proteção das rotas.

Os usuários ficam em dados/usuarios.json, só com o hash da senha. Para criar um usuário:
    python -m src.api.auth criar <email> <nome>
"""
import getpass
import json
import os
import secrets
import sys
import threading
import time
from datetime import timedelta
from typing import Callable

from flask import Blueprint, Flask, current_app, jsonify, redirect, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
USUARIOS_PADRAO = os.path.join(RAIZ, "dados", "usuarios.json")

MAX_FALHAS = 5
JANELA_BLOQUEIO_S = 900
DURACAO_SESSAO_PERMANENTE = timedelta(days=30)
MAX_EMAIL = 254
MAX_SENHA = 128

MSG_INVALIDO = "E-mail ou senha inválidos."
MSG_BLOQUEADO = "Muitas tentativas. Tente novamente em alguns minutos."
MSG_SEM_SESSAO = "Sessão expirada. Entre novamente."

# Caminhos que não exigem sessão (a tela de login e o que ela precisa para abrir).
LIBERADOS = {"/login", "/api/auth/login", "/login.css", "/login.js", "/logo.svg", "/favicon.ico"}

# Hash fictício: a verificação roda mesmo para e-mails inexistentes, para o tempo de
# resposta não revelar quais e-mails existem.
_HASH_FALSO = generate_password_hash("senha-ficticia-sem-uso")

bp = Blueprint("auth", __name__)


class LimitadorTentativas:
    """Bloqueia uma chave depois de `maximo` falhas; o bloqueio dura `janela_s` desde a última falha."""

    def __init__(self, maximo: int = MAX_FALHAS, janela_s: int = JANELA_BLOQUEIO_S,
                 relogio: Callable[[], float] = time.monotonic):
        self.maximo = maximo
        self.janela_s = janela_s
        self.relogio = relogio
        self._falhas: dict[str, tuple[int, float]] = {}
        self._trava = threading.Lock()  # o servidor do Flask atende requisições em threads

    def _contagem_valida(self, chave: str) -> int:
        contagem, ultima = self._falhas.get(chave, (0, 0.0))
        if contagem and self.relogio() - ultima >= self.janela_s:
            self._falhas.pop(chave, None)
            return 0
        return contagem

    def _descartar_expiradas(self) -> None:
        agora = self.relogio()
        for chave, (_, ultima) in list(self._falhas.items()):
            if agora - ultima >= self.janela_s:
                self._falhas.pop(chave, None)

    def bloqueado(self, chave: str) -> bool:
        with self._trava:
            return self._contagem_valida(chave) >= self.maximo

    def registrar_falha(self, chave: str) -> None:
        with self._trava:
            self._descartar_expiradas()
            self._falhas[chave] = (self._contagem_valida(chave) + 1, self.relogio())

    def zerar(self, chave: str) -> None:
        with self._trava:
            self._falhas.pop(chave, None)


class EstadoAuth:
    def __init__(self, usuarios: dict, limitador: LimitadorTentativas):
        self.usuarios = usuarios
        self.limitador = limitador


def carregar_usuarios(caminho: str) -> dict[str, dict]:
    """Lê o arquivo de usuários. Ausente = nenhum usuário; inválido = ValueError citando o caminho."""
    if not os.path.exists(caminho):
        return {}
    try:
        with open(caminho, encoding="utf-8-sig") as f:  # aceita o BOM que o Bloco de Notas grava
            bruto = json.load(f)
    except (OSError, ValueError) as erro:
        raise ValueError(f"Arquivo de usuários inválido ({caminho}): {erro}") from erro
    if not isinstance(bruto, dict) or not all(
        isinstance(v, dict) and isinstance(v.get("nome"), str) and isinstance(v.get("hash"), str)
        for v in bruto.values()
    ):
        raise ValueError(f"Arquivo de usuários inválido ({caminho}): esperado {{email: {{nome, hash}}}}")
    for email, dados in bruto.items():
        try:
            check_password_hash(dados["hash"], "")  # hash malformado levanta ValueError
        except ValueError as erro:
            raise ValueError(f"Arquivo de usuários inválido ({caminho}): hash malformado para {email}") from erro
    return {email.strip().lower(): dados for email, dados in bruto.items()}


def verificar_credenciais(usuarios: dict, email: str, senha: str) -> dict | None:
    usuario = usuarios.get(email)
    ok = check_password_hash(usuario["hash"] if usuario else _HASH_FALSO, senha)
    return {"nome": usuario["nome"], "email": email} if usuario and ok else None


def _ler_credenciais() -> tuple[str, str, bool] | None:
    corpo = request.get_json(silent=True) if request.is_json else None
    if not isinstance(corpo, dict):
        return None
    email, senha = corpo.get("email"), corpo.get("senha")
    if not isinstance(email, str) or not isinstance(senha, str):
        return None
    email = email.strip().lower()
    if not email or len(email) > MAX_EMAIL or not senha or len(senha) > MAX_SENHA:
        return None
    try:  # surrogate solitário (ex.: "\ud83d") é JSON válido, mas não vira UTF-8
        email.encode("utf-8"), senha.encode("utf-8")
    except UnicodeEncodeError:
        return None
    return email, senha, bool(corpo.get("manter"))


def _estado() -> EstadoAuth:
    return current_app.extensions["rotagrafo_auth"]


def _usuario_da_sessao() -> dict | None:
    """Usuário da sessão atual, desde que ele ainda exista em usuarios.json; senão encerra a sessão."""
    email = session.get("email")
    usuario = _estado().usuarios.get(email) if email else None
    if email and usuario is None:
        session.clear()
    return usuario


@bp.get("/login")
def pagina_login():
    if _usuario_da_sessao():
        return redirect("/")
    return send_from_directory(current_app.static_folder, "login.html")


@bp.post("/api/auth/login")
def login():
    credenciais = _ler_credenciais()
    if credenciais is None:
        return jsonify({"erro": "Informe e-mail e senha válidos."}), 400
    email, senha, manter = credenciais
    estado = _estado()
    chave = f"{email}|{request.remote_addr}"
    if estado.limitador.bloqueado(chave):
        return jsonify({"erro": MSG_BLOQUEADO}), 429
    usuario = verificar_credenciais(estado.usuarios, email, senha)
    if usuario is None:
        estado.limitador.registrar_falha(chave)
        return jsonify({"erro": MSG_INVALIDO}), 401
    estado.limitador.zerar(chave)
    session.clear()
    session["email"] = usuario["email"]
    session.permanent = manter
    return jsonify({"usuario": usuario})


@bp.post("/api/auth/logout")
def logout():
    session.clear()
    return "", 204


@bp.get("/api/auth/me")
def me():
    usuario = _usuario_da_sessao()
    if usuario is None:
        return jsonify({"erro": MSG_SEM_SESSAO}), 401
    return jsonify({"nome": usuario["nome"], "email": session["email"]})


def _proteger():
    if request.path in LIBERADOS or _usuario_da_sessao():
        return None
    if request.path.startswith("/api/"):
        return jsonify({"erro": MSG_SEM_SESSAO}), 401
    return redirect("/login")


def registrar_auth(app: Flask, caminho_usuarios: str = USUARIOS_PADRAO) -> None:
    chave = os.environ.get("SECRET_KEY")
    if not chave:
        chave = secrets.token_hex(32)
        print("AVISO: SECRET_KEY não definida; usando chave aleatória (as sessões caem ao reiniciar).",
              file=sys.stderr)
    app.secret_key = chave
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE") == "1",
        PERMANENT_SESSION_LIFETIME=DURACAO_SESSAO_PERMANENTE,
    )
    app.extensions["rotagrafo_auth"] = EstadoAuth(carregar_usuarios(caminho_usuarios), LimitadorTentativas())
    app.register_blueprint(bp)
    app.before_request(_proteger)


def _criar_usuario(email: str, nome: str, caminho: str = USUARIOS_PADRAO) -> None:
    senha = getpass.getpass("Senha (mínimo 8 caracteres): ")
    if len(senha) < 8 or len(senha) > MAX_SENHA:
        sys.exit(f"A senha deve ter entre 8 e {MAX_SENHA} caracteres.")
    if senha != getpass.getpass("Repita a senha: "):
        sys.exit("As senhas não conferem.")
    usuarios = carregar_usuarios(caminho)
    usuarios[email.strip().lower()] = {"nome": nome, "hash": generate_password_hash(senha)}
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(usuarios, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Usuário {email.strip().lower()} gravado em {caminho}.")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "criar":
        _criar_usuario(sys.argv[2], sys.argv[3])
    else:
        sys.exit("Uso: python -m src.api.auth criar <email> <nome>")
