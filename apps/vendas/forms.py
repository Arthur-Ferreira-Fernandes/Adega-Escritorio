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


class ItemVendaForm(forms.Form):
    produto_busca = forms.CharField(
        label="Produto",
        widget=forms.TextInput(
            attrs={
                "list": "produtos-datalist",
                "autocomplete": "off",
                "placeholder": "Digite o nome do produto…",
            }
        ),
    )
    quantidade = forms.IntegerField(min_value=1, initial=1, label="Quantidade")

    def clean_produto_busca(self):
        texto = self.cleaned_data["produto_busca"].strip()
        _, separador, sku = texto.rpartition(" | ")
        if not separador:
            raise forms.ValidationError(
                "Selecione um produto da lista de sugestões digitando parte do nome."
            )
        produto = Produto.objects.filter(sku=sku.strip(), ativo=True).first()
        if produto is None:
            raise forms.ValidationError(
                "Produto não encontrado ou inativo. Selecione um item da lista de sugestões."
            )
        return produto


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
