"""Filtro de período compartilhado pelas abas de análise."""

from datetime import timedelta

from django import forms
from django.utils import timezone

ATALHOS = [
    ("hoje", "Hoje"),
    ("7", "7 dias"),
    ("30", "30 dias"),
    ("90", "90 dias"),
    ("mes", "Este mês"),
    ("mes_passado", "Mês passado"),
]


class PeriodoForm(forms.Form):
    # O campo de data do navegador só aceita AAAA-MM-DD, não o formato brasileiro.
    data_inicio = forms.DateField(
        required=False, label="De", widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})
    )
    data_fim = forms.DateField(
        required=False, label="Até", widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})
    )


def intervalo_do_atalho(atalho, hoje):
    if atalho == "hoje":
        return hoje, hoje
    if atalho == "mes":
        return hoje.replace(day=1), hoje
    if atalho == "mes_passado":
        fim = hoje.replace(day=1) - timedelta(days=1)
        return fim.replace(day=1), fim
    if atalho in ("7", "30", "90"):
        return hoje - timedelta(days=int(atalho) - 1), hoje
    return None


def ler_periodo(request, padrao="30"):
    """Devolve (inicio, fim, form, atalho_ativo). Atalho tem prioridade sobre as datas."""
    hoje = timezone.localdate()
    atalho = request.GET.get("periodo", "")
    intervalo = intervalo_do_atalho(atalho, hoje)
    if intervalo:
        inicio, fim = intervalo
    else:
        form = PeriodoForm(request.GET)
        datas = form.cleaned_data if form.is_valid() else {}
        if datas.get("data_inicio") or datas.get("data_fim"):
            inicio = datas.get("data_inicio") or hoje - timedelta(days=29)
            fim = datas.get("data_fim") or hoje
            atalho = ""
        else:
            atalho = padrao
            inicio, fim = intervalo_do_atalho(padrao, hoje)
    if inicio > fim:
        inicio, fim = fim, inicio
    form = PeriodoForm(initial={"data_inicio": inicio, "data_fim": fim})
    return inicio, fim, form, atalho
