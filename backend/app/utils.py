import calendar
from datetime import datetime


def add_one_month(dt: datetime) -> datetime:
    """Suma un mes calendario a una fecha, respetando meses de distinta duración
    (ej: 31 de enero + 1 mes = 28/29 de febrero, no un 31 de febrero inexistente)."""
    year = dt.year + (dt.month // 12)
    month = dt.month % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)
