import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.auditoria import servicos as auditoria
from apps.auditoria.models import RegistroAuditoria
from apps.caixa.models import Caixa
from apps.clientes.models import Cliente, Fornecedor
from apps.estoque.models import Categoria, EntradaEstoque, Produto
from apps.financeiro.models import ContaPagar, ContaReceber
from apps.notificacoes.models import Notificacao
from apps.vendas.models import Venda

User = get_user_model()

CATALOGO = {
    "Vinhos Tintos": [
        ("Malbec Reserva", 69.90, "gf"),
        ("Cabernet Sauvignon Concha y Toro", 54.90, "gf"),
        ("Merlot Miolo", 49.90, "gf"),
        ("Tannat Salton", 44.90, "gf"),
        ("Rioja Crianza", 89.90, "gf"),
        ("Chianti Classico", 119.90, "gf"),
        ("Pinot Noir Chileno", 79.90, "gf"),
        ("Syrah Argentino", 64.90, "gf"),
        ("Cabernet Franc Casa Valduga", 94.90, "gf"),
        ("Carmenère Chileno", 59.90, "gf"),
        ("Primitivo Italiano", 99.90, "gf"),
        ("Sangiovese Toscano", 84.90, "gf"),
    ],
    "Vinhos Brancos": [
        ("Chardonnay Miolo", 59.90, "gf"),
        ("Sauvignon Blanc Chileno", 54.90, "gf"),
        ("Riesling Alemão", 89.90, "gf"),
        ("Pinot Grigio Italiano", 69.90, "gf"),
        ("Moscato Salton", 39.90, "gf"),
        ("Viognier Argentino", 64.90, "gf"),
        ("Torrontés Argentino", 49.90, "gf"),
        ("Verdejo Espanhol", 74.90, "gf"),
    ],
    "Vinhos Rosés": [
        ("Rosé Miolo", 54.90, "gf"),
        ("Rosé Provence", 129.90, "gf"),
        ("Rosé Chandon", 89.90, "gf"),
        ("Rosé Salton", 44.90, "gf"),
        ("Rosé Casa Valduga", 69.90, "gf"),
    ],
    "Espumantes": [
        ("Chandon Brut", 99.90, "gf"),
        ("Salton Brut", 49.90, "gf"),
        ("Casa Valduga 130", 89.90, "gf"),
        ("Cave Geisse Brut", 149.90, "gf"),
        ("Moët Chandon Imperial", 449.90, "gf"),
        ("Prosecco Italiano", 79.90, "gf"),
    ],
    "Whiskies e Destilados": [
        ("Johnnie Walker Red Label", 99.90, "gf"),
        ("Johnnie Walker Black Label", 189.90, "gf"),
        ("Jack Daniel's", 149.90, "gf"),
        ("Chivas Regal 12 anos", 219.90, "gf"),
        ("Ballantine's Finest", 109.90, "gf"),
        ("Jameson", 129.90, "gf"),
        ("Absolut Vodka", 79.90, "gf"),
        ("Smirnoff Vodka", 49.90, "gf"),
        ("Gin Tanqueray", 139.90, "gf"),
        ("Rum Bacardi", 69.90, "gf"),
    ],
    "Charutos": [
        ("Cohiba Robusto", 89.90, "un"),
        ("Montecristo No.4", 79.90, "un"),
        ("Romeo y Julieta", 69.90, "un"),
        ("Partagás", 74.90, "un"),
        ("Davidoff Especial", 99.90, "un"),
        ("H.Upmann", 64.90, "un"),
        ("Dunhill", 84.90, "un"),
        ("Cuaba", 59.90, "un"),
    ],
    "Acessórios": [
        ("Saca-rolhas Elétrico", 129.90, "un"),
        ("Umidor de Charuto", 349.90, "un"),
        ("Isqueiro para Charuto", 89.90, "un"),
        ("Cortador de Charuto", 59.90, "un"),
        ("Decantador de Cristal", 179.90, "un"),
        ("Taça de Vinho (Jogo 6un)", 149.90, "un"),
    ],
}

PREFIXOS_SKU = {
    "Vinhos Tintos": "VDT",
    "Vinhos Brancos": "VDB",
    "Vinhos Rosés": "VRO",
    "Espumantes": "ESP",
    "Whiskies e Destilados": "WHI",
    "Charutos": "CHA",
    "Acessórios": "ACE",
}

