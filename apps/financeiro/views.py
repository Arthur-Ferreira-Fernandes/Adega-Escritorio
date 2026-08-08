from django.views.generic import TemplateView

from .models import ContaPagar, ContaReceber


class InicioView(TemplateView):
    template_name = "financeiro/inicio.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["total_contas_pagar"] = ContaPagar.objects.count()
        contexto["total_contas_receber"] = ContaReceber.objects.count()
        return contexto
