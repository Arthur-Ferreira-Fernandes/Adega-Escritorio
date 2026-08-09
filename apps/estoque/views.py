from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from .forms import CategoriaForm, ProdutoForm
from .models import Categoria, Produto


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
            form.save()
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
        if form.is_valid():
            form.save()
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
    try:
        produto.delete()
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
            form.save()
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
        if form.is_valid():
            form.save()
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
    try:
        categoria.delete()
        messages.success(request, "Categoria excluída.")
    except ProtectedError:
        messages.error(
            request,
            "Não é possível excluir: existem produtos cadastrados nessa categoria. "
            "Mova ou exclua os produtos primeiro.",
        )
    return _renderizar_categorias(request, _contexto_categorias())
