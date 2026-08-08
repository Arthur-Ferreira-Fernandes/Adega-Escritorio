from django import forms

from .models import Produto


class ProdutoForm(forms.ModelForm):
    class Meta:
        model = Produto
        fields = [
            "nome",
            "sku",
            "codigo_barras",
            "categoria",
            "preco_custo",
            "preco_venda",
            "quantidade_estoque",
            "unidade",
            "ativo",
        ]
