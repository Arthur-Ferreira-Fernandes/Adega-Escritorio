from decimal import Decimal

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
        self.assertEqual(config.limite_sangria, Decimal("1000"))

    def test_obter_sempre_retorna_a_mesma_linha(self):
        primeira = Configuracao.obter()
        primeira.limite_sangria = Decimal("500.00")
        primeira.save()
        segunda = Configuracao.obter()
        self.assertEqual(segunda.pk, 1)
        self.assertEqual(segunda.limite_sangria, Decimal("500.00"))

    def test_save_forca_pk_1(self):
        config = Configuracao(limite_sangria=Decimal("800.00"))
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
                "limite_sangria": "500.00",
                "meta_faturamento_mensal": "R$ 60.000,00",
                "taxa_cartao": "2.5",
                "taxa_pix": "0.99",
                "dias_cobertura_compra": "10",
                "desconto_maximo_percentual": "15",
                "taxa_servico_percentual": "10",
                "couvert_por_pessoa": "R$ 8,00",
                "prazo_fiado_dias": "15",
                "formato_comprovante": "80mm",
                "impressora_gaveta": "",
                "salvar_configuracoes": "1",
            },
        )
        config = Configuracao.obter()
        self.assertEqual(config.limite_sangria, Decimal("500.00"))
        self.assertEqual(config.meta_faturamento_mensal, Decimal("60000.00"))
        self.assertEqual((config.taxa_cartao, config.taxa_pix), (Decimal("2.50"), Decimal("0.99")))
        self.assertEqual(config.dias_cobertura_compra, 10)
        self.assertEqual((config.taxa_servico_percentual, config.couvert_por_pessoa), (Decimal("10.00"), Decimal("8.00")))
        self.assertEqual((config.prazo_fiado_dias, config.formato_comprovante), (15, "80mm"))
