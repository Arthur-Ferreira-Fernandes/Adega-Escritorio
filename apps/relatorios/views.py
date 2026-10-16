import json
from datetime import timedelta

from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render
from django.utils import timezone

from . import analises
from .exportar import resposta_csv
from .forms import FiltroRelatorioForm
from .periodo import ATALHOS, ler_periodo
from .servicos import calcular_metricas


def _json_seguro(dados):
    return json.dumps(dados).replace("<", "\\u003c")


@login_required
def dashboard(request):
    form = FiltroRelatorioForm(request.GET or None)
    hoje = timezone.localdate()
    data_inicio = hoje - timedelta(days=30)
    data_fim = hoje
    categoria = None
    forma_pagamento = ""

    if form.is_valid():
        data_inicio = form.cleaned_data.get("data_inicio") or data_inicio
        data_fim = form.cleaned_data.get("data_fim") or data_fim
        categoria = form.cleaned_data.get("categoria")
        forma_pagamento = form.cleaned_data.get("forma_pagamento") or ""

    metricas = calcular_metricas(data_inicio, data_fim, categoria, forma_pagamento)

    contexto = {
        "aba": "geral",
        "form": form,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        **metricas,
        "faturamento_por_dia_json": _json_seguro(
            [
                {"rotulo": i["dia"].strftime("%d/%m"), "valor": float(i["total"])}
                for i in metricas["faturamento_por_dia"]
            ]
        ),
        "produtos_mais_vendidos_json": _json_seguro(
            [
                {"rotulo": p["produto__nome"], "valor": float(p["valor"])}
                for p in metricas["produtos_mais_vendidos"]
            ]
        ),
        "produtos_lucro_json": _json_seguro(
            [
                {"rotulo": p["produto__nome"], "valor": float(p["lucro"])}
                for p in metricas["produtos_lucro"]
            ]
        ),
    }

    template = (
        "relatorios/_conteudo.html"
        if request.headers.get("HX-Request") == "true"
        else "relatorios/dashboard.html"
    )
    return render(request, template, contexto)


# Abas de análise -------------------------------------------------------------


def _somente_dono(user):
    return user.is_superuser


def _analise(request, template, aba, contexto):
    return render(request, f"relatorios/{template}.html", {"aba": aba, **contexto})


def _base(request, padrao="30"):
    inicio, fim, form, atalho = ler_periodo(request, padrao)
    return {
        "inicio": inicio,
        "fim": fim,
        "periodo_form": form,
        "atalho": atalho,
        "atalhos": ATALHOS,
        "sufixo": f"{inicio:%Y-%m-%d}_a_{fim:%Y-%m-%d}",
        # Mantém o período ao trocar de aba ou exportar.
        "periodo_qs": f"periodo={atalho}" if atalho else f"data_inicio={inicio:%Y-%m-%d}&data_fim={fim:%Y-%m-%d}",
    }


@login_required
def horarios(request):
    base = _base(request, "90")
    mapa = analises.mapa_de_horarios(base["inicio"], base["fim"])
    if request.GET.get("exportar") == "horarios":
        return resposta_csv(
            f"vendas_por_horario_{base['sufixo']}",
            ["Dia"] + [f"{hora:02d}h" for hora in mapa["horas"]] + ["Total"],
            [[l["dia"], *[c["valor"] for c in l["celulas"]], l["total"]] for l in mapa["linhas"]],
        )
    return _analise(request, "horarios", "horarios", {**base, "mapa": mapa})


@login_required
def produtos(request):
    base = _base(request)
    dias_parado = int(request.GET.get("parado", 30)) if request.GET.get("parado", "30").isdigit() else 30
    abc = analises.curva_abc(base["inicio"], base["fim"])
    parados = analises.produtos_parados(dias_parado)
    juntos = analises.comprados_juntos(base["inicio"], base["fim"])
    exportar = request.GET.get("exportar")
    if exportar == "abc":
        return resposta_csv(
            f"curva_abc_{base['sufixo']}",
            ["Classe", "Produto", "Categoria", "Quantidade", "Faturamento", "% do faturamento", "% acumulado", "Estoque"],
            [[l["classe"], l["produto__nome"], l["produto__categoria__nome"], l["quantidade"], l["faturamento"],
              l["participacao"], l["acumulado"], l["produto__quantidade_estoque"]] for l in abc["linhas"]],
        )
    if exportar == "parados":
        return resposta_csv(
            f"produtos_parados_{dias_parado}_dias",
            ["Produto", "Categoria", "Última venda", "Dias parado", "Estoque", "Dinheiro parado (custo)"],
            [[l["produto"].nome, l["produto"].categoria, l["ultima_venda"] or "Nunca vendido", l["dias_parado"],
              l["estoque"], l["capital"]] for l in parados["linhas"]],
        )
    if exportar == "juntos":
        return resposta_csv(
            f"comprados_juntos_{base['sufixo']}",
            ["Quem leva", "Também leva", "Vendas juntos", "Vendas do produto", "% das vezes"],
            [[l["produto"], l["leva_tambem"], l["vezes"], l["vendas_produto"], l["confianca"]] for l in juntos["linhas"]],
        )
    return _analise(request, "produtos", "produtos", {
        **base, "abc": abc, "parados": parados, "juntos": juntos,
        "dias_parado": dias_parado, "opcoes_parado": [15, 30, 60, 90],
    })


