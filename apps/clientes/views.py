from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from apps.auditoria import servicos as auditoria
from apps.auditoria.models import RegistroAuditoria

from .forms import ClienteForm, FornecedorForm
from .models import Cliente, Fornecedor


class InicioView(TemplateView):
    template_name = "clientes/inicio.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["total_clientes"] = Cliente.objects.count()
        contexto["total_fornecedores"] = Fornecedor.objects.count()
        return contexto


def _renderizar(request, contexto, *, template_htmx, template_completo):
    template = (
        template_htmx
        if request.headers.get("HX-Request") == "true"
        else template_completo
    )
    return render(request, template, contexto)


# --- Clientes ---------------------------------------------------------------

def _contexto_clientes(form_ativo=False, form=None, editando=None):
    return {
        "clientes": Cliente.objects.all(),
        "form_ativo": form_ativo,
        "form": form,
        "editando": editando,
    }


def _renderizar_clientes(request, contexto):
    return _renderizar(
        request,
        contexto,
        template_htmx="clientes/_clientes_conteudo_htmx.html",
        template_completo="clientes/clientes.html",
    )


@login_required
def clientes_lista(request):
    return _renderizar_clientes(request, _contexto_clientes())


@login_required
def clientes_novo(request):
    if request.method == "POST":
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente = form.save()
            auditoria.registrar(request.user, RegistroAuditoria.Acao.CRIACAO, cliente)
            messages.success(request, "Cliente cadastrado com sucesso.")
            if request.headers.get("HX-Request") == "true":
                return _renderizar_clientes(request, _contexto_clientes())
            return redirect("clientes:clientes")
    else:
        form = ClienteForm()
    return _renderizar_clientes(request, _contexto_clientes(form_ativo=True, form=form))


@login_required
def clientes_editar(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == "POST":
        form = ClienteForm(request.POST, instance=cliente)
        valores_antigos = auditoria.capturar_valores(cliente, form.fields)
        if form.is_valid():
            form.save()
            auditoria.registrar(
                request.user, RegistroAuditoria.Acao.EDICAO, cliente,
                detalhes=auditoria.resumir_alteracoes(form, valores_antigos),
            )
            messages.success(request, "Cliente atualizado com sucesso.")
            if request.headers.get("HX-Request") == "true":
                return _renderizar_clientes(request, _contexto_clientes())
            return redirect("clientes:clientes")
    else:
        form = ClienteForm(instance=cliente)
    return _renderizar_clientes(
        request, _contexto_clientes(form_ativo=True, form=form, editando=cliente)
    )


@login_required
@require_POST
def clientes_excluir(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    repr_objeto, id_objeto = str(cliente), cliente.pk
    try:
        cliente.delete()
        auditoria.registrar(
            request.user, RegistroAuditoria.Acao.EXCLUSAO, cliente,
            objeto_id=id_objeto, detalhes=repr_objeto,
        )
        messages.success(request, "Cliente excluído.")
    except ProtectedError:
        messages.error(
            request,
            "Não é possível excluir: este cliente tem contas a receber registradas.",
        )
    return _renderizar_clientes(request, _contexto_clientes())


# --- Fornecedores -------------------------------------------------------------

def _contexto_fornecedores(form_ativo=False, form=None, editando=None):
    return {
        "fornecedores": Fornecedor.objects.all(),
        "form_ativo": form_ativo,
        "form": form,
        "editando": editando,
    }


def _renderizar_fornecedores(request, contexto):
    return _renderizar(
        request,
        contexto,
        template_htmx="clientes/_fornecedores_conteudo_htmx.html",
        template_completo="clientes/fornecedores.html",
    )


@login_required
def fornecedores_lista(request):
    return _renderizar_fornecedores(request, _contexto_fornecedores())


@login_required
def fornecedores_novo(request):
    if request.method == "POST":
        form = FornecedorForm(request.POST)
        if form.is_valid():
            fornecedor = form.save()
            auditoria.registrar(request.user, RegistroAuditoria.Acao.CRIACAO, fornecedor)
            messages.success(request, "Fornecedor cadastrado com sucesso.")
            if request.headers.get("HX-Request") == "true":
                return _renderizar_fornecedores(request, _contexto_fornecedores())
            return redirect("clientes:fornecedores")
    else:
        form = FornecedorForm()
    return _renderizar_fornecedores(
        request, _contexto_fornecedores(form_ativo=True, form=form)
    )


@login_required
def fornecedores_editar(request, pk):
    fornecedor = get_object_or_404(Fornecedor, pk=pk)
    if request.method == "POST":
        form = FornecedorForm(request.POST, instance=fornecedor)
        valores_antigos = auditoria.capturar_valores(fornecedor, form.fields)
        if form.is_valid():
            form.save()
            auditoria.registrar(
                request.user, RegistroAuditoria.Acao.EDICAO, fornecedor,
                detalhes=auditoria.resumir_alteracoes(form, valores_antigos),
            )
            messages.success(request, "Fornecedor atualizado com sucesso.")
            if request.headers.get("HX-Request") == "true":
                return _renderizar_fornecedores(request, _contexto_fornecedores())
            return redirect("clientes:fornecedores")
    else:
        form = FornecedorForm(instance=fornecedor)
    return _renderizar_fornecedores(
        request,
        _contexto_fornecedores(form_ativo=True, form=form, editando=fornecedor),
    )


@login_required
@require_POST
def fornecedores_excluir(request, pk):
    fornecedor = get_object_or_404(Fornecedor, pk=pk)
    repr_objeto, id_objeto = str(fornecedor), fornecedor.pk
    try:
        fornecedor.delete()
        auditoria.registrar(
            request.user, RegistroAuditoria.Acao.EXCLUSAO, fornecedor,
            objeto_id=id_objeto, detalhes=repr_objeto,
        )
        messages.success(request, "Fornecedor excluído.")
    except ProtectedError:
        messages.error(
            request,
            "Não é possível excluir: este fornecedor tem contas a pagar registradas.",
        )
    return _renderizar_fornecedores(request, _contexto_fornecedores())
