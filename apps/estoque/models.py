from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
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

    def registrar_entrada(self, *, quantidade, fornecedor, custo_unitario, usuario):
        if quantidade < 1:
            raise ValidationError("A quantidade deve ser maior que zero.")
        if custo_unitario <= 0:
            raise ValidationError("O custo unitário deve ser maior que zero.")
        entrada = EntradaEstoque.objects.create(
            produto=self,
            fornecedor=fornecedor,
            quantidade=quantidade,
            custo_unitario=custo_unitario,
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
