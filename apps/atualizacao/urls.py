from django.urls import path

from . import views

app_name = "atualizacao"

urlpatterns = [
    path("", views.painel, name="painel"),
    path("verificar/", views.verificar_agora, name="verificar"),
    path("instalar/", views.instalar, name="instalar"),
    path("progresso/", views.progresso, name="progresso"),
]
