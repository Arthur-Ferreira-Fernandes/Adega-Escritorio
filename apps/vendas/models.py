from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import F
from django.utils import timezone
from django.utils.formats import number_format

from apps.clientes.models import Cliente
from apps.estoque.models import Produto
from config.agregados import Soma


# Comanda aberta sem item ou pagamento novo há esse tempo aparece como parada.
MINUTOS_COMANDA_PARADA = 40


def interpretar_valor_ou_percentual(texto, base):
    """ "10%" vira 10% de base; "5,50" ou "R$ 5,50" vira R$ 5,50."""
    from decimal import InvalidOperation

    texto = (texto or "").strip().replace("R$", "").strip()
    if not texto:
        return Decimal("0")
    try:
        if texto.endswith("%"):
            percentual = Decimal(texto[:-1].strip().replace(",", "."))
            return (base * percentual / 100).quantize(Decimal("0.01"))
        if "," in texto:
            texto = texto.replace(".", "").replace(",", ".")
        return Decimal(texto).quantize(Decimal("0.01"))
    except InvalidOperation:
        raise ValidationError("Informe o desconto como valor (ex.: 5,00) ou percentual (ex.: 10%).")


class Venda(models.Model):
    class Status(models.TextChoices):
        ABERTA = "aberta", "Aberta"
        CONCLUIDA = "concluida", "Concluída"
        CANCELADA = "cancelada", "Cancelada"

    class FormaPagamento(models.TextChoices):
        DINHEIRO = "dinheiro", "Dinheiro"
        CARTAO = "cartao", "Cartão"
        PIX = "pix", "Pix"
        FIADO = "fiado", "Fiado"

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
    # total = subtotal (itens, já com desconto de item) - desconto + serviço + couvert
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    desconto = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    desconto_motivo = models.CharField("Motivo do desconto", max_length=120, blank=True)
    desconto_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    # Percentual e valor por pessoa ficam guardados na comanda: mudar a
    # configuração não muda o que já foi combinado com a mesa.
    servico_percentual = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    taxa_servico = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    couvert_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    couvert = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    dividir_em = models.PositiveSmallIntegerField("Dividir a conta em", null=True, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    criado_em = models.DateTimeField(auto_now_add=True)
    finalizada_em = models.DateTimeField(null=True, blank=True)
    # Último item ou pagamento lançado: mostra comandas paradas há muito tempo.
    atualizada_em = models.DateTimeField(null=True, blank=True)
    cancelada_em = models.DateTimeField(null=True, blank=True)
    cancelada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="vendas_canceladas",
    )

    class Meta:
        verbose_name = "Venda"
        verbose_name_plural = "Vendas"
        ordering = ["-criado_em"]
        # Relatórios e tela inicial filtram por status + data: sem índice, o
        # SQLite leria todas as vendas de todos os anos a cada consulta.
        indexes = [
            models.Index(fields=["status", "finalizada_em"], name="venda_status_finalizada"),
            models.Index(fields=["criado_em"], name="venda_criada_em"),
        ]

    def __str__(self):
        return self.identificador or f"Venda #{self.pk}"

    @property
    def ultima_movimentacao(self):
        return self.atualizada_em or self.criado_em

    @property
    def minutos_parada(self):
        return int((timezone.now() - self.ultima_movimentacao).total_seconds() // 60)

    @property
    def parada(self):
        return self.status == self.Status.ABERTA and self.minutos_parada >= MINUTOS_COMANDA_PARADA

    def recalcular_total(self):
        self.subtotal = sum((item.subtotal for item in self.itens.all()), Decimal("0"))
        self.desconto = min(self.desconto, self.subtotal)
        base = self.subtotal - self.desconto
        self.taxa_servico = (base * self.servico_percentual / 100).quantize(Decimal("0.01"))
        self.couvert = self.couvert_unitario * (self.quantidade_pessoas or 0)
        self.total = base + self.taxa_servico + self.couvert
        self.atualizada_em = timezone.now()
        self.save(update_fields=["subtotal", "desconto", "taxa_servico", "couvert", "total", "atualizada_em"])

    # Desconto, serviço, couvert e divisão ---------------------------------

    def _exigir_aberta(self):
        if self.status != self.Status.ABERTA:
            raise ValidationError("Só é possível alterar uma venda aberta.")

    def aplicar_desconto(self, usuario, valor_texto, motivo, item=None):
        """Desconto na venda ou num item. Aceita valor ("5,00") ou percentual ("10%").

        Quem não é administrador fica limitado ao percentual da configuração.
        """
        from apps.configuracoes.models import Configuracao

        self._exigir_aberta()
        base = item.quantidade * item.preco_unitario if item else self.subtotal
        valor = interpretar_valor_ou_percentual(valor_texto, base)
        if valor < 0 or valor > base:
            raise ValidationError(
                f"O desconto precisa ficar entre R$ 0,00 e R$ {number_format(base, decimal_pos=2)}."
            )
        if valor and not motivo.strip():
            raise ValidationError("Informe o motivo do desconto.")
        limite = Configuracao.obter().desconto_maximo_percentual
        percentual = (valor / base * 100) if base else Decimal("0")
        if percentual > limite and not usuario.is_superuser:
            raise ValidationError(
                f"Desconto de {number_format(percentual, decimal_pos=1)}% passa do limite de "
                f"{number_format(limite, decimal_pos=0)}% para atendentes. Peça a um administrador."
            )
        with transaction.atomic():
            if item:
                item.desconto = valor
                item.desconto_motivo = motivo.strip() if valor else ""
                item.desconto_por = usuario if valor else None
                item.save()
            else:
                self.desconto = valor
                self.desconto_motivo = motivo.strip() if valor else ""
                self.desconto_por = usuario if valor else None
                self.save(update_fields=["desconto", "desconto_motivo", "desconto_por"])
            self.recalcular_total()
            self._exigir_total_cobre_pagamentos()
        return valor

    def definir_servico(self, cobrar):
        from apps.configuracoes.models import Configuracao

        self._exigir_aberta()
        with transaction.atomic():
            self.servico_percentual = Configuracao.obter().taxa_servico_percentual if cobrar else Decimal("0")
            self.save(update_fields=["servico_percentual"])
            self.recalcular_total()
            self._exigir_total_cobre_pagamentos()

    def definir_couvert(self, cobrar):
        from apps.configuracoes.models import Configuracao

        self._exigir_aberta()
        with transaction.atomic():
            self.couvert_unitario = Configuracao.obter().couvert_por_pessoa if cobrar else Decimal("0")
            self.save(update_fields=["couvert_unitario"])
            self.recalcular_total()
            self._exigir_total_cobre_pagamentos()

    def _exigir_total_cobre_pagamentos(self):
        recebido = self.pagamentos.aggregate(t=Soma("valor"))["t"] or Decimal("0")
        if recebido > self.total:
            raise ValidationError(
                "O total ficaria menor do que o já recebido. Remova um pagamento antes de fazer essa alteração."
            )

    def aplicar_padroes_de_comanda(self):
        """Comanda (mesa) nova já vem com o serviço e o couvert configurados."""
        from apps.configuracoes.models import Configuracao

        config = Configuracao.obter()
        self.servico_percentual = config.taxa_servico_percentual
        self.couvert_unitario = config.couvert_por_pessoa
        self.save(update_fields=["servico_percentual", "couvert_unitario"])
        self.recalcular_total()

    @property
    def valor_da_parte(self):
        if not self.dividir_em:
            return None
        return (self.total / self.dividir_em).quantize(Decimal("0.01"))

    def partes_pagas(self, recebido=None):
        if not self.dividir_em or not self.valor_da_parte:
            return 0
        if recebido is None:
            recebido = self.pagamentos.aggregate(t=Soma("valor"))["t"] or Decimal("0")
        # Tolerância de centavos: a última parte absorve o arredondamento.
        return min(int((recebido + Decimal("0.05")) // self.valor_da_parte), self.dividir_em)

    def adicionar_item(self, produto, quantidade):
        if self.status != self.Status.ABERTA:
            raise ValidationError("Só é possível adicionar itens a uma venda aberta.")
        if quantidade < 1:
            raise ValidationError("A quantidade deve ser maior que zero.")

        item_existente = self.itens.filter(produto=produto, desconto=0).first()
        quantidade_total = quantidade + (item_existente.quantidade if item_existente else 0)

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
                custo_unitario=produto.custo_atual(),
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

    def remover_item(self, item, usuario=None):
        if self.status != self.Status.ABERTA:
            raise ValidationError("Só é possível remover itens de uma venda aberta.")
        with transaction.atomic():
            ItemRemovido.objects.create(
                venda=self,
                produto=item.produto,
                quantidade=item.quantidade,
                valor=item.subtotal,
                removido_por=usuario or self.criado_por,
            )
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
        if forma_pagamento == self.FormaPagamento.FIADO:
            self._validar_fiado(min(valor_informado, falta))
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
        self.atualizada_em = timezone.now()
        self.save(update_fields=["atualizada_em"])
        return pagamento

    def _validar_fiado(self, valor):
        if self.cliente is None:
            raise ValidationError("Fiado só para cliente cadastrado: escolha o cliente da venda primeiro.")
        limite = self.cliente.limite_fiado
        if limite <= 0:
            raise ValidationError(
                f"{self.cliente} não tem limite de fiado. Defina um limite no cadastro do cliente."
            )
        ja_nesta_venda = (
            self.pagamentos.filter(forma_pagamento=self.FormaPagamento.FIADO).aggregate(t=Soma("valor"))["t"]
            or Decimal("0")
        )
        devendo = self.cliente.saldo_fiado() + ja_nesta_venda
        if devendo + valor > limite:
            raise ValidationError(
                f"Passa do limite de fiado de {self.cliente}: deve R$ {number_format(devendo, decimal_pos=2)} "
                f"de R$ {number_format(limite, decimal_pos=2)}; disponível R$ "
                f"{number_format(max(limite - devendo, Decimal('0')), decimal_pos=2)}."
            )

    def receber(self, forma_pagamento, valor_informado=None):
        """Registra um pagamento e, se ele quitar a venda, já finaliza.

        Sem valor, recebe exatamente o que falta. Tudo numa transação só: se a
        finalização falhar (ex.: o estoque acabou), o pagamento é desfeito junto.
        """
        if not self.itens.exists():
            raise ValidationError("Adicione pelo menos um item antes de receber o pagamento.")
        with transaction.atomic():
            if valor_informado is None:
                valor_informado = self.falta_receber
            pagamento = self.adicionar_pagamento(forma_pagamento, valor_informado)
            if self.falta_receber <= 0:
                self.finalizar()
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

        # O estoque pode ficar negativo: a contagem é corrigida depois, pela
        # entrada de estoque ou pela edição do produto.
        with transaction.atomic():
            # Kit baixa o estoque de cada componente, não o dele.
            necessario_por_produto = {}
            for item in itens:
                for produto_id, quantidade in item.produto.baixas_de_estoque(item.quantidade):
                    necessario_por_produto[produto_id] = necessario_por_produto.get(produto_id, 0) + quantidade
            for produto_id, necessario in necessario_por_produto.items():
                Produto.objects.filter(pk=produto_id).update(
                    quantidade_estoque=F("quantidade_estoque") - necessario
                )
            self._lancar_fiado()
            self.status = self.Status.CONCLUIDA
            self.finalizada_em = timezone.now()
            self.save(update_fields=["status", "finalizada_em"])

    def _lancar_fiado(self):
        """O que foi para o fiado vira conta a receber do cliente."""
        from datetime import timedelta

        from apps.configuracoes.models import Configuracao
        from apps.financeiro.models import ContaReceber

        fiado = self.pagamentos.filter(forma_pagamento=self.FormaPagamento.FIADO).first()
        if fiado is None:
            return
        ContaReceber.objects.create(
            cliente=self.cliente,
            venda=self,
            descricao=f"Fiado — {self}",
            valor=fiado.valor,
            vencimento=timezone.localdate() + timedelta(days=Configuracao.obter().prazo_fiado_dias),
        )

    def cancelar(self, usuario=None):
        if self.status != self.Status.ABERTA:
            raise ValidationError("Somente vendas abertas podem ser canceladas.")
        self.pagamentos.all().delete()
        self.status = self.Status.CANCELADA
        self.cancelada_em = timezone.now()
        self.cancelada_por = usuario or self.criado_por
        self.save(update_fields=["status", "cancelada_em", "cancelada_por"])


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
    desconto = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    desconto_motivo = models.CharField(max_length=120, blank=True)
    desconto_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    # Já com o desconto do item: relatórios por produto mostram o que entrou de fato.
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, editable=False)

    class Meta:
        verbose_name = "Item da venda"
        verbose_name_plural = "Itens da venda"

    def __str__(self):
        return f"{self.produto} x{self.quantidade}"

    def save(self, *args, **kwargs):
        self.subtotal = self.quantidade * self.preco_unitario - self.desconto
        super().save(*args, **kwargs)


class ItemRemovido(models.Model):
    """Item tirado de uma venda aberta: sem isso, a remoção não deixaria rastro."""

    venda = models.ForeignKey(Venda, on_delete=models.CASCADE, related_name="itens_removidos")
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name="+")
    quantidade = models.PositiveIntegerField()
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    removido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="itens_removidos"
    )
    removido_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Item removido da venda"
        verbose_name_plural = "Itens removidos das vendas"
        ordering = ["-removido_em"]

    def __str__(self):
        return f"{self.produto} x{self.quantidade} (removido)"
