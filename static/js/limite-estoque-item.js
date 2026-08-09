function atualizarLimiteQuantidade() {
    const campoBusca = document.getElementById("id_produto_busca");
    const campoQuantidade = document.getElementById("id_quantidade");
    if (!campoBusca || !campoQuantidade) return;

    const datalist = document.getElementById(campoBusca.getAttribute("list"));
    const opcao = datalist && Array.from(datalist.options).find((op) => op.value === campoBusca.value);

    if (!opcao) {
        campoQuantidade.removeAttribute("max");
        return;
    }
    const estoque = parseInt(opcao.dataset.estoque, 10);
    campoQuantidade.max = estoque;
    if (parseInt(campoQuantidade.value, 10) > estoque) {
        campoQuantidade.value = estoque;
    }
}

document.body.addEventListener("input", (evento) => {
    if (evento.target.id === "id_produto_busca") atualizarLimiteQuantidade();
});
