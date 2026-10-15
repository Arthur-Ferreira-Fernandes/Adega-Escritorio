from django import forms

from config.campos_monetarios import DecimalMonetarioField


class AbrirCaixaForm(forms.Form):
    valor_abertura = DecimalMonetarioField(
        label="Valor de abertura", max_digits=10, decimal_places=2
    )


class MovimentoCaixaForm(forms.Form):
    valor = DecimalMonetarioField(label="Valor", max_digits=10, decimal_places=2)
    descricao = forms.CharField(label="Descrição", max_length=255)


class FecharCaixaForm(forms.Form):
    valor_contado = DecimalMonetarioField(label="Valor contado", max_digits=10, decimal_places=2)

