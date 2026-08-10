"""Разбор того, что пользователь пишет обычным текстом."""

import re

# «гречка 150 г», «куриная грудка 200г», «творог 5% 180 грамм», «яблоко 1 шт»
_GRAMS = re.compile(
    r"^(?P<name>.+?)[\s,]+(?P<amount>\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>г|гр|грамм[а-я]*|g|мл|ml)?\.?$",
    re.IGNORECASE,
)

_WEIGHT = re.compile(r"^\d{2,3}(?:[.,]\d)?$")
_TIME = re.compile(r"^([01]?\d|2[0-3])[:. ]([0-5]\d)$")


def food_line(text: str) -> tuple[str, float] | None:
    """«гречка 150 г» → ("гречка", 150.0). Без граммовки — None."""
    m = _GRAMS.match(text.strip())
    if not m:
        return None
    name = m.group("name").strip(" ,-")
    if not name:
        return None
    amount = float(m.group("amount").replace(",", "."))
    if not 1 <= amount <= 5000:
        return None
    return name, amount


def weight_value(text: str) -> float | None:
    """«85,4» → 85.4. Отсекает значения вне разумного диапазона."""
    t = text.strip().replace(",", ".")
    if not _WEIGHT.match(text.strip().replace(",", ".")):
        return None
    try:
        value = float(t)
    except ValueError:
        return None
    return value if 30 <= value <= 300 else None


def time_value(text: str) -> str | None:
    """«7:30», «07.30», «7 30» → "07:30"."""
    m = _TIME.match(text.strip())
    if not m:
        return None
    return f"{int(m.group(1)):02d}:{m.group(2)}"


def int_value(text: str, lo: int, hi: int) -> int | None:
    t = text.strip()
    if not t.isdigit():
        return None
    value = int(t)
    return value if lo <= value <= hi else None


def float_value(text: str, lo: float, hi: float) -> float | None:
    t = text.strip().replace(",", ".")
    try:
        value = float(t)
    except ValueError:
        return None
    return value if lo <= value <= hi else None
