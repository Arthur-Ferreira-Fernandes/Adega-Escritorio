from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import Caixa, MovimentoCaixa

User = get_user_model()


class CaixaModelTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username="operador", password="senha123")

    def test_abrir_cria_caixa(self):
        caixa = Caixa.abrir(self.usuario, Decimal("100.00"))
        self.assertEqual(caixa.status, Caixa.Status.ABERTO)
        self.assertEqual(caixa.valor_abertura, Decimal("100.00"))
        self.assertEqual(caixa.aberto_por, self.usuario)

    def test_abrir_bloqueia_valor_negativo(self):
        with self.assertRaises(ValidationError):
            Caixa.abrir(self.usuario, Decimal("-1.00"))

    def test_abrir_bloqueia_caixa_duplicado(self):
        Caixa.abrir(self.usuario, Decimal("100.00"))
        with self.assertRaises(ValidationError):
            Caixa.abrir(self.usuario, Decimal("50.00"))

    def test_registrar_sangria_bloqueia_saldo_insuficiente(self):
        caixa = Caixa.abrir(self.usuario, Decimal("100.00"))
        with self.assertRaises(ValidationError):
            caixa.registrar_sangria(self.usuario, Decimal("200.00"), "teste")

    def test_registrar_sangria_bloqueia_valor_zero(self):
        caixa = Caixa.abrir(self.usuario, Decimal("100.00"))
        with self.assertRaises(ValidationError):
            caixa.registrar_sangria(self.usuario, Decimal("0"), "teste")

    def test_registrar_sangria_com_saldo_suficiente(self):
        caixa = Caixa.abrir(self.usuario, Decimal("100.00"))
        movimento = caixa.registrar_sangria(self.usuario, Decimal("30.00"), "retirada")
        self.assertEqual(movimento.tipo, MovimentoCaixa.Tipo.SANGRIA)
        self.assertEqual(caixa.saldo_esperado(), Decimal("70.00"))

    def test_registrar_reforco_aumenta_saldo(self):
        caixa = Caixa.abrir(self.usuario, Decimal("100.00"))
        caixa.registrar_reforco(self.usuario, Decimal("50.00"), "troco extra")
        self.assertEqual(caixa.saldo_esperado(), Decimal("150.00"))

    def test_registrar_reforco_bloqueia_valor_negativo(self):
        caixa = Caixa.abrir(self.usuario, Decimal("100.00"))
        with self.assertRaises(ValidationError):
            caixa.registrar_reforco(self.usuario, Decimal("-10.00"), "teste")

    def test_fechar_atualiza_status_e_diferenca(self):
        caixa = Caixa.abrir(self.usuario, Decimal("100.00"))
        caixa.fechar(self.usuario, Decimal("90.00"))
        self.assertEqual(caixa.status, Caixa.Status.FECHADO)
        self.assertEqual(caixa.diferenca(), Decimal("-10.00"))
        self.assertIsNotNone(caixa.fechado_em)

    def test_fechar_bloqueia_valor_negativo(self):
        caixa = Caixa.abrir(self.usuario, Decimal("100.00"))
        with self.assertRaises(ValidationError):
            caixa.fechar(self.usuario, Decimal("-5.00"))

    def test_nao_pode_operar_caixa_ja_fechado(self):
        caixa = Caixa.abrir(self.usuario, Decimal("100.00"))
        caixa.fechar(self.usuario, Decimal("100.00"))
        with self.assertRaises(ValidationError):
            caixa.registrar_sangria(self.usuario, Decimal("10.00"), "teste")
        with self.assertRaises(ValidationError):
            caixa.fechar(self.usuario, Decimal("100.00"))

    def test_aberto_atual_retorna_none_sem_caixa(self):
        self.assertIsNone(Caixa.aberto_atual())

    def test_aberto_atual_retorna_caixa_aberto(self):
        caixa = Caixa.abrir(self.usuario, Decimal("100.00"))
        self.assertEqual(Caixa.aberto_atual(), caixa)


class CaixaViewTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(
            username="operador", password="senha123", is_staff=True
        )
        self.client.force_login(self.usuario)

    def test_painel_requer_login(self):
        self.client.logout()
        resposta = self.client.get(reverse("caixa:painel"))
        self.assertEqual(resposta.status_code, 302)

    def test_abrir_via_view(self):
        resposta = self.client.post(
            reverse("caixa:abrir"), {"valor_abertura": "100.00"}
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertIsNotNone(Caixa.aberto_atual())

    def test_abrir_duplicado_nao_gera_segundo_caixa(self):
        self.client.post(reverse("caixa:abrir"), {"valor_abertura": "100.00"})
        self.client.post(reverse("caixa:abrir"), {"valor_abertura": "50.00"})
        self.assertEqual(Caixa.objects.filter(status=Caixa.Status.ABERTO).count(), 1)

    def test_fechar_via_view(self):
        self.client.post(reverse("caixa:abrir"), {"valor_abertura": "100.00"})
        self.client.post(reverse("caixa:fechar"), {"valor_contado": "100.00"})
        self.assertIsNone(Caixa.aberto_atual())



class CalcularTotaisTests(TestCase):
    """O cálculo em lote (listas de caixas) tem que bater com o de cada caixa."""

    def test_lote_igual_ao_calculo_individual(self):
        from datetime import timedelta

        from django.utils import timezone

        from apps.estoque.models import Categoria, Produto
        from apps.vendas.models import Venda

        usuario = User.objects.create_user(username="lote", password="x")
        produto = Produto.objects.create(
            nome="Vinho", sku="V1", categoria=Categoria.objects.create(nome="C"),
            preco_venda=Decimal("10"), preco_custo=Decimal("4"), quantidade_estoque=100,
        )
        agora = timezone.now()
        for dias in (3, 2, 1):
            caixa = Caixa.abrir(usuario, Decimal("50"))
            Caixa.objects.filter(pk=caixa.pk).update(aberto_em=agora - timedelta(days=dias, hours=5))
            caixa.refresh_from_db()
            for horas, forma in ((4, Venda.FormaPagamento.DINHEIRO), (3, Venda.FormaPagamento.PIX), (1, Venda.FormaPagamento.DINHEIRO)):
                venda = Venda.objects.create(criado_por=usuario)
                venda.adicionar_item(produto, dias)
                venda.receber(forma)
                Venda.objects.filter(pk=venda.pk).update(finalizada_em=agora - timedelta(days=dias, hours=horas))
            caixa.registrar_reforco(usuario, Decimal("20"), "troco")
            caixa.registrar_sangria(usuario, Decimal("15"), "depósito")
            caixa.fechar(usuario, Decimal("70"))
            Caixa.objects.filter(pk=caixa.pk).update(fechado_em=agora - timedelta(days=dias, hours=2))
        Caixa.abrir(usuario, Decimal("30"))  # o aberto também entra na lista

        def resumo(caixa):
            return (caixa.total_sangrias(), caixa.total_reforcos(), caixa.total_vendas_dinheiro(),
                    caixa.saldo_esperado(), caixa.diferenca())

        individual = {c.pk: resumo(c) for c in Caixa.objects.all()}
        lote = {c.pk: resumo(c) for c in Caixa.calcular_totais(Caixa.objects.all())}
        self.assertEqual(individual, lote)
        # Cada caixa fechado pega só a venda em dinheiro de 4h antes (a de 1h é depois do fechamento).
        self.assertEqual(sorted(v[2] for v in individual.values()), [Decimal("0"), Decimal("10"), Decimal("20"), Decimal("30")])
