"""Exportação das tabelas para planilha (CSV que o Excel abre em português)."""

import csv
from datetime import date, datetime
from decimal import Decimal

from django.http import HttpResponse
from django.utils import timezone


def _celula(valor):
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "Sim" if valor else "Não"
    if isinstance(valor, Decimal):
        return f"{valor:.2f}".replace(".", ",")
    if isinstance(valor, float):
        return f"{valor:.2f}".replace(".", ",")
    if isinstance(valor, datetime):
        return timezone.localtime(valor).strftime("%d/%m/%Y %H:%M")
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    return str(valor)


def resposta_csv(nome_arquivo, cabecalho, linhas):
    """Separador ";" e vírgula decimal: o padrão do Excel em português.

    O BOM no início faz o Excel reconhecer o UTF-8 (acentos corretos).
    """
    resposta = HttpResponse(content_type="text/csv; charset=utf-8")
    resposta["Content-Disposition"] = f'attachment; filename="{nome_arquivo}.csv"'
    resposta.write("﻿")
    escritor = csv.writer(resposta, delimiter=";")
    escritor.writerow(cabecalho)
    for linha in linhas:
        escritor.writerow([_celula(valor) for valor in linha])
    return resposta
