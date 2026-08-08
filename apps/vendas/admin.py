from django.contrib import admin

from .models import ItemVenda, Venda


class ItemVendaInline(admin.TabularInline):
    model = ItemVenda
    extra = 1


@admin.register(Venda)
class VendaAdmin(admin.ModelAdmin):
    list_display = ("id", "cliente", "criado_por", "status", "total", "criado_em")
    list_filter = ("status",)
    inlines = [ItemVendaInline]
