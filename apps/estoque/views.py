from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from apps.auditoria import servicos as auditoria
from apps.auditoria.models import RegistroAuditoria

from .forms import CategoriaForm, EntradaEstoqueForm, ProdutoForm
from .models import Categoria, EntradaEstoque, Produto


class InicioView(TemplateView):
    template_name = "estoque/inicio.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["total_produtos"] = Produto.objects.count()
        contexto["total_categorias"] = Categoria.objects.count()
        return contexto


def _renderizar(request, contexto, *, template_htmx, template_completo):
    template = (
        template_htmx
        if request.headers.get("HX-Request") == "true"
        else template_completo
    )
    return render(request, template, contexto)


def _contexto_produtos(form_ativo=False, form=None, editando=None):
    return {
        "produtos": Produto.objects.select_related("categoria").all(),
        "form_ativo": form_ativo,
        "form": form,
        "editando": editando,
    }


def _renderizar_produtos(request, contexto):
    return _renderizar(
        request,
        contexto,
        template_htmx="estoque/_produtos_conteudo_htmx.html",
        template_completo="estoque/produtos.html",
    )


@login_required
def produtos_lista(request):
    return _renderizar_produtos(request, _contexto_produtos())


@login_required
def produtos_novo(request):
    if request.method == "POST":
        form = ProdutoForm(request.POST)
        if form.is_valid():
            produto = form.save()
            auditoria.registrar(request.user, RegistroAuditoria.Acao.CRIACAO, produto)
            messages.success(request, "Produto cadastrado com sucesso.")
            if request.headers.get("HX-Request") == "true":
                return _renderizar_produtos(request, _contexto_produtos())
            return redirect("estoque:produtos")
    else:
        form = ProdutoForm()
    return _renderizar_produtos(request, _contexto_produtos(form_ativo=True, form=form))


@login_required
def produtos_editar(request, pk):
    produto = get_object_or_404(Produto, pk=pk)
    if request.method == "POST":
        form = ProdutoForm(request.POST, instance=produto)
        valores_antigos = auditoria.capturar_valores(produto, form.fields)
        if form.is_valid():
            form.save()
            auditoria.registrar(
                request.user, RegistroAuditoria.Acao.EDICAO, produto,
                detalhes=auditoria.resumir_alteracoes(form, valores_antigos),
            )
            messages.success(request, "Produto atualizado com sucesso.")
            if request.headers.get("HX-Request") == "true":
                return _renderizar_produtos(request, _contexto_produtos())
            return redirect("estoque:produtos")
    else:
        form = ProdutoForm(instance=produto)
    return _renderizar_produtos(
        request, _contexto_produtos(form_ativo=True, form=form, editando=produto)
    )


@login_required
@require_POST
def produtos_excluir(request, pk):
    produto = get_object_or_404(Produto, pk=pk)
    repr_objeto, id_objeto = str(produto), produto.pk
    try:
        produto.delete()
        auditoria.registrar(
            request.user, RegistroAuditoria.Acao.EXCLUSAO, produto,
            objeto_id=id_objeto, detalhes=repr_objeto,
        )
        messages.success(request, "Produto excluído.")
    except ProtectedError:
        messages.error(
            request,
            "Não é possível excluir: este produto já tem vendas registradas. "
            "Desative-o em vez de excluir.",
        )
    return _renderizar_produtos(request, _contexto_produtos())


def _contexto_categorias(form_ativo=False, form=None, editando=None):
    return {
        "categorias": Categoria.objects.all(),
        "form_ativo": form_ativo,
        "form": form,
        "editando": editando,
    }


def _renderizar_categorias(request, contexto):
    return _renderizar(
        request,
        contexto,
        template_htmx="estoque/_categorias_conteudo_htmx.html",
        template_completo="estoque/categorias.html",
    )


@login_required
def categorias_lista(request):
    return _renderizar_categorias(request, _contexto_categorias())


@login_required
def categorias_nova(request):
    if request.method == "POST":
        form = CategoriaForm(request.POST)
        if form.is_valid():
            categoria = form.save()
            auditoria.registrar(request.user, RegistroAuditoria.Acao.CRIACAO, categoria)
            messages.success(request, "Categoria cadastrada com sucesso.")
            if request.headers.get("HX-Request") == "true":
                return _renderizar_categorias(request, _contexto_categorias())
            return redirect("estoque:categorias")
    else:
        form = CategoriaForm()
    return _renderizar_categorias(
        request, _contexto_categorias(form_ativo=True, form=form)
    )


@login_required
def categorias_editar(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)
    if request.method == "POST":
        form = CategoriaForm(request.POST, instance=categoria)
        valores_antigos = auditoria.capturar_valores(categoria, form.fields)
        if form.is_valid():
            form.save()
            auditoria.registrar(
                request.user, RegistroAuditoria.Acao.EDICAO, categoria,
                detalhes=auditoria.resumir_alteracoes(form, valores_antigos),
            )
            messages.success(request, "Categoria atualizada com sucesso.")
            if request.headers.get("HX-Request") == "true":
                return _renderizar_categorias(request, _contexto_categorias())
            return redirect("estoque:categorias")
    else:
        form = CategoriaForm(instance=categoria)
    return _renderizar_categorias(
        request, _contexto_categorias(form_ativo=True, form=form, editando=categoria)
    )


@login_required
@require_POST
def categorias_excluir(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)
    repr_objeto, id_objeto = str(categoria), categoria.pk
    try:
        categoria.delete()
        auditoria.registrar(
            request.user, RegistroAuditoria.Acao.EXCLUSAO, categoria,
            objeto_id=id_objeto, detalhes=repr_objeto,
        )
        messages.success(request, "Categoria excluída.")
    except ProtectedError:
        messages.error(
            request,
            "Não é possível excluir: existem produtos cadastrados nessa categoria. "
            "Mova ou exclua os produtos primeiro.",
        )
    return _renderizar_categorias(request, _contexto_categorias())


def _contexto_entradas(form=None):
    return {
        "entrada_form": form or EntradaEstoqueForm(),
        "entradas": EntradaEstoque.objects.select_related(
            "produto", "fornecedor", "criado_por"
        )[:50],
        "produtos_ativos": Produto.objects.filter(ativo=True),
    }


def _renderizar_entradas(request, contexto):
    return _renderizar(
        request,
        contexto,
        template_htmx="estoque/_entradas_conteudo_htmx.html",
        template_completo="estoque/entradas.html",
    )


@login_required
def entradas_lista(request):
    return _renderizar_entradas(request, _contexto_entradas())


@login_required
@require_POST
def entradas_registrar(request):
    form = EntradaEstoqueForm(request.POST)
    if form.is_valid():
        try:
            form.cleaned_data["produto_busca"].registrar_entrada(
                quantidade=form.cleaned_data["quantidade"],
                fornecedor=form.cleaned_data["fornecedor"],
                custo_unitario=form.cleaned_data["custo_unitario"],
                usuario=request.user,
            )
            messages.success(request, "Entrada de estoque registrada com sucesso.")
        except ValidationError as erro:
            messages.error(request, "; ".join(erro.messages))
    else:
        erros = [msg for mensagens in form.errors.values() for msg in mensagens]
        messages.error(request, "; ".join(erros) or "Não foi possível registrar a entrada.")
    return _renderizar_entradas(request, _contexto_entradas())
