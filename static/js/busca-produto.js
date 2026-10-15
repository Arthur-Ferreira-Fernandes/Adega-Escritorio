// Busca de produto por nome na venda: ao entrar no campo a lista inteira
// aparece, e vai sendo filtrada enquanto digita; agrupada por categoria, com
// preço e estoque (que pode estar zerado ou negativo: a venda não é barrada). ↑/↓ escolhem, Enter confirma
// (e leva para a quantidade), Esc fecha. O formulário envia só o SKU, num
// campo oculto. Os produtos vêm do <script id="produtos-dados"> da página.
(function () {
    var LIMITE = 300;
    var real = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
    var cache = { elemento: null, produtos: [] };
    var estado = { resultados: [], ativo: -1 };

    function semAcento(texto) {
        return texto.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
    }

    function escapar(texto) {
        var div = document.createElement("div");
        div.textContent = texto;
        return div.innerHTML;
    }

    function produtos() {
        var elemento = document.getElementById("produtos-dados");
        if (!elemento) return [];
        if (cache.elemento !== elemento) {  // o HTMX trocou o conteúdo da venda
            cache.elemento = elemento;
            cache.produtos = JSON.parse(elemento.textContent).map(function (produto) {
                produto.busca = semAcento([produto.nome, produto.categoria, produto.sku, produto.codigo].join(" "));
                produto.nomeBusca = semAcento(produto.nome);
                return produto;
            });
        }
        return cache.produtos;
    }

    function partes() {
        var campo = document.getElementById("busca-produto");
        if (!campo) return null;
        return {
            campo: campo,
            lista: document.getElementById("busca-produto-lista"),
            sku: document.getElementById("id_produto_busca"),
            quantidade: document.getElementById("id_quantidade"),
        };
    }

    // Quem começa com o que foi digitado aparece primeiro; depois, em ordem alfabética.
    function filtrar(texto, mostrarTodos) {
        var termos = semAcento(texto).split(/\s+/).filter(Boolean);
        if (!termos.length && !mostrarTodos) return [];
        var achados = produtos().filter(function (produto) {
            return termos.every(function (termo) { return produto.busca.indexOf(termo) !== -1; });
        });
        function peso(produto) {
            if (!termos.length) return 0;
            if (produto.nomeBusca.indexOf(termos[0]) === 0) return 0;
            if (produto.nomeBusca.indexOf(" " + termos[0]) !== -1) return 1;
            return 2;
        }
        achados.sort(function (a, b) {
            // Lista inteira (nada digitado): categorias em ordem alfabética.
            var categoria = termos.length ? 0 : a.categoria.localeCompare(b.categoria, "pt-BR");
            return categoria || peso(a) - peso(b) || a.nome.localeCompare(b.nome, "pt-BR");
        });
        // Agrupa por categoria mantendo a ordem de relevância das categorias.
        var grupos = [];
        var porCategoria = {};
        achados.forEach(function (produto) {
            if (!porCategoria[produto.categoria]) {
                porCategoria[produto.categoria] = [];
                grupos.push(porCategoria[produto.categoria]);
            }
            porCategoria[produto.categoria].push(produto);
        });
        var ordenados = [].concat.apply([], grupos);
        ordenados.total = achados.length;
        return ordenados;
    }

    function destacar(nome, texto) {
        var termos = semAcento(texto).split(/\s+/).filter(Boolean);
        var letras = Array.from(nome);
        var base = letras.map(semAcento);
        // Só destaca quando cada letra vira uma letra sem acento (o normal em português).
        if (!termos.length || base.some(function (letra) { return letra.length !== 1; })) {
            return escapar(nome);
        }
        var plano = base.join("");
        var marcado = letras.map(function () { return false; });
        termos.forEach(function (termo) {
            var posicao = plano.indexOf(termo);
            while (posicao !== -1) {
                for (var i = posicao; i < posicao + termo.length; i++) marcado[i] = true;
                posicao = plano.indexOf(termo, posicao + termo.length);
            }
        });
        var html = "";
        var aberto = false;
        letras.forEach(function (letra, i) {
            if (marcado[i] && !aberto) { html += "<mark>"; aberto = true; }
            if (!marcado[i] && aberto) { html += "</mark>"; aberto = false; }
            html += escapar(letra);
        });
        return aberto ? html + "</mark>" : html;
    }

    function selo(produto) {
        if (produto.estoque <= 0) {
            var texto = produto.estoque < 0 ? produto.estoque + " em estoque" : "Sem estoque";
            return '<span class="busca-produto__estoque busca-produto__estoque--esgotado">' + texto + "</span>";
        }
        var classe = produto.estoque <= produto.minimo ? " busca-produto__estoque--baixo" : "";
        return '<span class="busca-produto__estoque' + classe + '">' + produto.estoque + " em estoque</span>";
    }

    function desenhar(p, texto, mostrarTodos) {
        var resultados = filtrar(texto, mostrarTodos);
        estado.resultados = resultados.slice(0, LIMITE);
        estado.ativo = estado.resultados.length ? 0 : -1;

        if (!estado.resultados.length && !texto.trim()) {
            fechar(p);
            return;
        }
        var html = "";
        var categoria = null;
        estado.resultados.forEach(function (produto, indice) {
            if (produto.categoria !== categoria) {
                categoria = produto.categoria;
                html += '<div class="busca-produto__grupo" role="presentation">' + escapar(categoria) + "</div>";
            }
            html += '<div class="busca-produto__item" role="option" id="busca-produto-op-' + indice +
                '" data-indice="' + indice + '">' +
                '<span class="busca-produto__nome">' + destacar(produto.nome, texto) + "</span>" +
                selo(produto) +
                '<span class="busca-produto__preco">' + real.format(Number(produto.preco)) + "</span>" +
                "</div>";
        });
        if (!estado.resultados.length) {
            html = '<div class="busca-produto__aviso">Nenhum produto encontrado para “' + escapar(texto.trim()) + "”.</div>";
        } else if (resultados.total > LIMITE) {
            html += '<div class="busca-produto__aviso">Mostrando ' + LIMITE + " de " + resultados.total +
                " — continue digitando para refinar.</div>";
        }
        p.lista.innerHTML = html;
        p.lista.hidden = false;
        p.campo.setAttribute("aria-expanded", "true");
        marcar(p);
    }

    function marcar(p) {
        var anterior = p.lista.querySelector(".busca-produto__item--ativo");
        if (anterior) anterior.classList.remove("busca-produto__item--ativo");
        var atual = document.getElementById("busca-produto-op-" + estado.ativo);
        if (atual) {
            atual.classList.add("busca-produto__item--ativo");
            atual.scrollIntoView({ block: "nearest" });
            p.campo.setAttribute("aria-activedescendant", atual.id);
        } else {
            p.campo.removeAttribute("aria-activedescendant");
        }
    }

    function mover(p, passo) {
        var total = estado.resultados.length;
        estado.ativo = (estado.ativo + passo + total) % total;
        marcar(p);
    }

    function fechar(p) {
        p.lista.hidden = true;
        p.campo.setAttribute("aria-expanded", "false");
        p.campo.removeAttribute("aria-activedescendant");
    }

    function escolher(p, produto) {
        if (!produto) return;
        p.campo.value = produto.nome;
        p.sku.value = produto.sku;
        fechar(p);
        p.quantidade.focus();
        p.quantidade.select();
    }

    function aberta(p) {
        return !p.lista.hidden;
    }

    document.addEventListener("input", function (evento) {
        if (evento.target.id !== "busca-produto") return;
        var p = partes();
        p.sku.value = "";  // mudou o texto: o produto escolhido deixa de valer
        desenhar(p, p.campo.value, true);
    });

    document.addEventListener("keydown", function (evento) {
        if (evento.target.id !== "busca-produto") return;
        var p = partes();
        if (evento.key === "ArrowDown" || evento.key === "ArrowUp") {
            evento.preventDefault();
            if (!aberta(p)) {
                desenhar(p, p.campo.value, true);  // com o campo vazio, mostra tudo
            } else if (estado.resultados.length) {
                mover(p, evento.key === "ArrowDown" ? 1 : -1);
            }
        } else if (evento.key === "Enter") {
            if (aberta(p)) {
                evento.preventDefault();
                escolher(p, estado.resultados[estado.ativo]);
            } else if (!p.sku.value) {
                evento.preventDefault();
                desenhar(p, p.campo.value, true);
            }
        } else if (evento.key === "Escape" && aberta(p)) {
            evento.preventDefault();
            evento.stopPropagation();
            fechar(p);
        } else if (evento.key === "Tab" && aberta(p) && estado.ativo !== -1) {
            evento.preventDefault();
            escolher(p, estado.resultados[estado.ativo]);
        }
    });

    // mousedown, e não click: assim o campo não perde o foco antes da escolha.
    document.addEventListener("mousedown", function (evento) {
        var item = evento.target.closest(".busca-produto__item");
        if (!item) return;
        evento.preventDefault();
        var p = partes();
        escolher(p, estado.resultados[Number(item.dataset.indice)]);
    });

    document.addEventListener("mousemove", function (evento) {
        var item = evento.target.closest(".busca-produto__item");
        if (!item || Number(item.dataset.indice) === estado.ativo) return;
        estado.ativo = Number(item.dataset.indice);
        var p = partes();
        var anterior = p.lista.querySelector(".busca-produto__item--ativo");
        if (anterior) anterior.classList.remove("busca-produto__item--ativo");
        item.classList.add("busca-produto__item--ativo");
    });

    // Ao entrar no campo (clique, Tab ou F4) a lista já abre. Com um produto já
    // escolhido, mostra todos de novo e seleciona o texto para trocar digitando.
    function abrirAoEntrar(evento) {
        if (evento.target.id !== "busca-produto") return;
        var p = partes();
        if (aberta(p)) return;
        desenhar(p, p.sku.value ? "" : p.campo.value, true);
        if (p.sku.value) p.campo.select();
    }
    document.addEventListener("focusin", abrirAoEntrar);
    document.addEventListener("click", abrirAoEntrar);  // reabre depois do Esc

    document.addEventListener("focusout", function (evento) {
        if (evento.target.id === "busca-produto") fechar(partes());
    });

    // Enviar sem escolher um produto da lista só daria erro: reabre as sugestões.
    // Fase de captura para chegar antes do HTMX, que escuta no próprio formulário.
    document.addEventListener("submit", function (evento) {
        var p = partes();
        if (!p || evento.target !== p.campo.form || p.sku.value) return;
        evento.preventDefault();
        evento.stopPropagation();
        p.campo.focus();
        desenhar(p, p.campo.value, true);
    }, true);
})();
