from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.clientes.models import Fornecedor
from apps.configuracoes.models import Configuracao
from apps.notificacoes import servicos as sino
from apps.notificacoes.models import Notificacao
from apps.relatorios import analises
from apps.vendas.models import Venda

from .models import ComponenteKit, EntradaEstoque, PedidoCompra, Produto, Categoria

User = get_user_model()


class Base(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_superuser(username="dono", password="x")
        self.categoria = Categoria.objects.create(nome="Bebidas")
        self.fornecedor = Fornecedor.objects.create(nome="Distribuidora", documento="1", telefone="11999998888")
        self.hoje = timezone.localdate()

    def produto(self, nome, estoque=50, custo="4.00", preco="10.00", minimo=5):
        return Produto.objects.create(
            nome=nome, sku=nome.upper(), categoria=self.categoria, preco_custo=Decimal(custo),
            preco_venda=Decimal(preco), quantidade_estoque=estoque, estoque_minimo=minimo,
        )


class KitTests(Base):
    def setUp(self):
        super().setUp()
        self.vodka = self.produto("Vodka", estoque=10, custo="30.00")
        self.energetico = self.produto("Energetico", estoque=9, custo="5.00")
        self.kit = self.produto("Kit Balada", estoque=0, preco="70.00")
        ComponenteKit.objects.create(kit=self.kit, componente=self.vodka, quantidade=1)
        ComponenteKit.objects.create(kit=self.kit, componente=self.energetico, quantidade=2)
        self.kit.refresh_from_db()

    def test_vender_kit_baixa_os_componentes_e_custa_a_soma(self):
        self.assertTrue(self.kit.e_kit)
        self.assertEqual(self.kit.estoque_disponivel(), 4)  # 9 energéticos / 2
        venda = Venda.objects.create(criado_por=self.usuario)
        item = venda.adicionar_item(self.kit, 3)
        self.assertEqual(item.custo_unitario, Decimal("40.00"))
        venda.receber(Venda.FormaPagamento.PIX)
        for produto, esperado in ((self.vodka, 7), (self.energetico, 3), (self.kit, 0)):
            produto.refresh_from_db()
            self.assertEqual(produto.quantidade_estoque, esperado, produto.nome)

    def test_kit_fora_dos_avisos_de_estoque_e_da_lista_de_compras(self):
        sino.sincronizar()
        avisos = Notificacao.objects.filter(tipo=Notificacao.Tipo.ESTOQUE_MINIMO, resolvida=False)
        self.assertNotIn("Kit Balada", " ".join(avisos.values_list("mensagem", flat=True)))
        nomes = [i["produto"].nome for g in analises.previsao_de_compras()["fornecedores"] for i in g["itens"]]
        self.assertNotIn("Kit Balada", nomes)

    def test_kit_nao_recebe_entrada_nem_contem_outro_kit(self):
        with self.assertRaises(ValidationError):
            self.kit.registrar_entrada(quantidade=1, fornecedor=self.fornecedor, custo_unitario=Decimal("1"), usuario=self.usuario)
        self.client.force_login(self.usuario)
        outro = self.produto("Kit Duplo", estoque=0)
        self.client.post(reverse("estoque:kit", kwargs={"pk": outro.pk}), {"produto_busca": self.kit.sku, "quantidade": "1"})
        self.assertFalse(ComponenteKit.objects.filter(kit=outro).exists())

    def test_tirar_todos_os_componentes_desfaz_o_kit(self):
        self.client.force_login(self.usuario)
        for componente in list(self.kit.componentes.all()):
            self.client.post(reverse("estoque:kit_remover", kwargs={"pk": self.kit.pk, "componente_id": componente.pk}))
        self.kit.refresh_from_db()
        self.assertFalse(self.kit.e_kit)


class PedidoTests(Base):
    def test_gerar_editar_e_receber_pedido(self):
        cerveja = self.produto("Cerveja", estoque=2)
        gelo = self.produto("Gelo", estoque=0, custo="3.00")
        self.client.force_login(self.usuario)
        resposta = self.client.post(reverse("estoque:pedido_gerar"), {
            "fornecedor": self.fornecedor.pk, "produto": [cerveja.pk, gelo.pk], "quantidade": ["24", "10"],
        })
        pedido = PedidoCompra.objects.get()
        self.assertRedirects(resposta, reverse("estoque:pedido", kwargs={"pk": pedido.pk}))
        self.assertEqual(pedido.total, Decimal("126.00"))  # 24x4 + 10x3

        pagina = self.client.get(reverse("estoque:pedido", kwargs={"pk": pedido.pk})).content.decode()
        self.assertIn("24 × Cerveja", pagina)
        self.assertIn("https://wa.me/5511999998888?text=", pagina)

        itens = {i.produto.nome: i for i in pedido.itens.all()}
        url = reverse("estoque:pedido", kwargs={"pk": pedido.pk})
        self.client.post(url, {"acao": "salvar", f"quantidade_{itens['Gelo'].pk}": "0", f"quantidade_{itens['Cerveja'].pk}": "30"})
        self.assertEqual([(i.produto.nome, i.quantidade) for i in pedido.itens.all()], [("Cerveja", 30)])

        validade = self.hoje + timedelta(days=90)
        self.client.post(url, {
            "acao": "receber", f"recebido_{itens['Cerveja'].pk}": "28",
            f"custo_{itens['Cerveja'].pk}": "4,20", f"validade_{itens['Cerveja'].pk}": validade.isoformat(),
        })
        pedido.refresh_from_db()
        cerveja.refresh_from_db()
        entrada = EntradaEstoque.objects.get()
        self.assertEqual(pedido.status, PedidoCompra.Status.RECEBIDO)
        self.assertEqual((cerveja.quantidade_estoque, cerveja.preco_custo), (30, Decimal("4.20")))
        self.assertEqual((entrada.quantidade, entrada.validade, entrada.fornecedor), (28, validade, self.fornecedor))

    def test_lista_de_compras_traz_o_fornecedor_para_gerar_o_pedido(self):
        cerveja = self.produto("Cerveja", estoque=50)
        cerveja.registrar_entrada(quantidade=1, fornecedor=self.fornecedor, custo_unitario=Decimal("4"), usuario=self.usuario)
        Produto.objects.filter(pk=cerveja.pk).update(quantidade_estoque=0)
        grupo = analises.previsao_de_compras()["fornecedores"][0]
        self.assertEqual((grupo["fornecedor_id"], grupo["fornecedor"]), (self.fornecedor.pk, "Distribuidora"))


class ValidadeTests(Base):
    def entrada(self, produto, quantidade, validade_em_dias, dias_atras):
        entrada = produto.registrar_entrada(
            quantidade=quantidade, fornecedor=self.fornecedor, custo_unitario=Decimal("4"), usuario=self.usuario,
            validade=self.hoje + timedelta(days=validade_em_dias) if validade_em_dias is not None else None,
        )
        EntradaEstoque.objects.filter(pk=entrada.pk).update(criado_em=timezone.now() - timedelta(days=dias_atras))
        return entrada

    def test_estima_o_que_ainda_esta_na_prateleira(self):
        cerveja = self.produto("Cerveja", estoque=0)
        self.entrada(cerveja, 24, -2, dias_atras=60)   # o lote mais antigo, já vencido
        self.entrada(cerveja, 24, 10, dias_atras=30)   # vence em 10 dias
        self.entrada(cerveja, 24, 200, dias_atras=1)   # recente, longe de vencer
        Produto.objects.filter(pk=cerveja.pk).update(quantidade_estoque=30)  # vendeu 42

        dados = analises.validades(dias=30)
        # 30 na prateleira: 24 do lote recente + 6 do lote de 30 dias atrás; o vencido já saiu.
        self.assertEqual(dados["vencidos"], [])
        self.assertEqual([(l["dias"], l["quantidade"]) for l in dados["vencendo"]], [(10, 6)])

        Produto.objects.filter(pk=cerveja.pk).update(quantidade_estoque=60)  # sobrou do lote vencido também
        dados = analises.validades(dias=30)
        self.assertEqual([(l["dias"], l["quantidade"]) for l in dados["vencidos"]], [(-2, 12)])

    def test_aviso_no_sino(self):
        cerveja = self.produto("Cerveja", estoque=0)
        self.entrada(cerveja, 10, 5, dias_atras=1)
        sino.sincronizar()
        aviso = Notificacao.objects.get(tipo=Notificacao.Tipo.VALIDADE, resolvida=False)
        self.assertEqual(aviso.mensagem, "Validade: 1 lote vence em até 30 dias.")
        Produto.objects.filter(pk=cerveja.pk).update(quantidade_estoque=0)  # vendeu tudo
        sino.sincronizar()
        self.assertFalse(Notificacao.objects.filter(tipo=Notificacao.Tipo.VALIDADE, resolvida=False).exists())

    def test_aba_de_compras_mostra_e_exporta(self):
        cerveja = self.produto("Cerveja", estoque=0)
        self.entrada(cerveja, 10, 3, dias_atras=1)
        self.client.force_login(self.usuario)
        self.assertContains(self.client.get(reverse("relatorios:compras")), "Vence em 3 dias")
        csv = self.client.get(reverse("relatorios:compras"), {"exportar": "validade"}).content.decode()
        self.assertIn("Cerveja;", csv)


class ComprovanteTests(Base):
    def test_formato_termico_e_linhas_de_ajuste(self):
        Configuracao.objects.update_or_create(pk=1, defaults={"formato_comprovante": "80mm"})
        cerveja = self.produto("Cerveja")
        venda = Venda.objects.create(criado_por=self.usuario, quantidade_pessoas=2)
        venda.adicionar_item(cerveja, 10)
        venda.aplicar_desconto(self.usuario, "10", "Promo")
        venda.receber(Venda.FormaPagamento.PIX)
        self.client.force_login(self.usuario)
        html = self.client.get(reverse("vendas:comprovante", kwargs={"pk": venda.pk})).content.decode()
        self.assertIn('class="termica largura-80"', html)
        self.assertIn("Desconto", html)
        self.assertIn("R$&nbsp;90,00", html)
