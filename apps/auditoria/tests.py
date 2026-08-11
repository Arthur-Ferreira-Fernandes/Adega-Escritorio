from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.estoque.models import Categoria

from . import servicos as auditoria
from .models import RegistroAuditoria

User = get_user_model()


class _CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ["nome"]


class ServicosTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username="operador", password="senha123")

    def test_registrar_grava_ator_e_objeto(self):
        categoria = Categoria.objects.create(nome="Vinhos")
        auditoria.registrar(
            self.usuario, RegistroAuditoria.Acao.CRIACAO, categoria
        )
        registro = RegistroAuditoria.objects.get()
        self.assertEqual(registro.usuario, self.usuario)
        self.assertEqual(registro.usuario_repr, "operador")
        self.assertEqual(registro.modelo, "Categoria")
        self.assertEqual(registro.objeto_repr, "Vinhos")
        self.assertEqual(registro.objeto_id, categoria.pk)

    def test_registrar_aceita_objeto_id_explicito(self):
        categoria = Categoria.objects.create(nome="Vinhos")
        pk = categoria.pk
        categoria.delete()
        auditoria.registrar(
            self.usuario, RegistroAuditoria.Acao.EXCLUSAO, categoria,
            objeto_id=pk, detalhes="Vinhos",
        )
        registro = RegistroAuditoria.objects.get()
        self.assertEqual(registro.objeto_id, pk)

    def test_usuario_null_nao_apaga_registro(self):
        categoria = Categoria.objects.create(nome="Vinhos")
        auditoria.registrar(self.usuario, RegistroAuditoria.Acao.CRIACAO, categoria)
        self.usuario.delete()
        registro = RegistroAuditoria.objects.get()
        self.assertIsNone(registro.usuario)
        self.assertEqual(registro.usuario_repr, "operador")

    def test_capturar_valores_le_atributos_atuais(self):
        categoria = Categoria.objects.create(nome="Vinhos")
        valores = auditoria.capturar_valores(categoria, ["nome"])
        self.assertEqual(valores, {"nome": "Vinhos"})

    def test_resumir_alteracoes_gera_diff_legivel(self):
        categoria = Categoria.objects.create(nome="Vinhos")
        valores_antigos = auditoria.capturar_valores(categoria, ["nome"])
        form = _CategoriaForm(
            {"nome": "Vinhos Finos"}, instance=categoria
        )
        self.assertTrue(form.is_valid())
        resumo = auditoria.resumir_alteracoes(form, valores_antigos)
        self.assertIn("Vinhos", resumo)
        self.assertIn("Vinhos Finos", resumo)


class AuditoriaViewTests(TestCase):
    def setUp(self):
        self.superusuario = User.objects.create_user(
            username="admin_teste", password="senha123", is_staff=True, is_superuser=True
        )
        self.staff = User.objects.create_user(
            username="staff_teste", password="senha123", is_staff=True
        )

    def test_bloqueado_para_nao_superusuario(self):
        self.client.force_login(self.staff)
        resposta = self.client.get(reverse("auditoria:lista"))
        self.assertNotEqual(resposta.status_code, 200)

    def test_permitido_para_superusuario(self):
        self.client.force_login(self.superusuario)
        resposta = self.client.get(reverse("auditoria:lista"))
        self.assertEqual(resposta.status_code, 200)

    def test_filtro_por_modelo(self):
        self.client.force_login(self.superusuario)
        categoria = Categoria.objects.create(nome="Vinhos")
        auditoria.registrar(self.superusuario, RegistroAuditoria.Acao.CRIACAO, categoria)
        resposta = self.client.get(reverse("auditoria:lista"), {"modelo": "Produto"})
        self.assertNotContains(resposta, "Vinhos")
