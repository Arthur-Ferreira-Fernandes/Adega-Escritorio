"""Cálculos dos insights para o dono (tela inicial e abas de análise dos relatórios).

Tudo trabalha sobre vendas concluídas pela data de finalização, no fuso local.
O volume de uma adega é pequeno, então várias análises agregam em Python, o que
mantém o fuso horário correto tanto no SQLite (desktop) quanto no Postgres.
"""

import calendar
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal
from itertools import combinations

from django.contrib.auth import get_user_model
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Max, Min, Sum
from django.utils import timezone

from apps.caixa.models import Caixa
from apps.clientes.models import Cliente
from apps.configuracoes.models import Configuracao
from apps.estoque.models import AjusteEstoque, EntradaEstoque, Produto
from apps.financeiro.models import ContaPagar
from apps.vendas.models import ItemRemovido, ItemVenda, PagamentoVenda, Venda
from config.agregados import Soma

ZERO = Decimal("0")
DIAS_SEMANA = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
DIAS_SEMANA_COMPLETOS = [
    "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
    "sexta-feira", "sábado", "domingo",
]

LUCRO_ITEM = ExpressionWrapper(
    F("subtotal") - F("custo_unitario") * F("quantidade"),
    output_field=DecimalField(max_digits=12, decimal_places=2),
)


def _q(valor):
    return Decimal(valor).quantize(Decimal("0.01"))


def _pct(parte, todo, casas="0.1"):
    if not todo:
        return ZERO
    return (Decimal(parte) / Decimal(todo) * 100).quantize(Decimal(casas))


def _soma(queryset, campo):
    return queryset.aggregate(t=Soma(campo))["t"] or ZERO


def vendas_concluidas(inicio, fim):
    return Venda.objects.filter(
        status=Venda.Status.CONCLUIDA,
        finalizada_em__date__gte=inicio,
        finalizada_em__date__lte=fim,
    )


def itens_concluidos(inicio, fim):
    return ItemVenda.objects.filter(
        venda__status=Venda.Status.CONCLUIDA,
        venda__finalizada_em__date__gte=inicio,
        venda__finalizada_em__date__lte=fim,
    )


def _lucro(itens):
    return _soma(itens.filter(custo_unitario__isnull=False).annotate(l=LUCRO_ITEM), "l")


def _inicio_do_dia(data):
    return timezone.make_aware(datetime.combine(data, time.min))


# Tela inicial ----------------------------------------------------------------


def resumo_do_dia(agora=None):
    """Indicadores do dia comparados com o mesmo dia da semana passada, até a mesma hora."""
    agora = timezone.localtime(agora)
    hoje = agora.date()
    semana_passada = agora - timedelta(days=7)

    vendas_hoje = Venda.objects.filter(
        status=Venda.Status.CONCLUIDA, finalizada_em__gte=_inicio_do_dia(hoje), finalizada_em__lte=agora
    )
    vendas_semana_passada = Venda.objects.filter(
        status=Venda.Status.CONCLUIDA,
        finalizada_em__gte=_inicio_do_dia(semana_passada.date()),
        finalizada_em__lte=semana_passada,
    )
    faturamento = _soma(vendas_hoje, "total")
    faturamento_antes = _soma(vendas_semana_passada, "total")
    numero_vendas = vendas_hoje.count()
    lucro = _lucro(ItemVenda.objects.filter(venda__in=vendas_hoje))
    abertas = Venda.objects.filter(status=Venda.Status.ABERTA)

    variacao = None
    if faturamento_antes:
        variacao = ((faturamento - faturamento_antes) / faturamento_antes * 100).quantize(Decimal("1"))

    return {
        "faturamento": faturamento,
        "faturamento_semana_passada": faturamento_antes,
        "variacao": variacao,
        "dia_comparado": DIAS_SEMANA_COMPLETOS[semana_passada.weekday()],
        "numero_vendas": numero_vendas,
        "ticket_medio": _q(faturamento / numero_vendas) if numero_vendas else ZERO,
        "lucro": lucro,
        "margem": _pct(lucro, faturamento),
        "comandas_abertas": abertas.count(),
        "valor_em_aberto": _soma(abertas, "total"),
        "meta": meta_do_mes(agora),
    }


