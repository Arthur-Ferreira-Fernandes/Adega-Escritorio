from django.urls import path

from . import views

app_name = "estoque"

urlpatterns = [
    path("", views.InicioView.as_view(), name="inicio"),
    path("produtos/", views.produtos_lista, name="produtos"),
    path("produtos/novo/", views.produtos_novo, name="produtos_novo"),
    path("produtos/<int:pk>/editar/", views.produtos_editar, name="produtos_editar"),
    path("produtos/<int:pk>/excluir/", views.produtos_excluir, name="produtos_excluir"),
    path("categorias/", views.categorias_lista, name="categorias"),
    path("categorias/nova/", views.categorias_nova, name="categorias_nova"),
    path("categorias/<int:pk>/editar/", views.categorias_editar, name="categorias_editar"),
    path(
        "categorias/<int:pk>/excluir/",
        views.categorias_excluir,
        name="categorias_excluir",
    ),
    path("entradas/", views.entradas_lista, name="entradas"),
    path("entradas/registrar/", views.entradas_registrar, name="entradas_registrar"),
]
