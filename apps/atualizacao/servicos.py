"""Atualização da versão desktop pelas Releases do GitHub.

Fluxo: ao abrir (e a cada 6 horas) consulta a última Release em segundo plano;
se for mais nova que a instalada, o administrador vê um aviso. Ao confirmar, o
instalador é baixado, conferido (SHA-256 informado pelo GitHub) e executado em
modo silencioso; o programa fecha e o instalador o reabre na versão nova. Os
dados ficam fora da pasta do programa e não são tocados.

Só funciona no executável instalado no Windows (settings.ATUALIZACAO_ATIVA).
Sem internet, nada acontece: a verificação falha em silêncio e tenta depois.
"""

import hashlib
import json
import logging
import os
import re
import socket
import ssl
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from django.conf import settings
from django.utils import timezone

log = logging.getLogger("apps.atualizacao")

INTERVALO_VERIFICACAO = 6 * 60 * 60
TEMPO_LIMITE = 10
NOME_INSTALADOR = re.compile(r"^AdegaSetup-[\w.\-]+\.exe$")
HOSTS_PERMITIDOS = ("github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com")

_trava = threading.Lock()
_estado = {
    "verificado_em": None,
    "disponivel": None,  # dados da Release mais nova que a instalada
    "erro": "",  # frase para a tela (explicar_erro)
    "erro_detalhe": "",  # erro técnico, para o suporte
    "instalacao": None,  # {"fase", "baixado", "total", "mensagem"} durante a atualização
    "atualizado_de": None,  # versão anterior, quando acabou de atualizar
}


def estado():
    with _trava:
        return {chave: (dict(valor) if isinstance(valor, dict) else valor) for chave, valor in _estado.items()}


def _atualizar_estado(**valores):
    with _trava:
        _estado.update(valores)


# Versões ---------------------------------------------------------------------


def chave_versao(texto):
    """'1.2.0' > '1.2.0-teste' > '1.1.9'. Texto fora do padrão vale menos que tudo."""
    casamento = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)(?:-([\w.\-]+))?", (texto or "").strip())
    if not casamento:
        return (-1,)
    maior, menor, correcao, pre = casamento.groups()
    return (int(maior), int(menor), int(correcao), 0 if pre else 1, pre or "")


def mais_nova(candidata, atual):
    return chave_versao(candidata) > chave_versao(atual)


# Consulta ao GitHub ----------------------------------------------------------


_contexto = None


def _contexto_ssl():
    """Confere o certificado do GitHub pelo próprio Windows, como o navegador.

    O Python do executável só conhece as autoridades que já estão guardadas no
    Windows; o navegador baixa as que faltam. Sem o truststore, uma máquina com
    poucas atualizações recusava a conexão e o programa dizia "sem internet".
    """
    global _contexto
    if _contexto is None:
        try:
            import truststore

            _contexto = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        except Exception:
            _contexto = ssl.create_default_context()
    return _contexto


def _pedir(url, *, aceitar="application/vnd.github+json"):
    pedido = urllib.request.Request(url, headers={
        "Accept": aceitar,
        "User-Agent": f"AdegaEscritorio/{settings.VERSAO}",
    })
    return urllib.request.urlopen(pedido, timeout=TEMPO_LIMITE, context=_contexto_ssl())


def explicar_erro(erro):
    """Frase para a tela dizendo o motivo real (não só "sem internet")."""
    if isinstance(erro, urllib.error.HTTPError):
        if erro.code in (403, 429):
            return "O GitHub limitou as consultas deste computador por um tempo. Tente de novo daqui a uma hora."
        return f"O GitHub respondeu com erro {erro.code}. Tente de novo mais tarde."
    motivo = getattr(erro, "reason", erro)
    if isinstance(motivo, ssl.SSLError) or isinstance(erro, ssl.SSLError):
        return (
            "O Windows não confirmou o certificado de segurança do GitHub e a conexão foi recusada. "
            "Atualizar o Windows costuma resolver; antivírus que inspecionam sites seguros também podem causar isso."
        )
    if isinstance(motivo, socket.gaierror):
        return "Não foi possível encontrar o GitHub: o computador está sem internet ou o endereço está bloqueado na rede."
    if isinstance(motivo, (TimeoutError, socket.timeout)):
        return "O GitHub demorou demais para responder. A internet pode estar lenta; tente de novo."
    if isinstance(motivo, OSError):
        return "A conexão com o GitHub foi recusada. Um firewall, proxy ou antivírus pode estar bloqueando o programa."
    return "Não foi possível consultar as atualizações."


