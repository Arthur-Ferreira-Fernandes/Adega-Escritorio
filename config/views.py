from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import F, Sum
from django.shortcuts import render
from django.utils import timezone

from apps.caixa.models import Caixa
from apps.estoque.models import Produto
from apps.financeiro.models import ContaPagar, ContaReceber
from apps.vendas.models import Venda


@login_required
def inicio(request):
    hoje = timezone.now().date()

    faturamento_hoje = (
        Venda.objects.filter(
            status=Venda.Status.CONCLUIDA, finalizada_em__date=hoje
        ).aggregate(t=Sum("total"))["t"]
        or Decimal("0")
    )
    a_pagar_vencido = (
        ContaPagar.objects.filter(pago=False, vencimento__lt=hoje).aggregate(t=Sum("valor"))["t"]
        or Decimal("0")
    )
    a_receber_vencido = (
        ContaReceber.objects.filter(recebido=False, vencimento__lt=hoje).aggregate(t=Sum("valor"))["t"]
        or Decimal("0")
    )

    contexto = {
        "caixa": Caixa.aberto_atual(),
        "faturamento_hoje": faturamento_hoje,
        "comandas_abertas": Venda.objects.filter(status=Venda.Status.ABERTA).count(),
        "estoque_baixo": Produto.objects.filter(
            ativo=True, quantidade_estoque__lte=F("estoque_minimo")
        ).count(),
        "a_pagar_vencido": a_pagar_vencido,
        "a_receber_vencido": a_receber_vencido,
    }
    return render(request, "inicio.html", contexto)
