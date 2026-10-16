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
    desconto_maximo_percentual = models.DecimalField(
        "Desconto máximo sem administrador (%)",
        max_digits=5,
        decimal_places=2,
        default=Decimal("10"),
        help_text="Atendentes dão desconto até esse percentual; acima, só um administrador.",
    )
    taxa_servico_percentual = models.DecimalField(
        "Taxa de serviço nas comandas (%)",
        max_digits=5,
        decimal_places=2,
        default=Decimal("0"),
        help_text="Ex.: 10. Entra nas comandas novas e pode ser tirada em cada uma. Zero = não cobra.",
    )
    couvert_por_pessoa = models.DecimalField(
        "Couvert por pessoa",
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
        help_text="Cobrado nas comandas novas, vezes o número de pessoas. Zero = não cobra.",
    )
    prazo_fiado_dias = models.PositiveSmallIntegerField(
        "Prazo do fiado (dias)", default=30,
        help_text="Vencimento da conta a receber criada numa venda fiado.",
    )

    class FormatoComprovante(models.TextChoices):
        A4 = "a4", "Folha comum (A4)"
        TERMICA_80 = "80mm", "Impressora térmica 80 mm"
        TERMICA_58 = "58mm", "Impressora térmica 58 mm"

    formato_comprovante = models.CharField(
        "Formato do comprovante", max_length=4, choices=FormatoComprovante.choices, default=FormatoComprovante.A4
    )
    impressora_gaveta = models.CharField(
        "Impressora ligada à gaveta", max_length=200, blank=True,
        help_text="A gaveta de dinheiro abre por um sinal enviado a essa impressora (térmica).",
    )
    abrir_gaveta_no_dinheiro = models.BooleanField(
        "Abrir a gaveta ao receber em dinheiro", default=False
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
