from django.views.generic import TemplateView

from .models import Categoria, Produto


class InicioView(TemplateView):
    template_name = "estoque/inicio.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["total_produtos"] = Produto.objects.count()
        contexto["total_categorias"] = Categoria.objects.count()
        return contexto
