from django import forms

from .models import Categoria, Produto


class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ["nome", "descricao"]


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
