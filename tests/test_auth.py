"""Testes de autenticação: login, sessão, bloqueio por tentativas e proteção das rotas.

    python -m unittest discover tests -v
"""
import json
import os
import tempfile
import unittest

from flask import Flask
from werkzeug.security import generate_password_hash

from src.api import app as api
from src.api.auth import LimitadorTentativas, carregar_usuarios, registrar_auth

EMAIL = "demo@rotagrafo.com"
SENHA = "senha-teste-123"
HASH = generate_password_hash(SENHA)


class BaseAuth(unittest.TestCase):
    def setUp(self):
        self.agora = 1000.0
        self.client = api.app.test_client()
        self.estado = api.app.extensions["rotagrafo_auth"]
        campos = ("usuarios", "limitador", "limitador_cadastro", "caminho_local")
        original = {c: getattr(self.estado, c) for c in campos}
        self.addCleanup(lambda: [setattr(self.estado, c, v) for c, v in original.items()])
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.caminho_local = os.path.join(pasta.name, "usuarios.local.json")
        self.estado.usuarios = {EMAIL: {"nome": "Demo", "hash": HASH}}
        self.estado.limitador = LimitadorTentativas(relogio=lambda: self.agora)
        self.estado.limitador_cadastro = LimitadorTentativas(maximo=10, janela_s=3600, relogio=lambda: self.agora)
        self.estado.caminho_local = self.caminho_local

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


class TestCadastro(BaseAuth):
    def cadastrar(self, nome="Ana Souza", email="ana@teste.com", senha="senha-da-ana-1", cliente=None):
        return (cliente or self.client).post(
            "/api/auth/registrar", json={"nome": nome, "email": email, "senha": senha})

    def test_cadastro_cria_conta_e_ja_entra(self):
        resp = self.cadastrar()
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.get_json(), {"usuario": {"nome": "Ana Souza", "email": "ana@teste.com"}})
        self.assertEqual(self.client.get("/api/auth/me").get_json()["nome"], "Ana Souza")
        self.client.post("/api/auth/logout")
        self.assertEqual(self.entrar("ana@teste.com", "senha-da-ana-1").status_code, 200)

    def test_cadastro_grava_so_o_hash_no_arquivo_local(self):
        self.cadastrar()
        with open(self.caminho_local, encoding="utf-8") as f:
            texto = f.read()
        self.assertNotIn("senha-da-ana-1", texto)
        self.assertIn("ana@teste.com", carregar_usuarios(self.caminho_local))

    def test_cadastro_normaliza_nome_e_email(self):
        resp = self.cadastrar(nome="  Ana   Souza ", email=" ANA@Teste.COM ")
        self.assertEqual(resp.get_json()["usuario"], {"nome": "Ana Souza", "email": "ana@teste.com"})

    def test_email_repetido_devolve_409(self):
        for email in (EMAIL, "  DEMO@rotagrafo.com"):
            with self.subTest(email=email):
                resp = self.cadastrar(email=email)
                self.assertEqual(resp.status_code, 409)
                self.assertEqual(resp.get_json()["campo"], "email")
        self.assertEqual(self.cadastrar().status_code, 201)
        self.assertEqual(self.cadastrar(cliente=api.app.test_client()).status_code, 409)

    def test_entradas_invalidas_devolvem_400_com_o_campo(self):
        casos = [("nome", {"nome": "", "email": "a@b.co", "senha": "12345678"}),
                 ("nome", {"nome": "A", "email": "a@b.co", "senha": "12345678"}),
                 ("nome", {"nome": "x" * 81, "email": "a@b.co", "senha": "12345678"}),
                 ("nome", {"nome": "Ana\nSouza", "email": "a@b.co", "senha": "12345678"}),
                 ("email", {"nome": "Ana", "email": "semarroba", "senha": "12345678"}),
                 ("email", {"nome": "Ana", "email": "a@b", "senha": "12345678"}),
                 ("email", {"nome": "Ana", "email": "a" * 250 + "@b.com", "senha": "12345678"}),
                 ("senha", {"nome": "Ana", "email": "a@b.co", "senha": "1234567"}),
                 ("senha", {"nome": "Ana", "email": "a@b.co", "senha": "x" * 129}),
                 ("senha", {"nome": "Ana", "email": "a@b.co", "senha": "\ud83d1234567"})]
        for campo, corpo in casos:
            with self.subTest(campo=campo, corpo=str(corpo)[:40]):
                resp = self.client.post("/api/auth/registrar", json=corpo)
                self.assertEqual(resp.status_code, 400)
                self.assertEqual(resp.get_json()["campo"], campo)
                self.assertTrue(resp.get_json()["erro"])

    def test_corpo_malformado_devolve_400(self):
        for corpo in ([], "texto", None, {}, {"nome": 1, "email": 2, "senha": 3}):
            with self.subTest(corpo=str(corpo)):
                self.assertEqual(self.client.post("/api/auth/registrar", json=corpo).status_code, 400)
        self.assertEqual(self.client.post("/api/auth/registrar", data="nome=a").status_code, 400)

    def test_limite_de_cadastros_por_ip(self):
        for i in range(10):
            self.assertEqual(self.cadastrar(email=f"pessoa{i}@teste.com",
                                            cliente=api.app.test_client()).status_code, 201)
        self.assertEqual(self.cadastrar(email="onze@teste.com", cliente=api.app.test_client()).status_code, 429)
        self.agora += 3601
        self.assertEqual(self.cadastrar(email="onze@teste.com", cliente=api.app.test_client()).status_code, 201)

    def test_falha_ao_gravar_nao_cria_a_conta(self):
        self.estado.caminho_local = os.path.join(os.path.dirname(self.caminho_local), "nao", "existe", "u.json")
        resp = self.cadastrar()
        self.assertEqual(resp.status_code, 500)
        self.assertTrue(resp.get_json()["erro"])
        self.assertNotIn("ana@teste.com", self.estado.usuarios)

    def test_pagina_de_cadastro(self):
        resp = self.client.get("/registrar")
        self.assertEqual(resp.status_code, 200)
        resp.close()
        for caminho in ("/registrar.js", "/login.css"):
            with self.subTest(caminho=caminho):
                resp = self.client.get(caminho)
                self.assertEqual(resp.status_code, 200)
                resp.close()
        self.entrar()
        resp = self.client.get("/registrar")
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.headers["Location"].endswith("/"))

    def test_registrar_auth_carrega_usuarios_do_arquivo_local(self):
        with tempfile.TemporaryDirectory() as pasta:
            base = os.path.join(pasta, "usuarios.json")
            local = os.path.join(pasta, "usuarios.local.json")
            for caminho, email in ((base, "base@teste.com"), (local, "local@teste.com")):
                with open(caminho, "w", encoding="utf-8") as f:
                    json.dump({email: {"nome": "X", "hash": HASH}}, f)
            app = Flask("teste")
            registrar_auth(app, base)
            usuarios = app.extensions["rotagrafo_auth"].usuarios
            self.assertEqual(set(usuarios), {"base@teste.com", "local@teste.com"})
            self.assertEqual(app.extensions["rotagrafo_auth"].caminho_local, local)


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
