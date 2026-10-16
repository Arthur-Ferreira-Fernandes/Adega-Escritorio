// Cartão e Pix não dão troco: se o valor digitado passa do que falta, esses
// botões ficam desativados (Dinheiro continua, e calcula o troco).
function verificarLimitePagamento(form) {
    const campoValor = form.querySelector('input[name="valor"]');
    const aviso = form.querySelector("#aviso-valor-pagamento");
    if (!campoValor || !aviso || form.hasAttribute("data-sem-itens")) return;

    const faltaCentavos = Math.round(parseFloat(form.dataset.falta || "0") * 100);
    const valorCentavos = paraCentavos(campoValor.value, parseInt(campoValor.dataset.maxDigitos || "10", 10));
    const excede = valorCentavos > faltaCentavos;

    if (excede) {
        aviso.textContent = `Cartão e Pix não permitem troco — o valor passa do restante (${formatarCentavos(faltaCentavos)}). Use Dinheiro.`;
        aviso.style.display = "";
    } else {
        aviso.textContent = "";
        aviso.style.display = "none";
    }
    form.querySelectorAll("[data-sem-troco]").forEach((botao) => {
        // data-indisponivel: bloqueado pelo servidor (ex.: fiado sem cliente).
        botao.disabled = excede || botao.hasAttribute("data-indisponivel");
    });
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
