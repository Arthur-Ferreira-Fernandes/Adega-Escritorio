"""Abre a gaveta de dinheiro ligada à impressora térmica.

A gaveta não fala com o computador: ela fica plugada na impressora (conector
RJ11 "DK"/"Cash drawer"), e abre quando a impressora recebe o comando ESC/POS
"ESC p". O comando vai direto para a impressora, sem passar pelo driver
gráfico (modo RAW). Só existe na versão desktop: na versão web o comando
sairia na impressora do servidor, e não na do caixa.
"""

import logging
import subprocess
import sys
import threading

from django.conf import settings

log = logging.getLogger("apps.caixa")

# ESC p m t1 t2: pulso no pino 2 e no pino 5 (cada gaveta usa um dos dois).
COMANDO_ABRIR = b"\x1bp\x00\x19\xfa" + b"\x1bp\x01\x19\xfa"


def disponivel():
    return getattr(settings, "GAVETA_DISPONIVEL", False)


def listar_impressoras():
    """Nomes das impressoras instaladas (vazio se não der para listar)."""
    try:
        if sys.platform == "win32":
            return _listar_windows()
        resultado = subprocess.run(["lpstat", "-e"], capture_output=True, text=True, timeout=5)
        return sorted(linha.strip() for linha in resultado.stdout.splitlines() if linha.strip())
    except Exception:
        log.exception("Não foi possível listar as impressoras")
        return []


def abrir(impressora):
    """Manda o comando de abrir para a impressora. Levanta RuntimeError com o motivo."""
    if not impressora:
        raise RuntimeError("Nenhuma impressora configurada para a gaveta.")
    if sys.platform == "win32":
        _enviar_windows(impressora, COMANDO_ABRIR)
    else:
        resultado = subprocess.run(
            ["lp", "-d", impressora, "-o", "raw"], input=COMANDO_ABRIR, capture_output=True, timeout=10
        )
        if resultado.returncode != 0:
            raise RuntimeError(resultado.stderr.decode(errors="replace").strip() or "A impressora recusou o comando.")


def abrir_ao_receber_dinheiro():
    """Chamado depois de um pagamento em dinheiro. Nunca atrasa nem derruba a venda."""
    from apps.configuracoes.models import Configuracao

    if not disponivel():
        return
    config = Configuracao.obter()
    if not (config.abrir_gaveta_no_dinheiro and config.impressora_gaveta):
        return

    def enviar():
        try:
            abrir(config.impressora_gaveta)
        except Exception:
            log.exception("Não foi possível abrir a gaveta", extra={"impressora": config.impressora_gaveta})

    threading.Thread(target=enviar, name="abrir-gaveta", daemon=True).start()


# Windows (winspool.drv, sem instalar nada) -----------------------------------


def _winspool():
    import ctypes
    from ctypes import wintypes

    winspool = ctypes.WinDLL("winspool.drv", use_last_error=True)
    winspool.OpenPrinterW.argtypes = [wintypes.LPWSTR, ctypes.POINTER(wintypes.HANDLE), ctypes.c_void_p]
    winspool.StartDocPrinterW.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p]
    winspool.WritePrinter.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    for nome in ("StartPagePrinter", "EndPagePrinter", "EndDocPrinter", "ClosePrinter"):
        getattr(winspool, nome).argtypes = [wintypes.HANDLE]
    winspool.EnumPrintersW.argtypes = [
        wintypes.DWORD, wintypes.LPWSTR, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
    ]
    return ctypes, wintypes, winspool


def _enviar_windows(impressora, dados):
    ctypes, wintypes, winspool = _winspool()

    class DOC_INFO_1(ctypes.Structure):
        _fields_ = [("pDocName", wintypes.LPWSTR), ("pOutputFile", wintypes.LPWSTR), ("pDatatype", wintypes.LPWSTR)]

    def falhou(etapa):
        return RuntimeError(f"{etapa}: {ctypes.FormatError(ctypes.get_last_error())}")

    alca = wintypes.HANDLE()
    if not winspool.OpenPrinterW(impressora, ctypes.byref(alca), None):
        raise falhou(f"Impressora '{impressora}' não encontrada")
    try:
        documento = DOC_INFO_1("Abrir gaveta", None, "RAW")
        if not winspool.StartDocPrinterW(alca, 1, ctypes.byref(documento)):
            raise falhou("A impressora recusou o comando")
        try:
            winspool.StartPagePrinter(alca)
            escritos = wintypes.DWORD()
            buffer = ctypes.create_string_buffer(dados, len(dados))
            if not winspool.WritePrinter(alca, buffer, len(dados), ctypes.byref(escritos)):
                raise falhou("Falha ao enviar para a impressora")
            winspool.EndPagePrinter(alca)
        finally:
            winspool.EndDocPrinter(alca)
    finally:
        winspool.ClosePrinter(alca)


def _listar_windows():
    ctypes, wintypes, winspool = _winspool()

    class PRINTER_INFO_4(ctypes.Structure):
        _fields_ = [("pPrinterName", wintypes.LPWSTR), ("pServerName", wintypes.LPWSTR), ("Attributes", wintypes.DWORD)]

    tipos = 0x2 | 0x4  # PRINTER_ENUM_LOCAL | PRINTER_ENUM_CONNECTIONS
    necessario, quantidade = wintypes.DWORD(), wintypes.DWORD()
    winspool.EnumPrintersW(tipos, None, 4, None, 0, ctypes.byref(necessario), ctypes.byref(quantidade))
    if not necessario.value:
        return []
    buffer = ctypes.create_string_buffer(necessario.value)
    if not winspool.EnumPrintersW(tipos, None, 4, buffer, necessario, ctypes.byref(necessario), ctypes.byref(quantidade)):
        return []
    lista = ctypes.cast(buffer, ctypes.POINTER(PRINTER_INFO_4))
    return sorted(lista[i].pPrinterName for i in range(quantidade.value))
