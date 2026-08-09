from django import forms


class DecimalMonetarioField(forms.DecimalField):
    def __init__(self, *args, **kwargs):
        max_digitos = kwargs.get("max_digits", 10)
        kwargs.setdefault(
            "widget",
            forms.TextInput(
                attrs={
                    "class": "campo-monetario",
                    "inputmode": "numeric",
                    "autocomplete": "off",
                    "placeholder": "R$ 0,00",
                    "data-max-digitos": str(max_digitos),
                }
            ),
        )
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        if isinstance(value, str):
            value = value.strip()
            if value.upper().startswith("R$"):
                value = value[2:].strip()
            if "," in value:
                value = value.replace(".", "").replace(",", ".")
        return super().to_python(value)
