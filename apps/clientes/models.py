from django.db import models


class Cliente(models.Model):
    nome = models.CharField(max_length=150)
    documento = models.CharField("CPF/CNPJ", max_length=20, unique=True)
    telefone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    endereco = models.CharField(max_length=255, blank=True)
    observacoes = models.TextField(blank=True)
    limite_fiado = models.DecimalField(
        "Limite de fiado",
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Quanto o cliente pode ficar devendo. Zero = não compra fiado.",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ["nome"]

    def __str__(self):
        return self.nome

    def saldo_fiado(self):
        """Quanto o cliente deve hoje (contas a receber em aberto)."""
        from decimal import Decimal

        from config.agregados import Soma

        return self.contas_a_receber.filter(recebido=False).aggregate(t=Soma("valor"))["t"] or Decimal("0")


class Fornecedor(models.Model):
    nome = models.CharField(max_length=150)
    documento = models.CharField("CNPJ", max_length=20, unique=True)
    telefone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    endereco = models.CharField(max_length=255, blank=True)
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Fornecedor"
        verbose_name_plural = "Fornecedores"
        ordering = ["nome"]

    def __str__(self):
        return self.nome
