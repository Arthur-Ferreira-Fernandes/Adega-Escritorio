from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.clientes.models import Fornecedor

from .models import Categoria, Produto

User = get_user_model()


class CategoriaModelTests(TestCase):
    def test_save_gera_slug_a_partir_do_nome(self):
        categoria = Categoria.objects.create(nome="Vinhos Tintos")
        self.assertEqual(categoria.slug, "vinhos-tintos")

    def test_save_gera_slug_unico_para_nomes_repetidos(self):
        primeira = Categoria.objects.create(nome="Vinhos")
        segunda = Categoria.objects.create(nome="Vinhos")
        self.assertEqual(primeira.slug, "vinhos")
        self.assertEqual(segunda.slug, "vinhos-2")


class ProdutoModelTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username="operador", password="senha123")
        self.categoria = Categoria.objects.create(nome="Vinhos")
        self.fornecedor = Fornecedor.objects.create(nome="Fornecedor Teste", documento="00000000000191")
        self.produto = Produto.objects.create(
            nome="Malbec",
            sku="MLB-001",
            categoria=self.categoria,
            preco_custo=Decimal("10.00"),
            preco_venda=Decimal("30.00"),
            quantidade_estoque=5,
        )

    def test_registrar_entrada_soma_estoque_e_atualiza_custo(self):
        self.produto.registrar_entrada(
            quantidade=10,
            fornecedor=self.fornecedor,
            custo_unitario=Decimal("12.50"),
            usuario=self.usuario,
        )
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.quantidade_estoque, 15)
        self.assertEqual(self.produto.preco_custo, Decimal("12.50"))

    def test_registrar_entrada_bloqueia_quantidade_zero(self):
        with self.assertRaises(ValidationError):
            self.produto.registrar_entrada(
                quantidade=0,
                fornecedor=self.fornecedor,
                custo_unitario=Decimal("12.50"),
                usuario=self.usuario,
            )

    def test_registrar_entrada_bloqueia_custo_zero(self):
        with self.assertRaises(ValidationError):
            self.produto.registrar_entrada(
                quantidade=5,
                fornecedor=self.fornecedor,
                custo_unitario=Decimal("0"),
                usuario=self.usuario,
            )

    def test_registrar_entrada_cria_registro_com_criado_por(self):
        entrada = self.produto.registrar_entrada(
            quantidade=1,
            fornecedor=self.fornecedor,
            custo_unitario=Decimal("9.00"),
            usuario=self.usuario,
        )
        self.assertEqual(entrada.criado_por, self.usuario)
        self.assertEqual(entrada.valor_total, Decimal("9.00"))


class ProdutoViewTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(
            username="operador", password="senha123", is_staff=True
        )
        self.client.force_login(self.usuario)
        self.categoria = Categoria.objects.create(nome="Vinhos")

    def test_produtos_novo_cria_produto(self):
        resposta = self.client.post(
            reverse("estoque:produtos_novo"),
            {
                "nome": "Malbec",
                "sku": "MLB-001",
                "categoria": self.categoria.pk,
                "preco_custo": "10.00",
                "preco_venda": "30.00",
                "quantidade_estoque": "5",
                "estoque_minimo": "2",
                "unidade": "un",
                "ativo": "on",
            },
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(Produto.objects.filter(sku="MLB-001").exists())

    def test_produtos_excluir_bloqueado_por_venda(self):
        produto = Produto.objects.create(
            nome="Malbec",
            sku="MLB-001",
            categoria=self.categoria,
            preco_custo=Decimal("10.00"),
            preco_venda=Decimal("30.00"),
            quantidade_estoque=5,
        )
        from apps.vendas.models import ItemVenda, Venda

        venda = Venda.objects.create(criado_por=self.usuario)
        ItemVenda.objects.create(
            venda=venda, produto=produto, quantidade=1, preco_unitario=Decimal("30.00")
        )
        self.client.post(reverse("estoque:produtos_excluir", args=[produto.pk]))
        self.assertTrue(Produto.objects.filter(pk=produto.pk).exists())
