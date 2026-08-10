from datetime import timedelta
from decimal import Decimal

from django.db.models import F
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import number_format

from apps.caixa.models import Caixa
from apps.estoque.models import Produto

from .models import Notificacao

LIMITE_SANGRIA = Decimal("1000")
ANTECEDENCIA_LIMITE_CAIXA = timedelta(hours=1)


def sincronizar():
    _sincronizar_caixa()
    _sincronizar_estoque()


def contexto_sino():
    sincronizar()
    ativas = Notificacao.objects.filter(resolvida=False).order_by("-criado_em")
    return {"notificacoes": ativas, "total_nao_lidas": ativas.filter(lida=False).count()}


def _sincronizar_caixa():
    caixa = Caixa.aberto_atual()
    if caixa is None:
        Notificacao.resolver_ausentes(Notificacao.Tipo.CAIXA_LIMITE, [])
        Notificacao.resolver_ausentes(Notificacao.Tipo.CAIXA_SANGRIA, [])
        return
    _sincronizar_caixa_limite(caixa)
    _sincronizar_caixa_sangria(caixa)


def _sincronizar_caixa_limite(caixa):
    chaves = []
    restante = caixa.limite_em - timezone.now()
    chave = f"caixa:{caixa.pk}:{caixa.horas_extras}"
    if restante <= timedelta(0):
        Notificacao.registrar(
            Notificacao.Tipo.CAIXA_LIMITE,
            chave,
            "O caixa passou do limite de horas para iniciar novas vendas. Peça a um "
            "administrador para autorizar mais tempo.",
            link=reverse("caixa:painel"),
            nivel=Notificacao.Nivel.PERIGO,
        )
        chaves.append(chave)
    elif restante <= ANTECEDENCIA_LIMITE_CAIXA:
        minutos = int(restante.total_seconds() // 60)
        Notificacao.registrar(
            Notificacao.Tipo.CAIXA_LIMITE,
            chave,
            f"O caixa atinge o limite de horas em {minutos} minuto(s).",
            link=reverse("caixa:painel"),
            nivel=Notificacao.Nivel.AVISO,
        )
        chaves.append(chave)
    Notificacao.resolver_ausentes(Notificacao.Tipo.CAIXA_LIMITE, chaves)


def _sincronizar_caixa_sangria(caixa):
    chaves = []
    saldo = caixa.saldo_esperado()
    if saldo > LIMITE_SANGRIA:
        chave = f"caixa:{caixa.pk}"
        Notificacao.registrar(
            Notificacao.Tipo.CAIXA_SANGRIA,
            chave,
            f"O caixa está com R$ {number_format(saldo, decimal_pos=2)} — considere fazer uma sangria.",
            link=reverse("caixa:painel"),
            nivel=Notificacao.Nivel.AVISO,
        )
        chaves.append(chave)
    Notificacao.resolver_ausentes(Notificacao.Tipo.CAIXA_SANGRIA, chaves)


def _sincronizar_estoque():
    produtos_baixos = Produto.objects.filter(ativo=True, quantidade_estoque__lte=F("estoque_minimo"))
    chaves = []
    for produto in produtos_baixos:
        chave = f"produto:{produto.pk}"
        Notificacao.registrar(
            Notificacao.Tipo.ESTOQUE_MINIMO,
            chave,
            f"{produto.nome} está no estoque mínimo (disponível: {produto.quantidade_estoque}).",
            link=reverse("estoque:produtos"),
            nivel=Notificacao.Nivel.AVISO,
        )
        chaves.append(chave)
    Notificacao.resolver_ausentes(Notificacao.Tipo.ESTOQUE_MINIMO, chaves)
