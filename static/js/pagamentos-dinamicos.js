function centavosDoCampo(campo) {
    if (!campo) return 0;
    const maxDigitos = parseInt(campo.dataset.maxDigitos || "10", 10);
    return paraCentavos(campo.value, maxDigitos);
}

function atualizarLinha(linha) {
    const forma = linha.querySelector('select[name="forma_pagamento"]');
    const campoRecebido = linha.querySelector(".campo-recebido");
    const trocoSpan = linha.querySelector(".troco-linha");
    if (!forma || !campoRecebido || !trocoSpan) return;

    const ehDinheiro = forma.value === "dinheiro";
    campoRecebido.style.display = ehDinheiro ? "" : "none";
    if (!ehDinheiro || !campoRecebido.value) {
        if (!ehDinheiro) campoRecebido.value = "";
        trocoSpan.textContent = "";
        trocoSpan.classList.remove("texto-perigo");
        return;
    }

    const valorCentavos = centavosDoCampo(linha.querySelector('input[name="valor"]'));
    const recebidoCentavos = centavosDoCampo(campoRecebido);
    const trocoCentavos = recebidoCentavos - valorCentavos;
    trocoSpan.textContent = trocoCentavos >= 0
        ? `Troco: ${formatarCentavos(trocoCentavos)}`
        : "Valor recebido insuficiente";
    trocoSpan.classList.toggle("texto-perigo", trocoCentavos < 0);
}

function inicializarLinhasPagamento(escopo) {
    (escopo || document).querySelectorAll(".linha-pagamento").forEach(atualizarLinha);
}

function atualizarResumoPagamento(form) {
    const resumo = form.querySelector("#resumo-pagamento");
    if (!resumo) return;
    const totalCentavos = Math.round(parseFloat(form.dataset.total || "0") * 100);
    let somaCentavos = 0;
    form.querySelectorAll('#linhas-pagamento input[name="valor"]').forEach((campo) => {
        somaCentavos += centavosDoCampo(campo);
    });
    resumo.textContent = `Soma informada: ${formatarCentavos(somaCentavos)} / Total: ${formatarCentavos(totalCentavos)}`;
    resumo.classList.toggle("texto-perigo", somaCentavos !== totalCentavos);
}

document.addEventListener("DOMContentLoaded", () => inicializarLinhasPagamento());
document.body.addEventListener("htmx:afterSwap", (evento) => inicializarLinhasPagamento(evento.target));

document.body.addEventListener("click", (evento) => {
    if (evento.target.id === "botao-adicionar-pagamento") {
        const form = evento.target.closest("form");
        const modelo = form.querySelector("#modelo-linha-pagamento");
        const container = form.querySelector("#linhas-pagamento");
        if (!modelo || !container) return;
        container.appendChild(modelo.content.cloneNode(true));
        const linhaAdicionada = container.lastElementChild;
        inicializarMascarasMonetarias(linhaAdicionada);
        atualizarLinha(linhaAdicionada);
    } else if (evento.target.classList.contains("botao-remover-linha")) {
        const linha = evento.target.closest(".linha-pagamento");
        const form = linha.closest("form");
        linha.remove();
        if (form) atualizarResumoPagamento(form);
    }
});

document.body.addEventListener("change", (evento) => {
    if (evento.target.matches('#linhas-pagamento select[name="forma_pagamento"]')) {
        atualizarLinha(evento.target.closest(".linha-pagamento"));
    }
});

document.body.addEventListener("input", (evento) => {
    if (evento.target.matches("#linhas-pagamento .campo-monetario")) {
        const linha = evento.target.closest(".linha-pagamento");
        const form = evento.target.closest("form");
        atualizarLinha(linha);
        if (form) atualizarResumoPagamento(form);
    }
});
