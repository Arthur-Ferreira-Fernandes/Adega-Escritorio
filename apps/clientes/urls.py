from django.urls import path

from . import views

app_name = "clientes"

urlpatterns = [
    path("", views.InicioView.as_view(), name="inicio"),
    path("clientes/", views.clientes_lista, name="clientes"),
    path("clientes/novo/", views.clientes_novo, name="clientes_novo"),
    path("clientes/<int:pk>/editar/", views.clientes_editar, name="clientes_editar"),
    path("clientes/<int:pk>/excluir/", views.clientes_excluir, name="clientes_excluir"),
    path("fornecedores/", views.fornecedores_lista, name="fornecedores"),
    path("fornecedores/novo/", views.fornecedores_novo, name="fornecedores_novo"),
    path(
        "fornecedores/<int:pk>/editar/",
        views.fornecedores_editar,
        name="fornecedores_editar",
    ),
    path(
        "fornecedores/<int:pk>/excluir/",
        views.fornecedores_excluir,
        name="fornecedores_excluir",
    ),
]
