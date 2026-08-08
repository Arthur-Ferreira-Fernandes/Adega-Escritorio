from django.urls import path

from . import views

app_name = "estoque"

urlpatterns = [
    path("", views.InicioView.as_view(), name="inicio"),
    path("produtos/", views.produtos_lista, name="produtos"),
    path("produtos/novo/", views.produtos_novo, name="produtos_novo"),
    path("produtos/<int:pk>/editar/", views.produtos_editar, name="produtos_editar"),
    path("produtos/<int:pk>/excluir/", views.produtos_excluir, name="produtos_excluir"),
]
