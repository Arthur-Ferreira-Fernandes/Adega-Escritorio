import json
import logging

_CAMPOS_PADRAO = set(logging.makeLogRecord({}).__dict__.keys())


class FormatadorJSON(logging.Formatter):
    def format(self, record):
        dados = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "nivel": record.levelname,
            "logger": record.name,
            "mensagem": record.getMessage(),
        }
        for chave, valor in record.__dict__.items():
            if chave not in _CAMPOS_PADRAO and chave not in dados:
                dados[chave] = valor
        if record.exc_info:
            dados["excecao"] = self.formatException(record.exc_info)
        return json.dumps(dados, default=str, ensure_ascii=False)
