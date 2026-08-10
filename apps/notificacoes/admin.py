from django.contrib import admin

from .models import Notificacao


@admin.register(Notificacao)
class NotificacaoAdmin(admin.ModelAdmin):
    list_display = ("mensagem", "tipo", "nivel", "lida", "resolvida", "criado_em")
    list_filter = ("tipo", "nivel", "lida", "resolvida")
    readonly_fields = ("criado_em", "lida_em", "resolvida_em")
