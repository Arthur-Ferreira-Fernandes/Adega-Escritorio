from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.estoque.models import Produto
from apps.financeiro.models import ContaPagar, ContaReceber
from apps.vendas.models import ItemVenda, Venda
from config.agregados import Soma


def calcular_metricas(data_inicio, data_fim, categoria, forma_pagamento):
    itens = ItemVenda.objects.filter(
        venda__status=Venda.Status.CONCLUIDA,
        venda__criado_em__date__gte=data_inicio,
        venda__criado_em__date__lte=data_fim,
    )
    if categoria:
        itens = itens.filter(produto__categoria=categoria)
    if forma_pagamento:
        itens = itens.filter(venda__pagamentos__forma_pagamento=forma_pagamento)

    faturamento_total = itens.aggregate(total=Soma("subtotal"))["total"] or Decimal("0")
    numero_vendas = itens.values("venda").distinct().count()
    ticket_medio = (
        (faturamento_total / numero_vendas).quantize(Decimal("0.01"))
        if numero_vendas
        else Decimal("0")
    )

    faturamento_por_dia = list(
        itens.annotate(dia=TruncDate("venda__criado_em"))
        .values("dia")
        .annotate(total=Soma("subtotal"))
        .order_by("dia")
    )

    produtos_mais_vendidos = list(
        itens.values("produto__nome")
        .annotate(quantidade=Soma("quantidade"), valor=Soma("subtotal"))
        .order_by("-valor")[:8]
    )

    itens_com_custo = itens.filter(custo_unitario__isnull=False).annotate(
        lucro_item=ExpressionWrapper(
            F("subtotal") - F("custo_unitario") * F("quantidade"),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    )
    lucro_total = itens_com_custo.aggregate(t=Soma("lucro_item"))["t"] or Decimal("0")
    margem_total = (
        (lucro_total / faturamento_total * 100).quantize(Decimal("0.1"))
        if faturamento_total
        else Decimal("0")
    )

    produtos_lucro = []
    for produto in (
        itens_com_custo.values("produto__nome")
        .annotate(
            quantidade=Soma("quantidade"),
            faturamento=Soma("subtotal"),
            lucro=Soma("lucro_item"),
        )
        .order_by("-lucro")[:8]
    ):
        margem = (
            (produto["lucro"] / produto["faturamento"] * 100).quantize(Decimal("0.1"))
            if produto["faturamento"]
            else Decimal("0")
        )
        produtos_lucro.append(
            {
                **produto,
                "custo": produto["faturamento"] - produto["lucro"],
                "margem": margem,
            }
        )

    estoque_baixo_qs = Produto.objects.filter(
        ativo=True, quantidade_estoque__lte=F("estoque_minimo")
    ).select_related("categoria")
    if categoria:
        estoque_baixo_qs = estoque_baixo_qs.filter(categoria=categoria)

    hoje = timezone.localdate()
    pagar_pendente = ContaPagar.objects.filter(pago=False)
    receber_pendente = ContaReceber.objects.filter(recebido=False)

    return {
        "faturamento_total": faturamento_total,
        "numero_vendas": numero_vendas,
        "ticket_medio": ticket_medio,
        "faturamento_por_dia": faturamento_por_dia,
        "produtos_mais_vendidos": produtos_mais_vendidos,
        "lucro_total": lucro_total,
        "margem_total": margem_total,
        "produtos_lucro": produtos_lucro,
        "estoque_baixo": estoque_baixo_qs.order_by("quantidade_estoque"),
        "a_pagar_total": pagar_pendente.aggregate(t=Soma("valor"))["t"] or Decimal("0"),
        "a_pagar_vencido": (
            pagar_pendente.filter(vencimento__lt=hoje).aggregate(t=Soma("valor"))["t"]
            or Decimal("0")
        ),
        "a_receber_total": receber_pendente.aggregate(t=Soma("valor"))["t"] or Decimal("0"),
        "a_receber_vencido": (
            receber_pendente.filter(vencimento__lt=hoje).aggregate(t=Soma("valor"))["t"]
            or Decimal("0")
        ),
    }
