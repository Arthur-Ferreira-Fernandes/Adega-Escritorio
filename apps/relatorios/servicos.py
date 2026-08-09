from decimal import Decimal

from django.db.models import F, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.estoque.models import Produto
from apps.financeiro.models import ContaPagar, ContaReceber
from apps.vendas.models import ItemVenda, Venda


def calcular_metricas(data_inicio, data_fim, categoria, forma_pagamento):
    itens = ItemVenda.objects.filter(
        venda__status=Venda.Status.CONCLUIDA,
        venda__criado_em__date__gte=data_inicio,
        venda__criado_em__date__lte=data_fim,
    )
    if categoria:
        itens = itens.filter(produto__categoria=categoria)
    if forma_pagamento:
        itens = itens.filter(venda__forma_pagamento=forma_pagamento)

    faturamento_total = itens.aggregate(total=Sum("subtotal"))["total"] or Decimal("0")
    numero_vendas = itens.values("venda").distinct().count()
    ticket_medio = (
        (faturamento_total / numero_vendas).quantize(Decimal("0.01"))
        if numero_vendas
        else Decimal("0")
    )

    faturamento_por_dia = list(
        itens.annotate(dia=TruncDate("venda__criado_em"))
        .values("dia")
        .annotate(total=Sum("subtotal"))
        .order_by("dia")
    )

    produtos_mais_vendidos = list(
        itens.values("produto__nome")
        .annotate(quantidade=Sum("quantidade"), valor=Sum("subtotal"))
        .order_by("-valor")[:8]
    )

    estoque_baixo_qs = Produto.objects.filter(
        ativo=True, quantidade_estoque__lte=F("estoque_minimo")
    ).select_related("categoria")
    if categoria:
        estoque_baixo_qs = estoque_baixo_qs.filter(categoria=categoria)

    hoje = timezone.now().date()
    pagar_pendente = ContaPagar.objects.filter(pago=False)
    receber_pendente = ContaReceber.objects.filter(recebido=False)

    return {
        "faturamento_total": faturamento_total,
        "numero_vendas": numero_vendas,
        "ticket_medio": ticket_medio,
        "faturamento_por_dia": faturamento_por_dia,
        "produtos_mais_vendidos": produtos_mais_vendidos,
        "estoque_baixo": estoque_baixo_qs.order_by("quantidade_estoque"),
        "a_pagar_total": pagar_pendente.aggregate(t=Sum("valor"))["t"] or Decimal("0"),
        "a_pagar_vencido": (
            pagar_pendente.filter(vencimento__lt=hoje).aggregate(t=Sum("valor"))["t"]
            or Decimal("0")
        ),
        "a_receber_total": receber_pendente.aggregate(t=Sum("valor"))["t"] or Decimal("0"),
        "a_receber_vencido": (
            receber_pendente.filter(vencimento__lt=hoje).aggregate(t=Sum("valor"))["t"]
            or Decimal("0")
        ),
    }
