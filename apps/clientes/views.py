from django.views.generic import TemplateView

from .models import Cliente, Fornecedor


class InicioView(TemplateView):
    template_name = "clientes/inicio.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["total_clientes"] = Cliente.objects.count()
        contexto["total_fornecedores"] = Fornecedor.objects.count()
        return contexto
