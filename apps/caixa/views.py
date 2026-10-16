import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import number_format
from django.views.decorators.http import require_POST

from apps.notificacoes.models import Notificacao
from apps.relatorios import analises

from .forms import AbrirCaixaForm, FecharCaixaForm, MovimentoCaixaForm
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
    if caixa:
        Caixa.calcular_totais([caixa])
    return {
        "caixa": caixa,
        "movimentos": caixa.movimentos.select_related("criado_por").all() if caixa else [],
        "historico": Caixa.calcular_totais(
            Caixa.objects.filter(status=Caixa.Status.FECHADO).select_related("aberto_por", "fechado_por")[:10]
        ),
        "abrir_form": AbrirCaixaForm(),
        "sangria_form": MovimentoCaixaForm(),
        "reforco_form": MovimentoCaixaForm(),
        "fechar_form": FecharCaixaForm(),
        "gaveta_configurada": _gaveta_configurada(),
    }


def _gaveta_configurada():
    from apps.configuracoes.models import Configuracao

    from . import gaveta

    return gaveta.disponivel() and bool(Configuracao.obter().impressora_gaveta)


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
            resumo = _notificar_fechamento(caixa)
            logger.info(
                "Caixa fechado",
                extra={
                    "usuario": request.user.username,
                    "valor_contado": str(caixa.valor_contado),
                    "diferenca": str(caixa.diferenca()),
                },
            )
            messages.success(
                request,
                f"Caixa fechado. No turno: R$ {number_format(resumo['faturamento'], decimal_pos=2)} "
                f"em {resumo['numero_vendas']} venda{'s' if resumo['numero_vendas'] != 1 else ''}, "
                f"lucro de R$ {number_format(resumo['lucro'], decimal_pos=2)}.",
            )
        except ValidationError as erro:
            messages.error(request, "; ".join(erro.messages))
    else:
        messages.error(request, _erros_formulario(form, "Informe o valor contado."))
    return _renderizar_painel(request)


@login_required
@require_POST
def caixa_abrir_gaveta(request):
    from apps.configuracoes.models import Configuracao

    from . import gaveta

    impressora = request.POST.get("impressora") or Configuracao.obter().impressora_gaveta
    try:
        gaveta.abrir(impressora)
        messages.success(request, "Comando de abrir a gaveta enviado.")
    except Exception as erro:
        logger.exception("Falha ao abrir a gaveta")
        messages.error(request, f"Não foi possível abrir a gaveta: {erro}")
    if request.POST.get("voltar") == "configuracoes":
        return redirect("configuracoes:administracao")
    return _renderizar_painel(request)


@login_required
def caixa_relatorio(request, pk):
    caixa = get_object_or_404(
        Caixa.objects.select_related("aberto_por", "fechado_por"),
        pk=pk,
        status=Caixa.Status.FECHADO,
    )
    Caixa.calcular_totais([caixa])
    contexto = {
        "caixa": caixa,
        "movimentos": caixa.movimentos.select_related("criado_por").all(),
        "resumo": analises.resumo_do_caixa(caixa),
    }
    return render(request, "caixa/relatorio.html", contexto)


def _notificar_fechamento(caixa):
    """Deixa o resumo do turno no sino; só o do último fechamento fica ativo."""
    resumo = analises.resumo_do_caixa(caixa)
    diferenca = caixa.diferenca()
    chave = f"caixa:{caixa.pk}"
    texto_diferenca = (
        "caixa sem diferença" if not diferenca
        else f"{'sobra' if diferenca > 0 else 'falta'} de R$ {number_format(abs(diferenca), decimal_pos=2)} no caixa"
    )
    Notificacao.registrar(
        Notificacao.Tipo.RESUMO_CAIXA,
        chave,
        (
            f"Fechamento {timezone.localtime(caixa.fechado_em):%d/%m}: "
            f"R$ {number_format(resumo['faturamento'], decimal_pos=2)} em {resumo['numero_vendas']} "
            f"venda{'s' if resumo['numero_vendas'] != 1 else ''}, "
            f"lucro R$ {number_format(resumo['lucro'], decimal_pos=2)}; {texto_diferenca}."
        )[:255],
        link=reverse("caixa:relatorio", kwargs={"pk": caixa.pk}),
        nivel=Notificacao.Nivel.PERIGO if diferenca and diferenca < 0 else Notificacao.Nivel.AVISO,
    )
    Notificacao.resolver_ausentes(Notificacao.Tipo.RESUMO_CAIXA, [chave])
    return resumo
