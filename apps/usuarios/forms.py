from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

User = get_user_model()


def _validar_senhas(form, cleaned):
    p1, p2 = cleaned.get("password1"), cleaned.get("password2")
    if p1 and p2:
        if p1 != p2:
            form.add_error("password2", "As senhas não coincidem.")
        else:
            try:
                validate_password(p1)
            except forms.ValidationError as erro:
                form.add_error("password1", erro)
    return cleaned


class NovoUsuarioForm(forms.Form):
    username = forms.CharField(label="Usuário (login)", max_length=150)
    first_name = forms.CharField(label="Nome", max_length=150)
    password1 = forms.CharField(label="Senha", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirmar senha", widget=forms.PasswordInput)
    is_superuser = forms.BooleanField(label="É administrador?", required=False)

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Já existe um usuário com esse nome de login.")
        return username

    def clean(self):
        return _validar_senhas(self, super().clean())


class ResetarSenhaForm(forms.Form):
    password1 = forms.CharField(label="Nova senha", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirmar nova senha", widget=forms.PasswordInput)

    def clean(self):
        return _validar_senhas(self, super().clean())
