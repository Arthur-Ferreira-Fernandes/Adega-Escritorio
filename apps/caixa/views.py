import logging

from django.contrib import messages
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from .forms import AbrirCaixaForm, AutorizacaoAdminForm, FecharCaixaForm, MovimentoCaixaForm
from .models import Caixa

logger = logging.getLogger("apps.caixa")


def _renderizar(request, contexto, *, template_htmx, template_completo):
    template = (
        template_htmx
        if request.headers.get("HX-Request") == "true"
        else template_completo
    )
    return render(request, template, contexto)


def _contexto_painel():
    caixa = Caixa.aberto_atual()
    return {
        "caixa": caixa,
        "movimentos": caixa.movimentos.select_related("criado_por").all() if caixa else [],
        "historico": Caixa.objects.filter(status=Caixa.Status.FECHADO).select_related(
            "aberto_por", "fechado_por"
        )[:10],
        "abrir_form": AbrirCaixaForm(),
        "sangria_form": MovimentoCaixaForm(),
        "reforco_form": MovimentoCaixaForm(),
        "fechar_form": FecharCaixaForm(),
        "autorizacao_form": AutorizacaoAdminForm(),
    }


def _renderizar_painel(request):
    return _renderizar(
        request,
        _contexto_painel(),
        template_htmx="caixa/_conteudo_htmx.html",
        template_completo="caixa/painel.html",
    )


def _erros_formulario(form, mensagem_padrao):
    erros = [msg for mensagens in form.errors.values() for msg in mensagens]
    return "; ".join(erros) or mensagem_padrao


@login_required
def caixa_painel(request):
    return _renderizar_painel(request)


@login_required
@require_POST
def caixa_abrir(request):
    form = AbrirCaixaForm(request.POST)
    if form.is_valid():
        try:
            caixa = Caixa.abrir(request.user, form.cleaned_data["valor_abertura"])
            logger.info(
                "Caixa aberto",
                extra={"usuario": request.user.username, "valor_abertura": str(caixa.valor_abertura)},
            )
            messages.success(request, "Caixa aberto com sucesso.")
        except ValidationError as erro:
            messages.error(request, "; ".join(erro.messages))
    else:
        messages.error(request, _erros_formulario(form, "Informe um valor de abertura válido."))
    return _renderizar_painel(request)


@login_required
@require_POST
def caixa_sangria(request):
    caixa = Caixa.aberto_atual()
    if caixa is None:
        messages.error(request, "Não há caixa aberto no momento.")
        return _renderizar_painel(request)
    form = MovimentoCaixaForm(request.POST)
    if form.is_valid():
        try:
            caixa.registrar_sangria(
                request.user, form.cleaned_data["valor"], form.cleaned_data["descricao"]
            )
            messages.success(request, "Sangria registrada com sucesso.")
        except ValidationError as erro:
            messages.error(request, "; ".join(erro.messages))
    else:
        messages.error(
            request, _erros_formulario(form, "Informe um valor e uma descrição válidos.")
        )
    return _renderizar_painel(request)


@login_required
@require_POST
def caixa_reforco(request):
    caixa = Caixa.aberto_atual()
    if caixa is None:
        messages.error(request, "Não há caixa aberto no momento.")
        return _renderizar_painel(request)
    form = MovimentoCaixaForm(request.POST)
    if form.is_valid():
        try:
            caixa.registrar_reforco(
                request.user, form.cleaned_data["valor"], form.cleaned_data["descricao"]
            )
            messages.success(request, "Reforço registrado com sucesso.")
        except ValidationError as erro:
            messages.error(request, "; ".join(erro.messages))
    else:
        messages.error(
            request, _erros_formulario(form, "Informe um valor e uma descrição válidos.")
        )
    return _renderizar_painel(request)


@login_required
@require_POST
def caixa_fechar(request):
    caixa = Caixa.aberto_atual()
    if caixa is None:
        messages.error(request, "Não há caixa aberto no momento.")
        return _renderizar_painel(request)
    form = FecharCaixaForm(request.POST)
    if form.is_valid():
        try:
            caixa.fechar(request.user, form.cleaned_data["valor_contado"])
            logger.info(
                "Caixa fechado",
                extra={
                    "usuario": request.user.username,
                    "valor_contado": str(caixa.valor_contado),
                    "diferenca": str(caixa.diferenca()),
                },
            )
            messages.success(request, "Caixa fechado com sucesso.")
        except ValidationError as erro:
            messages.error(request, "; ".join(erro.messages))
    else:
        messages.error(request, _erros_formulario(form, "Informe o valor contado."))
    return _renderizar_painel(request)


@login_required
def caixa_relatorio(request, pk):
    caixa = get_object_or_404(
        Caixa.objects.select_related("aberto_por", "fechado_por"),
        pk=pk,
        status=Caixa.Status.FECHADO,
    )
    contexto = {
        "caixa": caixa,
        "movimentos": caixa.movimentos.select_related("criado_por").all(),
    }
    return render(request, "caixa/relatorio.html", contexto)


@login_required
@require_POST
def caixa_estender_limite(request):
    caixa = Caixa.aberto_atual()
    if caixa is None:
        messages.error(request, "Não há caixa aberto no momento.")
        return _renderizar_painel(request)
    form = AutorizacaoAdminForm(request.POST)
    if form.is_valid():
        usuario = authenticate(
            request,
            username=form.cleaned_data["username"],
            password=form.cleaned_data["password"],
        )
        if usuario is not None and usuario.is_superuser:
            caixa.estender_limite()
            messages.success(request, "Autorizado: mais 1 hora liberada para iniciar vendas.")
        else:
            messages.error(
                request, "Usuário ou senha inválidos, ou sem permissão de administrador."
            )
    else:
        messages.error(request, _erros_formulario(form, "Informe usuário e senha do administrador."))
    return _renderizar_painel(request)
