from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import redirect, render

from .forms import ConfiguracaoForm, MeuUsuarioForm
from .models import Configuracao


def _somente_admin(user):
    return user.is_superuser


@login_required
@user_passes_test(_somente_admin)
def administracao(request):
    configuracao = Configuracao.obter()
    usuario_form = MeuUsuarioForm(
        usuario_atual=request.user, initial={"username": request.user.username}
    )
    senha_form = PasswordChangeForm(user=request.user)
    config_form = ConfiguracaoForm(instance=configuracao)

    if request.method == "POST":
        if "salvar_usuario" in request.POST:
            usuario_form = MeuUsuarioForm(request.POST, usuario_atual=request.user)
            if usuario_form.is_valid():
                request.user.username = usuario_form.cleaned_data["username"]
                request.user.save(update_fields=["username"])
                messages.success(request, "Usuário atualizado com sucesso.")
                return redirect("configuracoes:administracao")
        elif "salvar_senha" in request.POST:
            senha_form = PasswordChangeForm(user=request.user, data=request.POST)
            if senha_form.is_valid():
                usuario = senha_form.save()
                update_session_auth_hash(request, usuario)
                messages.success(request, "Senha alterada com sucesso.")
                return redirect("configuracoes:administracao")
        elif "salvar_configuracoes" in request.POST:
            config_form = ConfiguracaoForm(request.POST, instance=configuracao)
            if config_form.is_valid():
                config_form.save()
                messages.success(request, "Configurações atualizadas com sucesso.")
                return redirect("configuracoes:administracao")

    return render(
        request,
        "configuracoes/administracao.html",
        {
            "usuario_form": usuario_form,
            "senha_form": senha_form,
            "config_form": config_form,
        },
    )
