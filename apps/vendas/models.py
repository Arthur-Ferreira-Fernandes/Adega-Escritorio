from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from django.utils.formats import number_format

from apps.clientes.models import Cliente
from apps.estoque.models import Produto
from config.agregados import Soma


class Venda(models.Model):
    class Status(models.TextChoices):
        ABERTA = "aberta", "Aberta"
        CONCLUIDA = "concluida", "Concluída"
        CANCELADA = "cancelada", "Cancelada"

    class FormaPagamento(models.TextChoices):
        DINHEIRO = "dinheiro", "Dinheiro"
        CARTAO = "cartao", "Cartão"
        PIX = "pix", "Pix"

    cliente = models.ForeignKey(
        Cliente, on_delete=models.SET_NULL, null=True, blank=True, related_name="vendas"
    )
    identificador = models.CharField(
        "Identificador (mesa/comanda)", max_length=50, blank=True
    )
    quantidade_pessoas = models.PositiveIntegerField(
        "Quantidade de pessoas na mesa", null=True, blank=True
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="vendas"
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ABERTA)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    criado_em = models.DateTimeField(auto_now_add=True)
    finalizada_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Venda"
        verbose_name_plural = "Vendas"
        ordering = ["-criado_em"]

    def __str__(self):
        return self.identificador or f"Venda #{self.pk}"

    def recalcular_total(self):
        self.total = sum((item.subtotal for item in self.itens.all()), start=0)
        self.save(update_fields=["total"])

    def adicionar_item(self, produto, quantidade):
        if self.status != self.Status.ABERTA:
            raise ValidationError("Só é possível adicionar itens a uma venda aberta.")
        if quantidade < 1:
            raise ValidationError("A quantidade deve ser maior que zero.")

        item_existente = self.itens.filter(produto=produto).first()
        quantidade_total = quantidade + (item_existente.quantidade if item_existente else 0)
        if produto.quantidade_estoque < quantidade_total:
            raise ValidationError(
                f"Estoque insuficiente para {produto.nome} "
                f"(disponível: {produto.quantidade_estoque})."
            )

        if item_existente:
            item_existente.quantidade = quantidade_total
            item_existente.save()
            item = item_existente
        else:
            item = ItemVenda.objects.create(
                venda=self,
                produto=produto,
                quantidade=quantidade,
                preco_unitario=produto.preco_venda,
                custo_unitario=produto.preco_custo,
            )
        self.recalcular_total()
        return item

    def adicionar_por_codigo_barras(self, codigo_barras):
        if self.status != self.Status.ABERTA:
            raise ValidationError("Só é possível adicionar itens a uma venda aberta.")
        produto = Produto.objects.filter(codigo_barras=codigo_barras, ativo=True).first()
        if produto is None:
            raise ValidationError("Nenhum produto ativo encontrado para este código de barras.")
        return self.adicionar_item(produto, quantidade=1)

    def remover_item(self, item):
        if self.status != self.Status.ABERTA:
            raise ValidationError("Só é possível remover itens de uma venda aberta.")
        item.delete()
        self.recalcular_total()

    @property
    def falta_receber(self):
        recebido = self.pagamentos.aggregate(t=Soma("valor"))["t"] or Decimal("0")
        return self.total - recebido

    @property
    def valor_por_pessoa(self):
        if not self.quantidade_pessoas:
            return None
        return (self.total / self.quantidade_pessoas).quantize(Decimal("0.01"))

    @property
    def troco_total(self):
        return sum((pagamento.troco for pagamento in self.pagamentos.all()), Decimal("0"))

    def adicionar_pagamento(self, forma_pagamento, valor_informado):
        if self.status != self.Status.ABERTA:
            raise ValidationError("Só é possível registrar pagamentos em uma venda aberta.")
        if forma_pagamento not in self.FormaPagamento.values:
            raise ValidationError("Forma de pagamento inválida.")
        if not valor_informado or valor_informado <= 0:
            raise ValidationError("Informe um valor maior que zero.")

        falta = self.falta_receber
        if falta <= 0:
            raise ValidationError("Esta venda já está com o pagamento completo.")

        eh_dinheiro = forma_pagamento == self.FormaPagamento.DINHEIRO
        if not eh_dinheiro and valor_informado > falta:
            raise ValidationError(
                f"O valor informado (R$ {number_format(valor_informado, decimal_pos=2)}) é maior "
                f"que o restante a receber (R$ {number_format(falta, decimal_pos=2)}). "
                f"{dict(self.FormaPagamento.choices)[forma_pagamento]} não permite troco — "
                "informe um valor até o restante ou use Dinheiro."
            )

        valor_aplicado = min(valor_informado, falta)
        pagamento, _ = self.pagamentos.get_or_create(
            forma_pagamento=forma_pagamento, defaults={"valor": Decimal("0")}
        )
        pagamento.valor += valor_aplicado
        if eh_dinheiro:
            pagamento.valor_recebido = (pagamento.valor_recebido or Decimal("0")) + valor_informado
        pagamento.save(update_fields=["valor", "valor_recebido"])
        return pagamento

    def remover_pagamento(self, pagamento):
        if self.status != self.Status.ABERTA:
            raise ValidationError("Só é possível remover pagamentos de uma venda aberta.")
        pagamento.delete()

    def finalizar(self):
        if self.status != self.Status.ABERTA:
            raise ValidationError("Somente vendas abertas podem ser finalizadas.")
        itens = list(self.itens.select_related("produto"))
        if not itens:
            raise ValidationError("Não é possível finalizar uma venda sem itens.")
        if self.falta_receber > 0:
            raise ValidationError(
                f"Ainda falta receber R$ {number_format(self.falta_receber, decimal_pos=2)} "
                "para finalizar a venda."
            )

        with transaction.atomic():
            produto_ids = {item.produto_id for item in itens}
            produtos = {
                produto.id: produto
                for produto in Produto.objects.select_for_update().filter(id__in=produto_ids)
            }
            necessario_por_produto = {}
            for item in itens:
                necessario_por_produto[item.produto_id] = (
                    necessario_por_produto.get(item.produto_id, 0) + item.quantidade
                )
            for produto_id, necessario in necessario_por_produto.items():
                produto = produtos[produto_id]
                if produto.quantidade_estoque < necessario:
                    raise ValidationError(
                        f"Estoque insuficiente para {produto.nome} no momento de finalizar "
                        f"(disponível: {produto.quantidade_estoque}, necessário: {necessario})."
                    )
            for produto_id, necessario in necessario_por_produto.items():
                produto = produtos[produto_id]
                produto.quantidade_estoque -= necessario
                produto.save(update_fields=["quantidade_estoque"])
            self.status = self.Status.CONCLUIDA
            self.finalizada_em = timezone.now()
            self.save(update_fields=["status", "finalizada_em"])

    def cancelar(self):
        if self.status != self.Status.ABERTA:
            raise ValidationError("Somente vendas abertas podem ser canceladas.")
        self.pagamentos.all().delete()
        self.status = self.Status.CANCELADA
        self.save(update_fields=["status"])


