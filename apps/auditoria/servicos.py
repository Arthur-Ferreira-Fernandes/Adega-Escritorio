from .models import RegistroAuditoria


def registrar(usuario, acao, instancia, *, objeto_id=None, detalhes=""):
    RegistroAuditoria.objects.create(
        usuario=usuario,
        usuario_repr=str(usuario),
        acao=acao,
        modelo=type(instancia).__name__,
        objeto_repr=str(instancia)[:255],
        objeto_id=objeto_id if objeto_id is not None else instancia.pk,
        detalhes=detalhes,
    )


def capturar_valores(instancia, campos):
    return {campo: getattr(instancia, campo, None) for campo in campos}


def resumir_alteracoes(form, valores_antigos):
    partes = []
    for campo in form.changed_data:
        label = form.fields[campo].label or campo
        partes.append(f"{label}: {valores_antigos.get(campo)} → {form.cleaned_data.get(campo)}")
    return "; ".join(partes)
