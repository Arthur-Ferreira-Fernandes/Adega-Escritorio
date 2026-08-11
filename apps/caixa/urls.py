from django.urls import path

from . import views

app_name = "caixa"

urlpatterns = [
    path("", views.caixa_painel, name="painel"),
    path("abrir/", views.caixa_abrir, name="abrir"),
    path("sangria/", views.caixa_sangria, name="sangria"),
    path("reforco/", views.caixa_reforco, name="reforco"),
    path("fechar/", views.caixa_fechar, name="fechar"),
    path("estender-limite/", views.caixa_estender_limite, name="estender_limite"),
    path("<int:pk>/relatorio/", views.caixa_relatorio, name="relatorio"),
]
