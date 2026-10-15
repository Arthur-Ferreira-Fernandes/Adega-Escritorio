from django import forms
from django.contrib.auth import get_user_model

from config.campos_monetarios import DecimalMonetarioField

from .models import Configuracao

User = get_user_model()


class ConfiguracaoForm(forms.ModelForm):
    limite_sangria = DecimalMonetarioField(
        label="Valor em caixa a partir do qual sugerir sangria",
        max_digits=10,
        decimal_places=2,
    )

    class Meta:
        model = Configuracao
        fields = ["limite_sangria"]


class MeuUsuarioForm(forms.Form):
    username = forms.CharField(label="Usuário (login)", max_length=150)

    def __init__(self, *args, usuario_atual, **kwargs):
        self.usuario_atual = usuario_atual
        super().__init__(*args, **kwargs)

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.exclude(pk=self.usuario_atual.pk).filter(username=username).exists():
            raise forms.ValidationError("Já existe um usuário com esse nome de login.")
        return username
