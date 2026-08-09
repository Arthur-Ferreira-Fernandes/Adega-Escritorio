from django import forms

from .models import Cliente, Fornecedor


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ["nome", "documento", "telefone", "email", "endereco", "observacoes"]


class FornecedorForm(forms.ModelForm):
    class Meta:
        model = Fornecedor
        fields = ["nome", "documento", "telefone", "email", "endereco", "observacoes"]
