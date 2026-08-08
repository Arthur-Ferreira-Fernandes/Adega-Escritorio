from django import forms

from apps.clientes.models import Cliente
from apps.estoque.models import Produto

from .models import Venda


class NovaVendaForm(forms.Form):
    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.all(), required=False, label="Cliente"
    )
    identificador = forms.CharField(
        max_length=50, required=False, label="Identificador (mesa/comanda)"
    )


class ProdutoChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, produto):
        return (
            f"{produto.nome} — R$ {produto.preco_venda} "
            f"(estoque: {produto.quantidade_estoque})"
        )


class ItemVendaForm(forms.Form):
    produto = ProdutoChoiceField(
        queryset=Produto.objects.filter(ativo=True), label="Produto"
    )
    quantidade = forms.IntegerField(min_value=1, initial=1, label="Quantidade")


class FinalizarVendaForm(forms.Form):
    forma_pagamento = forms.ChoiceField(
        choices=Venda.FormaPagamento.choices, label="Forma de pagamento"
    )


class EscanearCodigoForm(forms.Form):
    codigo_barras = forms.CharField(
        label="Código de barras",
        widget=forms.TextInput(
            attrs={
                "autofocus": True,
                "autocomplete": "off",
                "placeholder": "Escaneie o código de barras…",
            }
        ),
    )

    def clean_codigo_barras(self):
        return self.cleaned_data["codigo_barras"].strip()
