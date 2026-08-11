from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.shortcuts import render

from .forms import FiltroAuditoriaForm
from .models import RegistroAuditoria


def _somente_admin(user):
    return user.is_superuser


@login_required
@user_passes_test(_somente_admin)
def lista(request):
    form = FiltroAuditoriaForm(request.GET or None)
    registros = RegistroAuditoria.objects.select_related("usuario")

    if form.is_valid():
        if form.cleaned_data.get("data_inicio"):
            registros = registros.filter(criado_em__date__gte=form.cleaned_data["data_inicio"])
        if form.cleaned_data.get("data_fim"):
            registros = registros.filter(criado_em__date__lte=form.cleaned_data["data_fim"])
        if form.cleaned_data.get("usuario"):
            registros = registros.filter(usuario=form.cleaned_data["usuario"])
        if form.cleaned_data.get("modelo"):
            registros = registros.filter(modelo=form.cleaned_data["modelo"])
        if form.cleaned_data.get("acao"):
            registros = registros.filter(acao=form.cleaned_data["acao"])

    paginator = Paginator(registros, 20)
    pagina = paginator.get_page(request.GET.get("pagina"))

    querystring = request.GET.copy()
    querystring.pop("pagina", None)

    contexto = {"form": form, "pagina": pagina, "querystring": querystring.urlencode()}
    template = (
        "auditoria/_conteudo.html"
        if request.headers.get("HX-Request") == "true"
        else "auditoria/lista.html"
    )
    return render(request, template, contexto)
