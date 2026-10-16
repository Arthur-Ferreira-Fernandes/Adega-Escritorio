from django.apps import AppConfig
from django.db.models.signals import post_save


class NotificacoesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notificacoes"
    label = "notificacoes"
    verbose_name = "Notificações"

    def ready(self):
        from apps.caixa.models import Caixa, MovimentoCaixa
        from apps.configuracoes.models import Configuracao
        from apps.estoque.models import AjusteEstoque, EntradaEstoque, Produto
        from apps.vendas.models import Venda

        from .servicos import marcar_para_sincronizar

        # Mudou caixa ou estoque: o sino recalcula na próxima página.
        for modelo in (Caixa, MovimentoCaixa, Configuracao, Produto, EntradaEstoque, AjusteEstoque):
            post_save.connect(marcar_para_sincronizar, sender=modelo, dispatch_uid=f"sino:{modelo.__name__}")
        # Venda só importa ao concluir/cancelar (estoque e caixa mudam); lançar
        # item numa venda aberta não muda nada que o sino mostra.
        post_save.connect(_venda_salva, sender=Venda, dispatch_uid="sino:Venda")


def _venda_salva(sender, instance, **kwargs):
    if instance.status != sender.Status.ABERTA:
        from .servicos import marcar_para_sincronizar

        marcar_para_sincronizar()
