from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.clientes.models import Fornecedor


class Categoria(models.Model):
    nome = models.CharField(max_length=100)
    slug = models.SlugField(max_length=110, unique=True)
    descricao = models.TextField(blank=True)

    class Meta:
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"
        ordering = ["nome"]

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.nome)
            slug = base
            i = 2
            while Categoria.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)


class Produto(models.Model):
    class Unidade(models.TextChoices):
        UNIDADE = "un", "Unidade"
        GARRAFA = "gf", "Garrafa"
        CAIXA = "cx", "Caixa"

    nome = models.CharField(max_length=150)
    sku = models.CharField("SKU", max_length=50, unique=True)
    codigo_barras = models.CharField(
        "Código de barras", max_length=64, unique=True, null=True, blank=True
    )
    categoria = models.ForeignKey(
        Categoria, on_delete=models.PROTECT, related_name="produtos"
    )
    preco_custo = models.DecimalField(max_digits=10, decimal_places=2)
    preco_venda = models.DecimalField(max_digits=10, decimal_places=2)
    # Pode ficar negativo: a venda não espera a contagem ser lançada no sistema.
    quantidade_estoque = models.IntegerField(default=0)
    estoque_minimo = models.PositiveIntegerField(
        "Estoque mínimo",
        default=5,
        help_text="Abaixo desse valor, o produto aparece no relatório de estoque baixo.",
    )
    unidade = models.CharField(max_length=2, choices=Unidade.choices, default=Unidade.UNIDADE)
    ativo = models.BooleanField(default=True)
    # Kit/combo: não tem estoque próprio; vender baixa os componentes. Marcado
    # sozinho quando o produto ganha componentes (ComponenteKit).
    e_kit = models.BooleanField("É kit/combo", default=False, editable=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"
        ordering = ["nome"]

    def __str__(self):
        return self.nome

    def clean(self):
        super().clean()
        if not self.codigo_barras:
            self.codigo_barras = None

    def save(self, *args, **kwargs):
        if not self.codigo_barras:
            self.codigo_barras = None
        super().save(*args, **kwargs)

    # Kits ----------------------------------------------------------------

    def componentes_do_kit(self):
        # .all() aproveita prefetch_related("componentes__componente") das listas.
        return list(self.componentes.all()) if self.e_kit else []

    def custo_atual(self):
        """Custo para o lucro: o do produto, ou a soma dos componentes num kit."""
        if not self.e_kit:
            return self.preco_custo
        return sum((c.componente.preco_custo * c.quantidade for c in self.componentes_do_kit()), Decimal("0"))

    def baixas_de_estoque(self, quantidade):
        """[(produto_id, quantidade)] que saem do estoque ao vender `quantidade`."""
        if not self.e_kit:
            return [(self.pk, quantidade)]
        return [(c.componente_id, c.quantidade * quantidade) for c in self.componentes_do_kit()]

    def estoque_disponivel(self):
        """Num kit, quantos dá para montar com o estoque dos componentes."""
        if not self.e_kit:
            return self.quantidade_estoque
        componentes = self.componentes_do_kit()
        if not componentes:
            return 0
        return min(c.componente.quantidade_estoque // c.quantidade for c in componentes)

    def atualizar_marcacao_de_kit(self):
        e_kit = self.componentes.exists()
        if e_kit != self.e_kit:
            self.e_kit = e_kit
            Produto.objects.filter(pk=self.pk).update(e_kit=e_kit)

    def registrar_entrada(self, *, quantidade, fornecedor, custo_unitario, usuario, validade=None):
        if quantidade < 1:
            raise ValidationError("A quantidade deve ser maior que zero.")
        if custo_unitario <= 0:
            raise ValidationError("O custo unitário deve ser maior que zero.")
        if self.e_kit:
            raise ValidationError("Kit não tem estoque próprio: registre a entrada dos componentes.")
        entrada = EntradaEstoque.objects.create(
            produto=self,
            fornecedor=fornecedor,
            quantidade=quantidade,
            custo_unitario=custo_unitario,
            validade=validade,
            criado_por=usuario,
        )
        self.quantidade_estoque = models.F("quantidade_estoque") + quantidade
        self.preco_custo = custo_unitario
        self.save(update_fields=["quantidade_estoque", "preco_custo"])
        self.refresh_from_db(fields=["quantidade_estoque", "preco_custo"])
        return entrada

    def ajustar_contagem(self, *, quantidade_contada, usuario):
        """Troca o estoque pela quantidade contada na prateleira e guarda a diferença."""
        with transaction.atomic():
            atual = Produto.objects.select_for_update().get(pk=self.pk).quantidade_estoque
            ajuste = AjusteEstoque.objects.create(
                produto=self,
                quantidade_anterior=atual,
                quantidade_contada=quantidade_contada,
                diferenca=quantidade_contada - atual,
                custo_unitario=self.preco_custo,
                criado_por=usuario,
            )
            Produto.objects.filter(pk=self.pk).update(quantidade_estoque=quantidade_contada)
        self.quantidade_estoque = quantidade_contada
        return ajuste


class EntradaEstoque(models.Model):
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name="entradas")
    fornecedor = models.ForeignKey(
        Fornecedor, on_delete=models.PROTECT, related_name="entradas_estoque"
    )
    quantidade = models.PositiveIntegerField()
    custo_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    validade = models.DateField("Validade", null=True, blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="entradas_estoque"
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Entrada de estoque"
        verbose_name_plural = "Entradas de estoque"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.produto} +{self.quantidade}"

    @property
    def valor_total(self):
        return self.quantidade * self.custo_unitario


class AjusteEstoque(models.Model):
    """Correção de estoque feita na contagem (inventário).

    Diferenças negativas repetidas no mesmo produto indicam perda ou furto.
    """

    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name="ajustes")
    quantidade_anterior = models.IntegerField()
    quantidade_contada = models.IntegerField()
    diferenca = models.IntegerField()
    custo_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ajustes_estoque"
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ajuste de estoque"
        verbose_name_plural = "Ajustes de estoque"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.produto} {self.diferenca:+d}"

    @property
    def valor_diferenca(self):
        return self.diferenca * self.custo_unitario


