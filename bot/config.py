"""Настройки бота. Всё чувствительное берётся из .env и в репозиторий не попадает."""

import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
ADMIN_ID = int((os.getenv("ADMIN_ID") or "0").strip() or 0)

FATSECRET_CLIENT_ID = (os.getenv("FATSECRET_CLIENT_ID") or "").strip()
FATSECRET_CLIENT_SECRET = (os.getenv("FATSECRET_CLIENT_SECRET") or "").strip()
FATSECRET_READY = bool(FATSECRET_CLIENT_ID and FATSECRET_CLIENT_SECRET)

TZ_NAME = (os.getenv("TZ") or "Europe/Moscow").strip()
TZ = ZoneInfo(TZ_NAME)

DB_PATH = ROOT / "formabot.db"

# Отдых между подходами и предупреждение перед его концом.
REST_SECONDS = 120
REST_WARNING_SECONDS = 30

# Время напоминаний по умолчанию. Каждое пользователь меняет под себя.
DEFAULT_TIMES = {
    "workout_am": "07:30",
    "breakfast": "08:40",
    "water_1": "10:00",
    "lunch": "14:00",
    "water_2": "16:30",
    "workout_pm": "19:00",
    "dinner": "20:30",
}
TIME_LABELS = {
    "workout_am": "Утренняя тренировка",
    "breakfast": "Завтрак",
    "water_1": "Вода, первое напоминание",
    "lunch": "Обед",
    "water_2": "Вода, второе напоминание",
    "workout_pm": "Вечерняя тренировка",
    "dinner": "Ужин",
}
# Взвешивание — раз в неделю, по воскресеньям.
WEIGH_IN_TIME = "09:00"
WEIGH_IN_WEEKDAY = 6  # 0 — понедельник, 6 — воскресенье

# Тарифы на работу с живым тренером. Цены поправьте под себя.
SERVICES = {
    "consult": {
        "title": "Консультация с тренером",
        "price_month": 0,
        "periods": False,
        "about": "Знакомство и разговор: какой у тебя уровень подготовки, "
                 "ради чего тренируешься, куда хочешь прийти.\n\n"
                 "Тренер посмотрит, что происходит, и скажет честно — нужен "
                 "ему человек рядом или справишься с ботом.",
    },
    "coaching": {
        "title": "Ведение онлайн",
        "price_month": 5000,
        "periods": True,
        "about": "Тренер правит программу под тебя, смотрит видео техники, "
                 "на связи в будни. Не даст слиться на второй неделе.",
    },
    "coaching_plus": {
        "title": "Ведение с питанием",
        "price_month": 7000,
        "periods": True,
        "about": "То же плюс разбор рациона и коррекция БЖУ каждую неделю. "
                 "Для тех, у кого зал идёт, а вес стоит.",
    },
}

# Скидки за оплату пакетом: (месяцев, процент скидки).
PERIODS = ((1, 0), (3, 10), (6, 15), (12, 25))


def price_for(code: str, months: int) -> dict:
    """Стоимость услуги за выбранный срок со скидкой."""
    service = SERVICES[code]
    per_month = service["price_month"]
    discount = dict((m, d) for m, d in PERIODS).get(months, 0)
    full = per_month * months
    total = round(full * (100 - discount) / 100)
    return {
        "months": months,
        "discount": discount,
        "full": full,
        "total": total,
        "saved": full - total,
        "per_month": round(total / months) if months else 0,
    }


def money(value: int) -> str:
    """15000 -> «15 000 ₽»."""
    return f"{value:,}".replace(",", " ") + " ₽"


def period_label(months: int) -> str:
    if months == 1:
        return "1 месяц"
    if months == 12:
        return "год"
    return f"{months} месяца" if months < 5 else f"{months} месяцев"


def missing_settings() -> list[str]:
    """Чего не хватает для запуска. Пустой список — всё готово."""
    problems = []
    if not BOT_TOKEN:
        problems.append(
            "BOT_TOKEN не задан. Создайте бота у @BotFather и впишите токен в .env"
        )
    if not ADMIN_ID:
        problems.append(
            "ADMIN_ID не задан. Узнайте свой ID у @userinfobot и впишите в .env — "
            "иначе заявки на тренера будет некуда отправлять"
        )
    return problems
