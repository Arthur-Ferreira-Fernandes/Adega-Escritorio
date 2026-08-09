from django import forms

from config.campos_monetarios import DecimalMonetarioField

from .models import Categoria, Produto


class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ["nome", "descricao"]


class ProdutoForm(forms.ModelForm):
    preco_custo = DecimalMonetarioField(
        label="Preço de custo", max_digits=10, decimal_places=2
    )
    preco_venda = DecimalMonetarioField(
        label="Preço de venda", max_digits=10, decimal_places=2
    )

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
