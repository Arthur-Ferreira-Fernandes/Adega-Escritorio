from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

User = get_user_model()


class UsuariosAcessoTests(TestCase):
    def setUp(self):
        self.superusuario = User.objects.create_user(
            username="admin_teste", password="senha123", is_staff=True, is_superuser=True
        )
        self.staff = User.objects.create_user(
            username="staff_teste", password="senha123", is_staff=True
        )

    def test_lista_bloqueada_para_nao_superusuario(self):
        self.client.force_login(self.staff)
        resposta = self.client.get(reverse("usuarios:lista"))
        self.assertNotEqual(resposta.status_code, 200)

    def test_novo_bloqueado_para_nao_superusuario(self):
        self.client.force_login(self.staff)
        resposta = self.client.post(
            reverse("usuarios:novo"),
            {
                "username": "novo_usuario",
                "first_name": "Novo",
                "password1": "SenhaForte123",
                "password2": "SenhaForte123",
            },
        )
        self.assertNotEqual(resposta.status_code, 200)
        self.assertFalse(User.objects.filter(username="novo_usuario").exists())

    def test_novo_cria_usuario_para_superusuario(self):
        self.client.force_login(self.superusuario)
        self.client.post(
            reverse("usuarios:novo"),
            {
                "username": "novo_usuario",
                "first_name": "Novo",
                "password1": "SenhaForte123",
                "password2": "SenhaForte123",
            },
        )
        self.assertTrue(User.objects.filter(username="novo_usuario").exists())

    def test_resetar_senha_bloqueado_para_nao_superusuario(self):
        alvo = User.objects.create_user(username="alvo", password="senhaantiga")
        self.client.force_login(self.staff)
        resposta = self.client.post(
            reverse("usuarios:resetar_senha", args=[alvo.pk]),
            {"password1": "SenhaNova123", "password2": "SenhaNova123"},
        )
        self.assertNotEqual(resposta.status_code, 200)
        alvo.refresh_from_db()
        self.assertTrue(alvo.check_password("senhaantiga"))

    def test_resetar_senha_funciona_para_superusuario(self):
        alvo = User.objects.create_user(username="alvo", password="senhaantiga")
        self.client.force_login(self.superusuario)
        self.client.post(
            reverse("usuarios:resetar_senha", args=[alvo.pk]),
            {"password1": "SenhaNova123", "password2": "SenhaNova123"},
        )
        alvo.refresh_from_db()
        self.assertTrue(alvo.check_password("SenhaNova123"))

    def test_nao_pode_autodesativar(self):
        self.client.force_login(self.superusuario)
        self.client.post(reverse("usuarios:alternar_ativo", args=[self.superusuario.pk]))
        self.superusuario.refresh_from_db()
        self.assertTrue(self.superusuario.is_active)

    def test_alternar_ativo_desativa_outro_usuario(self):
        alvo = User.objects.create_user(username="alvo", password="senha123")
        self.client.force_login(self.superusuario)
        self.client.post(reverse("usuarios:alternar_ativo", args=[alvo.pk]))
        alvo.refresh_from_db()
        self.assertFalse(alvo.is_active)


class MinhaContaViewTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(
            username="usuario_teste", password="senha123", first_name="Nome Antigo"
        )
        self.outro = User.objects.create_user(username="outro_usuario", password="senha123")
        self.client.force_login(self.usuario)

    def test_troca_nome_e_login_mantem_sessao(self):
        resposta = self.client.post(
            reverse("usuarios:minha_conta"),
            {
                "first_name": "Nome Novo",
                "username": "usuario_novo",
                "salvar_dados": "1",
            },
        )
        self.assertEqual(resposta.status_code, 302)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.first_name, "Nome Novo")
        self.assertEqual(self.usuario.username, "usuario_novo")
        resposta_seguinte = self.client.get(reverse("usuarios:minha_conta"))
        self.assertEqual(resposta_seguinte.status_code, 200)

    def test_login_duplicado_e_rejeitado(self):
        self.client.post(
            reverse("usuarios:minha_conta"),
            {
                "first_name": "Nome Novo",
                "username": "outro_usuario",
                "salvar_dados": "1",
            },
        )
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.username, "usuario_teste")

    def test_troca_senha_mantem_sessao(self):
        resposta = self.client.post(
            reverse("usuarios:minha_conta"),
            {
                "old_password": "senha123",
                "new_password1": "SenhaNova456",
                "new_password2": "SenhaNova456",
                "salvar_senha": "1",
            },
        )
        self.assertEqual(resposta.status_code, 302)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("SenhaNova456"))
        resposta_seguinte = self.client.get(reverse("usuarios:minha_conta"))
        self.assertEqual(resposta_seguinte.status_code, 200)


@override_settings(PRIMEIRO_ACESSO_PELA_TELA=True)
class PrimeiroAcessoTests(TestCase):
    dados = {
        "username": "dono",
        "first_name": "Dono",
        "password1": "SenhaForte123",
        "password2": "SenhaForte123",
    }

    def test_cria_administrador_e_ja_entra(self):
        resposta = self.client.post(reverse("usuarios:primeiro_acesso"), self.dados)
        self.assertRedirects(resposta, reverse("inicio"), fetch_redirect_response=False)
        dono = User.objects.get(username="dono")
        self.assertTrue(dono.is_superuser and dono.is_staff)
        self.assertEqual(int(self.client.session["_auth_user_id"]), dono.pk)

    def test_some_quando_ja_existe_administrador(self):
        User.objects.create_user(username="admin", password="x", is_superuser=True)
        resposta = self.client.post(reverse("usuarios:primeiro_acesso"), self.dados)
        self.assertEqual(resposta.status_code, 404)
        self.assertFalse(User.objects.filter(username="dono").exists())

    def test_bloqueado_para_outro_aparelho_da_rede(self):
        resposta = self.client.post(
            reverse("usuarios:primeiro_acesso"), self.dados, REMOTE_ADDR="192.168.0.20"
        )
        self.assertEqual(resposta.status_code, 404)
        self.assertFalse(User.objects.exists())

    @override_settings(PRIMEIRO_ACESSO_PELA_TELA=False)
    def test_desligado_fora_da_versao_desktop(self):
        resposta = self.client.get(reverse("usuarios:primeiro_acesso"))
        self.assertEqual(resposta.status_code, 404)
