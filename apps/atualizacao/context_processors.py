from django.conf import settings

from . import servicos


def atualizacao(request):
    contexto = {"versao_app": settings.VERSAO, "atualizacao_ativa": settings.ATUALIZACAO_ATIVA}
    if settings.ATUALIZACAO_ATIVA and request.user.is_authenticated and request.user.is_superuser:
        estado = servicos.estado()
        contexto["atualizacao_disponivel"] = estado["disponivel"]
        contexto["atualizado_de"] = estado["atualizado_de"]
    return contexto
