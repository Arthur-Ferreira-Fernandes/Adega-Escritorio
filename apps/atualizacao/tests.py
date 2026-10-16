import hashlib
import io
import json
import tempfile
import time
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from . import servicos

User = get_user_model()
INSTALADOR = b"MZ" + b"\x00" * 5000


def _release(tag, *, conteudo=INSTALADOR, digest=True, prerelease=False, nome_arquivo=None):
    return {
        "tag_name": tag,
        "name": f"Adega {tag}",
        "body": "- Relatórios novos",
        "prerelease": prerelease,
        "draft": False,
        "published_at": "2026-10-20T12:00:00Z",
        "assets": [
            {"name": "notas.txt", "browser_download_url": "https://github.com/x/notas.txt", "size": 1},
            {
                "name": nome_arquivo or f"AdegaSetup-{tag.lstrip('v')}.exe",
                "browser_download_url": f"https://github.com/x/releases/download/{tag}/AdegaSetup.exe",
                "size": len(conteudo),
                "digest": f"sha256:{hashlib.sha256(conteudo).hexdigest()}" if digest else None,
            },
        ],
    }


class _Resposta(io.BytesIO):
    def __init__(self, dados, url="https://release-assets.githubusercontent.com/x"):
        super().__init__(dados)
        self.headers = {"Content-Length": str(len(dados))}
        self._url = url

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *erro):
        self.close()


