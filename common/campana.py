"""Datos de la campaña. Demo con cifras ficticias."""
from datetime import date

NEGOCIO = "Vivero Ryokuen"
OFERTA = "Pack Verde de Diciembre"
DESCRIPCION = "2 plantas de interior de bajo mantenimiento, macetas y guía de cuidados impresa."
PRECIO_ANCLA = 16000
PRECIO_OFERTA = 9900
MONEDA = "₡"
CUPOS_POR_DIA = 8
FECHA_INICIO = date(2026, 11, 19)
FECHA_LIMITE = date(2026, 12, 20)
# 0 = lunes ... 5 = sábado. Retiro en el vivero, sin envíos.
DIAS_RETIRO = (0, 1, 2, 3, 4, 5)
ESPACIOS = {
    "poca_luz": "Poca luz",
    "luz_media": "Luz media",
    "sol_directo": "Sol directo",
}
DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
            "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def fecha_larga(d: date) -> str:
    return f"{DIAS_ES[d.weekday()]} {d.day} de {MESES_ES[d.month - 1]}"


def colones(n: int) -> str:
    return f"{MONEDA}{n:,}".replace(",", ".")
