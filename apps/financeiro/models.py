from django.db import models

from apps.clientes.models import Cliente, Fornecedor
from apps.vendas.models import Venda


class ContaPagar(models.Model):
    fornecedor = models.ForeignKey(
        Fornecedor, on_delete=models.PROTECT, related_name="contas_a_pagar"
    )
    descricao = models.CharField(max_length=255)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    vencimento = models.DateField()
    pago = models.BooleanField(default=False)
    pago_em = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "Conta a pagar"
        verbose_name_plural = "Contas a pagar"
        ordering = ["vencimento"]

    def __str__(self):
        return self.descricao


class ContaReceber(models.Model):
    cliente = models.ForeignKey(
        Cliente, on_delete=models.PROTECT, related_name="contas_a_receber"
    )
    venda = models.ForeignKey(
        Venda, on_delete=models.SET_NULL, null=True, blank=True, related_name="contas_a_receber"
    )
    descricao = models.CharField(max_length=255)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    vencimento = models.DateField()
    recebido = models.BooleanField(default=False)
    recebido_em = models.DateField(null=True, blank=True)
    class FormaRecebimento(models.TextChoices):
        DINHEIRO = "dinheiro", "Dinheiro"
        PIX = "pix", "Pix"
        CARTAO = "cartao", "Cartão"

    forma_recebimento = models.CharField(max_length=10, blank=True, choices=FormaRecebimento.choices)

    class Meta:
        verbose_name = "Conta a receber"
        verbose_name_plural = "Contas a receber"
        ordering = ["vencimento"]

    def __str__(self):
        return self.descricao
