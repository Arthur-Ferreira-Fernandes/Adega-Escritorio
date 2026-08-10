from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Notificacao
from .servicos import contexto_sino


@login_required
def notificacoes_sino(request):
    return render(request, "notificacoes/_sino_conteudo.html", contexto_sino())


@login_required
@require_POST
def notificacoes_marcar_lidas(request):
    Notificacao.objects.filter(resolvida=False, lida=False).update(
        lida=True, lida_em=timezone.now()
    )
    return render(request, "notificacoes/_sino_conteudo.html", contexto_sino())
