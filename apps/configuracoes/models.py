from decimal import Decimal

from django.db import models


class Configuracao(models.Model):
    limite_horas_caixa = models.PositiveIntegerField(
        "Limite de horas para o caixa ficar aberto", default=12
    )
    limite_sangria = models.DecimalField(
        "Valor em caixa a partir do qual sugerir sangria",
        max_digits=10,
        decimal_places=2,
        default=Decimal("1000"),
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