def _ler_release(dados):
    instalador = next(
        (a for a in dados.get("assets", []) if NOME_INSTALADOR.match(a.get("name", ""))), None
    )
    if instalador is None:
        return None
    digest = instalador.get("digest") or ""
    return {
        "versao": dados["tag_name"].lstrip("v"),
        "nome": dados.get("name") or dados["tag_name"],
        "novidades": formatar_novidades(dados.get("body")),
        "publicada_em": dados.get("published_at", ""),
        "pre_release": bool(dados.get("prerelease")),
        "url": instalador["browser_download_url"],
        "arquivo": instalador["name"],
        "tamanho": instalador.get("size") or 0,
        "sha256": digest.removeprefix("sha256:") if digest.startswith("sha256:") else "",
    }


def formatar_novidades(texto):
    """Markdown simples das notas da Release em linhas (titulo/item/texto) para a tela."""
    linhas = []
    for linha in (texto or "").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("**Full Changelog"):
            continue
        # "Melhora X by @fulano in https://github.com/..." (notas geradas pelo GitHub)
        linha = re.sub(r"\s+by @\S+ in https?://\S+$", "", linha).replace("**", "").replace("`", "")
        if linha.startswith("#"):
            linhas.append(("titulo", linha.lstrip("# ")))
        elif linha[:2] in ("- ", "* "):
            linhas.append(("item", linha[2:]))
        else:
            linhas.append(("texto", linha))
    return linhas


def buscar_ultima_release():
    """A Release mais nova do canal configurado (estável ou de testes), ou None."""
    base = f"https://api.github.com/repos/{settings.ATUALIZACAO_REPOSITORIO}/releases"
    if settings.ATUALIZACAO_CANAL == "testes":
        with _pedir(f"{base}?per_page=20") as resposta:
            lista = json.load(resposta)
        releases = [r for r in map(_ler_release, (d for d in lista if not d.get("draft"))) if r]
        return max(releases, key=lambda r: chave_versao(r["versao"]), default=None)
    try:
        with _pedir(f"{base}/latest") as resposta:
            return _ler_release(json.load(resposta))
    except urllib.error.HTTPError as erro:
        if erro.code == 404:  # nenhuma versão estável publicada ainda
            return None
        raise


def verificar():
    """Consulta o GitHub e guarda o resultado. Nunca levanta exceção."""
    try:
        release = buscar_ultima_release()
    except Exception as erro:  # sem internet, certificado, GitHub fora, limite de consultas...
        log.info("Não foi possível verificar atualizações", extra={"erro": repr(erro)})
        _atualizar_estado(verificado_em=timezone.now(), erro=explicar_erro(erro), erro_detalhe=repr(erro))
        return None
    disponivel = release if release and mais_nova(release["versao"], settings.VERSAO) else None
    _atualizar_estado(verificado_em=timezone.now(), erro="", erro_detalhe="", disponivel=disponivel)
    # O sino mostra a versão nova já na próxima página, sem esperar os 30 s.
    from apps.notificacoes.servicos import marcar_para_sincronizar

    marcar_para_sincronizar()
    if disponivel:
        log.info("Atualização disponível", extra={"versao": disponivel["versao"]})
    return disponivel


def iniciar_verificacao_periodica():
    def repetir():
        while True:
            verificar()
            time.sleep(INTERVALO_VERIFICACAO)

    threading.Thread(target=repetir, name="verificar-atualizacao", daemon=True).start()


