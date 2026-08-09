from django import forms

from apps.estoque.models import Categoria
from apps.vendas.models import Venda


class FiltroRelatorioForm(forms.Form):
    data_inicio = forms.DateField(
        required=False,
        label="De",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    data_fim = forms.DateField(
        required=False,
        label="Até",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    categoria = forms.ModelChoiceField(
        queryset=Categoria.objects.all(),
        required=False,
        empty_label="Todas as categorias",
        label="Categoria",
    )
    forma_pagamento = forms.ChoiceField(
        choices=[("", "Todas")] + list(Venda.FormaPagamento.choices),
        required=False,
        label="Forma de pagamento",
    )
