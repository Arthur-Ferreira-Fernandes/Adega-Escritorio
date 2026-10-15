from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import F, Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.formats import number_format
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from apps.auditoria import servicos as auditoria
from apps.auditoria.models import RegistroAuditoria
from apps.relatorios.exportar import resposta_csv

from .forms import CategoriaForm, EntradaEstoqueForm, ProdutoForm
from .models import AjusteEstoque, Categoria, EntradaEstoque, Produto
from .servicos import dados_para_busca


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
    if request.GET.get("exportar"):
        return resposta_csv(
            f"produtos_{timezone.localdate():%Y-%m-%d}",
            ["Produto", "SKU", "Código de barras", "Categoria", "Preço de custo", "Preço de venda",
             "Margem (%)", "Estoque", "Estoque mínimo", "Unidade", "Ativo", "Valor em estoque (custo)"],
            [
                [p.nome, p.sku, p.codigo_barras, p.categoria, p.preco_custo, p.preco_venda,
                 ((p.preco_venda - p.preco_custo) / p.preco_venda * 100) if p.preco_venda else None,
                 p.quantidade_estoque, p.estoque_minimo, p.get_unidade_display(), p.ativo,
                 max(p.quantidade_estoque, 0) * p.preco_custo]
                for p in Produto.objects.select_related("categoria").order_by("categoria__nome", "nome")
            ],
        )
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
        "produtos_busca": dados_para_busca(),
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


FILTROS_CONTAGEM = [
    ("todos", "Todos"),
    ("negativos", "Estoque negativo"),
    ("baixo", "No mínimo ou abaixo"),
]


@login_required
def contagem(request):
    """Inventário: digita o que tem na prateleira e o sistema acerta o estoque."""
    if request.method == "POST":
        contados = {}
        for chave, valor in request.POST.items():
            if chave.startswith("contado_") and valor.strip() != "":
                try:
                    contados[int(chave.removeprefix("contado_"))] = int(valor)
                except ValueError:
                    messages.error(request, "Use apenas números inteiros na quantidade contada.")
                    return redirect(request.get_full_path())
        if any(quantidade < 0 for quantidade in contados.values()):
            messages.error(request, "A quantidade contada não pode ser negativa.")
            return redirect(request.get_full_path())

        ajustados = 0
        unidades_a_menos = 0
        valor_a_menos = 0
        for produto in Produto.objects.filter(pk__in=contados):
            if contados[produto.pk] == produto.quantidade_estoque:
                continue
            ajuste = produto.ajustar_contagem(
                quantidade_contada=contados[produto.pk], usuario=request.user
            )
            auditoria.registrar(
                request.user, RegistroAuditoria.Acao.EDICAO, produto,
                detalhes=f"Contagem de estoque: {ajuste.quantidade_anterior} → {ajuste.quantidade_contada}",
            )
            ajustados += 1
            if ajuste.diferenca < 0:
                unidades_a_menos += -ajuste.diferenca
                valor_a_menos += -ajuste.valor_diferenca

        if ajustados:
            texto = f"Estoque ajustado em {ajustados} produto{'s' if ajustados > 1 else ''}."
            if unidades_a_menos:
                texto += (
                    f" Faltaram {unidades_a_menos} unidade{'s' if unidades_a_menos > 1 else ''}"
                    f" (R$ {number_format(valor_a_menos, decimal_pos=2)} a preço de custo)."
                )
            messages.success(request, texto)
        elif contados:
            messages.info(request, "As quantidades contadas batem com o sistema. Nada foi alterado.")
        else:
            messages.info(request, "Nenhuma quantidade foi preenchida.")
        return redirect(request.get_full_path())

    filtro = request.GET.get("filtro", "todos")
    categoria_id = request.GET.get("categoria", "")
    busca = request.GET.get("busca", "").strip()
    produtos = Produto.objects.filter(ativo=True).select_related("categoria").order_by("categoria__nome", "nome")
    if filtro == "negativos":
        produtos = produtos.filter(quantidade_estoque__lt=0)
    elif filtro == "baixo":
        produtos = produtos.filter(quantidade_estoque__lte=F("estoque_minimo"))
    if categoria_id.isdigit():
        produtos = produtos.filter(categoria_id=categoria_id)
    if busca:
        produtos = produtos.filter(Q(nome__icontains=busca) | Q(sku__icontains=busca) | Q(codigo_barras=busca))

    return render(request, "estoque/contagem.html", {
        "produtos": produtos,
        "filtros": FILTROS_CONTAGEM,
        "filtro": filtro,
        "categorias": Categoria.objects.all(),
        "categoria_id": categoria_id,
        "busca": busca,
        "negativos": Produto.objects.filter(ativo=True, quantidade_estoque__lt=0).count(),
        "ultimos_ajustes": AjusteEstoque.objects.select_related("produto", "criado_por")[:15],
    })
