window.addEventListener("beforeunload", function (evento) {
    if (document.getElementById("aviso-venda-pendente")) {
        evento.preventDefault();
        evento.returnValue = "";
    }
});

window.addEventListener("pagehide", function () {
    var aviso = document.getElementById("aviso-venda-pendente");
    if (!aviso) return;
    var url = aviso.dataset.cancelarUrl;
    var token = document.querySelector("[name=csrfmiddlewaretoken]");
    if (!url || !token) return;
    var dados = new Blob(
        ["csrfmiddlewaretoken=" + encodeURIComponent(token.value)],
        { type: "application/x-www-form-urlencoded" }
    );
    navigator.sendBeacon(url, dados);
});
