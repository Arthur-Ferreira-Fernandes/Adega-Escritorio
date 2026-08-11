import json
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from .forms import FiltroRelatorioForm
from .servicos import calcular_metricas


def _json_seguro(dados):
    return json.dumps(dados).replace("<", "\\u003c")


@login_required
def dashboard(request):
    form = FiltroRelatorioForm(request.GET or None)
    hoje = timezone.now().date()
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
