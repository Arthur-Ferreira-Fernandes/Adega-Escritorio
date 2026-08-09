function verificarLimitePagamento(form) {
    const select = form.querySelector('select[name="forma_pagamento"]');
    const campoValor = form.querySelector('input[name="valor"]');
    const aviso = form.querySelector("#aviso-valor-pagamento");
    const botao = form.querySelector("#botao-confirmar-pagamento");
    if (!select || !campoValor || !aviso || !botao) return;

    const ehDinheiro = select.value === "dinheiro";
    const faltaCentavos = Math.round(parseFloat(form.dataset.falta || "0") * 100);
    const valorCentavos = paraCentavos(campoValor.value, parseInt(campoValor.dataset.maxDigitos || "10", 10));

    const excede = !ehDinheiro && valorCentavos > faltaCentavos;
    if (excede) {
        const forma = select.options[select.selectedIndex].text;
        aviso.textContent = `${forma} não permite troco — o valor não pode ultrapassar o restante (${formatarCentavos(faltaCentavos)}).`;
        aviso.style.display = "";
    } else {
        aviso.textContent = "";
        aviso.style.display = "none";
    }
    botao.disabled = excede;
}

function inicializarLimitesPagamento(escopo) {
    (escopo || document).querySelectorAll("form[data-falta]").forEach(verificarLimitePagamento);
}

document.addEventListener("DOMContentLoaded", () => inicializarLimitesPagamento());
document.body.addEventListener("htmx:afterSwap", (evento) => inicializarLimitesPagamento(evento.target));

document.body.addEventListener("input", (evento) => {
    const form = evento.target.closest("form[data-falta]");
    if (form) verificarLimitePagamento(form);
});
document.body.addEventListener("change", (evento) => {
    const form = evento.target.closest("form[data-falta]");
    if (form) verificarLimitePagamento(form);
});

document.body.addEventListener("click", (evento) => {
    if (evento.target.id !== "botao-usar-valor-total") return;
    const form = evento.target.closest("form[data-falta]");
    const campoValor = form && form.querySelector('input[name="valor"]');
    if (!campoValor) return;
    campoValor.value = form.dataset.falta;
    campoValor.dispatchEvent(new Event("input", { bubbles: true }));
});
