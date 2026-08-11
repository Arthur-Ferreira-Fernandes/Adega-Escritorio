from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.caixa.models import Caixa
from apps.configuracoes.models import Configuracao
from apps.estoque.models import Categoria, Produto

from . import servicos
from .models import Notificacao

User = get_user_model()


class SincronizarCaixaSangriaTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username="operador", password="senha123")

    def test_dispara_notificacao_quando_saldo_ultrapassa_limite(self):
        config = Configuracao.obter()
        config.limite_sangria = Decimal("200.00")
        config.save()
        caixa = Caixa.abrir(self.usuario, Decimal("300.00"))

        servicos.sincronizar()

        self.assertTrue(
            Notificacao.objects.filter(
                tipo=Notificacao.Tipo.CAIXA_SANGRIA, resolvida=False
            ).exists()
        )

    def test_nao_dispara_quando_saldo_abaixo_do_limite(self):
        config = Configuracao.obter()
        config.limite_sangria = Decimal("1000.00")
        config.save()
        Caixa.abrir(self.usuario, Decimal("100.00"))

        servicos.sincronizar()

        self.assertFalse(
            Notificacao.objects.filter(
                tipo=Notificacao.Tipo.CAIXA_SANGRIA, resolvida=False
            ).exists()
        )

    def test_resolve_notificacao_quando_saldo_volta_ao_normal(self):
        config = Configuracao.obter()
        config.limite_sangria = Decimal("200.00")
        config.save()
        caixa = Caixa.abrir(self.usuario, Decimal("300.00"))
        servicos.sincronizar()

        caixa.registrar_sangria(self.usuario, Decimal("250.00"), "retirada")
        servicos.sincronizar()

        self.assertFalse(
            Notificacao.objects.filter(
                tipo=Notificacao.Tipo.CAIXA_SANGRIA, resolvida=False
            ).exists()
        )

    def test_sem_caixa_aberto_nao_gera_notificacao(self):
        servicos.sincronizar()
        self.assertFalse(Notificacao.objects.filter(tipo=Notificacao.Tipo.CAIXA_SANGRIA).exists())


class SincronizarCaixaLimiteTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username="operador", password="senha123")

    def test_dispara_notificacao_de_perigo_apos_limite(self):
        config = Configuracao.obter()
        config.limite_horas_caixa = 6
        config.save()
        caixa = Caixa.abrir(self.usuario, Decimal("100.00"))
        Caixa.objects.filter(pk=caixa.pk).update(aberto_em=timezone.now() - timedelta(hours=7))

        servicos.sincronizar()

        notificacao = Notificacao.objects.get(
            tipo=Notificacao.Tipo.CAIXA_LIMITE, resolvida=False
        )
        self.assertEqual(notificacao.nivel, Notificacao.Nivel.PERIGO)

    def test_sem_notificacao_dentro_do_limite(self):
        config = Configuracao.obter()
        config.limite_horas_caixa = 12
        config.save()
        Caixa.abrir(self.usuario, Decimal("100.00"))

        servicos.sincronizar()

        self.assertFalse(
            Notificacao.objects.filter(
                tipo=Notificacao.Tipo.CAIXA_LIMITE, resolvida=False
            ).exists()
        )


class SincronizarEstoqueTests(TestCase):
    def test_dispara_notificacao_para_produto_no_minimo(self):
        categoria = Categoria.objects.create(nome="Vinhos")
        Produto.objects.create(
            nome="Malbec",
            sku="MLB-001",
            categoria=categoria,
            preco_custo=Decimal("10.00"),
            preco_venda=Decimal("30.00"),
            quantidade_estoque=2,
            estoque_minimo=5,
        )

        servicos.sincronizar()

        self.assertTrue(
            Notificacao.objects.filter(
                tipo=Notificacao.Tipo.ESTOQUE_MINIMO, resolvida=False
            ).exists()
        )

    def test_produto_inativo_nao_gera_notificacao(self):
        categoria = Categoria.objects.create(nome="Vinhos")
        Produto.objects.create(
            nome="Malbec",
            sku="MLB-001",
            categoria=categoria,
            preco_custo=Decimal("10.00"),
            preco_venda=Decimal("30.00"),
            quantidade_estoque=2,
            estoque_minimo=5,
            ativo=False,
        )

        servicos.sincronizar()

        self.assertFalse(Notificacao.objects.filter(tipo=Notificacao.Tipo.ESTOQUE_MINIMO).exists())

    def test_produto_acima_do_minimo_nao_gera_notificacao(self):
        categoria = Categoria.objects.create(nome="Vinhos")
        Produto.objects.create(
            nome="Malbec",
            sku="MLB-001",
            categoria=categoria,
            preco_custo=Decimal("10.00"),
            preco_venda=Decimal("30.00"),
            quantidade_estoque=50,
            estoque_minimo=5,
        )

        servicos.sincronizar()

        self.assertFalse(Notificacao.objects.filter(tipo=Notificacao.Tipo.ESTOQUE_MINIMO).exists())
