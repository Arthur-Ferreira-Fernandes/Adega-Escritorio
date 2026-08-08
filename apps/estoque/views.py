from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from .forms import ProdutoForm
from .models import Categoria, Produto


class InicioView(TemplateView):
    template_name = "estoque/inicio.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["total_produtos"] = Produto.objects.count()
        contexto["total_categorias"] = Categoria.objects.count()
        return contexto


def _contexto_produtos(form_ativo=False, form=None, editando=None):
    return {
        "produtos": Produto.objects.select_related("categoria").all(),
        "form_ativo": form_ativo,
        "form": form,
        "editando": editando,
    }


def _renderizar(request, contexto):
    template = (
        "estoque/_produtos_conteudo_htmx.html"
        if request.headers.get("HX-Request") == "true"
        else "estoque/produtos.html"
    )
    return render(request, template, contexto)


@login_required
def produtos_lista(request):
    return _renderizar(request, _contexto_produtos())


@login_required
def produtos_novo(request):
    if request.method == "POST":
        form = ProdutoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Produto cadastrado com sucesso.")
            if request.headers.get("HX-Request") == "true":
                return _renderizar(request, _contexto_produtos())
            return redirect("estoque:produtos")
    else:
        form = ProdutoForm()
    return _renderizar(request, _contexto_produtos(form_ativo=True, form=form))


@login_required
def produtos_editar(request, pk):
    produto = get_object_or_404(Produto, pk=pk)
    if request.method == "POST":
        form = ProdutoForm(request.POST, instance=produto)
        if form.is_valid():
            form.save()
            messages.success(request, "Produto atualizado com sucesso.")
            if request.headers.get("HX-Request") == "true":
                return _renderizar(request, _contexto_produtos())
            return redirect("estoque:produtos")
    else:
        form = ProdutoForm(instance=produto)
    return _renderizar(
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
    return _renderizar(request, _contexto_produtos())
