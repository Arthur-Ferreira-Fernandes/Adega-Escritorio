from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.clientes.models import Fornecedor
from apps.estoque.models import Categoria, Produto
from apps.financeiro.models import ContaPagar
from apps.vendas.models import ItemVenda, PagamentoVenda, Venda
from config.agregados import Soma

from .servicos import calcular_metricas

User = get_user_model()


class CalcularMetricasTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username="operador", password="senha123")
        self.categoria = Categoria.objects.create(nome="Vinhos")
        self.produto = Produto.objects.create(
            nome="Malbec Reserva",
            sku="MLB-001",
            categoria=self.categoria,
            preco_custo=Decimal("10.00"),
            preco_venda=Decimal("59.90"),
            quantidade_estoque=25,
        )
        hoje = timezone.now().date()
        venda = Venda.objects.create(criado_por=self.usuario, status=Venda.Status.CONCLUIDA)
        ItemVenda.objects.create(
            venda=venda,
            produto=self.produto,
            quantidade=2,
            preco_unitario=Decimal("59.90"),
            custo_unitario=Decimal("10.00"),
        )
        PagamentoVenda.objects.create(
            venda=venda, forma_pagamento=Venda.FormaPagamento.DINHEIRO, valor=Decimal("119.80")
        )
        self.data_inicio = hoje
        self.data_fim = hoje

    def test_faturamento_e_lucro_batem_com_o_calculo_manual(self):
        metricas = calcular_metricas(self.data_inicio, self.data_fim, None, "")
        self.assertEqual(metricas["faturamento_total"], Decimal("119.80"))
        self.assertEqual(metricas["lucro_total"], Decimal("99.80"))
        self.assertEqual(metricas["margem_total"], Decimal("83.3"))

    def test_produtos_lucro_traz_o_produto_com_valores_corretos(self):
        metricas = calcular_metricas(self.data_inicio, self.data_fim, None, "")
        produto_lucro = metricas["produtos_lucro"][0]
        self.assertEqual(produto_lucro["produto__nome"], "Malbec Reserva")
        self.assertEqual(produto_lucro["custo"], Decimal("20.00"))
        self.assertEqual(produto_lucro["lucro"], Decimal("99.80"))

    def test_filtro_forma_pagamento_exclui_vendas_de_outra_forma(self):
        metricas = calcular_metricas(self.data_inicio, self.data_fim, None, "cartao")
        self.assertEqual(metricas["faturamento_total"], Decimal("0"))

    def test_ticket_medio(self):
        metricas = calcular_metricas(self.data_inicio, self.data_fim, None, "")
        self.assertEqual(metricas["numero_vendas"], 1)
        self.assertEqual(metricas["ticket_medio"], Decimal("119.80"))


class SomaMonetariaTests(TestCase):
    def test_soma_devolve_sempre_duas_casas(self):
        fornecedor = Fornecedor.objects.create(nome="Fornecedor", documento="00.000.000/0001-00")
        hoje = timezone.now().date()
        for valor in ("1000.10", "978.10", "0.10"):
            ContaPagar.objects.create(
                fornecedor=fornecedor, descricao="Conta", valor=Decimal(valor), vencimento=hoje
            )
        total = ContaPagar.objects.aggregate(t=Soma("valor"))["t"]
        self.assertEqual(str(total), "1978.30")

    def test_soma_redonda_mantem_centavos(self):
        fornecedor = Fornecedor.objects.create(nome="Fornecedor", documento="00.000.000/0001-00")
        ContaPagar.objects.create(
            fornecedor=fornecedor, descricao="Conta", valor=Decimal("4587.00"),
            vencimento=timezone.now().date(),
        )
        self.assertEqual(str(ContaPagar.objects.aggregate(t=Soma("valor"))["t"]), "4587.00")