def meta_do_mes(agora=None):
    agora = timezone.localtime(agora)
    meta = Configuracao.obter().meta_faturamento_mensal
    hoje = agora.date()
    dias_no_mes = calendar.monthrange(hoje.year, hoje.month)[1]
    faturamento = _soma(
        vendas_concluidas(hoje.replace(day=1), hoje), "total"
    )
    # Projeção pelo ritmo até agora (dias corridos, contando hoje como dia inteiro).
    projecao = _q(faturamento / hoje.day * dias_no_mes)
    dias_restantes = dias_no_mes - hoje.day + 1
    falta = max(meta - faturamento, ZERO)
    return {
        "ativa": meta > 0,
        "valor": meta,
        "faturamento": faturamento,
        "percentual": _pct(faturamento, meta, "1") if meta else ZERO,
        "percentual_barra": min(_pct(faturamento, meta, "1"), Decimal("100")) if meta else ZERO,
        "projecao": projecao,
        "projecao_percentual": _pct(projecao, meta, "1") if meta else ZERO,
        "falta": falta,
        "por_dia_necessario": _q(falta / dias_restantes) if falta else ZERO,
        "dias_restantes": dias_restantes,
    }


# Horários --------------------------------------------------------------------


def mapa_de_horarios(inicio, fim):
    celulas = defaultdict(lambda: {"valor": ZERO, "vendas": 0})
    for finalizada_em, total in vendas_concluidas(inicio, fim).values_list("finalizada_em", "total"):
        local = timezone.localtime(finalizada_em)
        celula = celulas[(local.weekday(), local.hour)]
        celula["valor"] += total
        celula["vendas"] += 1

    if not celulas:
        return {"linhas": [], "horas": [], "destaques": {}}

    horas = list(range(min(h for _, h in celulas), max(h for _, h in celulas) + 1))
    maior = max(c["valor"] for c in celulas.values())
    linhas = []
    for dia, nome in enumerate(DIAS_SEMANA):
        linha = []
        for hora in horas:
            celula = celulas.get((dia, hora), {"valor": ZERO, "vendas": 0})
            linha.append({
                "hora": hora,
                "valor": celula["valor"],
                "vendas": celula["vendas"],
                "intensidade": int(celula["valor"] / maior * 100) if maior else 0,
            })
        linhas.append({"dia": nome, "celulas": linha, "total": sum(c["valor"] for c in linha)})

    por_hora = defaultdict(lambda: ZERO)
    for (_, hora), celula in celulas.items():
        por_hora[hora] += celula["valor"]
    melhor_hora = max(por_hora, key=por_hora.get)
    dias_com_venda = [linha for linha in linhas if linha["total"]]
    melhor_dia = max(dias_com_venda, key=lambda linha: linha["total"])
    pior_dia = min(dias_com_venda, key=lambda linha: linha["total"])
    pico = max(celulas.items(), key=lambda item: item[1]["valor"])

    return {
        "linhas": linhas,
        "horas": horas,
        "destaques": {
            "melhor_hora": f"{melhor_hora:02d}h–{melhor_hora + 1:02d}h",
            "melhor_dia": melhor_dia["dia"],
            "pior_dia": pior_dia["dia"],
            "pico": f"{DIAS_SEMANA[pico[0][0]]} {pico[0][1]:02d}h",
            "pico_valor": pico[1]["valor"],
        },
    }


# Produtos --------------------------------------------------------------------


def curva_abc(inicio, fim):
    """Classe A: produtos que somam 80% do faturamento; B: até 95%; C: o resto."""
    linhas = list(
        itens_concluidos(inicio, fim)
        .values("produto_id", "produto__nome", "produto__categoria__nome", "produto__quantidade_estoque")
        .annotate(quantidade=Sum("quantidade"), faturamento=Soma("subtotal"))
        .order_by("-faturamento", "produto__nome")
    )
    total = sum((linha["faturamento"] for linha in linhas), ZERO)
    acumulado = ZERO
    resumo = {classe: {"produtos": 0, "faturamento": ZERO} for classe in "ABC"}
    for linha in linhas:
        # A classe vem do acumulado ANTES do produto: o que cruza a linha dos 80% ainda é A.
        anterior = _pct(acumulado, total)
        classe = "A" if anterior < 80 else "B" if anterior < 95 else "C"
        acumulado += linha["faturamento"]
        linha.update(
            classe=classe,
            participacao=_pct(linha["faturamento"], total),
            acumulado=_pct(acumulado, total),
        )
        resumo[classe]["produtos"] += 1
        resumo[classe]["faturamento"] += linha["faturamento"]
    for dados in resumo.values():
        dados["participacao"] = _pct(dados["faturamento"], total)
    return {"linhas": linhas, "resumo": resumo, "total": total}


