from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Cliente, Fornecedor

User = get_user_model()


class ClienteViewTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(
            username="operador", password="senha123", is_staff=True
        )
        self.client.force_login(self.usuario)

    def test_criar_cliente(self):
        resposta = self.client.post(
            reverse("clientes:clientes_novo"),
            {"nome": "Cliente Teste", "documento": "11111111111"},
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(Cliente.objects.filter(documento="11111111111").exists())

    def test_editar_cliente(self):
        cliente = Cliente.objects.create(nome="Cliente Antigo", documento="22222222222")
        self.client.post(
            reverse("clientes:clientes_editar", args=[cliente.pk]),
            {"nome": "Cliente Novo", "documento": "22222222222"},
        )
        cliente.refresh_from_db()
        self.assertEqual(cliente.nome, "Cliente Novo")

    def test_excluir_cliente_sem_referencia(self):
        cliente = Cliente.objects.create(nome="Cliente Teste", documento="33333333333")
        self.client.post(reverse("clientes:clientes_excluir", args=[cliente.pk]))
        self.assertFalse(Cliente.objects.filter(pk=cliente.pk).exists())

    def test_excluir_cliente_com_conta_a_receber_e_bloqueado(self):
        from apps.financeiro.models import ContaReceber

        cliente = Cliente.objects.create(nome="Cliente Teste", documento="44444444444")
        ContaReceber.objects.create(
            cliente=cliente,
            descricao="Fiado",
            valor=Decimal("50.00"),
            vencimento="2026-01-01",
        )
        self.client.post(reverse("clientes:clientes_excluir", args=[cliente.pk]))
        self.assertTrue(Cliente.objects.filter(pk=cliente.pk).exists())


class FornecedorViewTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(
            username="operador", password="senha123", is_staff=True
        )
        self.client.force_login(self.usuario)

    def test_criar_fornecedor(self):
        resposta = self.client.post(
            reverse("clientes:fornecedores_novo"),
            {"nome": "Fornecedor Teste", "documento": "55555555000155"},
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(Fornecedor.objects.filter(documento="55555555000155").exists())

    def test_excluir_fornecedor_com_entrada_de_estoque_e_bloqueado(self):
        from apps.estoque.models import Categoria, EntradaEstoque, Produto

        fornecedor = Fornecedor.objects.create(nome="Fornecedor Teste", documento="66666666000166")
        categoria = Categoria.objects.create(nome="Vinhos")
        produto = Produto.objects.create(
            nome="Malbec",
            sku="MLB-001",
            categoria=categoria,
            preco_custo=Decimal("10.00"),
            preco_venda=Decimal("30.00"),
        )
        EntradaEstoque.objects.create(
            produto=produto,
            fornecedor=fornecedor,
            quantidade=1,
            custo_unitario=Decimal("10.00"),
            criado_por=self.usuario,
        )
        self.client.post(reverse("clientes:fornecedores_excluir", args=[fornecedor.pk]))
        self.assertTrue(Fornecedor.objects.filter(pk=fornecedor.pk).exists())
