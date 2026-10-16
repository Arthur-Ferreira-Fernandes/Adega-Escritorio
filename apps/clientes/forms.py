from django import forms

from config.campos_monetarios import DecimalMonetarioField

from .models import Cliente, Fornecedor


class ClienteForm(forms.ModelForm):
    limite_fiado = DecimalMonetarioField(
        label="Limite de fiado", max_digits=10, decimal_places=2, required=False,
        help_text="Quanto o cliente pode ficar devendo. Vazio ou zero = não compra fiado.",
    )

    class Meta:
        model = Cliente
        fields = ["nome", "documento", "telefone", "email", "endereco", "limite_fiado", "observacoes"]

    def clean_limite_fiado(self):
        from decimal import Decimal

        return self.cleaned_data.get("limite_fiado") or Decimal("0")


class FornecedorForm(forms.ModelForm):
    class Meta:
        model = Fornecedor
        fields = ["nome", "documento", "telefone", "email", "endereco", "observacoes"]
