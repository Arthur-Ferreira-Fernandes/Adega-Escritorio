from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.caixa.models import Caixa
from apps.clientes.models import Cliente, Fornecedor
from apps.configuracoes.models import Configuracao
from apps.estoque.models import AjusteEstoque, Categoria, Produto
from apps.financeiro.models import ContaPagar
from apps.notificacoes.models import Notificacao
from apps.vendas.models import ItemRemovido, Venda

from . import analises

User = get_user_model()
FUSO = timezone.get_current_timezone()


def _local(ano, mes, dia, hora=12, minuto=0):
    return timezone.make_aware(datetime(ano, mes, dia, hora, minuto), FUSO)


class BaseAnalise(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username="ana", password="x")
        self.categoria = Categoria.objects.create(nome="Bebidas")
        self.hoje = timezone.localdate()

    def produto(self, nome, preco="10.00", custo="4.00", estoque=50, minimo=5):
        return Produto.objects.create(
            nome=nome, sku=nome.upper(), categoria=self.categoria, preco_venda=Decimal(preco),
            preco_custo=Decimal(custo), quantidade_estoque=estoque, estoque_minimo=minimo,
        )

    def vender(self, itens, quando=None, forma=Venda.FormaPagamento.DINHEIRO, usuario=None, **campos):
        """Cria e conclui uma venda. `itens` = [(produto, quantidade), ...]."""
        venda = Venda.objects.create(criado_por=usuario or self.usuario, **campos)
        for produto, quantidade in itens:
            venda.adicionar_item(produto, quantidade)
        venda.receber(forma)
        if quando:
            Venda.objects.filter(pk=venda.pk).update(finalizada_em=quando)
            venda.refresh_from_db()
        return venda


class ResumoDoDiaTests(BaseAnalise):
    def test_compara_com_o_mesmo_dia_da_semana_passada_ate_a_mesma_hora(self):
        cerveja = self.produto("Cerveja")
        agora = timezone.localtime().replace(hour=20, minute=0, second=0, microsecond=0)
        self.vender([(cerveja, 15)], quando=agora - timedelta(hours=2))  # R$ 150 hoje
        self.vender([(cerveja, 10)], quando=agora - timedelta(days=7, hours=3))  # R$ 100 até a hora
        self.vender([(cerveja, 50)], quando=agora - timedelta(days=7) + timedelta(hours=1))  # depois: não conta

        resumo = analises.resumo_do_dia(agora)
        self.assertEqual(resumo["faturamento"], Decimal("150.00"))
        self.assertEqual(resumo["faturamento_semana_passada"], Decimal("100.00"))
        self.assertEqual(resumo["variacao"], Decimal("50"))
        self.assertEqual(resumo["lucro"], Decimal("90.00"))

    def test_meta_do_mes_projeta_pelo_ritmo(self):
        Configuracao.objects.update_or_create(pk=1, defaults={"meta_faturamento_mensal": Decimal("3000")})
        cerveja = self.produto("Cerveja")
        agora = _local(2026, 4, 10, 18)  # abril tem 30 dias
        self.vender([(cerveja, 100)], quando=_local(2026, 4, 3))  # R$ 1.000 em 10 dias
        meta = analises.meta_do_mes(agora)
        self.assertEqual(meta["percentual"], Decimal("33"))
        self.assertEqual(meta["projecao"], Decimal("3000.00"))
        self.assertEqual(meta["falta"], Decimal("2000.00"))
        self.assertEqual(meta["dias_restantes"], 21)


