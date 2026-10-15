from decimal import Decimal

from django.db.models import DecimalField, Sum


class Soma(Sum):
    """Sum que devolve decimais com as casas do campo (R$ 1.978,20, não 1.978,20000).

    O Postgres já devolve assim; o SQLite (versão desktop) não arredonda o
    resultado de agregações, então o total sai com casas a mais ou a menos.
    """

    def get_db_converters(self, connection):
        converters = super().get_db_converters(connection)
        if isinstance(self.output_field, DecimalField):
            converters.append(self._quantizar)
        return converters

    def _quantizar(self, valor, expression, connection):
        if valor is None:
            return valor
        return Decimal(valor).quantize(Decimal(1).scaleb(-self.output_field.decimal_places))
