from django.views.generic import TemplateView

from .models import Venda


class InicioView(TemplateView):
    template_name = "vendas/inicio.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["total_vendas"] = Venda.objects.count()
        return contexto