class ProdutosTests(BaseAnalise):
    def test_curva_abc_classifica_pelo_acumulado(self):
        produtos = [self.produto(n) for n in ("A1", "A2", "B1", "C1")]
        for produto, quantidade in zip(produtos, (70, 20, 6, 4)):
            self.vender([(produto, quantidade)])
        abc = analises.curva_abc(self.hoje, self.hoje)
        classes = {l["produto__nome"]: l["classe"] for l in abc["linhas"]}
        # A2 começa em 70% (ainda abaixo de 80) e por isso é A; B1 começa em 90%.
        self.assertEqual(classes, {"A1": "A", "A2": "A", "B1": "B", "C1": "C"})
        self.assertEqual(abc["resumo"]["A"]["participacao"], Decimal("90.0"))

    def test_produtos_parados_e_dinheiro_empatado(self):
        parado = self.produto("Parado", custo="20.00", estoque=3)
        vendendo = self.produto("Vendendo")
        negativo = self.produto("Negativo", estoque=-2)
        antigo = timezone.now() - timedelta(days=40)
        Produto.objects.filter(pk__in=[parado.pk, vendendo.pk, negativo.pk]).update(criado_em=antigo)
        self.vender([(parado, 1)], quando=antigo)
        self.vender([(vendendo, 1)])

        resultado = analises.produtos_parados(30)
        por_nome = {l["produto"].nome: l for l in resultado["linhas"]}
        self.assertNotIn("Vendendo", por_nome)
        self.assertEqual(por_nome["Parado"]["capital"], Decimal("40.00"))  # sobraram 2 x R$ 20
        self.assertIsNone(por_nome["Negativo"]["ultima_venda"])
        self.assertEqual(por_nome["Negativo"]["capital"], Decimal("0.00"))

    def test_comprados_juntos_le_na_direcao_mais_forte(self):
        vodka, gelo, energetico = (self.produto(n) for n in ("Vodka", "Gelo", "Energetico"))
        for _ in range(3):
            self.vender([(vodka, 1), (gelo, 1)])
        self.vender([(gelo, 1)])
        self.vender([(vodka, 1), (energetico, 1)])
        linhas = analises.comprados_juntos(self.hoje, self.hoje)["linhas"]
        self.assertEqual(len(linhas), 1)  # vodka + energético saiu junto só 1 vez
        par = linhas[0]
        # 3 de 4 vendas de vodka levam gelo (75%); 3 de 4 de gelo levam vodka: empate fica no 1º.
        self.assertEqual((par["vezes"], par["confianca"]), (3, Decimal("75")))


class LucroRealTests(BaseAnalise):
    def test_desconta_custo_taxas_perdas_e_despesas(self):
        Configuracao.objects.update_or_create(
            pk=1, defaults={"taxa_cartao": Decimal("2.00"), "taxa_pix": Decimal("1.00")}
        )
        cerveja = self.produto("Cerveja")
        self.vender([(cerveja, 10)], forma=Venda.FormaPagamento.CARTAO)  # 100, custo 40, taxa 2
        self.vender([(cerveja, 10)], forma=Venda.FormaPagamento.PIX)  # 100, custo 40, taxa 1
        cerveja.ajustar_contagem(quantidade_contada=cerveja.quantidade_estoque - 5 - 20, usuario=self.usuario)
        fornecedor = Fornecedor.objects.create(nome="Distribuidora", documento="1")
        ContaPagar.objects.create(
            fornecedor=fornecedor, descricao="Luz", valor=Decimal("30.00"),
            vencimento=self.hoje, pago=True, pago_em=self.hoje,
        )
        dre = analises.lucro_real(self.hoje, self.hoje)
        valores = {l["rotulo"]: l["valor"] for l in dre["linhas"]}
        self.assertEqual(dre["faturamento"], Decimal("200.00"))
        self.assertEqual(dre["lucro_bruto"], Decimal("120.00"))
        self.assertEqual(dre["taxas"], Decimal("3.00"))
        self.assertEqual(valores["(−) Perdas na contagem de estoque"], Decimal("-20.00"))  # 5 x R$ 4
        self.assertEqual(dre["lucro_liquido"], Decimal("67.00"))  # 120 - 3 - 20 - 30


class MesasTests(BaseAnalise):
    def test_permanencia_e_gasto_por_pessoa(self):
        cerveja = self.produto("Cerveja")
        for minutos, pessoas, quantidade in ((30, 2, 4), (150, 4, 20)):
            venda = self.vender([(cerveja, quantidade)], identificador="Mesa", quantidade_pessoas=pessoas)
            Venda.objects.filter(pk=venda.pk).update(criado_em=venda.finalizada_em - timedelta(minutes=minutos))
        self.vender([(cerveja, 1)])  # balcão: não entra

        mesas = analises.analise_mesas(self.hoje, self.hoje)
        self.assertEqual(mesas["quantidade"], 2)
        self.assertEqual(mesas["por_pessoa"], Decimal("40.00"))  # 240 / 6 pessoas
        self.assertEqual(mesas["permanencia_media"], "1h30")
        faixas = {l["rotulo"]: l["mesas"] for l in mesas["por_permanencia"]}
        self.assertEqual((faixas["Até 1h"], faixas["2h a 3h"]), (1, 1))
        self.assertEqual(mesas["por_hora_de_mesa"], Decimal("80.00"))  # 240 / 3h


