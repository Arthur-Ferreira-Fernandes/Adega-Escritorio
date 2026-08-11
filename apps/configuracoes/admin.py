from django.contrib import admin

from .models import Configuracao


@admin.register(Configuracao)
class ConfiguracaoAdmin(admin.ModelAdmin):
    list_display = ("limite_horas_caixa", "limite_sangria")
