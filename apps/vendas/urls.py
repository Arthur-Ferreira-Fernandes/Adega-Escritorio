from django.urls import path

from .views import InicioView

app_name = "vendas"

urlpatterns = [
    path("", InicioView.as_view(), name="inicio"),
]
