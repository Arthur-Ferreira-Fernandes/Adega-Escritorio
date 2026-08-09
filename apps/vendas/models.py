from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from django.utils.formats import number_format

from apps.clientes.models import Cliente
from apps.estoque.models import Produto


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

    def finalizar(self, pagamentos):
        if self.status != self.Status.ABERTA:
            raise ValidationError("Somente vendas abertas podem ser finalizadas.")
        itens = list(self.itens.select_related("produto"))
        if not itens:
            raise ValidationError("Não é possível finalizar uma venda sem itens.")

        formas_validas = set(self.FormaPagamento.values)
        formas_usadas = set()
        pagamentos_validos = []
        for pagamento in pagamentos:
            valor = pagamento.get("valor")
            if not valor:
                continue
            if valor <= 0:
                raise ValidationError("Os valores informados devem ser maiores que zero.")
            forma = pagamento.get("forma_pagamento")
            if forma not in formas_validas:
                raise ValidationError("Forma de pagamento inválida.")
            if forma in formas_usadas:
                raise ValidationError("Cada forma de pagamento pode ser usada apenas uma vez.")
            formas_usadas.add(forma)
            valor_recebido = (
                pagamento.get("valor_recebido") if forma == self.FormaPagamento.DINHEIRO else None
            )
            if valor_recebido is not None and valor_recebido < valor:
                raise ValidationError(
                    "O valor recebido em dinheiro não pode ser menor que o valor pago em dinheiro."
                )
            pagamentos_validos.append(
                {"forma_pagamento": forma, "valor": valor, "valor_recebido": valor_recebido}
            )

        if not pagamentos_validos:
            raise ValidationError("Informe ao menos uma forma de pagamento com valor maior que zero.")

        soma = sum(p["valor"] for p in pagamentos_validos)
        if soma != self.total:
            raise ValidationError(
                f"A soma dos valores informados (R$ {number_format(soma, decimal_pos=2)}) "
                f"deve ser igual ao total da venda (R$ {number_format(self.total, decimal_pos=2)})."
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
            PagamentoVenda.objects.bulk_create(
                PagamentoVenda(venda=self, **p) for p in pagamentos_validos
            )

    def cancelar(self):
        if self.status != self.Status.ABERTA:
            raise ValidationError("Somente vendas abertas podem ser canceladas.")
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
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, editable=False)

    class Meta:
        verbose_name = "Item da venda"
        verbose_name_plural = "Itens da venda"

    def __str__(self):
        return f"{self.produto} x{self.quantidade}"

    def save(self, *args, **kwargs):
        self.subtotal = self.quantidade * self.preco_unitario
        super().save(*args, **kwargs)
