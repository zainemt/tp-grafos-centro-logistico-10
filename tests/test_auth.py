"""Testes de autenticação: login, sessão, bloqueio por tentativas e proteção das rotas.

    python -m unittest discover tests -v
"""
import json
import os
import tempfile
import unittest

from werkzeug.security import generate_password_hash

from src.api import app as api
from src.api.auth import LimitadorTentativas, carregar_usuarios

EMAIL = "demo@rotagrafo.com"
SENHA = "senha-teste-123"
HASH = generate_password_hash(SENHA)


class BaseAuth(unittest.TestCase):
    def setUp(self):
        self.agora = 1000.0
        self.client = api.app.test_client()
        self.estado = api.app.extensions["rotagrafo_auth"]
        original = (self.estado.usuarios, self.estado.limitador)
        self.addCleanup(lambda: (setattr(self.estado, "usuarios", original[0]),
                                 setattr(self.estado, "limitador", original[1])))
        self.estado.usuarios = {EMAIL: {"nome": "Demo", "hash": HASH}}
        self.estado.limitador = LimitadorTentativas(relogio=lambda: self.agora)

    def entrar(self, email=EMAIL, senha=SENHA, manter=False):
        return self.client.post("/api/auth/login", json={"email": email, "senha": senha, "manter": manter})


class TestLogin(BaseAuth):
    def test_login_correto(self):
        resp = self.entrar()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), {"usuario": {"nome": "Demo", "email": EMAIL}})
        me = self.client.get("/api/auth/me")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.get_json()["nome"], "Demo")

    def test_email_com_maiusculas_e_espacos(self):
        self.assertEqual(self.entrar("  Demo@RotaGrafo.COM ").status_code, 200)

    def test_senha_errada_e_email_inexistente_mesma_mensagem(self):
        for email, senha in [(EMAIL, "errada"), ("naoexiste@x.com", SENHA)]:
            with self.subTest(email=email):
                resp = self.entrar(email, senha)
                self.assertEqual(resp.status_code, 401)
                self.assertEqual(resp.get_json()["erro"], "E-mail ou senha inválidos.")

    def test_corpo_invalido_devolve_400(self):
        corpos = [[], "texto", None, {}, {"email": None, "senha": "x"},
                  {"email": "a@b.c", "senha": 123}, {"email": EMAIL, "senha": "x" * 129},
                  {"email": "a" * 250 + "@b.com", "senha": "x"},
                  {"email": "a@b.c", "senha": "\ud83d"}]  # surrogate solitário não é UTF-8 válido
        for corpo in corpos:
            with self.subTest(corpo=str(corpo)[:30]):
                resp = self.client.post("/api/auth/login", json=corpo)
                self.assertEqual(resp.status_code, 400)
                self.assertIn("erro", resp.get_json())

    def test_sem_content_type_json_devolve_400(self):
        resp = self.client.post("/api/auth/login", data="email=a&senha=b")
        self.assertEqual(resp.status_code, 400)

    def test_manter_conectado_define_cookie_permanente(self):
        com = self.entrar(manter=True).headers.get("Set-Cookie")
        self.assertIn("Expires=", com)
        self.assertIn("HttpOnly", com)
        self.assertIn("SameSite=Lax", com)
        outro = api.app.test_client()
        sem = outro.post("/api/auth/login", json={"email": EMAIL, "senha": SENHA}).headers.get("Set-Cookie")
        self.assertNotIn("Expires=", sem)
        self.assertIn("HttpOnly", sem)

    def test_logout_encerra_sessao(self):
        self.entrar()
        self.assertEqual(self.client.post("/api/auth/logout").status_code, 204)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)


class TestBloqueio(BaseAuth):
    def test_cinco_falhas_bloqueiam(self):
        for _ in range(5):
            self.assertEqual(self.entrar(senha="errada").status_code, 401)
        self.assertEqual(self.entrar().status_code, 429)
        self.agora += 901
        self.assertEqual(self.entrar().status_code, 200)

    def test_sucesso_zera_contador(self):
        for _ in range(2):
            for _ in range(4):
                self.entrar(senha="errada")
            self.assertEqual(self.entrar().status_code, 200)
            self.client.post("/api/auth/logout")

    def test_limitador_isolado(self):
        t = [0.0]
        lim = LimitadorTentativas(relogio=lambda: t[0])
        for _ in range(4):
            lim.registrar_falha("k")
        self.assertFalse(lim.bloqueado("k"))
        lim.registrar_falha("k")
        self.assertTrue(lim.bloqueado("k"))
        self.assertFalse(lim.bloqueado("outra"))
        t[0] = 901
        self.assertFalse(lim.bloqueado("k"))
        for _ in range(5):
            lim.registrar_falha("k")
        lim.zerar("k")
        self.assertFalse(lim.bloqueado("k"))

    def test_limitador_descarta_entradas_expiradas(self):
        t = [0.0]
        lim = LimitadorTentativas(relogio=lambda: t[0])
        for chave in ("a", "b", "c"):
            lim.registrar_falha(chave)
        t[0] = 901
        lim.registrar_falha("d")
        self.assertEqual(set(lim._falhas), {"d"})


