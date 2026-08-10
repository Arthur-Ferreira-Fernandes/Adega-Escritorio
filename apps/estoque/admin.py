from django.contrib import admin

from .models import Categoria, EntradaEstoque, Produto


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nome", "slug")
    prepopulated_fields = {"slug": ("nome",)}
    search_fields = ("nome",)


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = (
        "nome",
        "sku",
        "codigo_barras",
        "categoria",
        "preco_venda",
        "quantidade_estoque",
        "estoque_minimo",
        "ativo",
    )
    list_filter = ("categoria", "ativo", "unidade")
    search_fields = ("nome", "sku", "codigo_barras")


@admin.register(EntradaEstoque)
class EntradaEstoqueAdmin(admin.ModelAdmin):
    list_display = (
        "produto",
        "fornecedor",
        "quantidade",
        "custo_unitario",
        "criado_por",
        "criado_em",
    )
    list_filter = ("fornecedor",)
    search_fields = ("produto__nome", "produto__sku")
