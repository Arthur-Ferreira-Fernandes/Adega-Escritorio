from django.contrib import admin

from .models import Cliente, Fornecedor


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("nome", "documento", "telefone", "email")
    search_fields = ("nome", "documento", "email")


@admin.register(Fornecedor)
class FornecedorAdmin(admin.ModelAdmin):
    list_display = ("nome", "documento", "telefone", "email")
    search_fields = ("nome", "documento", "email")
