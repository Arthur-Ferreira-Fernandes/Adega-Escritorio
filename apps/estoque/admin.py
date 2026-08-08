from django.contrib import admin

from .models import Categoria, Produto


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
        "ativo",
    )
    list_filter = ("categoria", "ativo", "unidade")
    search_fields = ("nome", "sku", "codigo_barras")
