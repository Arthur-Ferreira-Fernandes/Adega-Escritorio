from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("estoque/", include("apps.estoque.urls")),
    path("clientes/", include("apps.clientes.urls")),
    path("vendas/", include("apps.vendas.urls")),
    path("financeiro/", include("apps.financeiro.urls")),
]
