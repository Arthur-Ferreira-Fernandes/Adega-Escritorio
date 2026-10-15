from decimal import Decimal

from django.db import models


class Configuracao(models.Model):
    limite_sangria = models.DecimalField(
        "Valor em caixa a partir do qual sugerir sangria",
        max_digits=10,
        decimal_places=2,
        default=Decimal("1000"),
    )
    meta_faturamento_mensal = models.DecimalField(
        "Meta de faturamento do mês",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        help_text="Deixe zero para não acompanhar meta.",
    )
    taxa_cartao = models.DecimalField(
        "Taxa da maquininha no cartão (%)",
        max_digits=5,
        decimal_places=2,
        default=Decimal("0"),
        help_text="Média entre débito e crédito. Usada no lucro real.",
    )
    taxa_pix = models.DecimalField(
        "Taxa no Pix (%)", max_digits=5, decimal_places=2, default=Decimal("0")
    )
    dias_cobertura_compra = models.PositiveSmallIntegerField(
        "Comprar estoque para quantos dias",
        default=7,
        help_text="Base da sugestão de compras: a quantidade que dura esse número de dias.",
    )

    class Meta:
        verbose_name = "Configuração"
        verbose_name_plural = "Configurações"

    def __str__(self):
        return "Configurações do sistema"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def obter(cls):
        return cls.objects.first() or cls.objects.create()