def produtos_parados(dias, hoje=None):
    """Produtos ativos sem venda há `dias` dias e o dinheiro parado neles."""
    hoje = hoje or timezone.localdate()
    corte = hoje - timedelta(days=dias)
    ultima_venda = dict(
        ItemVenda.objects.filter(venda__status=Venda.Status.CONCLUIDA)
        .values("produto_id")
        .annotate(ultima=Max("venda__finalizada_em"))
        .values_list("produto_id", "ultima")
    )
    linhas = []
    for produto in Produto.objects.filter(ativo=True).select_related("categoria"):
        ultima = ultima_venda.get(produto.pk)
        ultima_data = timezone.localtime(ultima).date() if ultima else None
        referencia = ultima_data or timezone.localtime(produto.criado_em).date()
        if referencia > corte:
            continue
        estoque = max(produto.quantidade_estoque, 0)
        linhas.append({
            "produto": produto,
            "ultima_venda": ultima_data,
            "dias_parado": (hoje - referencia).days,
            "estoque": produto.quantidade_estoque,
            "capital": _q(estoque * produto.preco_custo),
        })
    linhas.sort(key=lambda linha: (-linha["capital"], -linha["dias_parado"]))
    return {"linhas": linhas, "capital_total": sum((l["capital"] for l in linhas), ZERO)}


def comprados_juntos(inicio, fim, limite=15):
    """Pares de produtos que aparecem na mesma venda, com a força da relação."""
    produtos_por_venda = defaultdict(set)
    for venda_id, produto_id in itens_concluidos(inicio, fim).values_list("venda_id", "produto_id"):
        produtos_por_venda[venda_id].add(produto_id)

    vendas_com = Counter()
    pares = Counter()
    for produtos in produtos_por_venda.values():
        vendas_com.update(produtos)
        pares.update(combinations(sorted(produtos), 2))

    nomes = dict(Produto.objects.filter(pk__in=vendas_com).values_list("pk", "nome"))
    linhas = []
    for (a, b), juntos in pares.items():
        if juntos < 2:
            continue
        # Lê na direção mais forte: "quem leva A também leva B em X% das vezes".
        if juntos / vendas_com[a] >= juntos / vendas_com[b]:
            base, junto = a, b
        else:
            base, junto = b, a
        linhas.append({
            "produto": nomes[base],
            "leva_tambem": nomes[junto],
            "vezes": juntos,
            "vendas_produto": vendas_com[base],
            "confianca": _pct(juntos, vendas_com[base], "1"),
        })
    linhas.sort(key=lambda linha: (-linha["vezes"], -linha["confianca"], linha["produto"]))
    return {"linhas": linhas[:limite], "vendas_analisadas": len(produtos_por_venda)}


# Financeiro ------------------------------------------------------------------