NOMES_CLIENTES = [
    "Ana Paula Ribeiro", "Bruno Costa Lima", "Carla Mendes Souza", "Diego Fernandes",
    "Elaine Cristina Alves", "Fábio Henrique Santos", "Gabriela Nunes", "Henrique Barbosa",
    "Isabela Martins", "João Vitor Pereira", "Karina Rocha", "Leandro Oliveira",
    "Mariana Castro", "Nelson Almeida", "Otávio Ramos", "Patrícia Gomes",
    "Rafael Teixeira", "Sandra Regina Dias",
]

NOMES_FORNECEDORES = [
    "Distribuidora Vinícola Sul Ltda",
    "Casa do Whisky Importados",
    "Charutaria Premium Comércio",
    "Adega Atacado Distribuidora",
    "Bebidas & Cia Distribuidora",
    "Vinhos do Mundo Importadora",
]


class Command(BaseCommand):
    help = "Limpa o banco (mantém usuários) e popula com dados de demonstração de uma adega de porte médio."

    def handle(self, *args, **options):
        random.seed(42)
        self.admin = User.objects.filter(is_superuser=True).order_by("pk").first()
        if self.admin is None:
            self.stderr.write("Nenhum superusuário encontrado — crie um antes de rodar este comando.")
            return

        self._limpar()
        categorias = self._criar_categorias()
        produtos = self._criar_produtos(categorias)
        fornecedores = self._criar_fornecedores()
        clientes = self._criar_clientes()
        self._criar_entradas_estoque(produtos, fornecedores)
        total_vendas, total_caixas = self._criar_historico_vendas_e_caixa(produtos, clientes)
        self._criar_contas(fornecedores, clientes)

        self.stdout.write(self.style.SUCCESS(
            "\nDados de demonstração gerados com sucesso:\n"
            f"  Categorias: {len(categorias)}\n"
            f"  Produtos: {len(produtos)}\n"
            f"  Fornecedores: {len(fornecedores)}\n"
            f"  Clientes: {len(clientes)}\n"
            f"  Caixas (histórico + 1 aberto hoje): {total_caixas}\n"
            f"  Vendas: {total_vendas}\n"
            f"  Contas a pagar: {ContaPagar.objects.count()}\n"
            f"  Contas a receber: {ContaReceber.objects.count()}\n"
        ))

    def _limpar(self):
        RegistroAuditoria.objects.all().delete()
        Notificacao.objects.all().delete()
        Caixa.objects.all().delete()
        ContaPagar.objects.all().delete()
        ContaReceber.objects.all().delete()
        Venda.objects.all().delete()
        EntradaEstoque.objects.all().delete()
        Produto.objects.all().delete()
        Categoria.objects.all().delete()
        Cliente.objects.all().delete()
        Fornecedor.objects.all().delete()

    def _criar_categorias(self):
        categorias = {}
        for nome in CATALOGO:
            categoria = Categoria.objects.create(nome=nome)
            auditoria.registrar(self.admin, RegistroAuditoria.Acao.CRIACAO, categoria)
            categorias[nome] = categoria
        return categorias

    def _criar_produtos(self, categorias):
        produtos = []
        contador = 1
        for nome_categoria, itens in CATALOGO.items():
            prefixo = PREFIXOS_SKU[nome_categoria]
            for indice, (nome, preco_venda, unidade) in enumerate(itens, start=1):
                preco_venda = Decimal(str(preco_venda))
                preco_custo = (preco_venda * Decimal("0.5")).quantize(Decimal("0.01"))
                estoque_minimo = random.randint(3, 8)
                # ~1 em cada 9 produtos nasce abaixo do mínimo, pra testar o alerta
                if contador % 9 == 0:
                    quantidade_estoque = max(0, estoque_minimo - random.randint(1, 3))
                else:
                    quantidade_estoque = estoque_minimo + random.randint(5, 35)
                produto = Produto.objects.create(
                    nome=nome,
                    sku=f"{prefixo}-{indice:03d}",
                    codigo_barras=f"789{contador:010d}",
                    categoria=categorias[nome_categoria],
                    preco_custo=preco_custo,
                    preco_venda=preco_venda,
                    quantidade_estoque=quantidade_estoque,
                    estoque_minimo=estoque_minimo,
                    unidade=unidade,
                    ativo=True,
                )
                auditoria.registrar(self.admin, RegistroAuditoria.Acao.CRIACAO, produto)
                produtos.append(produto)
                contador += 1
        return produtos

    def _criar_fornecedores(self):
        fornecedores = []
        for indice, nome in enumerate(NOMES_FORNECEDORES, start=1):
            fornecedor = Fornecedor.objects.create(
                nome=nome,
                documento=f"{indice:014d}",
                telefone=f"(11) 3{indice:03d}-{indice:04d}",
                email=f"contato{indice}@fornecedor-demo.com.br",
            )
            auditoria.registrar(self.admin, RegistroAuditoria.Acao.CRIACAO, fornecedor)
            fornecedores.append(fornecedor)
        return fornecedores

    def _criar_clientes(self):
        clientes = []
        for indice, nome in enumerate(NOMES_CLIENTES, start=1):
            cliente = Cliente.objects.create(
                nome=nome,
                documento=f"{10000000000 + indice}",
                telefone=f"(11) 9{indice:04d}-{indice:04d}",
                email=f"{nome.split()[0].lower()}{indice}@email-demo.com.br",
            )
            auditoria.registrar(self.admin, RegistroAuditoria.Acao.CRIACAO, cliente)
            clientes.append(cliente)
        return clientes

    def _criar_entradas_estoque(self, produtos, fornecedores):
        amostra = random.sample(produtos, k=25)
        agora = timezone.now()
        for produto in amostra:
            fornecedor = random.choice(fornecedores)
            dias_atras = random.randint(3, 60)
            quantidade = random.randint(6, 24)
            custo_unitario = produto.preco_custo
            entrada = produto.registrar_entrada(
                quantidade=quantidade,
                fornecedor=fornecedor,
                custo_unitario=custo_unitario,
                usuario=self.admin,
            )
            data = agora - timedelta(days=dias_atras)
            EntradaEstoque.objects.filter(pk=entrada.pk).update(criado_em=data)

    def _finalizar_venda_em(self, venda, data):
        Venda.objects.filter(pk=venda.pk).update(criado_em=data, finalizada_em=data)

    def _backdatar_criacao(self, venda, data):
        Venda.objects.filter(pk=venda.pk).update(criado_em=data)

    def _criar_historico_vendas_e_caixa(self, produtos, clientes):
        formas = [Venda.FormaPagamento.DINHEIRO, Venda.FormaPagamento.CARTAO, Venda.FormaPagamento.PIX]
        agora = timezone.now()
        total_vendas = 0
        total_caixas = 0
        comandas_deixadas_abertas = 0

        # controle próprio de estoque restante — os objetos de `produtos` não são
        # atualizados automaticamente pelas vendas finalizadas ao longo do loop
        estoque_restante = {produto.pk: produto.quantidade_estoque for produto in produtos}

        for dias_atras in range(20, -1, -1):
            data_base = agora - timedelta(days=dias_atras)
            eh_hoje = dias_atras == 0

            valor_abertura = Decimal(random.choice([100, 150, 200, 250]))
            caixa = Caixa.abrir(self.admin, valor_abertura)
            # horários em UTC — America/Sao_Paulo é UTC-3, então 12h/22h UTC
            # aparecem como 09h/19h na hora local exibida nas telas
            abertura_em = data_base.replace(hour=12, minute=0, second=0, microsecond=0)
            Caixa.objects.filter(pk=caixa.pk).update(aberto_em=abertura_em)
            caixa.refresh_from_db()
            total_caixas += 1

            numero_vendas = random.randint(6, 9) if eh_hoje else random.randint(2, 5)
            for indice_venda in range(numero_vendas):
                eh_comanda = (eh_hoje and indice_venda < 4) or random.random() < 0.4
                cliente = random.choice(clientes) if random.random() < 0.5 else None
                if eh_comanda:
                    mesa = random.randint(1, 12)
                    venda = Venda.objects.create(
                        criado_por=self.admin,
                        cliente=cliente,
                        identificador=f"Mesa {mesa}",
                        quantidade_pessoas=random.randint(2, 6),
                    )
                else:
                    venda = Venda.objects.create(criado_por=self.admin, cliente=cliente)

                for _ in range(random.randint(1, 4)):
                    produto = random.choice(produtos)
                    disponivel = estoque_restante[produto.pk]
                    if disponivel < 1:
                        continue
                    quantidade = min(disponivel, random.randint(1, 3))
                    try:
                        venda.adicionar_item(produto, quantidade)
                    except Exception:
                        continue
                    estoque_restante[produto.pk] -= quantidade

                if not venda.itens.exists():
                    venda.delete()
                    continue

                # deixa algumas comandas de hoje propositalmente em aberto
                if eh_hoje and eh_comanda and comandas_deixadas_abertas < 3:
                    comandas_deixadas_abertas += 1
                    total_vendas += 1
                    continue

                # pequena chance de virar venda cancelada
                if random.random() < 0.08:
                    for item in venda.itens.all():
                        estoque_restante[item.produto_id] += item.quantidade
                    venda.cancelar()
                    hora = abertura_em + timedelta(hours=random.randint(0, 9))
                    self._backdatar_criacao(venda, hora)
                    total_vendas += 1
                    continue

                try:
                    forma = random.choices(formas, weights=[50, 30, 20])[0]
                    venda.adicionar_pagamento(forma, venda.total)
                    venda.finalizar()
                except Exception:
                    for item in venda.itens.all():
                        estoque_restante[item.produto_id] += item.quantidade
                    venda.delete()
                    continue
                hora = abertura_em + timedelta(hours=random.uniform(0.5, 9.5))
                self._finalizar_venda_em(venda, hora)
                total_vendas += 1

            if random.random() < 0.3:
                saldo = caixa.saldo_esperado()
                if saldo > Decimal("50"):
                    caixa.registrar_sangria(self.admin, (saldo * Decimal("0.3")).quantize(Decimal("0.01")), "Reforço de segurança / depósito")
            if random.random() < 0.15:
                caixa.registrar_reforco(self.admin, Decimal(random.choice([50, 100])), "Troco adicional")

            if not eh_hoje:
                saldo_esperado = caixa.saldo_esperado()
                diferenca = Decimal(random.choice([0, 0, 0, -5, 5, -10, 3])).quantize(Decimal("0.01"))
                valor_contado = saldo_esperado + diferenca
                if valor_contado < 0:
                    valor_contado = saldo_esperado
                caixa.fechar(self.admin, valor_contado)
                fechamento_em = abertura_em.replace(hour=22, minute=0)
                Caixa.objects.filter(pk=caixa.pk).update(fechado_em=fechamento_em)

        return total_vendas, total_caixas

    def _criar_contas(self, fornecedores, clientes):
        hoje = timezone.now().date()
        descricoes_pagar = [
            "Compra de mercadoria", "Manutenção do estabelecimento", "Aluguel do ponto comercial",
            "Serviço de contabilidade", "Compra de embalagens", "Frete de fornecedor",
            "Material de limpeza", "Conta de energia elétrica", "Conta de internet",
            "Manutenção de refrigeração", "Compra de mercadoria", "Serviço de marketing",
        ]
        for indice, descricao in enumerate(descricoes_pagar):
            vencimento = hoje + timedelta(days=random.randint(-20, 25))
            pago = vencimento < hoje and random.random() < 0.6
            conta = ContaPagar.objects.create(
                fornecedor=random.choice(fornecedores),
                descricao=descricao,
                valor=Decimal(random.randint(80, 3500)),
                vencimento=vencimento,
                pago=pago,
                pago_em=vencimento if pago else None,
            )
            auditoria.registrar(self.admin, RegistroAuditoria.Acao.CRIACAO, conta)

        descricoes_receber = [
            "Venda fiado", "Venda para evento", "Fechamento de comanda de festa",
            "Venda parcelada", "Encomenda especial", "Venda fiado", "Venda corporativa",
            "Encomenda de aniversário", "Venda fiado", "Venda para evento",
        ]
        for descricao in descricoes_receber:
            vencimento = hoje + timedelta(days=random.randint(-15, 20))
            recebido = vencimento < hoje and random.random() < 0.6
            conta = ContaReceber.objects.create(
                cliente=random.choice(clientes),
                descricao=descricao,
                valor=Decimal(random.randint(60, 1200)),
                vencimento=vencimento,
                recebido=recebido,
                recebido_em=vencimento if recebido else None,
            )
            auditoria.registrar(self.admin, RegistroAuditoria.Acao.CRIACAO, conta)
