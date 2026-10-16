from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.caixa.models import Caixa, MovimentoCaixa
from apps.clientes.models import Cliente
from apps.configuracoes.models import Configuracao
from apps.estoque.models import Categoria, Produto
from apps.financeiro.models import ContaReceber

from .models import Venda

User = get_user_model()


class BaseCaixa(TestCase):
    def setUp(self):
        self.atendente = User.objects.create_user(username="bia", password="x")
        self.dono = User.objects.create_superuser(username="dono", password="x")
        categoria = Categoria.objects.create(nome="Bebidas")
        self.cerveja = Produto.objects.create(
            nome="Cerveja", sku="CRV", categoria=categoria, preco_venda=Decimal("10.00"),
            preco_custo=Decimal("4.00"), quantidade_estoque=100,
        )
        self.venda = Venda.objects.create(criado_por=self.atendente)
        self.venda.adicionar_item(self.cerveja, 10)  # R$ 100,00

    def configurar(self, **valores):
        Configuracao.objects.update_or_create(pk=1, defaults=valores)


class DescontoTests(BaseCaixa):
    def test_desconto_em_valor_e_em_percentual(self):
        self.venda.aplicar_desconto(self.atendente, "5,50", "Cliente antigo")
        self.assertEqual((self.venda.desconto, self.venda.total), (Decimal("5.50"), Decimal("94.50")))
        self.venda.aplicar_desconto(self.atendente, "10%", "Promoção")
        self.assertEqual(self.venda.total, Decimal("90.00"))
        self.assertEqual(self.venda.desconto_por, self.atendente)

    def test_desconto_no_item_entra_no_subtotal_do_item(self):
        item = self.venda.itens.get()
        self.venda.aplicar_desconto(self.atendente, "R$ 3,00", "Embalagem amassada", item=item)
        item.refresh_from_db()
        self.assertEqual((item.subtotal, self.venda.total), (Decimal("97.00"), Decimal("97.00")))

    def test_limite_do_atendente_e_administrador_sem_limite(self):
        self.configurar(desconto_maximo_percentual=Decimal("10"))
        with self.assertRaisesMessage(ValidationError, "Peça a um administrador"):
            self.venda.aplicar_desconto(self.atendente, "15%", "Amigo")
        self.venda.aplicar_desconto(self.dono, "15%", "Amigo do dono")
        self.assertEqual(self.venda.total, Decimal("85.00"))

    def test_exige_motivo_e_nao_passa_do_total(self):
        with self.assertRaisesMessage(ValidationError, "motivo"):
            self.venda.aplicar_desconto(self.atendente, "5", "")
        with self.assertRaises(ValidationError):
            self.venda.aplicar_desconto(self.dono, "150", "Erro")

    def test_nao_deixa_o_total_ficar_menor_que_o_recebido(self):
        self.venda.adicionar_pagamento(Venda.FormaPagamento.PIX, Decimal("100.00"))
        with self.assertRaisesMessage(ValidationError, "Remova um pagamento"):
            self.venda.aplicar_desconto(self.dono, "10", "Tarde demais")
        self.venda.refresh_from_db()
        self.assertEqual(self.venda.total, Decimal("100.00"))

    def test_desconto_reduz_o_lucro(self):
        from apps.relatorios.analises import lucro_real

        from django.utils import timezone

        self.venda.aplicar_desconto(self.dono, "20", "Teste")
        self.venda.receber(Venda.FormaPagamento.PIX)
        hoje = timezone.localdate()
        self.assertEqual(lucro_real(hoje, hoje)["lucro_bruto"], Decimal("40.00"))  # 80 - custo 40


