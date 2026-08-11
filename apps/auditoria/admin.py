from django.contrib import admin

from .models import RegistroAuditoria


@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("criado_em", "usuario_repr", "acao", "modelo", "objeto_repr")
    list_filter = ("acao", "modelo")