def registrar_versao_iniciada():
    """Guarda a versão que abriu; se mudou desde a última vez, avisa que atualizou."""
    arquivo = Path(settings.DATA_DIR) / "versao_instalada.txt"
    anterior = arquivo.read_text(encoding="utf-8").strip() if arquivo.exists() else ""
    if anterior and anterior != settings.VERSAO:
        _atualizar_estado(atualizado_de=anterior)
        log.info("Adega atualizado", extra={"de": anterior, "para": settings.VERSAO})
    arquivo.write_text(settings.VERSAO, encoding="utf-8")


# Instalação ------------------------------------------------------------------


def _pasta_downloads():
    pasta = Path(settings.DATA_DIR) / "atualizacoes"
    pasta.mkdir(exist_ok=True)
    return pasta


def _baixar(release):
    destino = _pasta_downloads() / release["arquivo"]
    for antigo in destino.parent.glob("AdegaSetup-*.exe"):
        if antigo != destino:
            antigo.unlink(missing_ok=True)

    with _pedir(release["url"], aceitar="application/octet-stream") as resposta:
        host = urllib.parse.urlparse(resposta.geturl()).hostname or ""
        if not any(host == h or host.endswith("." + h) for h in HOSTS_PERMITIDOS):
            raise RuntimeError(f"Download veio de um endereço inesperado ({host}).")
        total = int(resposta.headers.get("Content-Length") or release["tamanho"] or 0)
        soma = hashlib.sha256()
        baixado = 0
        parcial = destino.with_suffix(".parcial")
        with open(parcial, "wb") as arquivo:
            while bloco := resposta.read(256 * 1024):
                arquivo.write(bloco)
                soma.update(bloco)
                baixado += len(bloco)
                _progresso(fase="baixando", baixado=baixado, total=total)

    _progresso(fase="verificando", mensagem="Conferindo o arquivo baixado…")
    if release["tamanho"] and baixado != release["tamanho"]:
        parcial.unlink(missing_ok=True)
        raise RuntimeError("O download veio incompleto. Tente de novo.")
    if release["sha256"] and soma.hexdigest() != release["sha256"]:
        parcial.unlink(missing_ok=True)
        raise RuntimeError("O arquivo baixado não confere com o publicado (SHA-256). A atualização foi cancelada.")
    parcial.replace(destino)
    return destino


def _progresso(**valores):
    with _trava:
        atual = dict(_estado["instalacao"] or {})
        atual.update(valores)
        _estado["instalacao"] = atual


def _executar_instalador(caminho):
    """Roda o instalador sem perguntas; ele fecha o Adega e o reabre no fim."""
    registro = Path(settings.DATA_DIR) / "logs" / "atualizacao.log"
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        [str(caminho), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
         "/CLOSEAPPLICATIONS", "/FORCECLOSEAPPLICATIONS", f"/LOG={registro}"],
        creationflags=flags,
        close_fds=True,
    )


def _encerrar_programa():
    # Dá tempo da tela mostrar "instalando" antes de fechar; o instalador
    # espera os arquivos do programa serem liberados.
    time.sleep(3)
    logging.shutdown()
    os._exit(0)


def instalar(release):
    """Baixa e instala em segundo plano. Acompanhe por estado()['instalacao']."""
    with _trava:
        if (_estado["instalacao"] or {}).get("fase") in ("baixando", "verificando", "instalando"):
            return False
        _estado["instalacao"] = {"fase": "baixando", "baixado": 0, "total": release["tamanho"], "mensagem": ""}

    def trabalhar():
        try:
            caminho = _baixar(release)
            _progresso(fase="instalando", mensagem="Instalando. O Adega vai fechar e abrir sozinho na versão nova.")
            log.info("Iniciando instalador", extra={"versao": release["versao"]})
            _executar_instalador(caminho)
            _encerrar_programa()
        except Exception as erro:
            log.exception("Falha na atualização")
            conexao = isinstance(erro, (urllib.error.URLError, ssl.SSLError, OSError)) and not isinstance(erro, RuntimeError)
            _progresso(fase="erro", mensagem=(explicar_erro(erro) if conexao else str(erro)) or "Não foi possível atualizar.")

    threading.Thread(target=trabalhar, name="instalar-atualizacao", daemon=True).start()
    return True
