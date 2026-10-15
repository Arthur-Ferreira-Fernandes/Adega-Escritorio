// As cores vêm das variáveis do CSS, então seguem o tema claro/escuro.
function coresGrafico() {
    const css = getComputedStyle(document.documentElement);
    const cor = (nome) => css.getPropertyValue(nome).trim();
    return {
        serie: cor("--cor-dourado"),
        serieArea: "rgba(201, 162, 39, 0.12)",
        grade: cor("--cor-borda"),
        textoPrimario: cor("--cor-texto"),
        textoSecundario: cor("--cor-texto-suave"),
        superficie: cor("--cor-superficie"),
    };
}

function inicializarGraficos(escopo) {
    (escopo || document).querySelectorAll(".grafico").forEach((canvas) => {
        if (canvas.dataset.graficoInicializado) return;
        canvas.dataset.graficoInicializado = "true";

        const fonte = document.getElementById(canvas.dataset.fonte);
        if (!fonte) return;
        const dados = JSON.parse(fonte.textContent);
        const cores = coresGrafico();

        const opcoesBase = {
            responsive: true,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: cores.superficie,
                    titleColor: cores.textoPrimario,
                    bodyColor: cores.textoPrimario,
                    borderColor: cores.grade,
                    borderWidth: 1,
                },
            },
            scales: {
                x: {
                    grid: { color: cores.grade },
                    ticks: { color: cores.textoSecundario },
                },
                y: {
                    grid: { color: cores.grade },
                    ticks: { color: cores.textoSecundario },
                    beginAtZero: true,
                },
            },
        };

        if (canvas.dataset.tipo === "line") {
            new Chart(canvas, {
                type: "line",
                data: {
                    labels: dados.map((d) => d.rotulo),
                    datasets: [
                        {
                            data: dados.map((d) => d.valor),
                            borderColor: cores.serie,
                            backgroundColor: cores.serieArea,
                            borderWidth: 2,
                            pointRadius: 4,
                            pointBackgroundColor: cores.serie,
                            fill: true,
                            tension: 0.2,
                        },
                    ],
                },
                options: {
                    ...opcoesBase,
                    plugins: {
                        ...opcoesBase.plugins,
                        tooltip: { ...opcoesBase.plugins.tooltip, mode: "index", intersect: false },
                    },
                },
            });
        } else {
            new Chart(canvas, {
                type: "bar",
                data: {
                    labels: dados.map((d) => d.rotulo),
                    datasets: [
                        {
                            data: dados.map((d) => d.valor),
                            backgroundColor: cores.serie,
                            borderRadius: 4,
                            maxBarThickness: 24,
                        },
                    ],
                },
                options: opcoesBase,
            });
        }
    });
}

document.addEventListener("DOMContentLoaded", () => inicializarGraficos());
document.body.addEventListener("htmx:afterSwap", (evento) => inicializarGraficos(evento.target));
document.addEventListener("tema:alterado", () => {
    document.querySelectorAll(".grafico").forEach((canvas) => {
        const grafico = Chart.getChart(canvas);
        if (grafico) grafico.destroy();
        delete canvas.dataset.graficoInicializado;
    });
    inicializarGraficos();
});
