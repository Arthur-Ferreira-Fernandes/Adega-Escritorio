from django import forms
from django.contrib.auth import get_user_model

from .models import RegistroAuditoria

User = get_user_model()

MODELO_CHOICES = [
    ("", "Todos"),
    ("Produto", "Produto"),
    ("Categoria", "Categoria"),
    ("Cliente", "Cliente"),
    ("Fornecedor", "Fornecedor"),
    ("ContaPagar", "Conta a pagar"),
    ("ContaReceber", "Conta a receber"),
    ("Configuracao", "Configurações"),
    ("User", "Usuário"),
]


class FiltroAuditoriaForm(forms.Form):
    data_inicio = forms.DateField(
        required=False, label="De", widget=forms.DateInput(attrs={"type": "date"})
    )
    data_fim = forms.DateField(
        required=False, label="Até", widget=forms.DateInput(attrs={"type": "date"})
    )
    usuario = forms.ModelChoiceField(
        queryset=User.objects.all().order_by("username"),
        required=False,
        empty_label="Todos os usuários",
        label="Usuário",
    )
    modelo = forms.ChoiceField(choices=MODELO_CHOICES, required=False, label="Modelo")
    acao = forms.ChoiceField(
        choices=[("", "Todas")] + list(RegistroAuditoria.Acao.choices),
        required=False,
        label="Ação",
    )
