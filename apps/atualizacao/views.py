from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.vendas.models import Venda

from . import servicos


def _somente_admin(user):
    return user.is_superuser


def _exigir_ativa():
    if not settings.ATUALIZACAO_ATIVA:
        raise Http404("Atualização automática só existe no programa instalado no Windows.")


@login_required
@user_passes_test(_somente_admin)
def painel(request):
    _exigir_ativa()
    estado = servicos.estado()
    return render(request, "atualizacao/painel.html", {
        "estado": estado,
        "release": estado["disponivel"],
        "instalacao": estado["instalacao"],
        "comandas_abertas": Venda.objects.filter(status=Venda.Status.ABERTA).count(),
        "canal": settings.ATUALIZACAO_CANAL,
    })


@login_required
@user_passes_test(_somente_admin)
@require_POST
def verificar_agora(request):
    _exigir_ativa()
    if servicos.verificar():
        messages.success(request, "Há uma versão nova disponível.")
    elif servicos.estado()["erro"]:
        messages.error(request, "Não foi possível consultar as atualizações. Confira a internet e tente de novo.")
    else:
        messages.info(request, f"O Adega já está na versão mais recente ({settings.VERSAO}).")
    return redirect("atualizacao:painel")


@login_required
@user_passes_test(_somente_admin)
@require_POST
def instalar(request):
    _exigir_ativa()
    release = servicos.estado()["disponivel"]
    if release is None:
        messages.error(request, "Nenhuma atualização disponível para instalar.")
    elif not servicos.instalar(release):
        messages.info(request, "A atualização já está em andamento.")
    return redirect("atualizacao:painel")


@login_required
@user_passes_test(_somente_admin)
def progresso(request):
    _exigir_ativa()
    return render(request, "atualizacao/_progresso.html", {"instalacao": servicos.estado()["instalacao"]})