class PagamentoVenda(models.Model):
    venda = models.ForeignKey(Venda, on_delete=models.CASCADE, related_name="pagamentos")
    forma_pagamento = models.CharField(max_length=10, choices=Venda.FormaPagamento.choices)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    valor_recebido = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pagamento da venda"
        verbose_name_plural = "Pagamentos da venda"
        constraints = [
            models.UniqueConstraint(
                fields=["venda", "forma_pagamento"], name="pagamento_unico_por_forma_e_venda"
            ),
        ]

    def __str__(self):
        return f"{self.get_forma_pagamento_display()}: R$ {self.valor}"

    @property
    def troco(self):
        return (self.valor_recebido - self.valor) if self.valor_recebido is not None else Decimal("0")


class ItemVenda(models.Model):
    venda = models.ForeignKey(Venda, on_delete=models.CASCADE, related_name="itens")
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name="itens_venda")
    quantidade = models.PositiveIntegerField(default=1)
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    custo_unitario = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, editable=False)

    class Meta:
        verbose_name = "Item da venda"
        verbose_name_plural = "Itens da venda"

    def __str__(self):
        return f"{self.produto} x{self.quantidade}"

    def save(self, *args, **kwargs):
        self.subtotal = self.quantidade * self.preco_unitario
        super().save(*args, **kwargs)
