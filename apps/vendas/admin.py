from django.contrib import admin

from .models import ItemVenda, PagamentoVenda, Venda


class ItemVendaInline(admin.TabularInline):
    model = ItemVenda
    extra = 1


class PagamentoVendaInline(admin.TabularInline):
    model = PagamentoVenda
    extra = 0


@admin.register(Venda)
class VendaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "identificador",
        "cliente",
        "criado_por",
        "status",
        "total",
        "criado_em",
        "finalizada_em",
    )
    list_filter = ("status",)
    readonly_fields = ("total", "finalizada_em")
    inlines = [ItemVendaInline, PagamentoVendaInline]
