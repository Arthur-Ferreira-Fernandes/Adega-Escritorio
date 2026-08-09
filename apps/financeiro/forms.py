from django import forms

from .models import ContaPagar, ContaReceber


class ContaPagarForm(forms.ModelForm):
    class Meta:
        model = ContaPagar
        fields = ["fornecedor", "descricao", "valor", "vencimento"]
        widgets = {"vencimento": forms.DateInput(attrs={"type": "date"})}


class ContaReceberForm(forms.ModelForm):
    class Meta:
        model = ContaReceber
        fields = ["cliente", "venda", "descricao", "valor", "vencimento"]
        widgets = {"vencimento": forms.DateInput(attrs={"type": "date"})}
