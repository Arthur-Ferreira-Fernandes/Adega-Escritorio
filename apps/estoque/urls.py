from django.urls import path

from .views import InicioView

app_name = "estoque"

urlpatterns = [
    path("", InicioView.as_view(), name="inicio"),
]
