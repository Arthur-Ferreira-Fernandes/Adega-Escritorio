from .servicos import contexto_sino


def notificacoes(request):
    if not request.user.is_authenticated:
        return {}
    return contexto_sino(request.user)
