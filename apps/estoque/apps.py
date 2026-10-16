from django.apps import AppConfig
from django.db.models.signals import post_delete, post_save


class EstoqueConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.estoque"
    label = "estoque"
    verbose_name = "Estoque"

    def ready(self):
        from apps.vendas.models import Venda

        from .models import AjusteEstoque, Categoria, ComponenteKit, EntradaEstoque, Produto
        from .servicos import limpar_cache_produtos

        for modelo in (Produto, Categoria, EntradaEstoque, AjusteEstoque, ComponenteKit):
            post_save.connect(limpar_cache_produtos, sender=modelo, dispatch_uid=f"busca:{modelo.__name__}")
            post_delete.connect(limpar_cache_produtos, sender=modelo, dispatch_uid=f"busca-del:{modelo.__name__}")
        # Venda concluída baixa o estoque (por update(), sem salvar o Produto).
        post_save.connect(_venda_salva, sender=Venda, dispatch_uid="busca:Venda")


def _venda_salva(sender, instance, **kwargs):
    if instance.status != sender.Status.ABERTA:
        from .servicos import limpar_cache_produtos

        limpar_cache_produtos()
