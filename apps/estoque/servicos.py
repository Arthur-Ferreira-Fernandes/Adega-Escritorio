from datetime import timedelta

from django.core.cache import cache
from django.db.models import Sum
from django.utils import timezone

from .models import Produto

# A busca e os "mais vendidos" aparecem a cada item lançado na venda: ficam
# guardados em memória e são refeitos quando produtos ou estoque mudam
# (limpar_cache_produtos, ligado em apps.py) ou, no máximo, a cada 10 minutos.
CHAVE_BUSCA = "estoque:busca"
CHAVE_MAIS_VENDIDOS = "estoque:mais_vendidos"
VALIDADE_CACHE = 10 * 60


def limpar_cache_produtos(**kwargs):
    cache.delete_many([CHAVE_BUSCA, CHAVE_MAIS_VENDIDOS])


def dados_para_busca():
    """Produtos ativos no formato da lista de busca (static/js/busca-produto.js)."""
    dados = cache.get(CHAVE_BUSCA)
    if dados is None:
        dados = _montar_busca()
        cache.set(CHAVE_BUSCA, dados, VALIDADE_CACHE)
    return dados


def _montar_busca():
    return [
        {
            "sku": produto.sku,
            "nome": produto.nome,
            "categoria": produto.categoria.nome,
            "codigo": produto.codigo_barras or "",
            "preco": str(produto.preco_venda),
            "estoque": produto.quantidade_estoque,
            "minimo": produto.estoque_minimo,
        }
        for produto in Produto.objects.filter(ativo=True)
        .select_related("categoria")
        .order_by("categoria__nome", "nome")
    ]


def mais_vendidos(dias=30, limite=12):
    """Produtos ativos mais vendidos em quantidade: os botões rápidos da venda."""
    produtos = cache.get(CHAVE_MAIS_VENDIDOS)
    if produtos is None:
        produtos = [
            {"sku": p.sku, "nome": p.nome, "preco_venda": p.preco_venda}
            for p in _calcular_mais_vendidos(dias, limite)
        ]
        cache.set(CHAVE_MAIS_VENDIDOS, produtos, VALIDADE_CACHE)
    return produtos


def _calcular_mais_vendidos(dias, limite):
    from apps.vendas.models import ItemVenda, Venda

    desde = timezone.now() - timedelta(days=dias)
    ids = list(
        ItemVenda.objects.filter(
            venda__status=Venda.Status.CONCLUIDA,
            venda__finalizada_em__gte=desde,
            produto__ativo=True,
        )
        .values("produto_id")
        .annotate(q=Sum("quantidade"))
        .order_by("-q", "produto_id")
        .values_list("produto_id", flat=True)[:limite]
    )
    produtos = Produto.objects.in_bulk(ids)
    return [produtos[pk] for pk in ids]


def gerar_sku(base):
    """SKU livre a partir de um texto (ex.: o código de barras no cadastro rápido)."""
    base = base[:44] or "PRD"
    sku, n = base, 2
    while Produto.objects.filter(sku=sku).exists():
        sku, n = f"{base}-{n}", n + 1
    return sku
