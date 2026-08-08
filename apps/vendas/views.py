from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from .forms import FinalizarVendaForm, ItemVendaForm, NovaVendaForm
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
def venda_detalhe(request, pk):
    venda = get_object_or_404(
        Venda.objects.select_related("cliente"), pk=pk
    )
    contexto = {
        "venda": venda,
        "itens": venda.itens.select_related("produto"),
        "item_form": ItemVendaForm(),
        "finalizar_form": FinalizarVendaForm(),
    }
    return render(request, "vendas/detalhe.html", contexto)


@login_required
@require_POST
def venda_adicionar_item(request, pk):
    venda = get_object_or_404(Venda, pk=pk)
    form = ItemVendaForm(request.POST)
    if form.is_valid():
        try:
            venda.adicionar_item(
                produto=form.cleaned_data["produto"],
                quantidade=form.cleaned_data["quantidade"],
            )
        except ValidationError as erro:
            messages.error(request, "; ".join(erro.messages))
    else:
        messages.error(request, "Não foi possível adicionar o item: verifique os dados informados.")
    return redirect("vendas:detalhe", pk=venda.pk)


@login_required
@require_POST
def venda_remover_item(request, pk, item_id):
    venda = get_object_or_404(Venda, pk=pk)
    item = get_object_or_404(ItemVenda, pk=item_id, venda=venda)
    try:
        venda.remover_item(item)
    except ValidationError as erro:
        messages.error(request, "; ".join(erro.messages))
    return redirect("vendas:detalhe", pk=venda.pk)


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
    return redirect("vendas:detalhe", pk=venda.pk)


@login_required
@require_POST
def venda_cancelar(request, pk):
    venda = get_object_or_404(Venda, pk=pk)
    try:
        venda.cancelar()
        messages.success(request, "Venda cancelada.")
    except ValidationError as erro:
        messages.error(request, "; ".join(erro.messages))
    return redirect("vendas:detalhe", pk=venda.pk)
