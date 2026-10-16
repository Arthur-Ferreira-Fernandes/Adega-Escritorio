from bisect import bisect_left, bisect_right
from collections import defaultdict
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.formats import number_format

from apps.vendas.models import PagamentoVenda, Venda
from config.agregados import Soma


class Caixa(models.Model):
    class Status(models.TextChoices):
        ABERTO = "aberto", "Aberto"
        FECHADO = "fechado", "Fechado"

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ABERTO)
    valor_abertura = models.DecimalField(max_digits=10, decimal_places=2)
    valor_contado = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    aberto_em = models.DateTimeField(auto_now_add=True)
    fechado_em = models.DateTimeField(null=True, blank=True)
    aberto_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="caixas_abertos"
    )
    fechado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="caixas_fechados",
    )

    class Meta:
        verbose_name = "Caixa"
        verbose_name_plural = "Caixas"
        ordering = ["-aberto_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["status"],
                condition=Q(status="aberto"),
                name="caixa_apenas_um_aberto",
            ),
        ]

    def __str__(self):
        return f"Caixa #{self.pk} ({self.get_status_display()})"

    @classmethod
    def aberto_atual(cls):
        return cls.objects.filter(status=cls.Status.ABERTO).first()

    @classmethod
    def abrir(cls, usuario, valor_abertura):
        if valor_abertura < 0:
            raise ValidationError("O valor de abertura não pode ser negativo.")
        if cls.aberto_atual() is not None:
            raise ValidationError("Já existe um caixa aberto. Feche-o antes de abrir um novo.")
        try:
            with transaction.atomic():
                return cls.objects.create(valor_abertura=valor_abertura, aberto_por=usuario)
        except IntegrityError:
            raise ValidationError("Já existe um caixa aberto. Feche-o antes de abrir um novo.")

    def registrar_sangria(self, usuario, valor, descricao):
        if self.status != self.Status.ABERTO:
            raise ValidationError("Não é possível registrar sangria: não há caixa aberto.")
        if valor <= 0:
            raise ValidationError("O valor da sangria deve ser maior que zero.")
        with transaction.atomic():
            caixa = Caixa.objects.select_for_update().get(pk=self.pk)
            if caixa.status != Caixa.Status.ABERTO:
                raise ValidationError("Não é possível registrar sangria: não há caixa aberto.")
            saldo = caixa.saldo_esperado()
            if valor > saldo:
                raise ValidationError(
                    f"Valor da sangria (R$ {number_format(valor, decimal_pos=2)}) maior que o "
                    f"saldo esperado em caixa (R$ {number_format(saldo, decimal_pos=2)})."
                )
            return MovimentoCaixa.objects.create(
                caixa=caixa,
                tipo=MovimentoCaixa.Tipo.SANGRIA,
                valor=valor,
                descricao=descricao,
                criado_por=usuario,
            )

    def registrar_reforco(self, usuario, valor, descricao):
        if self.status != self.Status.ABERTO:
            raise ValidationError("Não é possível registrar reforço: não há caixa aberto.")
        if valor <= 0:
            raise ValidationError("O valor do reforço deve ser maior que zero.")
        with transaction.atomic():
            caixa = Caixa.objects.select_for_update().get(pk=self.pk)
            if caixa.status != Caixa.Status.ABERTO:
                raise ValidationError("Não é possível registrar reforço: não há caixa aberto.")
            return MovimentoCaixa.objects.create(
                caixa=caixa,
                tipo=MovimentoCaixa.Tipo.REFORCO,
                valor=valor,
                descricao=descricao,
                criado_por=usuario,
            )

    def fechar(self, usuario, valor_contado):
        if self.status != self.Status.ABERTO:
            raise ValidationError("Não é possível fechar: não há caixa aberto.")
        if valor_contado < 0:
            raise ValidationError("O valor contado não pode ser negativo.")
        with transaction.atomic():
            caixa = Caixa.objects.select_for_update().get(pk=self.pk)
            if caixa.status != Caixa.Status.ABERTO:
                raise ValidationError("Não é possível fechar: não há caixa aberto.")
            caixa.valor_contado = valor_contado
            caixa.fechado_em = timezone.now()
            caixa.fechado_por = usuario
            caixa.status = Caixa.Status.FECHADO
            caixa.save(update_fields=["valor_contado", "fechado_em", "fechado_por", "status"])
        self.refresh_from_db()
        return self

    @classmethod
    def calcular_totais(cls, caixas):
        """Totais de vários caixas com 2 consultas, em vez de 3 por caixa.

        Listas (histórico, quebra de caixa) chamam saldo e diferença de cada
        linha; com os totais guardados no objeto, nenhuma consulta se repete.
        """
        caixas = list(caixas)
        if not caixas:
            return caixas
        movimentos = defaultdict(Decimal)
        for caixa_id, tipo, total in (
            MovimentoCaixa.objects.filter(caixa__in=caixas)
            .values("caixa_id", "tipo").annotate(t=Soma("valor")).values_list("caixa_id", "tipo", "t")
        ):
            movimentos[(caixa_id, tipo)] = total
        agora = timezone.now()
        pagamentos = sorted(
            PagamentoVenda.objects.filter(
                forma_pagamento=Venda.FormaPagamento.DINHEIRO,
                venda__status=Venda.Status.CONCLUIDA,
                venda__finalizada_em__gte=min(c.aberto_em for c in caixas),
                venda__finalizada_em__lte=max(c.fechado_em or agora for c in caixas),
            ).values_list("venda__finalizada_em", "valor")
        )
        momentos = [momento for momento, _ in pagamentos]
        for caixa in caixas:
            fim = caixa.fechado_em or agora
            trecho = pagamentos[bisect_left(momentos, caixa.aberto_em):bisect_right(momentos, fim)]
            caixa._totais = {
                "sangrias": movimentos[(caixa.pk, MovimentoCaixa.Tipo.SANGRIA)],
                "reforcos": movimentos[(caixa.pk, MovimentoCaixa.Tipo.REFORCO)],
                "vendas_dinheiro": sum((valor for _, valor in trecho), Decimal("0")),
            }
        return caixas

    def _total(self, nome, calcular):
        totais = getattr(self, "_totais", None)
        return totais[nome] if totais is not None else calcular()

    def total_sangrias(self):
        return self._total("sangrias", lambda: (
            self.movimentos.filter(tipo=MovimentoCaixa.Tipo.SANGRIA).aggregate(t=Soma("valor"))["t"]
            or Decimal("0")
        ))

    def total_reforcos(self):
        return self._total("reforcos", lambda: (
            self.movimentos.filter(tipo=MovimentoCaixa.Tipo.REFORCO).aggregate(t=Soma("valor"))["t"]
            or Decimal("0")
        ))

    def total_vendas_dinheiro(self):
        return self._total("vendas_dinheiro", self._calcular_vendas_dinheiro)

    def _calcular_vendas_dinheiro(self):
        fim = self.fechado_em or timezone.now()
        return (
            PagamentoVenda.objects.filter(
                forma_pagamento=Venda.FormaPagamento.DINHEIRO,
                venda__status=Venda.Status.CONCLUIDA,
                venda__finalizada_em__gte=self.aberto_em,
                venda__finalizada_em__lte=fim,
            ).aggregate(t=Soma("valor"))["t"]
            or Decimal("0")
        )

    def saldo_esperado(self):
        return (
            self.valor_abertura
            + self.total_reforcos()
            + self.total_vendas_dinheiro()
            - self.total_sangrias()
        )

    def diferenca(self):
        return None if self.valor_contado is None else self.valor_contado - self.saldo_esperado()


class MovimentoCaixa(models.Model):
    class Tipo(models.TextChoices):
        SANGRIA = "sangria", "Sangria"
        REFORCO = "reforco", "Reforço"

    caixa = models.ForeignKey(Caixa, on_delete=models.CASCADE, related_name="movimentos")
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    descricao = models.CharField(max_length=255)
    criado_em = models.DateTimeField(auto_now_add=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="movimentos_caixa"
    )

    class Meta:
        verbose_name = "Movimento de caixa"
        verbose_name_plural = "Movimentos de caixa"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.get_tipo_display()} — R$ {self.valor}"
