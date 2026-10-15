// Alterna entre o tema escuro (padrão) e o claro. A escolha fica salva neste
// aparelho; o script inline no <head> de base.html aplica antes de desenhar a
// página, pra não piscar o tema errado.
document.addEventListener("click", (evento) => {
    const botao = evento.target.closest(".botao-tema");
    if (!botao) return;

    const raiz = document.documentElement;
    const claro = raiz.dataset.tema !== "claro";
    if (claro) {
        raiz.dataset.tema = "claro";
    } else {
        delete raiz.dataset.tema;
    }
    try {
        localStorage.setItem("adega-tema", claro ? "claro" : "escuro");
    } catch (erro) {
        // sem armazenamento (modo privado): o tema vale só até recarregar
    }
    document.dispatchEvent(new CustomEvent("tema:alterado"));
});
