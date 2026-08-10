from django import forms

from apps.clientes.models import Fornecedor
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
            "estoque_minimo",
            "unidade",
            "ativo",
        ]


class EntradaEstoqueForm(forms.Form):
    produto_busca = forms.CharField(
        label="Produto",
        widget=forms.TextInput(
            attrs={
                "list": "produtos-estoque-datalist",
                "autocomplete": "off",
                "placeholder": "Digite o nome do produto…",
            }
        ),
    )
    quantidade = forms.IntegerField(min_value=1, label="Quantidade recebida")
    fornecedor = forms.ModelChoiceField(queryset=Fornecedor.objects.all(), label="Fornecedor")
    custo_unitario = DecimalMonetarioField(
        label="Custo unitário pago", max_digits=10, decimal_places=2
    )

    def clean_produto_busca(self):
        texto = self.cleaned_data["produto_busca"].strip()
        _, separador, sku = texto.rpartition(" | ")
        if not separador:
            raise forms.ValidationError(
                "Selecione um produto da lista de sugestões digitando parte do nome."
            )
        produto = Produto.objects.filter(sku=sku.strip()).first()
        if produto is None:
            raise forms.ValidationError(
                "Produto não encontrado. Selecione um item da lista de sugestões."
            )
        return produto
