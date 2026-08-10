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
TARIFFS = {
    "consult": {
        "title": "Разовая консультация",
        "price": "2 500 ₽",
        "about": "Час разбора: техника, план на месяц, ответы на вопросы.",
    },
    "coaching": {
        "title": "Ведение, месяц",
        "price": "8 000 ₽",
        "about": "Тренер правит программу под вас, смотрит видео техники, на связи в будни.",
    },
    "coaching_plus": {
        "title": "Ведение с питанием, месяц",
        "price": "12 000 ₽",
        "about": "То же плюс разбор рациона и коррекция БЖУ каждую неделю.",
    },
}


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
