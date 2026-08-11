from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Configuracao

User = get_user_model()


class ConfiguracaoModelTests(TestCase):
    def test_obter_cria_configuracao_padrao(self):
        self.assertEqual(Configuracao.objects.count(), 0)
        config = Configuracao.obter()
        self.assertEqual(config.pk, 1)
        self.assertEqual(config.limite_horas_caixa, 12)

    def test_obter_sempre_retorna_a_mesma_linha(self):
        primeira = Configuracao.obter()
        primeira.limite_horas_caixa = 6
        primeira.save()
        segunda = Configuracao.obter()
        self.assertEqual(segunda.pk, 1)
        self.assertEqual(segunda.limite_horas_caixa, 6)

    def test_save_forca_pk_1(self):
        config = Configuracao(limite_horas_caixa=8)
        config.save()
        self.assertEqual(config.pk, 1)

    def test_delete_nao_remove_registro(self):
        config = Configuracao.obter()
        config.delete()
        self.assertEqual(Configuracao.objects.count(), 1)


class AdministracaoViewTests(TestCase):
    def setUp(self):
        self.superusuario = User.objects.create_user(
            username="admin_teste", password="senha123", is_staff=True, is_superuser=True
        )
        self.staff = User.objects.create_user(
            username="staff_teste", password="senha123", is_staff=True
        )

    def test_bloqueado_para_nao_superusuario(self):
        self.client.force_login(self.staff)
        resposta = self.client.get(reverse("configuracoes:administracao"))
        self.assertNotEqual(resposta.status_code, 200)

    def test_bloqueado_sem_login(self):
        resposta = self.client.get(reverse("configuracoes:administracao"))
        self.assertEqual(resposta.status_code, 302)

    def test_permitido_para_superusuario(self):
        self.client.force_login(self.superusuario)
        resposta = self.client.get(reverse("configuracoes:administracao"))
        self.assertEqual(resposta.status_code, 200)

    def test_salvar_configuracoes_atualiza_limite(self):
        self.client.force_login(self.superusuario)
        self.client.post(
            reverse("configuracoes:administracao"),
            {
                "limite_horas_caixa": "6",
                "limite_sangria": "500.00",
                "salvar_configuracoes": "1",
            },
        )
        config = Configuracao.obter()
        self.assertEqual(config.limite_horas_caixa, 6)
