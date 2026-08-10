from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

admin.site.site_header = "Adega & Tabacaria Escritório"
admin.site.site_title = "Adega & Tabacaria"
admin.site.index_title = "Administração"

urlpatterns = [
    path("", TemplateView.as_view(template_name="inicio.html"), name="inicio"),
    path("admin/", admin.site.urls),
    path("estoque/", include("apps.estoque.urls")),
    path("clientes/", include("apps.clientes.urls")),
    path("vendas/", include("apps.vendas.urls")),
    path("caixa/", include("apps.caixa.urls")),
    path("financeiro/", include("apps.financeiro.urls")),
    path("relatorios/", include("apps.relatorios.urls")),
    path("notificacoes/", include("apps.notificacoes.urls")),
]
