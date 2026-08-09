from django.urls import path

from . import views

app_name = "financeiro"

urlpatterns = [
    path("", views.InicioView.as_view(), name="inicio"),
    path("contas-a-pagar/", views.contas_pagar_lista, name="contas_pagar"),
    path("contas-a-pagar/nova/", views.contas_pagar_nova, name="contas_pagar_nova"),
    path(
        "contas-a-pagar/<int:pk>/editar/",
        views.contas_pagar_editar,
        name="contas_pagar_editar",
    ),
    path(
        "contas-a-pagar/<int:pk>/excluir/",
        views.contas_pagar_excluir,
        name="contas_pagar_excluir",
    ),
    path(
        "contas-a-pagar/<int:pk>/marcar-paga/",
        views.contas_pagar_marcar_paga,
        name="contas_pagar_marcar_paga",
    ),
    path("contas-a-receber/", views.contas_receber_lista, name="contas_receber"),
    path(
        "contas-a-receber/nova/", views.contas_receber_nova, name="contas_receber_nova"
    ),
    path(
        "contas-a-receber/<int:pk>/editar/",
        views.contas_receber_editar,
        name="contas_receber_editar",
    ),
    path(
        "contas-a-receber/<int:pk>/excluir/",
        views.contas_receber_excluir,
        name="contas_receber_excluir",
    ),
    path(
        "contas-a-receber/<int:pk>/marcar-recebida/",
        views.contas_receber_marcar_recebida,
        name="contas_receber_marcar_recebida",
    ),
]
