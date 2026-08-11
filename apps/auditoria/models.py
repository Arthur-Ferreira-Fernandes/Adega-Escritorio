from django.conf import settings
from django.db import models


class RegistroAuditoria(models.Model):
    class Acao(models.TextChoices):
        CRIACAO = "criacao", "Criação"
        EDICAO = "edicao", "Edição"
        EXCLUSAO = "exclusao", "Exclusão"
        OUTRA = "outra", "Outra"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="registros_auditoria",
    )
    usuario_repr = models.CharField(max_length=150, blank=True)
    acao = models.CharField(max_length=10, choices=Acao.choices)
    modelo = models.CharField(max_length=100)
    objeto_repr = models.CharField(max_length=255)
    objeto_id = models.PositiveIntegerField(null=True, blank=True)
    detalhes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Registro de auditoria"
        verbose_name_plural = "Registros de auditoria"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.get_acao_display()} · {self.modelo} · {self.objeto_repr}"
