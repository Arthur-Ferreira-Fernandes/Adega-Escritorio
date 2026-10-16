from django.core.cache import cache
from django.db.models import F
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import number_format

from apps.caixa.models import Caixa
from apps.configuracoes.models import Configuracao
from apps.estoque.models import Produto

from .models import Notificacao

# O sino aparece em toda página: recalcular a cada clique custava uma consulta
# por produto e escritas no banco. Agora é no máximo a cada 30 segundos, ou
# logo depois de algo que muda a situação (ver marcar_para_sincronizar).
INTERVALO_SINCRONIZACAO = 30
CHAVE_SINCRONIZADO = "notificacoes:sincronizado"


# Só quem pode agir sobre elas vê no sino (atualizar exige administrador).
SO_ADMINISTRADORES = [Notificacao.Tipo.ATUALIZACAO]


def sincronizar():
    _sincronizar_caixa()
    _sincronizar_estoque()
    _sincronizar_atualizacao()


def sincronizar_se_preciso():
    # cache.add só grava se a chave não existe: um único pedido sincroniza por vez.
    if cache.add(CHAVE_SINCRONIZADO, True, INTERVALO_SINCRONIZACAO):
        sincronizar()


def marcar_para_sincronizar(**kwargs):
    cache.delete(CHAVE_SINCRONIZADO)


def visiveis(usuario):
    notificacoes = Notificacao.objects.filter(resolvida=False)
    if not getattr(usuario, "is_superuser", False):
        notificacoes = notificacoes.exclude(tipo__in=SO_ADMINISTRADORES)
    return notificacoes


def contexto_sino(usuario=None):
    sincronizar_se_preciso()
    ativas = list(visiveis(usuario).order_by("-criado_em"))
    return {"notificacoes": ativas, "total_nao_lidas": sum(1 for n in ativas if not n.lida)}


def _aplicar(tipo, desejadas):
    """Deixa ativas exatamente as notificações `desejadas` ({chave: (mensagem, link, nivel)}).

    Poucas consultas fixas, e só escreve no banco quando algo mudou.
    """
    ativas = {n.chave: n for n in Notificacao.objects.filter(tipo=tipo, resolvida=False)}
    novas = [
        Notificacao(tipo=tipo, chave=chave, mensagem=mensagem, link=link, nivel=nivel)
        for chave, (mensagem, link, nivel) in desejadas.items()
        if chave not in ativas
    ]
    if novas:
        Notificacao.objects.bulk_create(novas, ignore_conflicts=True)
    for chave, notificacao in ativas.items():
        if chave in desejadas:
            mensagem, _, nivel = desejadas[chave]
            if (notificacao.mensagem, notificacao.nivel) != (mensagem, nivel):
                notificacao.mensagem, notificacao.nivel = mensagem, nivel
                notificacao.save(update_fields=["mensagem", "nivel"])
    resolvidas = [n.pk for chave, n in ativas.items() if chave not in desejadas]
    if resolvidas:
        Notificacao.objects.filter(pk__in=resolvidas).update(resolvida=True, resolvida_em=timezone.now())


def _sincronizar_caixa():
    desejadas = {}
    caixa = Caixa.aberto_atual()
    if caixa is not None:
        saldo = caixa.saldo_esperado()
        if saldo > Configuracao.obter().limite_sangria:
            desejadas[f"caixa:{caixa.pk}"] = (
                f"O caixa está com R$ {number_format(saldo, decimal_pos=2)} — considere fazer uma sangria.",
                reverse("caixa:painel"),
                Notificacao.Nivel.AVISO,
            )
    _aplicar(Notificacao.Tipo.CAIXA_SANGRIA, desejadas)


def _sincronizar_atualizacao():
    from django.conf import settings

    desejadas = {}
    if settings.ATUALIZACAO_ATIVA:
        from apps.atualizacao import servicos as atualizacao

        release = atualizacao.estado()["disponivel"]
        if release:
            desejadas[f"versao:{release['versao']}"] = (
                f"Versão {release['versao']} do Adega disponível. Clique para ver as novidades e atualizar.",
                reverse("atualizacao:painel"),
                Notificacao.Nivel.AVISO,
            )
    # Sem versão nova (ou já atualizado), o aviso some sozinho.
    _aplicar(Notificacao.Tipo.ATUALIZACAO, desejadas)


def _sincronizar_estoque():
    link = reverse("estoque:produtos")
    _aplicar(Notificacao.Tipo.ESTOQUE_MINIMO, {
        f"produto:{pk}": (
            f"{nome} está no estoque mínimo (disponível: {quantidade}).",
            link,
            Notificacao.Nivel.AVISO,
        )
        for pk, nome, quantidade in Produto.objects.filter(
            ativo=True, quantidade_estoque__lte=F("estoque_minimo")
        ).values_list("pk", "nome", "quantidade_estoque")
    })
