from django.urls import path

from . import views

app_name = "vendas"

urlpatterns = [
    path("", views.InicioView.as_view(), name="inicio"),
    path("nova/", views.nova_venda, name="nova"),
    path("<int:pk>/", views.venda_detalhe, name="detalhe"),
    path("<int:pk>/itens/adicionar/", views.venda_adicionar_item, name="adicionar_item"),
    path("<int:pk>/itens/<int:item_id>/remover/", views.venda_remover_item, name="remover_item"),
    path("<int:pk>/finalizar/", views.venda_finalizar, name="finalizar"),
    path("<int:pk>/cancelar/", views.venda_cancelar, name="cancelar"),
]
