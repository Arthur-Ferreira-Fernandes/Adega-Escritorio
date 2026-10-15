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
    meta_faturamento_mensal = DecimalMonetarioField(
        label="Meta de faturamento do mês",
        max_digits=12,
        decimal_places=2,
        help_text="Aparece na tela inicial com a projeção do mês. Zero = sem meta.",
    )

    class Meta:
        model = Configuracao
        fields = [
            "limite_sangria",
            "meta_faturamento_mensal",
            "taxa_cartao",
            "taxa_pix",
            "dias_cobertura_compra",
        ]
        widgets = {
            "taxa_cartao": forms.NumberInput(attrs={"step": "0.01", "min": "0", "max": "100"}),
            "taxa_pix": forms.NumberInput(attrs={"step": "0.01", "min": "0", "max": "100"}),
        }


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
