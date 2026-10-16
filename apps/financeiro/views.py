from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from apps.auditoria import servicos as auditoria
from apps.auditoria.models import RegistroAuditoria
from apps.caixa.models import Caixa

from .forms import ContaPagarForm, ContaReceberForm
from .models import ContaPagar, ContaReceber


class InicioView(TemplateView):
    template_name = "financeiro/inicio.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["total_contas_pagar"] = ContaPagar.objects.count()
        contexto["total_contas_receber"] = ContaReceber.objects.count()
        return contexto


def _renderizar(request, contexto, *, template_htmx, template_completo):
    template = (
        template_htmx
        if request.headers.get("HX-Request") == "true"
        else template_completo
    )
    return render(request, template, contexto)


# --- Contas a pagar --------------------------------------------------------

def _contexto_contas_pagar(form_ativo=False, form=None, editando=None):
    return {
        "contas": ContaPagar.objects.select_related("fornecedor").all(),
        "form_ativo": form_ativo,
        "form": form,
        "editando": editando,
    }


def _renderizar_contas_pagar(request, contexto):
    return _renderizar(
        request,
        contexto,
        template_htmx="financeiro/_contas_pagar_conteudo_htmx.html",
        template_completo="financeiro/contas_pagar.html",
    )


@login_required
def contas_pagar_lista(request):
    return _renderizar_contas_pagar(request, _contexto_contas_pagar())


@login_required
def contas_pagar_nova(request):
    if request.method == "POST":
        form = ContaPagarForm(request.POST)
        if form.is_valid():
            conta = form.save()
            auditoria.registrar(request.user, RegistroAuditoria.Acao.CRIACAO, conta)
            messages.success(request, "Conta a pagar cadastrada com sucesso.")
            if request.headers.get("HX-Request") == "true":
                return _renderizar_contas_pagar(request, _contexto_contas_pagar())
            return redirect("financeiro:contas_pagar")
    else:
        form = ContaPagarForm()
    return _renderizar_contas_pagar(
        request, _contexto_contas_pagar(form_ativo=True, form=form)
    )


@login_required
def contas_pagar_editar(request, pk):
    conta = get_object_or_404(ContaPagar, pk=pk)
    if request.method == "POST":
        form = ContaPagarForm(request.POST, instance=conta)
        valores_antigos = auditoria.capturar_valores(conta, form.fields)
        if form.is_valid():
            form.save()
            auditoria.registrar(
                request.user, RegistroAuditoria.Acao.EDICAO, conta,
                detalhes=auditoria.resumir_alteracoes(form, valores_antigos),
            )
            messages.success(request, "Conta a pagar atualizada com sucesso.")
            if request.headers.get("HX-Request") == "true":
                return _renderizar_contas_pagar(request, _contexto_contas_pagar())
            return redirect("financeiro:contas_pagar")
    else:
        form = ContaPagarForm(instance=conta)
    return _renderizar_contas_pagar(
        request, _contexto_contas_pagar(form_ativo=True, form=form, editando=conta)
    )


@login_required
@require_POST
def contas_pagar_excluir(request, pk):
    conta = get_object_or_404(ContaPagar, pk=pk)
    repr_objeto, id_objeto = str(conta), conta.pk
    conta.delete()
    auditoria.registrar(
        request.user, RegistroAuditoria.Acao.EXCLUSAO, conta,
        objeto_id=id_objeto, detalhes=repr_objeto,
    )
    messages.success(request, "Conta a pagar excluída.")
    return _renderizar_contas_pagar(request, _contexto_contas_pagar())


@login_required
@require_POST
def contas_pagar_marcar_paga(request, pk):
    conta = get_object_or_404(ContaPagar, pk=pk)
    if not conta.pago:
        conta.pago = True
        conta.pago_em = timezone.localdate()
        conta.save(update_fields=["pago", "pago_em"])
        auditoria.registrar(
            request.user, RegistroAuditoria.Acao.EDICAO, conta,
            detalhes="Marcada como paga",
        )
        messages.success(request, "Conta marcada como paga.")
    return _renderizar_contas_pagar(request, _contexto_contas_pagar())


# --- Contas a receber -------------------------------------------------------

