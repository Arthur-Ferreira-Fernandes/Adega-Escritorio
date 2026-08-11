from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.formats import number_format
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from apps.caixa.models import Caixa
from apps.estoque.models import Produto

from .forms import (
    EscanearCodigoForm,
    FiltroHistoricoVendaForm,
    ItemVendaForm,
    NovaVendaForm,
    QuantidadePessoasForm,
)
from .models import ItemVenda, PagamentoVenda, Venda


def _bloqueio_caixa():
    caixa = Caixa.aberto_atual()
    if caixa is None:
        return "É necessário abrir o caixa antes de iniciar uma venda."
    if not caixa.dentro_do_limite:
        return (
            "O caixa passou do limite de horas em aberto. Peça a um administrador para "
            "autorizar mais tempo na tela do Caixa."
        )
    return None


class InicioView(LoginRequiredMixin, TemplateView):
    template_name = "vendas/inicio.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["total_vendas"] = Venda.objects.count()
        contexto["comandas_abertas"] = Venda.objects.filter(
            status=Venda.Status.ABERTA
        ).select_related("cliente")
        contexto["pode_vender"] = _bloqueio_caixa() is None
        return contexto


@login_required
def nova_venda(request):
    bloqueio = _bloqueio_caixa()
    if bloqueio:
        messages.error(request, bloqueio)
        return redirect("caixa:painel")
    if request.method == "POST":
        form = NovaVendaForm(request.POST)
        if form.is_valid():
            venda = Venda.objects.create(
                cliente=form.cleaned_data["cliente"],
                identificador=form.cleaned_data["identificador"],
                quantidade_pessoas=form.cleaned_data["quantidade_pessoas"],
                criado_por=request.user,
            )
            return redirect("vendas:detalhe", pk=venda.pk)
    else:
        form = NovaVendaForm()
    return render(request, "vendas/nova.html", {"form": form})


@login_required
@require_POST
def venda_rapida(request):
    bloqueio = _bloqueio_caixa()
    if bloqueio:
        messages.error(request, bloqueio)
        return redirect("caixa:painel")
    venda = Venda.objects.create(criado_por=request.user)
    return redirect("vendas:detalhe", pk=venda.pk)


def _contexto_venda(venda):
    return {
        "venda": venda,
        "itens": venda.itens.select_related("produto"),
        "item_form": ItemVendaForm(),
        "escanear_form": EscanearCodigoForm(),
        "pessoas_form": QuantidadePessoasForm(
            initial={"quantidade_pessoas": venda.quantidade_pessoas}
        ),
        "produtos_ativos": Produto.objects.filter(ativo=True),
        "falta_receber_bruto": str(venda.falta_receber),
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
def venda_atualizar_pessoas(request, pk):
    venda = get_object_or_404(Venda, pk=pk)
    form = QuantidadePessoasForm(request.POST)
    if form.is_valid():
        venda.quantidade_pessoas = form.cleaned_data["quantidade_pessoas"]
        venda.save(update_fields=["quantidade_pessoas"])
        messages.success(request, "Quantidade de pessoas na mesa atualizada.")
    else:
        messages.error(request, "Informe uma quantidade de pessoas válida.")
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
    try:
        venda.finalizar()
        messages.success(request, "Venda finalizada com sucesso.")
    except ValidationError as erro:
        messages.error(request, "; ".join(erro.messages))
    return _responder_venda(request, venda)


@login_required
@require_POST
def venda_adicionar_pagamento(request, pk):
    venda = get_object_or_404(Venda, pk=pk)
    valor_txt = request.POST.get("valor", "")
    try:
        valor = Decimal(valor_txt) if valor_txt.strip() else None
    except InvalidOperation:
        valor = None
    if valor is None:
        messages.error(request, "Informe um valor válido.")
    else:
        try:
            pagamento = venda.adicionar_pagamento(request.POST.get("forma_pagamento", ""), valor)
            texto = f"Pagamento em {pagamento.get_forma_pagamento_display()} registrado."
            if pagamento.troco:
                texto += f" Troco: R$ {number_format(pagamento.troco, decimal_pos=2)}."
            messages.success(request, texto)
        except ValidationError as erro:
            messages.error(request, "; ".join(erro.messages))
    return _responder_venda(request, venda)


@login_required
@require_POST
def venda_remover_pagamento(request, pk, pagamento_id):
    venda = get_object_or_404(Venda, pk=pk)
    pagamento = get_object_or_404(PagamentoVenda, pk=pagamento_id, venda=venda)
    try:
        venda.remover_pagamento(pagamento)
        messages.success(request, "Pagamento removido.")
    except ValidationError as erro:
        messages.error(request, "; ".join(erro.messages))
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
    vendas = Venda.objects.select_related("cliente").prefetch_related("pagamentos")
    if form.is_valid():
        if form.cleaned_data.get("data_inicio"):
            vendas = vendas.filter(criado_em__date__gte=form.cleaned_data["data_inicio"])
        if form.cleaned_data.get("data_fim"):
            vendas = vendas.filter(criado_em__date__lte=form.cleaned_data["data_fim"])
        if form.cleaned_data.get("status"):
            vendas = vendas.filter(status=form.cleaned_data["status"])
        if form.cleaned_data.get("forma_pagamento"):
            vendas = vendas.filter(pagamentos__forma_pagamento=form.cleaned_data["forma_pagamento"])
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


@login_required
def venda_comprovante(request, pk):
    venda = get_object_or_404(Venda.objects.select_related("cliente", "criado_por"), pk=pk)
    if venda.status != Venda.Status.CONCLUIDA:
        messages.error(request, "Só é possível emitir comprovante de vendas finalizadas.")
        return redirect("vendas:detalhe", pk=venda.pk)
    contexto = {
        "venda": venda,
        "itens": venda.itens.select_related("produto"),
        "pagamentos": venda.pagamentos.all(),
    }
    return render(request, "vendas/comprovante.html", contexto)
