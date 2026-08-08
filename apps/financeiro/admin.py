from django.contrib import admin

from .models import ContaPagar, ContaReceber


@admin.register(ContaPagar)
class ContaPagarAdmin(admin.ModelAdmin):
    list_display = ("descricao", "fornecedor", "valor", "vencimento", "pago")
    list_filter = ("pago",)
    search_fields = ("descricao",)


@admin.register(ContaReceber)
class ContaReceberAdmin(admin.ModelAdmin):
    list_display = ("descricao", "cliente", "valor", "vencimento", "recebido")
    list_filter = ("recebido",)
    search_fields = ("descricao",)
