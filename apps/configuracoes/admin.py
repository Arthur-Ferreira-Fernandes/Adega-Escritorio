from django.contrib import admin

from .models import Configuracao


@admin.register(Configuracao)
class ConfiguracaoAdmin(admin.ModelAdmin):
    list_display = ("__str__", "limite_sangria")