class EquipeTests(BaseAnalise):
    def test_cancelamentos_remocoes_e_quebra_de_caixa_por_pessoa(self):
        bia = User.objects.create_user(username="bia", password="x")
        cerveja = self.produto("Cerveja")
        caixa = Caixa.abrir(self.usuario, Decimal("100"))
        self.vender([(cerveja, 5)], usuario=bia)

        venda = Venda.objects.create(criado_por=self.usuario)
        item = venda.adicionar_item(cerveja, 2)
        venda.remover_item(item, usuario=bia)
        venda.adicionar_item(cerveja, 1)
        venda.cancelar(usuario=bia)
        Venda.objects.create(criado_por=bia).cancelar(usuario=bia)  # vazia: não conta

        caixa.fechar(self.usuario, Decimal("140"))  # esperado 150: falta 10

        linhas = {l["usuario"].username: l for l in analises.desempenho_equipe(self.hoje, self.hoje)["linhas"]}
        self.assertEqual(linhas["bia"]["vendas"], 1)
        self.assertEqual((linhas["bia"]["canceladas"], linhas["bia"]["valor_cancelado"]), (1, Decimal("10.00")))
        self.assertEqual((linhas["bia"]["removidos"], linhas["bia"]["valor_removido"]), (1, Decimal("20.00")))
        self.assertEqual(linhas["bia"]["taxa_cancelamento"], Decimal("50"))
        self.assertEqual(linhas["ana"]["faltas"], Decimal("-10.00"))
        self.assertTrue(ItemRemovido.objects.filter(removido_por=bia).exists())


class ClientesTests(BaseAnalise):
    def test_melhores_sumidos_e_link_do_whatsapp(self):
        cerveja = self.produto("Cerveja")
        fiel = Cliente.objects.create(nome="Fiel", documento="1", telefone="(11) 98888-7777")
        sumido = Cliente.objects.create(nome="Sumido", documento="2", telefone="")
        self.vender([(cerveja, 5)], cliente=fiel)
        self.vender([(cerveja, 3)], cliente=fiel, quando=timezone.now() - timedelta(days=60))
        self.vender([(cerveja, 9)], cliente=sumido, quando=timezone.now() - timedelta(days=45))

        dados = analises.analise_clientes(self.hoje, self.hoje, dias_sumido=30)
        self.assertEqual([c["cliente"] for c in dados["melhores"]], [fiel])
        self.assertEqual(dados["melhores"][0]["whatsapp"], "https://wa.me/5511988887777")
        self.assertEqual((dados["novos"], dados["recorrentes"]), (0, 1))
        self.assertEqual([c["cliente"] for c in dados["sumidos"]], [sumido])


class PrevisaoComprasTests(BaseAnalise):
    def test_sugere_compra_pelo_ritmo_e_agrupa_pelo_ultimo_fornecedor(self):
        Configuracao.objects.update_or_create(pk=1, defaults={"dias_cobertura_compra": 7})
        antigo = Fornecedor.objects.create(nome="Antigo", documento="1")
        atual = Fornecedor.objects.create(nome="Atual", documento="2")
        cerveja = self.produto("Cerveja", estoque=0, minimo=5)
        for fornecedor in (antigo, atual):
            cerveja.registrar_entrada(quantidade=35, fornecedor=fornecedor, custo_unitario=Decimal("4"), usuario=self.usuario)
        self.vender([(cerveja, 60)])  # 60 em 30 dias = 2 por dia; sobram 10
        self.produto("Parado", estoque=50)

        previsao = analises.previsao_de_compras(dias_base=30)
        self.assertEqual([g["fornecedor"] for g in previsao["fornecedores"]], ["Atual"])
        item = previsao["fornecedores"][0]["itens"][0]
        self.assertEqual((item["dias_restantes"], item["comprar"]), (5, 9))  # 2x7 + 5 - 10
        self.assertEqual(item["custo_estimado"], Decimal("36.00"))

    def test_estoque_negativo_conta_como_zero_e_pede_conferencia(self):
        Configuracao.objects.update_or_create(pk=1, defaults={"dias_cobertura_compra": 7})
        cerveja = self.produto("Cerveja", estoque=0, minimo=5)
        self.vender([(cerveja, 60)])  # estoque vai a -60
        item = analises.previsao_de_compras(dias_base=30)["fornecedores"][0]["itens"][0]
        self.assertEqual((item["estoque"], item["comprar"], item["conferir"]), (-60, 19, True))  # 2x7 + 5


