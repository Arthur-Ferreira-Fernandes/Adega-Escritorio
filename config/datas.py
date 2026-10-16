from datetime import datetime, time, timedelta

from django.utils import timezone


def inicio_do_dia(data):
    """Meia-noite do dia, no fuso local (para filtros campo__gte / campo__lt)."""
    return timezone.make_aware(datetime.combine(data, time.min))


def periodo(campo, inicio, fim=None):
    """Filtro "campo entre os dias inicio e fim" (inclusive, no fuso local).

    Equivale a campo__date__gte/__lte, mas sem converter cada linha: no SQLite,
    __date chama uma função Python para cada registro e ignora os índices,
    o que fica lento quando o histórico cresce.
    """
    fim = fim or inicio
    return {f"{campo}__gte": inicio_do_dia(inicio), f"{campo}__lt": inicio_do_dia(fim + timedelta(days=1))}