class ServicoCouvertDivisaoTests(BaseCaixa):
    def test_comanda_nova_vem_com_servico_e_couvert_configurados(self):
        self.configurar(taxa_servico_percentual=Decimal("10"), couvert_por_pessoa=Decimal("8"))
        comanda = Venda.objects.create(criado_por=self.atendente, identificador="Mesa 1", quantidade_pessoas=3)
        comanda.aplicar_padroes_de_comanda()
        comanda.adicionar_item(self.cerveja, 10)
        self.assertEqual((comanda.taxa_servico, comanda.couvert, comanda.total),
                         (Decimal("10.00"), Decimal("24.00"), Decimal("134.00")))
        comanda.aplicar_desconto(self.dono, "20", "Aniversário")  # serviço sobre o valor com desconto
        self.assertEqual((comanda.taxa_servico, comanda.total), (Decimal("8.00"), Decimal("112.00")))

    def test_tirar_servico_e_couvert_da_comanda(self):
        self.configurar(taxa_servico_percentual=Decimal("10"), couvert_por_pessoa=Decimal("8"))
        self.venda.quantidade_pessoas = 2
        self.venda.save()
        self.venda.definir_servico(True)
        self.venda.definir_couvert(True)
        self.assertEqual(self.venda.total, Decimal("126.00"))
        self.venda.definir_servico(False)
        self.venda.definir_couvert(False)
        self.assertEqual(self.venda.total, Decimal("100.00"))

    def test_percentual_combinado_nao_muda_se_a_configuracao_mudar(self):
        self.configurar(taxa_servico_percentual=Decimal("10"))
        self.venda.definir_servico(True)
        self.configurar(taxa_servico_percentual=Decimal("15"))
        self.venda.adicionar_item(self.cerveja, 1)
        self.assertEqual(self.venda.taxa_servico, Decimal("11.00"))

    def test_dividir_e_receber_parte_por_parte(self):
        self.venda.dividir_em = 3
        self.venda.save()
        self.assertEqual(self.venda.valor_da_parte, Decimal("33.33"))
        self.venda.receber(Venda.FormaPagamento.PIX, Decimal("33.33"))
        self.venda.receber(Venda.FormaPagamento.CARTAO, Decimal("33.33"))
        self.assertEqual(self.venda.partes_pagas(), 2)
        self.venda.receber(Venda.FormaPagamento.DINHEIRO, Decimal("33.34"))  # a última leva o centavo
        self.venda.refresh_from_db()
        self.assertEqual(self.venda.status, Venda.Status.CONCLUIDA)


