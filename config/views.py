from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import F
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from apps.caixa.models import Caixa
from apps.estoque.models import Produto
from apps.financeiro.models import ContaPagar, ContaReceber
from apps.relatorios import analises
from apps.vendas.models import MINUTOS_COMANDA_PARADA, Venda
from config.agregados import Soma


def _resumo_do_dono():
    resumo = analises.resumo_do_dia()
    abertas = Venda.objects.filter(status=Venda.Status.ABERTA)
    atencao = []
    negativos = Produto.objects.filter(ativo=True, quantidade_estoque__lt=0).count()
    if negativos:
        atencao.append({
            "texto": f"{negativos} produto{'s' if negativos > 1 else ''} com estoque negativo",
            "acao": "Fazer contagem", "url": reverse("estoque:contagem") + "?filtro=negativos",
        })
    comprar = sum(len(g["itens"]) for g in analises.previsao_de_compras()["fornecedores"])
    if comprar:
        atencao.append({
            "texto": f"{comprar} produto{'s' if comprar > 1 else ''} acabando ou para repor",
            "acao": "Ver lista de compras", "url": reverse("relatorios:compras"),
        })
    paradas = [venda for venda in abertas if venda.parada]
    if paradas:
        atencao.append({
            "texto": (
                f"{len(paradas)} comanda{'s' if len(paradas) > 1 else ''} sem movimento há "
                f"mais de {MINUTOS_COMANDA_PARADA} minutos"
            ),
            "acao": "Ver mesas", "url": reverse("vendas:inicio"),
        })
    resumo["atencao"] = atencao
    agora = timezone.localtime()
    resumo["saudacao"] = "Bom dia" if agora.hour < 12 else "Boa tarde" if agora.hour < 18 else "Boa noite"
    return resumo


@login_required
def inicio(request):
    hoje = timezone.localdate()

    faturamento_hoje = (
        Venda.objects.filter(
            status=Venda.Status.CONCLUIDA, finalizada_em__date=hoje
        ).aggregate(t=Soma("total"))["t"]
        or Decimal("0")
    )
    a_pagar_vencido = (
        ContaPagar.objects.filter(pago=False, vencimento__lt=hoje).aggregate(t=Soma("valor"))["t"]
        or Decimal("0")
    )
    a_receber_vencido = (
        ContaReceber.objects.filter(recebido=False, vencimento__lt=hoje).aggregate(t=Soma("valor"))["t"]
        or Decimal("0")
    )

    contexto = {
        "resumo": _resumo_do_dono() if request.user.is_superuser else None,
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