class TelasTests(BaseAnalise):
    def setUp(self):
        super().setUp()
        self.dono = User.objects.create_superuser(username="dono", password="x")
        self.client.force_login(self.dono)

    def test_todas_as_abas_abrem_e_exportam(self):
        cerveja = self.produto("Cerveja")
        self.vender([(cerveja, 3)], identificador="Mesa 1", quantidade_pessoas=2)
        abas = {
            "horarios": "horarios", "produtos": "abc", "lucro": "lucro", "mesas": "mesas",
            "equipe": "equipe", "clientes": "melhores", "compras": "compras",
        }
        for aba, tabela in abas.items():
            url = reverse(f"relatorios:{aba}")
            self.assertEqual(self.client.get(url, {"periodo": "7"}).status_code, 200, aba)
            resposta = self.client.get(url, {"periodo": "7", "exportar": tabela})
            self.assertEqual(resposta["Content-Type"], "text/csv; charset=utf-8", aba)
            self.assertTrue(resposta.content.startswith("﻿".encode()), aba)

    def test_equipe_e_so_para_administrador(self):
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get(reverse("relatorios:equipe")).status_code, 302)
        self.assertEqual(self.client.get(reverse("relatorios:horarios")).status_code, 200)

    def test_inicio_do_dono_mostra_resumo_e_atencao(self):
        self.produto("Faltando", estoque=-3)
        resposta = self.client.get(reverse("inicio"))
        self.assertContains(resposta, "Meta do mês")
        self.assertContains(resposta, "1 produto com estoque negativo")
        self.client.force_login(self.usuario)
        self.assertNotContains(self.client.get(reverse("inicio")), "Meta do mês")

    def test_faturamento_de_hoje_continua_certo_depois_das_21h(self):
        # 23h40 em Brasília já é o dia seguinte em UTC: "hoje" tem que ser a data local.
        noite = timezone.now().astimezone(FUSO).replace(hour=23, minute=40)
        cerveja = self.produto("Cerveja")
        self.vender([(cerveja, 3)], quando=noite.replace(hour=22))
        # O relógio do Django devolve em UTC, como o de verdade.
        with mock.patch("django.utils.timezone.now", return_value=noite.astimezone(dt_timezone.utc)):
            resposta = self.client.get(reverse("inicio"))
        self.assertEqual(resposta.context["faturamento_hoje"], Decimal("30.00"))
        self.assertEqual(resposta.context["resumo"]["faturamento"], Decimal("30.00"))

    def test_contagem_ajusta_estoque_e_registra_a_perda(self):
        cerveja = self.produto("Cerveja", estoque=10)
        igual = self.produto("Igual", estoque=4)
        resposta = self.client.post(
            reverse("estoque:contagem"),
            {f"contado_{cerveja.pk}": "7", f"contado_{igual.pk}": "4"},
            follow=True,
        )
        cerveja.refresh_from_db()
        self.assertEqual(cerveja.quantidade_estoque, 7)
        ajuste = AjusteEstoque.objects.get()
        self.assertEqual((ajuste.produto, ajuste.diferenca, ajuste.criado_por), (cerveja, -3, self.dono))
        self.assertContains(resposta, "Faltaram 3 unidades")

    def test_codigo_desconhecido_oferece_cadastro_e_ja_adiciona(self):
        Caixa.abrir(self.dono, Decimal("0"))
        venda = Venda.objects.create(criado_por=self.dono)
        url = reverse("vendas:escanear", kwargs={"pk": venda.pk})
        resposta = self.client.post(url, {"codigo_barras": "7890001"}, HTTP_HX_REQUEST="true")
        self.assertContains(resposta, "Código 7890001 não cadastrado")

        self.client.post(
            reverse("vendas:cadastro_rapido", kwargs={"pk": venda.pk}),
            {"codigo_barras": "7890001", "nome": "Gelo 5kg", "categoria": self.categoria.pk,
             "preco_venda": "R$ 12,00", "preco_custo": "R$ 5,00"},
            HTTP_HX_REQUEST="true",
        )
        produto = Produto.objects.get(codigo_barras="7890001")
        self.assertEqual(produto.sku, "7890001")
        self.assertEqual(venda.itens.get().produto, produto)

    def test_fechar_caixa_deixa_resumo_no_sino(self):
        cerveja = self.produto("Cerveja")
        Caixa.abrir(self.dono, Decimal("50"))
        self.vender([(cerveja, 3)])
        self.client.post(reverse("caixa:fechar"), {"valor_contado": "R$ 80,00"})
        notificacao = Notificacao.objects.get(tipo=Notificacao.Tipo.RESUMO_CAIXA, resolvida=False)
        self.assertIn("R$ 30,00 em 1 venda,", notificacao.mensagem)
        self.assertIn("caixa sem diferença", notificacao.mensagem)

    def test_exporta_historico_de_vendas_e_produtos(self):
        cerveja = self.produto("Cerveja")
        self.vender([(cerveja, 2)])
        vendas = self.client.get(reverse("vendas:historico"), {"exportar": "1"}).content.decode()
        self.assertIn("Cerveja;Bebidas;2;10,00;20,00;4,00;12,00", vendas)
        produtos = self.client.get(reverse("estoque:produtos"), {"exportar": "1"}).content.decode()
        self.assertIn("Cerveja;CERVEJA;;Bebidas;4,00;10,00;60,00;48", produtos)
