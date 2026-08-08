from django.contrib import admin

from .models import ItemVenda, Venda


class ItemVendaInline(admin.TabularInline):
    model = ItemVenda
    extra = 1


@admin.register(Venda)
class VendaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "identificador",
        "cliente",
        "criado_por",
        "status",
        "forma_pagamento",
        "total",
        "criado_em",
        "finalizada_em",
    )
    list_filter = ("status", "forma_pagamento")
    readonly_fields = ("total", "finalizada_em")
    inlines = [ItemVendaInline]
