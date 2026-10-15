from django.urls import path

from . import views

app_name = "relatorios"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("horarios/", views.horarios, name="horarios"),
    path("produtos/", views.produtos, name="produtos"),
    path("lucro/", views.lucro, name="lucro"),
    path("mesas/", views.mesas, name="mesas"),
    path("equipe/", views.equipe, name="equipe"),
    path("clientes/", views.clientes, name="clientes"),
    path("compras/", views.compras, name="compras"),
]
