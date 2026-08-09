from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from apps.estoque.models import Produto

from .forms import (
    EscanearCodigoForm,
    FiltroHistoricoVendaForm,
    FinalizarVendaForm,
    ItemVendaForm,
    NovaVendaForm,
)
from .models import ItemVenda, Venda


class InicioView(LoginRequiredMixin, TemplateView):
    template_name = "vendas/inicio.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["total_vendas"] = Venda.objects.count()
        contexto["comandas_abertas"] = Venda.objects.filter(
            status=Venda.Status.ABERTA
        ).select_related("cliente")
        return contexto


@login_required
def nova_venda(request):
    if request.method == "POST":
        form = NovaVendaForm(request.POST)
        if form.is_valid():
            venda = Venda.objects.create(
                cliente=form.cleaned_data["cliente"],
                identificador=form.cleaned_data["identificador"],
                criado_por=request.user,
            )
            return redirect("vendas:detalhe", pk=venda.pk)
    else:
        form = NovaVendaForm()
    return render(request, "vendas/nova.html", {"form": form})


@login_required
@require_POST
def venda_rapida(request):
    venda = Venda.objects.create(criado_por=request.user)
    return redirect("vendas:detalhe", pk=venda.pk)


def _contexto_venda(venda):
    return {
        "venda": venda,
        "itens": venda.itens.select_related("produto"),
        "item_form": ItemVendaForm(),
        "finalizar_form": FinalizarVendaForm(),
        "escanear_form": EscanearCodigoForm(),
        "produtos_ativos": Produto.objects.filter(ativo=True),
    }


def _responder_venda(request, venda):
    if request.headers.get("HX-Request") == "true":
        return render(request, "vendas/_conteudo_htmx.html", _contexto_venda(venda))
    return redirect("vendas:detalhe", pk=venda.pk)


@login_required
def venda_detalhe(request, pk):
    venda = get_object_or_404(
        Venda.objects.select_related("cliente"), pk=pk
    )
    return render(request, "vendas/detalhe.html", _contexto_venda(venda))


@login_required
@require_POST
def venda_escanear(request, pk):
    venda = get_object_or_404(Venda, pk=pk)
    form = EscanearCodigoForm(request.POST)
    if form.is_valid():
        try:
            item = venda.adicionar_por_codigo_barras(form.cleaned_data["codigo_barras"])
            messages.success(
                request,
                f"Adicionado: {item.produto.nome} (quantidade na venda: {item.quantidade}).",
            )
        except ValidationError as erro:
            messages.error(request, "; ".join(erro.messages))
    else:
        messages.error(request, "Informe um código de barras válido.")
    return _responder_venda(request, venda)


@login_required
@require_POST
def venda_adicionar_item(request, pk):
    venda = get_object_or_404(Venda, pk=pk)
    form = ItemVendaForm(request.POST)
    if form.is_valid():
        try:
            venda.adicionar_item(
                produto=form.cleaned_data["produto_busca"],
                quantidade=form.cleaned_data["quantidade"],
            )
        except ValidationError as erro:
            messages.error(request, "; ".join(erro.messages))
    else:
        erros = [msg for mensagens in form.errors.values() for msg in mensagens]
        messages.error(request, "; ".join(erros) or "Não foi possível adicionar o item.")
    return _responder_venda(request, venda)


@login_required
@require_POST
def venda_remover_item(request, pk, item_id):
    venda = get_object_or_404(Venda, pk=pk)
    item = get_object_or_404(ItemVenda, pk=item_id, venda=venda)
    try:
        venda.remover_item(item)
    except ValidationError as erro:
        messages.error(request, "; ".join(erro.messages))
    return _responder_venda(request, venda)


@login_required
@require_POST
def venda_finalizar(request, pk):
    venda = get_object_or_404(Venda, pk=pk)
    form = FinalizarVendaForm(request.POST)
    if form.is_valid():
        try:
            venda.finalizar(form.cleaned_data["forma_pagamento"])
            messages.success(request, "Venda finalizada com sucesso.")
        except ValidationError as erro:
            messages.error(request, "; ".join(erro.messages))
    else:
        messages.error(request, "Selecione a forma de pagamento para finalizar.")
    return _responder_venda(request, venda)


@login_required
@require_POST
def venda_cancelar(request, pk):
    venda = get_object_or_404(Venda, pk=pk)
    try:
        venda.cancelar()
        messages.success(request, "Venda cancelada.")
    except ValidationError as erro:
        messages.error(request, "; ".join(erro.messages))
    return _responder_venda(request, venda)


@login_required
def historico(request):
    form = FiltroHistoricoVendaForm(request.GET or None)
    vendas = Venda.objects.select_related("cliente")
    if form.is_valid():
        if form.cleaned_data.get("data_inicio"):
            vendas = vendas.filter(criado_em__date__gte=form.cleaned_data["data_inicio"])
        if form.cleaned_data.get("data_fim"):
            vendas = vendas.filter(criado_em__date__lte=form.cleaned_data["data_fim"])
        if form.cleaned_data.get("status"):
            vendas = vendas.filter(status=form.cleaned_data["status"])
        if form.cleaned_data.get("forma_pagamento"):
            vendas = vendas.filter(forma_pagamento=form.cleaned_data["forma_pagamento"])
        if form.cleaned_data.get("cliente"):
            vendas = vendas.filter(cliente=form.cleaned_data["cliente"])

    paginator = Paginator(vendas, 20)
    pagina = paginator.get_page(request.GET.get("pagina"))

    querystring = request.GET.copy()
    querystring.pop("pagina", None)

    contexto = {"form": form, "pagina": pagina, "querystring": querystring.urlencode()}
    template = (
        "vendas/_historico_conteudo.html"
        if request.headers.get("HX-Request") == "true"
        else "vendas/historico.html"
    )
    return render(request, template, contexto)
