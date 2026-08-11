from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.clientes.models import Cliente, Fornecedor

from .models import ContaPagar, ContaReceber

User = get_user_model()


class ContaPagarViewTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(
            username="operador", password="senha123", is_staff=True
        )
        self.client.force_login(self.usuario)
        self.fornecedor = Fornecedor.objects.create(nome="Fornecedor Teste", documento="11111111000111")

    def test_criar_conta_a_pagar(self):
        resposta = self.client.post(
            reverse("financeiro:contas_pagar_nova"),
            {
                "fornecedor": self.fornecedor.pk,
                "descricao": "Compra de mercadoria",
                "valor": "150.00",
                "vencimento": "2026-12-01",
            },
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(ContaPagar.objects.filter(descricao="Compra de mercadoria").exists())

    def test_marcar_paga(self):
        conta = ContaPagar.objects.create(
            fornecedor=self.fornecedor,
            descricao="Compra",
            valor=Decimal("100.00"),
            vencimento="2026-01-01",
        )
        self.client.post(reverse("financeiro:contas_pagar_marcar_paga", args=[conta.pk]))
        conta.refresh_from_db()
        self.assertTrue(conta.pago)
        self.assertIsNotNone(conta.pago_em)

    def test_excluir_conta_a_pagar(self):
        conta = ContaPagar.objects.create(
            fornecedor=self.fornecedor,
            descricao="Compra",
            valor=Decimal("100.00"),
            vencimento="2026-01-01",
        )
        self.client.post(reverse("financeiro:contas_pagar_excluir", args=[conta.pk]))
        self.assertFalse(ContaPagar.objects.filter(pk=conta.pk).exists())


class ContaReceberViewTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(
            username="operador", password="senha123", is_staff=True
        )
        self.client.force_login(self.usuario)
        self.cliente = Cliente.objects.create(nome="Cliente Teste", documento="22222222222")

    def test_criar_conta_a_receber(self):
        resposta = self.client.post(
            reverse("financeiro:contas_receber_nova"),
            {
                "cliente": self.cliente.pk,
                "descricao": "Fiado",
                "valor": "80.00",
                "vencimento": "2026-12-01",
            },
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(ContaReceber.objects.filter(descricao="Fiado").exists())

    def test_marcar_recebida(self):
        conta = ContaReceber.objects.create(
            cliente=self.cliente,
            descricao="Fiado",
            valor=Decimal("80.00"),
            vencimento="2026-01-01",
        )
        self.client.post(reverse("financeiro:contas_receber_marcar_recebida", args=[conta.pk]))
        conta.refresh_from_db()
        self.assertTrue(conta.recebido)
        self.assertIsNotNone(conta.recebido_em)

    def test_excluir_conta_a_receber(self):
        conta = ContaReceber.objects.create(
            cliente=self.cliente,
            descricao="Fiado",
            valor=Decimal("80.00"),
            vencimento="2026-01-01",
        )
        self.client.post(reverse("financeiro:contas_receber_excluir", args=[conta.pk]))
        self.assertFalse(ContaReceber.objects.filter(pk=conta.pk).exists())
