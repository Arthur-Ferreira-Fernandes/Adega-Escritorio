from django import forms

from config.campos_monetarios import DecimalMonetarioField

from .models import ContaPagar, ContaReceber


class ContaPagarForm(forms.ModelForm):
    valor = DecimalMonetarioField(label="Valor", max_digits=10, decimal_places=2)

    class Meta:
        model = ContaPagar
        fields = ["fornecedor", "descricao", "valor", "vencimento"]
        widgets = {"vencimento": forms.DateInput(attrs={"type": "date"})}


class ContaReceberForm(forms.ModelForm):
    valor = DecimalMonetarioField(label="Valor", max_digits=10, decimal_places=2)

    class Meta:
        model = ContaReceber
        fields = ["cliente", "venda", "descricao", "valor", "vencimento"]
        widgets = {"vencimento": forms.DateInput(attrs={"type": "date"})}
