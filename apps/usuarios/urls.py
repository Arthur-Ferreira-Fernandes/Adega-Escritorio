from django.urls import path

from . import views

app_name = "usuarios"

urlpatterns = [
    path("", views.usuarios_lista, name="lista"),
    path("novo/", views.usuarios_novo, name="novo"),
    path("<int:pk>/resetar-senha/", views.usuarios_resetar_senha, name="resetar_senha"),
    path("<int:pk>/alternar-ativo/", views.usuarios_alternar_ativo, name="alternar_ativo"),
    path("minha-conta/", views.minha_conta, name="minha_conta"),
]
