"""Catálogo cerrado de monedas (ISO 4217) que una marca puede usar.

La marca elige un subconjunto en Configuración (la primera es la principal) y cada ruta usa una de ellas.
No hay moneda por defecto en el código: una marca sin monedas configuradas debe configurarlas antes de crear rutas.
"""
from dataclasses import asdict, dataclass
from typing import Optional


@dataclass(frozen=True)
class Currency:
    code: str
    name: str
    symbol: str
    decimals: int


_ALL = (
    Currency("COP", "Peso colombiano", "$", 0),
    Currency("USD", "Dólar estadounidense", "US$", 2),
    Currency("EUR", "Euro", "€", 2),
    Currency("MXN", "Peso mexicano", "MX$", 2),
    Currency("PEN", "Sol peruano", "S/", 2),
    Currency("ARS", "Peso argentino", "AR$", 2),
    Currency("CLP", "Peso chileno", "CLP$", 0),
    Currency("BRL", "Real brasileño", "R$", 2),
    Currency("GTQ", "Quetzal guatemalteco", "Q", 2),
    Currency("DOP", "Peso dominicano", "RD$", 2),
    Currency("PYG", "Guaraní paraguayo", "₲", 0),
    Currency("UYU", "Peso uruguayo", "$U", 2),
    Currency("BOB", "Boliviano", "Bs", 2),
    Currency("CRC", "Colón costarricense", "₡", 0),
    Currency("HNL", "Lempira hondureño", "L", 2),
    Currency("NIO", "Córdoba nicaragüense", "C$", 2),
    Currency("PAB", "Balboa panameño", "B/.", 2),
    Currency("VES", "Bolívar venezolano", "Bs.S", 2),
)

CURRENCIES: dict[str, Currency] = {currency.code: currency for currency in _ALL}


def is_valid(code: Optional[str]) -> bool:
    return bool(code) and code in CURRENCIES


def catalog() -> list[dict]:
    return [asdict(currency) for currency in _ALL]
