window.addEventListener("beforeunload", function (evento) {
    if (document.getElementById("aviso-venda-pendente")) {
        evento.preventDefault();
        evento.returnValue = "";
    }
});
