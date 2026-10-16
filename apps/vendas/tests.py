from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.caixa.models import Caixa
from apps.estoque.models import Categoria, Produto

from .models import Venda

User = get_user_model()


def _criar_produto(nome="Vinho Teste", preco_venda="50.00", preco_custo="20.00", estoque=10):
    categoria = Categoria.objects.create(nome="Categoria Teste")
    return Produto.objects.create(
        nome=nome,
        sku=f"SKU-{nome}",
        categoria=categoria,
        preco_custo=Decimal(preco_custo),
        preco_venda=Decimal(preco_venda),
        quantidade_estoque=estoque,
    )


class VendaModelTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username="operador", password="senha123")
        self.produto = _criar_produto()
        self.venda = Venda.objects.create(criado_por=self.usuario)

    def test_adicionar_item_soma_quantidade_existente(self):
        self.venda.adicionar_item(self.produto, 2)
        self.venda.adicionar_item(self.produto, 3)
        item = self.venda.itens.get(produto=self.produto)
        self.assertEqual(item.quantidade, 5)
        self.assertEqual(self.venda.total, Decimal("250.00"))

    def test_vender_sem_estoque_deixa_estoque_negativo(self):
        self.venda.adicionar_item(self.produto, 12)
        self.venda.receber(Venda.FormaPagamento.CARTAO)
        self.produto.refresh_from_db()
        self.assertEqual(self.venda.status, Venda.Status.CONCLUIDA)
        self.assertEqual(self.produto.quantidade_estoque, -2)

    def test_adicionar_item_bloqueia_quantidade_zero(self):
        with self.assertRaises(ValidationError):
            self.venda.adicionar_item(self.produto, 0)

    def test_adicionar_item_congela_custo_unitario(self):
        item = self.venda.adicionar_item(self.produto, 1)
        self.assertEqual(item.custo_unitario, Decimal("20.00"))

    def test_remover_item_recalcula_total(self):
        item = self.venda.adicionar_item(self.produto, 2)
        self.venda.remover_item(item)
        self.assertEqual(self.venda.total, Decimal("0.00"))

    def test_adicionar_pagamento_cartao_sem_troco_nao_ultrapassa(self):
        self.venda.adicionar_item(self.produto, 1)
        with self.assertRaises(ValidationError):
            self.venda.adicionar_pagamento(Venda.FormaPagamento.CARTAO, Decimal("100.00"))

    def test_adicionar_pagamento_dinheiro_calcula_troco(self):
        self.venda.adicionar_item(self.produto, 1)
        pagamento = self.venda.adicionar_pagamento(
            Venda.FormaPagamento.DINHEIRO, Decimal("100.00")
        )
        self.assertEqual(pagamento.valor, Decimal("50.00"))
        self.assertEqual(pagamento.troco, Decimal("50.00"))
        self.assertEqual(self.venda.falta_receber, Decimal("0.00"))

    def test_adicionar_pagamento_bloqueia_venda_ja_paga(self):
        self.venda.adicionar_item(self.produto, 1)
        self.venda.adicionar_pagamento(Venda.FormaPagamento.DINHEIRO, Decimal("50.00"))
        with self.assertRaises(ValidationError):
            self.venda.adicionar_pagamento(Venda.FormaPagamento.DINHEIRO, Decimal("10.00"))

    def test_finalizar_baixa_estoque(self):
        self.venda.adicionar_item(self.produto, 2)
        self.venda.adicionar_pagamento(Venda.FormaPagamento.DINHEIRO, Decimal("100.00"))
        self.venda.finalizar()
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.quantidade_estoque, 8)
        self.assertEqual(self.venda.status, Venda.Status.CONCLUIDA)
        self.assertIsNotNone(self.venda.finalizada_em)

    def test_receber_sem_valor_quita_e_finaliza(self):
        self.venda.adicionar_item(self.produto, 2)
        self.venda.receber(Venda.FormaPagamento.CARTAO)
        self.assertEqual(self.venda.status, Venda.Status.CONCLUIDA)
        self.assertEqual(self.venda.pagamentos.get().valor, Decimal("100.00"))
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.quantidade_estoque, 8)

    def test_receber_dinheiro_com_troco_finaliza(self):
        self.venda.adicionar_item(self.produto, 1)
        pagamento = self.venda.receber(Venda.FormaPagamento.DINHEIRO, Decimal("70.00"))
        self.assertEqual(pagamento.troco, Decimal("20.00"))
        self.assertEqual(self.venda.status, Venda.Status.CONCLUIDA)

    def test_receber_parcial_mantem_venda_aberta(self):
        self.venda.adicionar_item(self.produto, 2)
        self.venda.receber(Venda.FormaPagamento.PIX, Decimal("30.00"))
        self.assertEqual(self.venda.status, Venda.Status.ABERTA)
        self.assertEqual(self.venda.falta_receber, Decimal("70.00"))
        self.venda.receber(Venda.FormaPagamento.CARTAO)
        self.assertEqual(self.venda.status, Venda.Status.CONCLUIDA)

    def test_receber_desfaz_pagamento_se_finalizar_falhar(self):
        self.venda.adicionar_item(self.produto, 2)
        with (
            mock.patch.object(Venda, "finalizar", side_effect=ValidationError("falhou")),
            self.assertRaises(ValidationError),
        ):
            self.venda.receber(Venda.FormaPagamento.CARTAO)
        self.venda.refresh_from_db()
        self.assertEqual(self.venda.status, Venda.Status.ABERTA)
        self.assertFalse(self.venda.pagamentos.exists())

    def test_receber_bloqueia_venda_sem_itens(self):
        with self.assertRaises(ValidationError):
            self.venda.receber(Venda.FormaPagamento.CARTAO)
        self.assertFalse(self.venda.pagamentos.exists())

    def test_finalizar_bloqueia_sem_itens(self):
        with self.assertRaises(ValidationError):
            self.venda.finalizar()

    def test_finalizar_bloqueia_pagamento_incompleto(self):
        self.venda.adicionar_item(self.produto, 1)
        with self.assertRaises(ValidationError):
            self.venda.finalizar()

    def test_cancelar_remove_pagamentos(self):
        self.venda.adicionar_item(self.produto, 1)
        self.venda.adicionar_pagamento(Venda.FormaPagamento.DINHEIRO, Decimal("50.00"))
        self.venda.cancelar()
        self.assertEqual(self.venda.status, Venda.Status.CANCELADA)
        self.assertEqual(self.venda.pagamentos.count(), 0)

    def test_cancelar_bloqueia_venda_ja_finalizada(self):
        self.venda.adicionar_item(self.produto, 1)
        self.venda.adicionar_pagamento(Venda.FormaPagamento.DINHEIRO, Decimal("50.00"))
        self.venda.finalizar()
        with self.assertRaises(ValidationError):
            self.venda.cancelar()

    def test_valor_por_pessoa_none_sem_quantidade(self):
        self.venda.adicionar_item(self.produto, 1)
        self.assertIsNone(self.venda.valor_por_pessoa)

    def test_valor_por_pessoa_divide_total(self):
        self.venda.quantidade_pessoas = 2
        self.venda.adicionar_item(self.produto, 1)
        self.assertEqual(self.venda.valor_por_pessoa, Decimal("25.00"))


class VendaViewTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(
            username="operador", password="senha123", is_staff=True
        )
        self.client.force_login(self.usuario)
        self.produto = _criar_produto()

    def test_venda_rapida_bloqueada_sem_caixa_aberto(self):
        resposta = self.client.post(reverse("vendas:rapida"))
        self.assertRedirects(resposta, reverse("caixa:painel"))
        self.assertEqual(Venda.objects.count(), 0)

    def test_venda_rapida_cria_venda_com_caixa_aberto(self):
        Caixa.abrir(self.usuario, Decimal("100.00"))
        resposta = self.client.post(reverse("vendas:rapida"))
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(Venda.objects.count(), 1)

    def test_caixa_aberto_ha_muito_tempo_nao_bloqueia_vendas(self):
        caixa = Caixa.abrir(self.usuario, Decimal("100.00"))
        Caixa.objects.filter(pk=caixa.pk).update(aberto_em=timezone.now() - timedelta(hours=30))
        self.client.post(reverse("vendas:rapida"))
        self.assertEqual(Venda.objects.count(), 1)

    def test_um_clique_no_cartao_finaliza_a_venda(self):
        Caixa.abrir(self.usuario, Decimal("100.00"))
        venda = Venda.objects.create(criado_por=self.usuario)
        venda.adicionar_item(self.produto, 1)
        self.client.post(
            reverse("vendas:adicionar_pagamento", kwargs={"pk": venda.pk}),
            {"forma_pagamento": "cartao", "valor": ""},
        )
        venda.refresh_from_db()
        self.assertEqual(venda.status, Venda.Status.CONCLUIDA)

    def test_adicionar_item_pelo_sku_da_busca(self):
        venda = Venda.objects.create(criado_por=self.usuario)
        self.client.post(
            reverse("vendas:adicionar_item", kwargs={"pk": venda.pk}),
            {"produto_busca": self.produto.sku, "quantidade": "2"},
        )
        item = venda.itens.get()
        self.assertEqual((item.produto, item.quantidade), (self.produto, 2))

    def test_adicionar_item_sem_escolher_produto_nao_adiciona(self):
        venda = Venda.objects.create(criado_por=self.usuario)
        for valor in ("", "SKU-inexistente"):
            self.client.post(
                reverse("vendas:adicionar_item", kwargs={"pk": venda.pk}),
                {"produto_busca": valor, "quantidade": "1"},
            )
        self.assertFalse(venda.itens.exists())

    def test_tela_da_venda_envia_produtos_para_a_busca(self):
        venda = Venda.objects.create(criado_por=self.usuario)
        resposta = self.client.get(reverse("vendas:detalhe", kwargs={"pk": venda.pk}))
        self.assertEqual(
            resposta.context["produtos_busca"],
            [{
                "sku": self.produto.sku,
                "nome": "Vinho Teste",
                "categoria": "Categoria Teste",
                "codigo": "",
                "preco": "50.00",
                "estoque": 10,
                "minimo": 5,
                "kit": False,
            }],
        )
        self.assertContains(resposta, 'id="produtos-dados"')

    def test_nova_comanda_com_pessoas(self):
        Caixa.abrir(self.usuario, Decimal("100.00"))
        self.client.post(
            reverse("vendas:nova"),
            {"identificador": "Mesa 1", "quantidade_pessoas": "3"},
        )
        venda = Venda.objects.get(identificador="Mesa 1")
        self.assertEqual(venda.quantidade_pessoas, 3)