class BaseAtualizacao(TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        configuracao = override_settings(
            VERSAO="1.0.0", ATUALIZACAO_ATIVA=True, ATUALIZACAO_CANAL="estavel", DATA_DIR=Path(self.pasta.name),
        )
        configuracao.enable()
        self.addCleanup(configuracao.disable)
        (Path(self.pasta.name) / "logs").mkdir()
        servicos._estado.update(verificado_em=None, disponivel=None, erro="", instalacao=None, atualizado_de=None)

    def responder(self, *respostas):
        """Simula o GitHub: cada chamada ao urlopen devolve a próxima resposta."""
        fila = [r if isinstance(r, _Resposta) else _Resposta(json.dumps(r).encode()) for r in respostas]
        return mock.patch("urllib.request.urlopen", side_effect=lambda *a, **k: fila.pop(0))


class VersaoTests(BaseAtualizacao):
    def test_ordem_das_versoes(self):
        ordem = ["lixo", "0.9.9", "1.0.0-teste", "1.0.0", "1.0.1", "1.10.0", "v2.0.0"]
        self.assertEqual(sorted(reversed(ordem), key=servicos.chave_versao), ordem)

    def test_verificar_so_oferece_versao_mais_nova(self):
        with self.responder(_release("v1.0.0")):
            self.assertIsNone(servicos.verificar())
        with self.responder(_release("v1.2.0")):
            release = servicos.verificar()
        self.assertEqual((release["versao"], release["arquivo"]), ("1.2.0", "AdegaSetup-1.2.0.exe"))
        self.assertEqual(servicos.estado()["disponivel"]["novidades"], [("item", "Relatórios novos")])

    def test_sem_internet_nao_quebra(self):
        with mock.patch("urllib.request.urlopen", side_effect=OSError("sem rede")):
            self.assertIsNone(servicos.verificar())
        self.assertIn("conexão com o GitHub foi recusada", servicos.estado()["erro"])
        self.assertIn("sem rede", servicos.estado()["erro_detalhe"])

    def test_release_sem_instalador_e_ignorada(self):
        with self.responder(_release("v1.2.0", nome_arquivo="outra-coisa.zip")):
            self.assertIsNone(servicos.verificar())

    @override_settings(ATUALIZACAO_CANAL="testes")
    def test_canal_de_testes_considera_pre_release(self):
        lista = [_release("v1.1.0"), _release("v1.2.0-teste", prerelease=True)]
        with self.responder(lista):
            self.assertEqual(servicos.verificar()["versao"], "1.2.0-teste")

    def test_registra_quando_acabou_de_atualizar(self):
        servicos.registrar_versao_iniciada()
        self.assertIsNone(servicos.estado()["atualizado_de"])
        with override_settings(VERSAO="1.1.0"):
            servicos.registrar_versao_iniciada()
        self.assertEqual(servicos.estado()["atualizado_de"], "1.0.0")


class ErrosDeConexaoTests(BaseAtualizacao):
    def falhar(self, erro):
        with mock.patch("urllib.request.urlopen", side_effect=erro):
            self.assertIsNone(servicos.verificar())
        return servicos.estado()["erro"]

    def test_certificado_nao_e_confundido_com_falta_de_internet(self):
        import ssl
        import urllib.error

        erro = urllib.error.URLError(ssl.SSLCertVerificationError(1, "CERTIFICATE_VERIFY_FAILED"))
        self.assertIn("certificado de segurança", self.falhar(erro))
        self.assertIn("CERTIFICATE_VERIFY_FAILED", servicos.estado()["erro_detalhe"])

    def test_outros_motivos(self):
        import socket
        import urllib.error

        self.assertIn("sem internet", self.falhar(urllib.error.URLError(socket.gaierror(11001, "getaddrinfo failed"))))
        self.assertIn("demorou demais", self.falhar(urllib.error.URLError(TimeoutError())))
        self.assertIn("limitou as consultas", self.falhar(urllib.error.HTTPError("u", 403, "rate", {}, None)))
        self.assertIn("firewall", self.falhar(urllib.error.URLError(ConnectionResetError())))

    def test_sem_versao_estavel_nao_e_erro(self):
        import urllib.error

        self.assertEqual(self.falhar(urllib.error.HTTPError("u", 404, "Not Found", {}, None)), "")

    def test_usa_os_certificados_do_sistema(self):
        with mock.patch("urllib.request.urlopen", return_value=_Resposta(json.dumps(_release("v1.0.0")).encode())) as abrir:
            servicos.verificar()
        self.assertIsNotNone(abrir.call_args.kwargs["context"])


class NovidadesTests(TestCase):
    def test_formata_notas_escritas_e_geradas_pelo_github(self):
        texto = (
            "## O que mudou\n\n- Contagem de **estoque**\n* Fix by @arthur in https://github.com/x/pull/3\n"
            "Obrigado!\n\n**Full Changelog**: https://github.com/x/compare/v1...v2"
        )
        self.assertEqual(servicos.formatar_novidades(texto), [
            ("titulo", "O que mudou"), ("item", "Contagem de estoque"), ("item", "Fix"), ("texto", "Obrigado!"),
        ])


class InstalacaoTests(BaseAtualizacao):
    def instalar(self, release, resposta):
        with self.responder(resposta), \
                mock.patch.object(servicos, "_executar_instalador") as executar, \
                mock.patch.object(servicos, "_encerrar_programa") as encerrar:
            self.assertTrue(servicos.instalar(release))
            for _ in range(100):
                if servicos.estado()["instalacao"]["fase"] in ("instalando", "erro"):
                    break
                time.sleep(0.02)
            time.sleep(0.05)
        return executar, encerrar

    def test_baixa_confere_e_executa_o_instalador(self):
        release = servicos._ler_release(_release("v1.2.0"))
        executar, encerrar = self.instalar(release, _Resposta(INSTALADOR))
        destino = Path(self.pasta.name) / "atualizacoes" / "AdegaSetup-1.2.0.exe"
        self.assertEqual(destino.read_bytes(), INSTALADOR)
        executar.assert_called_once_with(destino)
        encerrar.assert_called_once()
        self.assertEqual(servicos.estado()["instalacao"]["fase"], "instalando")

    def test_arquivo_adulterado_nao_e_executado(self):
        release = servicos._ler_release(_release("v1.2.0"))
        executar, encerrar = self.instalar(release, _Resposta(b"MZ" + b"\x01" * 5000))
        executar.assert_not_called()
        encerrar.assert_not_called()
        self.assertEqual(servicos.estado()["instalacao"]["fase"], "erro")
        self.assertIn("SHA-256", servicos.estado()["instalacao"]["mensagem"])
        self.assertEqual(list((Path(self.pasta.name) / "atualizacoes").iterdir()), [])

    def test_download_de_outro_endereco_e_recusado(self):
        release = servicos._ler_release(_release("v1.2.0"))
        executar, _ = self.instalar(release, _Resposta(INSTALADOR, url="https://exemplo.com/x.exe"))
        executar.assert_not_called()
        self.assertIn("endereço inesperado", servicos.estado()["instalacao"]["mensagem"])


class TelasTests(BaseAtualizacao):
    def setUp(self):
        super().setUp()
        self.dono = User.objects.create_superuser(username="dono", password="x")
        self.client.force_login(self.dono)

    def test_faixa_aparece_so_para_administrador(self):
        servicos._estado["disponivel"] = servicos._ler_release(_release("v1.2.0"))
        self.assertContains(self.client.get(reverse("inicio")), "Versão <strong>1.2.0</strong> do Adega disponível")
        self.client.force_login(User.objects.create_user(username="caixa", password="x"))
        self.assertNotContains(self.client.get(reverse("inicio")), "do Adega disponível")

    def test_painel_e_instalar(self):
        servicos._estado["disponivel"] = servicos._ler_release(_release("v1.2.0"))
        resposta = self.client.get(reverse("atualizacao:painel"))
        self.assertContains(resposta, "Versão 1.2.0 disponível")
        self.assertContains(resposta, "Relatórios novos")
        with mock.patch.object(servicos, "instalar", return_value=True) as instalar:
            self.client.post(reverse("atualizacao:instalar"))
        instalar.assert_called_once()

    @override_settings(ATUALIZACAO_ATIVA=False)
    def test_desligado_fora_do_programa_instalado(self):
        self.assertEqual(self.client.get(reverse("atualizacao:painel")).status_code, 404)
        self.assertNotContains(self.client.get(reverse("inicio")), "Atualizações")


class SinoTests(BaseAtualizacao):
    def setUp(self):
        super().setUp()
        self.dono = User.objects.create_superuser(username="dono", password="x")
        self.caixa = User.objects.create_user(username="caixa", password="x")

    def sino(self, usuario):
        self.client.force_login(usuario)
        return self.client.get(reverse("notificacoes:sino")).content.decode()

    def test_versao_nova_aparece_no_sino_so_para_administrador(self):
        with self.responder(_release("v1.2.0")):
            servicos.verificar()
        self.assertIn("Versão 1.2.0 do Adega disponível", self.sino(self.dono))
        self.assertIn(reverse("atualizacao:painel"), self.sino(self.dono))
        self.assertNotIn("do Adega disponível", self.sino(self.caixa))

    def test_some_quando_nao_ha_mais_versao_nova(self):
        with self.responder(_release("v1.2.0")):
            servicos.verificar()
        self.assertIn("Versão 1.2.0", self.sino(self.dono))
        with override_settings(VERSAO="1.2.0"), self.responder(_release("v1.2.0")):
            servicos.verificar()  # ex.: depois de atualizar
            self.assertNotIn("Versão 1.2.0", self.sino(self.dono))

    def test_atendente_marcar_como_lidas_nao_afeta_o_aviso_do_administrador(self):
        from apps.notificacoes.models import Notificacao

        with self.responder(_release("v1.2.0")):
            servicos.verificar()
        self.sino(self.dono)
        self.client.force_login(self.caixa)
        self.client.post(reverse("notificacoes:marcar_lidas"))
        aviso = Notificacao.objects.get(tipo=Notificacao.Tipo.ATUALIZACAO)
        self.assertFalse(aviso.lida)
