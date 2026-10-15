from django.db import models
from django.db.models import Q
from django.utils import timezone


class Notificacao(models.Model):
    class Tipo(models.TextChoices):
        CAIXA_SANGRIA = "caixa_sangria", "Caixa precisa de sangria"
        ESTOQUE_MINIMO = "estoque_minimo", "Estoque no mínimo"

    class Nivel(models.TextChoices):
        AVISO = "aviso", "Aviso"
        PERIGO = "perigo", "Perigo"

    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    chave = models.CharField(max_length=255)
    nivel = models.CharField(max_length=10, choices=Nivel.choices, default=Nivel.AVISO)
    mensagem = models.CharField(max_length=255)
    link = models.CharField(max_length=255, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    lida = models.BooleanField(default=False)
    lida_em = models.DateTimeField(null=True, blank=True)
    resolvida = models.BooleanField(default=False)
    resolvida_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Notificação"
        verbose_name_plural = "Notificações"
        ordering = ["-criado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["tipo", "chave"],
                condition=Q(resolvida=False),
                name="notificacao_unica_ativa_por_chave",
            ),
        ]

    def __str__(self):
        return self.mensagem

    @classmethod
    def registrar(cls, tipo, chave, mensagem, *, link="", nivel=Nivel.AVISO):
        notificacao, criada = cls.objects.get_or_create(
            tipo=tipo,
            chave=chave,
            resolvida=False,
            defaults={"mensagem": mensagem, "link": link, "nivel": nivel},
        )
        if not criada and (notificacao.mensagem != mensagem or notificacao.nivel != nivel):
            notificacao.mensagem = mensagem
            notificacao.nivel = nivel
            notificacao.save(update_fields=["mensagem", "nivel"])
        return notificacao

    @classmethod
    def resolver_ausentes(cls, tipo, chaves_ativas):
        cls.objects.filter(tipo=tipo, resolvida=False).exclude(chave__in=chaves_ativas).update(
            resolvida=True, resolvida_em=timezone.now()
        )