def _contexto_contas_receber(form_ativo=False, form=None, editando=None):
    return {
        "contas": ContaReceber.objects.select_related("cliente", "venda").all(),
        "form_ativo": form_ativo,
        "form": form,
        "editando": editando,
    }


def _renderizar_contas_receber(request, contexto):
    return _renderizar(
        request,
        contexto,
        template_htmx="financeiro/_contas_receber_conteudo_htmx.html",
        template_completo="financeiro/contas_receber.html",
    )


@login_required
def contas_receber_lista(request):
    return _renderizar_contas_receber(request, _contexto_contas_receber())


@login_required
def contas_receber_nova(request):
    if request.method == "POST":
        form = ContaReceberForm(request.POST)
        if form.is_valid():
            conta = form.save()
            auditoria.registrar(request.user, RegistroAuditoria.Acao.CRIACAO, conta)
            messages.success(request, "Conta a receber cadastrada com sucesso.")
            if request.headers.get("HX-Request") == "true":
                return _renderizar_contas_receber(request, _contexto_contas_receber())
            return redirect("financeiro:contas_receber")
    else:
        form = ContaReceberForm()
    return _renderizar_contas_receber(
        request, _contexto_contas_receber(form_ativo=True, form=form)
    )


@login_required
def contas_receber_editar(request, pk):
    conta = get_object_or_404(ContaReceber, pk=pk)
    if request.method == "POST":
        form = ContaReceberForm(request.POST, instance=conta)
        valores_antigos = auditoria.capturar_valores(conta, form.fields)
        if form.is_valid():
            form.save()
            auditoria.registrar(
                request.user, RegistroAuditoria.Acao.EDICAO, conta,
                detalhes=auditoria.resumir_alteracoes(form, valores_antigos),
            )
            messages.success(request, "Conta a receber atualizada com sucesso.")
            if request.headers.get("HX-Request") == "true":
                return _renderizar_contas_receber(request, _contexto_contas_receber())
            return redirect("financeiro:contas_receber")
    else:
        form = ContaReceberForm(instance=conta)
    return _renderizar_contas_receber(
        request, _contexto_contas_receber(form_ativo=True, form=form, editando=conta)
    )


@login_required
@require_POST
def contas_receber_excluir(request, pk):
    conta = get_object_or_404(ContaReceber, pk=pk)
    repr_objeto, id_objeto = str(conta), conta.pk
    conta.delete()
    auditoria.registrar(
        request.user, RegistroAuditoria.Acao.EXCLUSAO, conta,
        objeto_id=id_objeto, detalhes=repr_objeto,
    )
    messages.success(request, "Conta a receber excluída.")
    return _renderizar_contas_receber(request, _contexto_contas_receber())


@login_required
@require_POST
def contas_receber_marcar_recebida(request, pk):
    conta = get_object_or_404(ContaReceber.objects.select_related("cliente"), pk=pk)
    forma = request.POST.get("forma") or ContaReceber.FormaRecebimento.PIX
    if forma not in ContaReceber.FormaRecebimento.values:
        messages.error(request, "Forma de recebimento inválida.")
    elif not conta.recebido:
        caixa = Caixa.aberto_atual()
        if forma == ContaReceber.FormaRecebimento.DINHEIRO and caixa is None:
            messages.error(request, "Para receber em dinheiro, abra o caixa: o valor precisa entrar nele.")
            return _renderizar_contas_receber(request, _contexto_contas_receber())
        with transaction.atomic():
            conta.recebido = True
            conta.recebido_em = timezone.localdate()
            conta.forma_recebimento = forma
            conta.save(update_fields=["recebido", "recebido_em", "forma_recebimento"])
            if forma == ContaReceber.FormaRecebimento.DINHEIRO:
                caixa.registrar_recebimento(request.user, conta.valor, f"Recebimento: {conta.descricao} ({conta.cliente})")
        auditoria.registrar(
            request.user, RegistroAuditoria.Acao.EDICAO, conta,
            detalhes=f"Recebida em {conta.get_forma_recebimento_display()}",
        )
        if forma == ContaReceber.FormaRecebimento.DINHEIRO:
            from apps.caixa import gaveta

            gaveta.abrir_ao_receber_dinheiro()
        messages.success(request, f"Conta recebida em {conta.get_forma_recebimento_display()}.")
    return _renderizar_contas_receber(request, _contexto_contas_receber())
