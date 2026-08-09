from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

admin.site.site_header = "Adega & Tabacaria Escritório"
admin.site.site_title = "Adega & Tabacaria"
admin.site.index_title = "Administração"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="estoque:inicio")),
    path("admin/", admin.site.urls),
    path("estoque/", include("apps.estoque.urls")),
    path("clientes/", include("apps.clientes.urls")),
    path("vendas/", include("apps.vendas.urls")),
    path("financeiro/", include("apps.financeiro.urls")),
    path("relatorios/", include("apps.relatorios.urls")),
]
