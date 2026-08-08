from django.conf import settings
from django.db import models

from apps.clientes.models import Cliente
from apps.estoque.models import Produto


class Venda(models.Model):
    class Status(models.TextChoices):
        ABERTA = "aberta", "Aberta"
        CONCLUIDA = "concluida", "Concluída"
        CANCELADA = "cancelada", "Cancelada"

    cliente = models.ForeignKey(
        Cliente, on_delete=models.SET_NULL, null=True, blank=True, related_name="vendas"
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="vendas"
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ABERTA)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Venda"
        verbose_name_plural = "Vendas"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"Venda #{self.pk}"

    def recalcular_total(self):
        self.total = sum((item.subtotal for item in self.itens.all()), start=0)
        self.save(update_fields=["total"])


class ItemVenda(models.Model):
    venda = models.ForeignKey(Venda, on_delete=models.CASCADE, related_name="itens")
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name="itens_venda")
    quantidade = models.PositiveIntegerField(default=1)
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, editable=False)

    class Meta:
        verbose_name = "Item da venda"
        verbose_name_plural = "Itens da venda"

    def __str__(self):
        return f"{self.produto} x{self.quantidade}"

    def save(self, *args, **kwargs):
        self.subtotal = self.quantidade * self.preco_unitario
        super().save(*args, **kwargs)
