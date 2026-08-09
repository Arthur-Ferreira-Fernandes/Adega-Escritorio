function paraCentavos(valorTexto, maxDigitos) {
    const digitos = (valorTexto || "").replace(/\D/g, "").slice(-(maxDigitos || 10));
    return digitos ? parseInt(digitos, 10) : 0;
}

function formatarCentavos(centavos) {
    const valor = (centavos / 100).toFixed(2);
    const [inteiro, decimal] = valor.split(".");
    const inteiroComPontos = inteiro.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return `R$ ${inteiroComPontos},${decimal}`;
}

function aplicarMascara(input) {
    const maxDigitos = parseInt(input.dataset.maxDigitos || "10", 10);
    const numero = parseFloat((input.value || "").replace(",", "."));
    const centavosIniciais = isNaN(numero) ? 0 : Math.round(numero * 100);
    input.value = centavosIniciais ? formatarCentavos(centavosIniciais) : "";

    input.addEventListener("input", () => {
        input.value = formatarCentavos(paraCentavos(input.value, maxDigitos));
        input.setSelectionRange(input.value.length, input.value.length);
    });
}

function inicializarMascarasMonetarias(escopo) {
    (escopo || document).querySelectorAll(".campo-monetario").forEach((el) => {
        if (!el.dataset.mascaraAplicada) {
            el.dataset.mascaraAplicada = "true";
            aplicarMascara(el);
        }
    });
}

document.addEventListener("DOMContentLoaded", () => inicializarMascarasMonetarias());
document.body.addEventListener("htmx:afterSwap", (evento) => inicializarMascarasMonetarias(evento.target));

// Reescreve pro formato decimal puro (ex: "1500.00") ANTES do htmx ler os
// valores do form pra montar a requisição -- capture:true no document roda
// antes do listener de submit que o htmx anexa direto no <form> (bubble phase).
document.addEventListener("submit", (evento) => {
    const form = evento.target;
    if (!(form instanceof HTMLFormElement)) return;
    form.querySelectorAll(".campo-monetario").forEach((campo) => {
        if (!campo.value.trim()) return;
        const maxDigitos = parseInt(campo.dataset.maxDigitos || "10", 10);
        campo.value = (paraCentavos(campo.value, maxDigitos) / 100).toFixed(2);
    });
}, true);