def lucro_real(inicio, fim):
    """DRE simplificado do período: do faturamento até o lucro líquido."""
    config = Configuracao.obter()
    vendas = vendas_concluidas(inicio, fim)
    itens = ItemVenda.objects.filter(venda__in=vendas)
    faturamento = _soma(vendas, "total")
    cmv = _soma(
        itens.filter(custo_unitario__isnull=False).annotate(
            c=ExpressionWrapper(
                F("custo_unitario") * F("quantidade"),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        ),
        "c",
    )
    sem_custo = itens.filter(custo_unitario__isnull=True).count()

    taxas_percentuais = {
        Venda.FormaPagamento.DINHEIRO: ZERO,
        Venda.FormaPagamento.CARTAO: config.taxa_cartao,
        Venda.FormaPagamento.PIX: config.taxa_pix,
    }
    por_forma = []
    taxas = ZERO
    recebido = dict(
        PagamentoVenda.objects.filter(venda__in=vendas)
        .values("forma_pagamento")
        .annotate(t=Soma("valor"))
        .values_list("forma_pagamento", "t")
    )
    for forma, rotulo in Venda.FormaPagamento.choices:
        valor = recebido.get(forma) or ZERO
        taxa = _q(valor * taxas_percentuais[forma] / 100)
        taxas += taxa
        por_forma.append({
            "forma": rotulo,
            "valor": valor,
            "participacao": _pct(valor, faturamento),
            "taxa_percentual": taxas_percentuais[forma],
            "taxa": taxa,
        })

    # Só a perda entra: sobra na contagem é, quase sempre, mercadoria que chegou
    # sem entrada registrada (estoque negativo corrigido), não lucro.
    ajustes = AjusteEstoque.objects.filter(
        criado_em__date__gte=inicio, criado_em__date__lte=fim, diferenca__lt=0
    )
    perdas = _q(-sum((a.valor_diferenca for a in ajustes), ZERO))
    despesas = _soma(
        ContaPagar.objects.filter(pago=True, pago_em__gte=inicio, pago_em__lte=fim), "valor"
    )

    lucro_bruto = faturamento - cmv
    lucro_liquido = lucro_bruto - taxas - perdas - despesas
    linhas = [
        {"rotulo": "Faturamento", "valor": faturamento, "tipo": "total"},
        {"rotulo": "(−) Custo dos produtos vendidos", "valor": -cmv, "tipo": "saida"},
        {"rotulo": "= Lucro bruto", "valor": lucro_bruto, "tipo": "subtotal"},
        {"rotulo": "(−) Taxas de cartão e Pix", "valor": -taxas, "tipo": "saida"},
        {"rotulo": "(−) Perdas na contagem de estoque", "valor": -perdas, "tipo": "saida"},
        {"rotulo": "(−) Despesas pagas (contas a pagar)", "valor": -despesas, "tipo": "saida"},
        {"rotulo": "= Lucro líquido", "valor": lucro_liquido, "tipo": "resultado"},
    ]
    for linha in linhas:
        linha["percentual"] = _pct(linha["valor"], faturamento)
    return {
        "linhas": linhas,
        "por_forma": por_forma,
        "faturamento": faturamento,
        "lucro_bruto": lucro_bruto,
        "lucro_liquido": lucro_liquido,
        "margem_bruta": _pct(lucro_bruto, faturamento),
        "margem_liquida": _pct(lucro_liquido, faturamento),
        "taxas": taxas,
        "itens_sem_custo": sem_custo,
        "taxas_configuradas": bool(config.taxa_cartao or config.taxa_pix),
    }


# Mesas -----------------------------------------------------------------------

# (a partir de, até antes de, rótulo)
FAIXAS_PERMANENCIA = [(0, 60, "Até 1h"), (60, 120, "1h a 2h"), (120, 180, "2h a 3h"), (180, None, "Mais de 3h")]
FAIXAS_PESSOAS = [(1, 3, "1 a 2 pessoas"), (3, 5, "3 a 4 pessoas"), (5, None, "5 ou mais")]


def _faixa(valor, faixas):
    for inicio, fim, rotulo in faixas:
        if valor >= inicio and (fim is None or valor < fim):
            return rotulo
    return faixas[0][2]


def _duracao(minutos):
    minutos = int(minutos)
    return f"{minutos // 60}h{minutos % 60:02d}" if minutos >= 60 else f"{minutos} min"


def analise_mesas(inicio, fim):
    mesas = list(
        vendas_concluidas(inicio, fim).exclude(identificador="")
        .values("total", "quantidade_pessoas", "criado_em", "finalizada_em")
    )
    if not mesas:
        return {"quantidade": 0}

    def agrupar(chave, faixas):
        grupos = {rotulo: [] for _, _, rotulo in faixas}
        for mesa in mesas:
            valor = chave(mesa)
            if valor is not None:
                grupos[_faixa(valor, faixas)].append(mesa)
        linhas = []
        for rotulo, itens in grupos.items():
            pessoas = sum(m["quantidade_pessoas"] or 0 for m in itens)
            total = sum((m["total"] for m in itens), ZERO)
            linhas.append({
                "rotulo": rotulo,
                "mesas": len(itens),
                "ticket": _q(total / len(itens)) if itens else ZERO,
                "por_pessoa": _q(total / pessoas) if pessoas else None,
            })
        return linhas

    for mesa in mesas:
        mesa["minutos"] = max((mesa["finalizada_em"] - mesa["criado_em"]).total_seconds() / 60, 1)

    faturamento = sum((m["total"] for m in mesas), ZERO)
    com_pessoas = [m for m in mesas if m["quantidade_pessoas"]]
    pessoas = sum(m["quantidade_pessoas"] for m in com_pessoas)
    horas = Decimal(sum(m["minutos"] for m in mesas) / 60)
    return {
        "quantidade": len(mesas),
        "faturamento": faturamento,
        "ticket_medio": _q(faturamento / len(mesas)),
        "por_pessoa": _q(sum((m["total"] for m in com_pessoas), ZERO) / pessoas) if pessoas else None,
        "permanencia_media": _duracao(sum(m["minutos"] for m in mesas) / len(mesas)),
        "por_hora_de_mesa": _q(faturamento / horas) if horas else ZERO,
        "por_permanencia": agrupar(lambda m: m["minutos"], FAIXAS_PERMANENCIA),
        "por_pessoas": agrupar(lambda m: m["quantidade_pessoas"], FAIXAS_PESSOAS),
    }


# Equipe ----------------------------------------------------------------------


def desempenho_equipe(inicio, fim):
    usuarios = {u.pk: u for u in get_user_model().objects.all()}
    dados = defaultdict(lambda: {
        "vendas": 0, "faturamento": ZERO, "canceladas": 0, "valor_cancelado": ZERO,
        "removidos": 0, "valor_removido": ZERO,
    })

    for linha in (
        vendas_concluidas(inicio, fim).values("criado_por")
        .annotate(n=Count("pk"), t=Soma("total"))
    ):
        dados[linha["criado_por"]]["vendas"] = linha["n"]
        dados[linha["criado_por"]]["faturamento"] = linha["t"] or ZERO

    # Vendas rápidas vazias são canceladas sozinhas ao sair da tela: não contam.
    canceladas = Venda.objects.filter(status=Venda.Status.CANCELADA, total__gt=0)
    for venda in canceladas.values("cancelada_por", "criado_por", "cancelada_em", "criado_em", "total"):
        quando = timezone.localtime(venda["cancelada_em"] or venda["criado_em"]).date()
        if not inicio <= quando <= fim:
            continue
        responsavel = venda["cancelada_por"] or venda["criado_por"]
        dados[responsavel]["canceladas"] += 1
        dados[responsavel]["valor_cancelado"] += venda["total"]

    for linha in (
        ItemRemovido.objects.filter(removido_em__date__gte=inicio, removido_em__date__lte=fim)
        .values("removido_por").annotate(n=Count("pk"), t=Soma("valor"))
    ):
        dados[linha["removido_por"]]["removidos"] = linha["n"]
        dados[linha["removido_por"]]["valor_removido"] = linha["t"] or ZERO

    caixas = quebra_de_caixa(inicio, fim)
    por_operador = defaultdict(lambda: {"fechamentos": 0, "diferenca": ZERO, "faltas": ZERO})
    for caixa in caixas["linhas"]:
        operador = por_operador[caixa["fechado_por_id"]]
        operador["fechamentos"] += 1
        operador["diferenca"] += caixa["diferenca"]
        if caixa["diferenca"] < 0:
            operador["faltas"] += caixa["diferenca"]

    linhas = []
    for pk in set(dados) | set(por_operador):
        linha = {"usuario": usuarios.get(pk), **dados[pk], **por_operador[pk]}
        linha["ticket_medio"] = _q(linha["faturamento"] / linha["vendas"]) if linha["vendas"] else ZERO
        total_iniciadas = linha["vendas"] + linha["canceladas"]
        linha["taxa_cancelamento"] = _pct(linha["canceladas"], total_iniciadas, "1")
        linhas.append(linha)
    linhas.sort(key=lambda linha: -linha["faturamento"])
    return {"linhas": linhas, "caixas": caixas}


def quebra_de_caixa(inicio, fim):
    linhas = []
    for caixa in Caixa.objects.filter(
        status=Caixa.Status.FECHADO, fechado_em__date__gte=inicio, fechado_em__date__lte=fim
    ).select_related("fechado_por"):
        linhas.append({
            "caixa": caixa,
            "fechado_por_id": caixa.fechado_por_id,
            "fechado_em": caixa.fechado_em,
            "esperado": caixa.saldo_esperado(),
            "contado": caixa.valor_contado,
            "diferenca": caixa.diferenca(),
        })
    return {
        "linhas": linhas,
        "total": sum((l["diferenca"] for l in linhas), ZERO),
        "faltas": sum((l["diferenca"] for l in linhas if l["diferenca"] < 0), ZERO),
        "com_diferenca": sum(1 for l in linhas if l["diferenca"]),
    }


# Clientes --------------------------------------------------------------------


def _link_whatsapp(telefone):
    digitos = re.sub(r"\D", "", telefone or "")
    if len(digitos) in (10, 11):
        digitos = "55" + digitos
    return f"https://wa.me/{digitos}" if len(digitos) >= 12 else ""


def analise_clientes(inicio, fim, dias_sumido=30, hoje=None):
    hoje = hoje or timezone.localdate()
    historico = {
        linha["cliente"]: linha
        for linha in Venda.objects.filter(status=Venda.Status.CONCLUIDA, cliente__isnull=False)
        .values("cliente")
        .annotate(compras=Count("pk"), total=Soma("total"), primeira=Min("finalizada_em"), ultima=Max("finalizada_em"))
    }
    no_periodo = {
        linha["cliente"]: linha
        for linha in vendas_concluidas(inicio, fim).filter(cliente__isnull=False)
        .values("cliente").annotate(compras=Count("pk"), total=Soma("total"))
    }
    clientes = Cliente.objects.in_bulk(set(historico))

    def montar(pk):
        h = historico[pk]
        cliente = clientes[pk]
        ultima = timezone.localtime(h["ultima"]).date()
        return {
            "cliente": cliente,
            "compras_total": h["compras"],
            "gasto_total": h["total"],
            "ticket": _q(h["total"] / h["compras"]),
            "ultima_compra": ultima,
            "dias_sem_comprar": (hoje - ultima).days,
            "compras_periodo": no_periodo.get(pk, {}).get("compras", 0),
            "gasto_periodo": no_periodo.get(pk, {}).get("total") or ZERO,
            "whatsapp": _link_whatsapp(cliente.telefone),
        }

    melhores = sorted((montar(pk) for pk in no_periodo), key=lambda c: -c["gasto_periodo"])[:20]
    sumidos = sorted(
        (c for c in (montar(pk) for pk in historico) if c["dias_sem_comprar"] > dias_sumido),
        key=lambda c: -c["gasto_total"],
    )
    novos = sum(
        1 for pk in no_periodo if inicio <= timezone.localtime(historico[pk]["primeira"]).date() <= fim
    )
    vendas_periodo = vendas_concluidas(inicio, fim)
    identificadas = vendas_periodo.filter(cliente__isnull=False).count()
    return {
        "melhores": melhores,
        "sumidos": sumidos,
        "ativos": len(no_periodo),
        "novos": novos,
        "recorrentes": sum(1 for pk in no_periodo if historico[pk]["compras"] > 1),
        "vendas_identificadas": _pct(identificadas, vendas_periodo.count(), "1"),
        "dias_sumido": dias_sumido,
    }


# Estoque ---------------------------------------------------------------------


def _ultimo_fornecedor_por_produto():
    fornecedores = {}
    for produto_id, nome in EntradaEstoque.objects.order_by("criado_em").values_list(
        "produto_id", "fornecedor__nome"
    ):
        fornecedores[produto_id] = nome  # a última entrada sobrescreve as anteriores
    return fornecedores


def previsao_de_compras(dias_base=30, hoje=None):
    """Quando cada produto acaba, pelo ritmo de venda, e quanto comprar de cada fornecedor."""
    hoje = hoje or timezone.localdate()
    cobertura = Configuracao.obter().dias_cobertura_compra
    vendido = dict(
        itens_concluidos(hoje - timedelta(days=dias_base - 1), hoje)
        .values("produto_id").annotate(q=Sum("quantidade")).values_list("produto_id", "q")
    )
    fornecedores = _ultimo_fornecedor_por_produto()

    grupos = defaultdict(list)
    for produto in Produto.objects.filter(ativo=True).select_related("categoria"):
        media = Decimal(vendido.get(produto.pk, 0)) / dias_base
        estoque = produto.quantidade_estoque
        dias_restantes = int(estoque / media) if media and estoque > 0 else (0 if media else None)
        alvo = math.ceil(media * cobertura) + produto.estoque_minimo
        # Negativo costuma ser entrada não lançada, não falta real: calcula como
        # zero e pede uma contagem antes de comprar.
        sugestao = alvo - max(estoque, 0)
        acabando = estoque <= produto.estoque_minimo or (
            dias_restantes is not None and dias_restantes <= cobertura
        )
        if not acabando or sugestao <= 0:
            continue
        grupos[fornecedores.get(produto.pk, "Sem fornecedor registrado")].append({
            "produto": produto,
            "estoque": estoque,
            "media_dia": media.quantize(Decimal("0.1")),
            "dias_restantes": dias_restantes,
            "comprar": sugestao,
            "conferir": estoque < 0,
            "custo_estimado": _q(sugestao * produto.preco_custo),
        })

    resultado = []
    for fornecedor, itens in sorted(grupos.items()):
        itens.sort(key=lambda i: (i["dias_restantes"] is None, i["dias_restantes"] or 0, i["produto"].nome))
        resultado.append({
            "fornecedor": fornecedor,
            "itens": itens,
            "total": sum((i["custo_estimado"] for i in itens), ZERO),
        })
    return {
        "fornecedores": resultado,
        "total": sum((g["total"] for g in resultado), ZERO),
        "cobertura": cobertura,
        "dias_base": dias_base,
    }


def perdas_de_estoque(inicio, fim):
    ajustes = AjusteEstoque.objects.filter(
        criado_em__date__gte=inicio, criado_em__date__lte=fim
    ).select_related("produto", "criado_por")
    por_produto = defaultdict(lambda: {"ajustes": 0, "diferenca": 0, "valor": ZERO})
    for ajuste in ajustes:
        dados = por_produto[ajuste.produto]
        dados["ajustes"] += 1
        dados["diferenca"] += ajuste.diferenca
        dados["valor"] += ajuste.valor_diferenca
    linhas = [
        {"produto": produto, **dados}
        for produto, dados in por_produto.items()
        if dados["diferenca"] < 0
    ]
    linhas.sort(key=lambda linha: linha["valor"])
    return {
        "linhas": linhas,
        "perdas": _q(-sum((a.valor_diferenca for a in ajustes if a.diferenca < 0), ZERO)),
        "sobras": _q(sum((a.valor_diferenca for a in ajustes if a.diferenca > 0), ZERO)),
        "ajustes": list(ajustes[:30]),
    }


# Fechamento de caixa ---------------------------------------------------------


def resumo_do_caixa(caixa):
    """Vendas do turno do caixa: entra no relatório impresso e na notificação do fechamento."""
    fim = caixa.fechado_em or timezone.now()
    vendas = Venda.objects.filter(
        status=Venda.Status.CONCLUIDA, finalizada_em__gte=caixa.aberto_em, finalizada_em__lte=fim
    )
    itens = ItemVenda.objects.filter(venda__in=vendas)
    faturamento = _soma(vendas, "total")
    numero = vendas.count()
    canceladas = Venda.objects.filter(
        status=Venda.Status.CANCELADA, total__gt=0, cancelada_em__gte=caixa.aberto_em, cancelada_em__lte=fim
    )
    rotulos = dict(Venda.FormaPagamento.choices)
    return {
        "faturamento": faturamento,
        "numero_vendas": numero,
        "ticket_medio": _q(faturamento / numero) if numero else ZERO,
        "lucro": _lucro(itens),
        "por_forma": [
            {"forma": rotulos[linha["forma_pagamento"]], "valor": linha["t"]}
            for linha in PagamentoVenda.objects.filter(venda__in=vendas)
            .values("forma_pagamento").annotate(t=Soma("valor")).order_by("-t")
        ],
        "mais_vendidos": list(
            itens.values("produto__nome")
            .annotate(quantidade=Sum("quantidade"), valor=Soma("subtotal"))
            .order_by("-quantidade", "-valor")[:5]
        ),
        "canceladas": canceladas.count(),
        "valor_cancelado": _soma(canceladas, "total"),
    }