class ComponenteKit(models.Model):
    kit = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name="componentes")
    componente = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name="usado_em_kits")
    quantidade = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "Componente do kit"
        verbose_name_plural = "Componentes do kit"
        constraints = [
            models.UniqueConstraint(fields=["kit", "componente"], name="componente_unico_por_kit"),
        ]

    def __str__(self):
        return f"{self.kit}: {self.quantidade}x {self.componente}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.kit.atualizar_marcacao_de_kit()

    def delete(self, *args, **kwargs):
        kit = self.kit
        resultado = super().delete(*args, **kwargs)
        kit.atualizar_marcacao_de_kit()
        return resultado

    def clean(self):
        if self.componente_id == self.kit_id:
            raise ValidationError("Um kit não pode conter ele mesmo.")
        if self.componente_id and Produto.objects.filter(pk=self.componente_id, e_kit=True).exists():
            raise ValidationError("Um kit não pode conter outro kit.")


class PedidoCompra(models.Model):
    class Status(models.TextChoices):
        ABERTO = "aberto", "Aberto"
        RECEBIDO = "recebido", "Recebido"
        CANCELADO = "cancelado", "Cancelado"

    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.PROTECT, related_name="pedidos_compra")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ABERTO)
    observacao = models.CharField("Observação", max_length=255, blank=True)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    criado_em = models.DateTimeField(auto_now_add=True)
    recebido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Pedido de compra"
        verbose_name_plural = "Pedidos de compra"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"Pedido #{self.pk} — {self.fornecedor}"

    @property
    def total(self):
        return sum((item.total for item in self.itens.all()), Decimal("0"))

    def receber(self, usuario, recebidos):
        """Lança as entradas de estoque. `recebidos` = {item_id: (quantidade, custo, validade)}."""
        if self.status != self.Status.ABERTO:
            raise ValidationError("Este pedido não está mais aberto.")
        entradas = []
        with transaction.atomic():
            for item in self.itens.select_related("produto"):
                quantidade, custo, validade = recebidos.get(item.pk, (item.quantidade, item.custo_unitario, None))
                if quantidade <= 0:
                    continue
                entradas.append(item.produto.registrar_entrada(
                    quantidade=quantidade, fornecedor=self.fornecedor,
                    custo_unitario=custo, usuario=usuario, validade=validade,
                ))
                item.quantidade_recebida = quantidade
                item.save(update_fields=["quantidade_recebida"])
            self.status = self.Status.RECEBIDO
            self.recebido_em = timezone.now()
            self.save(update_fields=["status", "recebido_em"])
        return entradas


class ItemPedidoCompra(models.Model):
    pedido = models.ForeignKey(PedidoCompra, on_delete=models.CASCADE, related_name="itens")
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name="+")
    quantidade = models.PositiveIntegerField()
    custo_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    quantidade_recebida = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "Item do pedido de compra"
        verbose_name_plural = "Itens do pedido de compra"

    def __str__(self):
        return f"{self.produto} x{self.quantidade}"

    @property
    def total(self):
        return self.quantidade * self.custo_unitario
