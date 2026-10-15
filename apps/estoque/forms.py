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


class ProdutoRapidoForm(forms.ModelForm):
    """Cadastro na hora, quando o leitor lê um código que ainda não existe."""

    preco_venda = DecimalMonetarioField(label="Preço de venda", max_digits=10, decimal_places=2)
    preco_custo = DecimalMonetarioField(label="Preço de custo", max_digits=10, decimal_places=2)

    class Meta:
        model = Produto
        fields = ["codigo_barras", "nome", "categoria", "preco_venda", "preco_custo"]
        widgets = {"codigo_barras": forms.HiddenInput}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["codigo_barras"].required = True
        self.fields["nome"].widget.attrs.update(autofocus=True, autocomplete="off")


class EntradaEstoqueForm(forms.Form):
    # Recebe o SKU escolhido na lista de busca (static/js/busca-produto.js).
    produto_busca = forms.CharField(
        label="Produto",
        widget=forms.HiddenInput,
        error_messages={
            "required": "Selecione um produto da lista digitando o nome ou lendo o código de barras."
        },
    )
    quantidade = forms.IntegerField(min_value=1, label="Quantidade recebida")
    fornecedor = forms.ModelChoiceField(queryset=Fornecedor.objects.all(), label="Fornecedor")
    custo_unitario = DecimalMonetarioField(
        label="Custo unitário pago", max_digits=10, decimal_places=2
    )

    def clean_produto_busca(self):
        produto = Produto.objects.filter(sku=self.cleaned_data["produto_busca"].strip()).first()
        if produto is None:
            raise forms.ValidationError(
                "Produto não encontrado. Selecione um item da lista de sugestões."
            )
        return produto
