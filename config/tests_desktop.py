"""Configuração da versão desktop: a chave secreta gerada tem que ser lida de volta."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

RAIZ = Path(__file__).resolve().parent.parent
LER_CHAVE = "import django; django.setup(); from django.conf import settings; print(settings.SECRET_KEY)"


def _abrir_configuracao(pasta):
    """Carrega config.settings.desktop num processo novo, como o programa ao abrir."""
    ambiente = {**os.environ, "ADEGA_DATA_DIR": str(pasta), "DJANGO_SETTINGS_MODULE": "config.settings.desktop"}
    resultado = subprocess.run(
        [sys.executable, "-c", LER_CHAVE], cwd=RAIZ, env=ambiente, capture_output=True, text=True, timeout=60
    )
    return resultado


class ChaveSecretaTests(SimpleTestCase):
    def test_chave_gerada_nao_tem_caracteres_que_o_environ_interpreta(self):
        with tempfile.TemporaryDirectory() as pasta:
            resultado = _abrir_configuracao(pasta)
            self.assertEqual(resultado.returncode, 0, resultado.stderr[-500:])
            chave = (Path(pasta) / "adega.env").read_text(encoding="utf-8").split("SECRET_KEY=")[1].splitlines()[0]
            self.assertEqual(resultado.stdout.strip(), chave)
            self.assertTrue(set(chave) <= set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"))

    def test_instalacao_com_chave_comecando_por_cifrao_volta_a_abrir(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "adega.env"
            arquivo.write_text("SECRET_KEY=$v0yos-sppic85)92bz3#l60*+bq@#h3!t)\nPORTA=8123\nACESSO_REDE=False\n", encoding="utf-8")
            resultado = _abrir_configuracao(pasta)
            self.assertEqual(resultado.returncode, 0, resultado.stderr[-500:])
            conteudo = arquivo.read_text(encoding="utf-8")
            self.assertNotIn("SECRET_KEY=$", conteudo)
            self.assertIn("PORTA=8123", conteudo)  # o resto da configuração fica como estava
            self.assertEqual(resultado.stdout.strip(), conteudo.split("SECRET_KEY=")[1].splitlines()[0])