class FiadoTests(BaseCaixa):
    def setUp(self):
        super().setUp()
        self.cliente = Cliente.objects.create(nome="Seu Zé", documento="1", limite_fiado=Decimal("150"))
        self.venda.cliente = self.cliente
        self.venda.save()

    def test_fiado_vira_conta_a_receber(self):
        self.configurar(prazo_fiado_dias=15)
        self.venda.receber(Venda.FormaPagamento.FIADO)
        conta = ContaReceber.objects.get()
        self.assertEqual((conta.cliente, conta.valor, conta.venda), (self.cliente, Decimal("100.00"), self.venda))
        from datetime import timedelta

        from django.utils import timezone

        self.assertEqual(conta.vencimento, timezone.localdate() + timedelta(days=15))
        self.assertEqual(self.cliente.saldo_fiado(), Decimal("100.00"))

    def test_bloqueia_sem_cliente_sem_limite_e_acima_do_limite(self):
        sem_cliente = Venda.objects.create(criado_por=self.atendente)
        sem_cliente.adicionar_item(self.cerveja, 1)
        with self.assertRaisesMessage(ValidationError, "cliente cadastrado"):
            sem_cliente.receber(Venda.FormaPagamento.FIADO)
        self.venda.receber(Venda.FormaPagamento.FIADO)  # deve 100 de 150
        outra = Venda.objects.create(criado_por=self.atendente, cliente=self.cliente)
        outra.adicionar_item(self.cerveja, 6)
        with self.assertRaisesMessage(ValidationError, "disponível R$ 50,00"):
            outra.receber(Venda.FormaPagamento.FIADO)
        outra.receber(Venda.FormaPagamento.FIADO, Decimal("50"))  # parte no fiado
        outra.receber(Venda.FormaPagamento.PIX)  # o resto no Pix
        self.assertEqual(self.cliente.saldo_fiado(), Decimal("150.00"))

    def test_receber_fiado_em_dinheiro_entra_no_caixa(self):
        self.venda.receber(Venda.FormaPagamento.FIADO)
        conta = ContaReceber.objects.get()
        self.client.force_login(self.atendente)
        url = reverse("financeiro:contas_receber_marcar_recebida", kwargs={"pk": conta.pk})
        self.client.post(url, {"forma": "dinheiro"})
        conta.refresh_from_db()
        self.assertFalse(conta.recebido)  # sem caixa aberto não recebe em dinheiro
        caixa = Caixa.abrir(self.atendente, Decimal("50"))
        self.client.post(url, {"forma": "dinheiro"})
        conta.refresh_from_db()
        self.assertEqual((conta.recebido, conta.forma_recebimento), (True, "dinheiro"))
        self.assertEqual(caixa.saldo_esperado(), Decimal("150.00"))  # 50 + 100 do fiado
        self.assertEqual(MovimentoCaixa.objects.get().tipo, MovimentoCaixa.Tipo.RECEBIMENTO)
        lote = Caixa.calcular_totais([Caixa.objects.get()])[0]
        self.assertEqual(lote.saldo_esperado(), Decimal("150.00"))

    def test_receber_fiado_no_pix_nao_mexe_no_caixa(self):
        self.venda.receber(Venda.FormaPagamento.FIADO)
        caixa = Caixa.abrir(self.atendente, Decimal("50"))
        self.client.force_login(self.atendente)
        self.client.post(reverse("financeiro:contas_receber_marcar_recebida", kwargs={"pk": ContaReceber.objects.get().pk}), {"forma": "pix"})
        self.assertTrue(ContaReceber.objects.get().recebido)
        self.assertEqual(caixa.saldo_esperado(), Decimal("50.00"))


class TelaVendaTests(BaseCaixa):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.atendente)

    def post(self, nome, dados=None, **kwargs):
        url = reverse(f"vendas:{nome}", kwargs={"pk": self.venda.pk, **kwargs})
        return self.client.post(url, dados or {}, HTTP_HX_REQUEST="true")

    def test_fluxo_pela_tela(self):
        cliente = Cliente.objects.create(nome="Ana", documento="2", limite_fiado=Decimal("500"))
        self.post("definir_cliente", {"cliente": cliente.pk})
        self.post("desconto", {"desconto": "10%", "motivo": "Cupom"})
        self.post("desconto_item", {"desconto": "2", "motivo": "Quente"}, item_id=self.venda.itens.get().pk)
        resposta = self.post("dividir", {"dividir_em": "2"})
        self.venda.refresh_from_db()
        # 10% vira R$ 10,00 na hora em que é dado; o desconto do item vem depois: 100 - 10 - 2.
        self.assertEqual((self.venda.cliente, self.venda.total, self.venda.dividir_em), (cliente, Decimal("88.00"), 2))
        self.assertContains(resposta, 'value="44.00"')  # a parte já vem no campo de valor
        self.assertContains(resposta, "Fiado disponível: R$ 500,00")
        resposta = self.post("desconto", {"desconto": "50%", "motivo": "Exagero"})
        self.assertContains(resposta, "Peça a um administrador")

    def test_receber_em_dinheiro_abre_a_gaveta_configurada(self):
        self.configurar(impressora_gaveta="Termica", abrir_gaveta_no_dinheiro=True)
        with self.settings(GAVETA_DISPONIVEL=True), mock.patch("apps.caixa.gaveta.abrir") as abrir:
            self.post("adicionar_pagamento", {"forma_pagamento": "dinheiro", "valor": ""})
            import time
            for _ in range(50):
                if abrir.called:
                    break
                time.sleep(0.02)
        abrir.assert_called_once_with("Termica")
