from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.auditoria import servicos as auditoria
from apps.auditoria.models import RegistroAuditoria

from .forms import MeusDadosForm, NovoUsuarioForm, ResetarSenhaForm

User = get_user_model()


def _somente_admin(user):
    return user.is_superuser


def _renderizar(request, contexto, *, template_htmx, template_completo):
    template = (
        template_htmx
        if request.headers.get("HX-Request") == "true"
        else template_completo
    )
    return render(request, template, contexto)


def _contexto_usuarios(
    form_ativo=False, form=None, reset_ativo=False, reset_form=None, resetando=None
):
    return {
        "usuarios": User.objects.all().order_by("username"),
        "form_ativo": form_ativo,
        "form": form or NovoUsuarioForm(),
        "reset_ativo": reset_ativo,
        "reset_form": reset_form or ResetarSenhaForm(),
        "resetando": resetando,
    }


def _renderizar_usuarios(request, contexto):
    return _renderizar(
        request,
        contexto,
        template_htmx="usuarios/_usuarios_conteudo_htmx.html",
        template_completo="usuarios/usuarios.html",
    )


@login_required
@user_passes_test(_somente_admin)
def usuarios_lista(request):
    return _renderizar_usuarios(request, _contexto_usuarios())


@login_required
@user_passes_test(_somente_admin)
def usuarios_novo(request):
    if request.method == "POST":
        form = NovoUsuarioForm(request.POST)
        if form.is_valid():
            novo_usuario = User.objects.create_user(
                username=form.cleaned_data["username"],
                first_name=form.cleaned_data["first_name"],
                password=form.cleaned_data["password1"],
                is_staff=True,
                is_superuser=form.cleaned_data["is_superuser"],
            )
            auditoria.registrar(request.user, RegistroAuditoria.Acao.CRIACAO, novo_usuario)
            messages.success(request, "Usuário criado com sucesso.")
            return _renderizar_usuarios(request, _contexto_usuarios())
    else:
        form = NovoUsuarioForm()
    return _renderizar_usuarios(request, _contexto_usuarios(form_ativo=True, form=form))


@login_required
@user_passes_test(_somente_admin)
def usuarios_resetar_senha(request, pk):
    usuario = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        form = ResetarSenhaForm(request.POST)
        if form.is_valid():
            usuario.set_password(form.cleaned_data["password1"])
            usuario.save(update_fields=["password"])
            auditoria.registrar(
                request.user, RegistroAuditoria.Acao.EDICAO, usuario,
                detalhes=f"Senha redefinida por {request.user}",
            )
            messages.success(request, f"Senha de {usuario.username} redefinida com sucesso.")
            return _renderizar_usuarios(request, _contexto_usuarios())
    else:
        form = ResetarSenhaForm()
    return _renderizar_usuarios(
        request, _contexto_usuarios(reset_ativo=True, reset_form=form, resetando=usuario)
    )


@login_required
@user_passes_test(_somente_admin)
@require_POST
def usuarios_alternar_ativo(request, pk):
    usuario = get_object_or_404(User, pk=pk)
    if usuario == request.user:
        messages.error(request, "Você não pode desativar sua própria conta.")
    else:
        usuario.is_active = not usuario.is_active
        usuario.save(update_fields=["is_active"])
        acao = "ativado" if usuario.is_active else "desativado"
        auditoria.registrar(
            request.user, RegistroAuditoria.Acao.EDICAO, usuario,
            detalhes=f"Conta {'ativada' if usuario.is_active else 'desativada'}",
        )
        messages.success(request, f"Usuário {usuario.username} {acao}.")
    return _renderizar_usuarios(request, _contexto_usuarios())


@login_required
def minha_conta(request):
    dados_form = MeusDadosForm(
        usuario_atual=request.user,
        initial={"first_name": request.user.first_name, "username": request.user.username},
    )
    senha_form = PasswordChangeForm(user=request.user)

    if request.method == "POST":
        if "salvar_dados" in request.POST:
            dados_form = MeusDadosForm(request.POST, usuario_atual=request.user)
            if dados_form.is_valid():
                nome_antigo, login_antigo = request.user.first_name, request.user.username
                request.user.first_name = dados_form.cleaned_data["first_name"]
                request.user.username = dados_form.cleaned_data["username"]
                request.user.save(update_fields=["first_name", "username"])
                auditoria.registrar(
                    request.user, RegistroAuditoria.Acao.EDICAO, request.user,
                    detalhes=(
                        f"Nome: {nome_antigo} → {request.user.first_name}; "
                        f"Usuário: {login_antigo} → {request.user.username}"
                    ),
                )
                messages.success(request, "Dados atualizados com sucesso.")
                return redirect("usuarios:minha_conta")
        elif "salvar_senha" in request.POST:
            senha_form = PasswordChangeForm(user=request.user, data=request.POST)
            if senha_form.is_valid():
                usuario = senha_form.save()
                update_session_auth_hash(request, usuario)
                auditoria.registrar(
                    request.user, RegistroAuditoria.Acao.EDICAO, usuario,
                    detalhes="Alterou a própria senha",
                )
                messages.success(request, "Senha alterada com sucesso.")
                return redirect("usuarios:minha_conta")

    return render(
        request,
        "usuarios/minha_conta.html",
        {"dados_form": dados_form, "senha_form": senha_form},
    )
