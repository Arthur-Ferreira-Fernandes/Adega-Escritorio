from django.urls import path

from . import views

app_name = "estoque"

urlpatterns = [
    path("", views.InicioView.as_view(), name="inicio"),
    path("produtos/", views.produtos_lista, name="produtos"),
    path("produtos/novo/", views.produtos_novo, name="produtos_novo"),
    path("produtos/<int:pk>/editar/", views.produtos_editar, name="produtos_editar"),
    path("produtos/<int:pk>/excluir/", views.produtos_excluir, name="produtos_excluir"),
    path("produtos/<int:pk>/kit/", views.kit, name="kit"),
    path("produtos/<int:pk>/kit/<int:componente_id>/remover/", views.kit_remover, name="kit_remover"),
    path("categorias/", views.categorias_lista, name="categorias"),
    path("categorias/nova/", views.categorias_nova, name="categorias_nova"),
    path("categorias/<int:pk>/editar/", views.categorias_editar, name="categorias_editar"),
    path(
        "categorias/<int:pk>/excluir/",
        views.categorias_excluir,
        name="categorias_excluir",
    ),
    path("contagem/", views.contagem, name="contagem"),
    path("pedidos/", views.pedidos_lista, name="pedidos"),
    path("pedidos/gerar/", views.pedido_gerar, name="pedido_gerar"),
    path("pedidos/<int:pk>/", views.pedido, name="pedido"),
    path("entradas/", views.entradas_lista, name="entradas"),
    path("entradas/registrar/", views.entradas_registrar, name="entradas_registrar"),
]