@login_required
def lucro(request):
    base = _base(request, "mes")
    dre = analises.lucro_real(base["inicio"], base["fim"])
    if request.GET.get("exportar") == "lucro":
        return resposta_csv(
            f"lucro_real_{base['sufixo']}",
            ["Linha", "Valor", "% do faturamento"],
            [[l["rotulo"], l["valor"], l["percentual"]] for l in dre["linhas"]]
            + [[], ["Forma de pagamento", "Recebido", "Taxa (%)", "Taxa (R$)"]]
            + [[f["forma"], f["valor"], f["taxa_percentual"], f["taxa"]] for f in dre["por_forma"]],
        )
    return _analise(request, "lucro", "lucro", {**base, "dre": dre})


@login_required
def mesas(request):
    base = _base(request)
    dados = analises.analise_mesas(base["inicio"], base["fim"])
    if request.GET.get("exportar") == "mesas" and dados["quantidade"]:
        return resposta_csv(
            f"mesas_{base['sufixo']}",
            ["Agrupamento", "Faixa", "Mesas", "Ticket médio", "Por pessoa"],
            [["Permanência", l["rotulo"], l["mesas"], l["ticket"], l["por_pessoa"]] for l in dados["por_permanencia"]]
            + [["Tamanho", l["rotulo"], l["mesas"], l["ticket"], l["por_pessoa"]] for l in dados["por_pessoas"]],
        )
    return _analise(request, "mesas", "mesas", {**base, "mesas": dados})


@login_required
@user_passes_test(_somente_dono)
def equipe(request):
    base = _base(request)
    dados = analises.desempenho_equipe(base["inicio"], base["fim"])
    exportar = request.GET.get("exportar")
    if exportar == "equipe":
        return resposta_csv(
            f"equipe_{base['sufixo']}",
            ["Atendente", "Vendas", "Faturamento", "Ticket médio", "Canceladas", "Valor cancelado",
             "% cancelamento", "Itens removidos", "Valor removido", "Caixas fechados", "Diferença de caixa"],
            [[l["usuario"], l["vendas"], l["faturamento"], l["ticket_medio"], l["canceladas"], l["valor_cancelado"],
              l["taxa_cancelamento"], l["removidos"], l["valor_removido"], l["fechamentos"], l["diferenca"]]
             for l in dados["linhas"]],
        )
    if exportar == "caixas":
        return resposta_csv(
            f"quebra_de_caixa_{base['sufixo']}",
            ["Fechado em", "Fechado por", "Esperado", "Contado", "Diferença"],
            [[l["fechado_em"], l["caixa"].fechado_por, l["esperado"], l["contado"], l["diferenca"]]
             for l in dados["caixas"]["linhas"]],
        )
    return _analise(request, "equipe", "equipe", {**base, "equipe": dados})


@login_required
def clientes(request):
    base = _base(request)
    dias_sumido = int(request.GET.get("sumido", 30)) if request.GET.get("sumido", "30").isdigit() else 30
    dados = analises.analise_clientes(base["inicio"], base["fim"], dias_sumido)
    exportar = request.GET.get("exportar")
    colunas = ["Cliente", "Telefone", "Compras no período", "Gasto no período", "Compras no total",
               "Gasto total", "Ticket médio", "Última compra", "Dias sem comprar"]

    def linha(c):
        return [c["cliente"].nome, c["cliente"].telefone, c["compras_periodo"], c["gasto_periodo"],
                c["compras_total"], c["gasto_total"], c["ticket"], c["ultima_compra"], c["dias_sem_comprar"]]

    if exportar == "melhores":
        return resposta_csv(f"melhores_clientes_{base['sufixo']}", colunas, map(linha, dados["melhores"]))
    if exportar == "sumidos":
        return resposta_csv(f"clientes_sumidos_{dias_sumido}_dias", colunas, map(linha, dados["sumidos"]))
    return _analise(request, "clientes", "clientes", {
        **base, "clientes": dados, "opcoes_sumido": [15, 30, 60, 90],
    })


@login_required
def compras(request):
    base = _base(request)
    previsao = analises.previsao_de_compras()
    perdas = analises.perdas_de_estoque(base["inicio"], base["fim"])
    exportar = request.GET.get("exportar")
    if exportar == "compras":
        return resposta_csv(
            f"lista_de_compras_{timezone.localdate():%Y-%m-%d}",
            ["Fornecedor", "Produto", "Estoque", "Vende por dia", "Acaba em (dias)", "Comprar", "Custo estimado"],
            [[g["fornecedor"], i["produto"].nome, i["estoque"], i["media_dia"], i["dias_restantes"],
              i["comprar"], i["custo_estimado"]] for g in previsao["fornecedores"] for i in g["itens"]],
        )
    if exportar == "perdas":
        return resposta_csv(
            f"perdas_de_estoque_{base['sufixo']}",
            ["Produto", "Ajustes", "Unidades (diferença)", "Valor (custo)"],
            [[l["produto"].nome, l["ajustes"], l["diferenca"], l["valor"]] for l in perdas["linhas"]],
        )
    return _analise(request, "compras", "compras", {**base, "previsao": previsao, "perdas": perdas})
