// Atalhos de teclado. Qualquer elemento com data-atalho="F6" (ou "Ctrl+P")
// responde à tecla: botões e links são clicados; campos — ou o <label> de um
// campo — recebem o foco. Como a busca é feita a cada tecla, funciona também
// no conteúdo trocado pelo HTMX. A lista completa fica na janela do F1.
(function () {
    function nomeDaTecla(evento) {
        var tecla = evento.key.length === 1 ? evento.key.toUpperCase() : evento.key;
        if (tecla === "Delete") tecla = "Del";
        if (tecla === "Escape") tecla = "Esc";
        var partes = [];
        if (evento.ctrlKey || evento.metaKey) partes.push("Ctrl");
        if (evento.altKey) partes.push("Alt");
        if (evento.shiftKey && tecla.length > 1) partes.push("Shift");
        partes.push(tecla);
        return partes.join("+");
    }

    function visivel(elemento) {
        return elemento.getClientRects().length > 0;
    }

    function encontrar(nome) {
        var candidatos = Array.prototype.filter.call(
            document.querySelectorAll("[data-atalho]"),
            function (elemento) {
                return elemento.dataset.atalho === nome && !elemento.disabled;
            }
        );
        // O da página tem prioridade sobre o do menu lateral (que pode estar recolhido).
        return candidatos.filter(visivel)[0] || candidatos[0];
    }

    function acionar(elemento) {
        var campo = elemento.tagName === "LABEL" ? elemento.control : elemento;
        if (campo && /^(INPUT|SELECT|TEXTAREA)$/.test(campo.tagName)) {
            campo.focus();
            if (campo.select) campo.select();
        } else {
            elemento.click();
        }
    }

    document.addEventListener("keydown", function (evento) {
        if (evento.repeat || evento.isComposing) return;
        // Com uma janela aberta (ajuda, confirmação), só ela responde ao teclado.
        if (document.querySelector("dialog[open]")) return;
        var alvo = encontrar(nomeDaTecla(evento));
        if (!alvo) return;
        evento.preventDefault();
        acionar(alvo);
    });

    document.addEventListener("click", function (evento) {
        var botao = evento.target.closest("[data-abrir-dialogo]");
        if (!botao) return;
        var dialogo = document.getElementById(botao.dataset.abrirDialogo);
        if (dialogo) dialogo.showModal();
    });
})();
