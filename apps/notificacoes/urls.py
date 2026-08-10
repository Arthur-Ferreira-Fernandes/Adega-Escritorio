from django.urls import path

from . import views

app_name = "notificacoes"

urlpatterns = [
    path("sino/", views.notificacoes_sino, name="sino"),
    path("marcar-lidas/", views.notificacoes_marcar_lidas, name="marcar_lidas"),
]