class TestProtecao(BaseAuth):
    def test_api_sem_sessao_devolve_401(self):
        resp = self.client.get("/api/grafo")
        self.assertEqual(resp.status_code, 401)
        self.assertIn("erro", resp.get_json())
        self.entrar()
        self.assertEqual(self.client.get("/api/grafo").status_code, 200)

    def test_pagina_sem_sessao_redireciona(self):
        for caminho in ["/", "/index.html", "/app.js", "/style.css"]:
            with self.subTest(caminho=caminho):
                resp = self.client.get(caminho)
                self.assertEqual(resp.status_code, 302)
                self.assertTrue(resp.headers["Location"].endswith("/login"))
        self.entrar()
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_login_com_sessao_redireciona_para_raiz(self):
        self.assertEqual(self.client.get("/login").status_code, 200)
        self.entrar()
        resp = self.client.get("/login")
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.headers["Location"].endswith("/"))

    def test_estaticos_do_login_liberados(self):
        for caminho in ["/login.css", "/login.js", "/logo.svg"]:
            with self.subTest(caminho=caminho):
                resp = self.client.get(caminho)
                self.assertEqual(resp.status_code, 200)
                resp.close()

    def test_head_e_options_tambem_sao_protegidos(self):
        for caminho in ["/", "/app.js", "/api/grafo"]:
            for metodo in ("head", "options"):
                with self.subTest(caminho=caminho, metodo=metodo):
                    resp = getattr(self.client, metodo)(caminho)
                    self.assertIn(resp.status_code, (302, 401))

    def test_usuario_removido_perde_o_acesso(self):
        self.entrar()
        self.assertEqual(self.client.get("/api/grafo").status_code, 200)
        self.estado.usuarios = {}
        self.assertEqual(self.client.get("/api/grafo").status_code, 401)
        self.assertEqual(self.client.get("/").status_code, 302)

    def test_sem_usuarios_cadastrados_todo_login_falha(self):
        self.estado.usuarios = {}
        self.assertEqual(self.entrar().status_code, 401)


class TestUsuarios(unittest.TestCase):
    def test_carregar_usuarios_arquivo_ausente_e_invalido(self):
        with tempfile.TemporaryDirectory() as pasta:
            ausente = os.path.join(pasta, "nao-existe.json")
            self.assertEqual(carregar_usuarios(ausente), {})
            quebrado = os.path.join(pasta, "usuarios.json")
            with open(quebrado, "w", encoding="utf-8") as f:
                f.write("{quebrado")
            with self.assertRaises(ValueError) as ctx:
                carregar_usuarios(quebrado)
            self.assertIn(quebrado, str(ctx.exception))

    def test_hash_malformado_falha_ao_carregar(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = os.path.join(pasta, "usuarios.json")
            with open(caminho, "w", encoding="utf-8") as f:
                json.dump({"ana@teste.com": {"nome": "Ana", "hash": "foo$bar$baz"}}, f)
            with self.assertRaises(ValueError) as ctx:
                carregar_usuarios(caminho)
            self.assertIn("ana@teste.com", str(ctx.exception))

    def test_arquivo_com_bom_do_bloco_de_notas_carrega(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = os.path.join(pasta, "usuarios.json")
            with open(caminho, "w", encoding="utf-8-sig") as f:
                json.dump({"ana@teste.com": {"nome": "Ana", "hash": HASH}}, f)
            self.assertIn("ana@teste.com", carregar_usuarios(caminho))

    def test_carregar_usuarios_normaliza_email(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = os.path.join(pasta, "usuarios.json")
            with open(caminho, "w", encoding="utf-8") as f:
                json.dump({"Ana@Teste.com": {"nome": "Ana", "hash": HASH}}, f)
            self.assertIn("ana@teste.com", carregar_usuarios(caminho))


if __name__ == "__main__":
    unittest.main()
