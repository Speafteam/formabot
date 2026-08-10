"""Достижения со ступенями.

Устроено как огонёк в ТикТоке: взял ступень — значок повышается, планка
сдвигается дальше, а набранное идёт в зачёт следующей. Прогресс не
обнуляется при повышении.

Серии считаются с поблажкой: один пропущенный день на каждые семь
прощается. Два пропуска рядом серию рвут. Уже взятые ступени при этом
никуда не деваются — заработанное не отнимаем.
"""

from dataclasses import dataclass
from datetime import date, timedelta

# Сколько дней подряд должно пройти между прощёнными пропусками.
FORGIVE_WINDOW = 7


@dataclass(frozen=True)
class Achievement:
    code: str
    title: str
    icon: str
    unit: str            # «дней подряд», «тренировок», «литров»
    tiers: tuple[int, ...]
    hint: str            # что нужно делать

    def tier_of(self, value: int) -> int:
        """Сколько ступеней взято при таком значении."""
        return sum(1 for t in self.tiers if value >= t)

    def next_target(self, value: int) -> int | None:
        """Следующая планка. None — все ступени взяты."""
        for t in self.tiers:
            if value < t:
                return t
        return None

    def max_tier(self) -> int:
        return len(self.tiers)


# Значки по ступеням: чем выше, тем ярче.
TIER_ICONS = ["🥉", "🥈", "🥇", "💎", "👑", "🔥"]

ALL: tuple[Achievement, ...] = (
    Achievement(
        "workout_streak", "Огонь", "🔥", "дней подряд",
        (3, 7, 14, 30, 60, 100),
        "Доводи тренировку до конца каждый день.",
    ),
    Achievement(
        "protein_streak", "Белковый режим", "🥩", "дней подряд",
        (3, 7, 14, 30, 60, 100),
        "Добирай норму белка каждый день.",
    ),
    Achievement(
        "water_streak", "Водохлёб", "💧", "дней подряд",
        (3, 7, 14, 30, 60),
        "Закрывай норму воды каждый день.",
    ),
    Achievement(
        "log_streak", "Дневник", "📓", "дней подряд",
        (3, 7, 14, 30, 60, 100),
        "Записывай еду каждый день.",
    ),
    Achievement(
        "weigh_streak", "Под контролем", "⚖️", "взвешиваний подряд",
        (2, 4, 8, 16, 32),
        "Вставай на весы каждую неделю.",
    ),
    Achievement(
        "workouts_total", "Стаж", "🏋️", "тренировок",
        (5, 25, 50, 100, 250, 500),
        "Просто тренируйся. Счёт идёт за всё время.",
    ),
    Achievement(
        "minutes_total", "Часы под штангой", "⏱️", "минут работы",
        (300, 1000, 3000, 6000, 12000),
        "Копится из длительности завершённых тренировок.",
    ),
    Achievement(
        "meals_total", "Счетовод", "🧮", "записей о еде",
        (20, 100, 300, 1000),
        "Записывай, что съел.",
    ),
    Achievement(
        "water_total", "Океан", "🌊", "литров",
        (30, 100, 300, 1000),
        "Копится из всей выпитой воды.",
    ),
    Achievement(
        "places_total", "Везде свой", "🗺️", "мест занятий",
        (1, 2, 3),
        "Потренируйся дома, в зале и на площадке.",
    ),
    Achievement(
        "early_total", "Жаворонок", "🌅", "тренировок до 8 утра",
        (1, 5, 20, 50),
        "Закрывай тренировку раньше восьми.",
    ),
    Achievement(
        "goal_progress", "К цели", "🎯", "% пути пройдено",
        (25, 50, 75, 100),
        "Двигайся к целевому весу.",
    ),
)

BY_CODE = {a.code: a for a in ALL}


def streak(days: list[str], today_: date | None = None,
           expected: set[int] | None = None) -> int:
    """Длина серии в днях с поблажкой: один пропуск на семь прощается.

    Сегодняшний день без отметки серию не рвёт — он ещё не закончился.

    expected — номера дней недели, в которые тренировка запланирована
    (0 это понедельник). Дни вне этого набора пропускаются целиком: они
    не идут в счёт и не считаются пропуском. Без этого человек с тремя
    тренировками в неделю не взял бы ни одной ступени.
    """
    if not days:
        return 0
    done = set(days)
    today_ = today_ or date.today()
    earliest = date.fromisoformat(min(done))

    count = 0
    forgiven_at: int | None = None   # на сколько дней назад был прощён пропуск
    offset = 0

    while True:
        day = today_ - timedelta(days=offset)
        if day < earliest:
            break                     # раньше первой отметки считать нечего
        if expected is not None and day.weekday() not in expected:
            offset += 1
            continue                  # выходной по плану — просто мимо
        if day.isoformat() in done:
            count += 1
        elif offset == 0:
            pass                      # сегодня ещё идёт, пропуском не считаем
        elif forgiven_at is not None and offset - forgiven_at < FORGIVE_WINDOW:
            break                     # второй пропуск рядом — серия рвётся
        else:
            forgiven_at = offset
        offset += 1
    return count


def week_streak(days: list[str], today_: date | None = None) -> int:
    """Серия недель подряд, в которые была хотя бы одна отметка."""
    if not days:
        return 0
    weeks = {date.fromisoformat(d).isocalendar()[:2] for d in days}
    today_ = today_ or date.today()
    cursor = today_
    # Текущая неделя может быть ещё не закрыта — её отсутствие не рвёт серию.
    if cursor.isocalendar()[:2] not in weeks:
        cursor -= timedelta(days=7)
    count = 0
    while cursor.isocalendar()[:2] in weeks:
        count += 1
        cursor -= timedelta(days=7)
    return count


def goal_percent(start_kg, current_kg, target_kg) -> int:
    """Сколько процентов пути к целевому весу пройдено."""
    if not start_kg or not target_kg or start_kg == target_kg:
        return 0
    done = (start_kg - current_kg) / (start_kg - target_kg)
    return max(0, min(100, round(done * 100)))


async def values_for(conn, row) -> dict[str, int]:
    """Текущие значения по всем достижениям одного пользователя."""
    from . import db

    tg_id = row["tg_id"]
    counts = await db.counters(conn, tg_id)
    planned = db.training_days(db.user_schedule(row))

    return {
        "workout_streak": streak(await db.workout_days(conn, tg_id),
                                 expected=planned or None),
        "protein_streak": streak(
            await db.protein_days(conn, tg_id, row["protein"] or 0)),
        "water_streak": streak(
            await db.water_days(conn, tg_id, row["water_ml"] or 0)),
        "log_streak": streak(await db.meal_days(conn, tg_id)),
        "weigh_streak": week_streak(await db.weigh_days(conn, tg_id)),
        "workouts_total": counts["workouts"],
        "minutes_total": counts["minutes"],
        "meals_total": counts["meals"],
        "water_total": counts["water_ml"] // 1000,
        "places_total": counts["places"],
        "early_total": counts["early"],
        "goal_progress": goal_percent(
            row["start_kg"], row["weight_kg"], row["target_kg"]),
    }


async def check(conn, row) -> list[tuple[Achievement, int, int]]:
    """Находит взятые с прошлого раза ступени и записывает их.

    Возвращает список (достижение, ступень, значение) для поздравления.
    """
    from . import db

    tg_id = row["tg_id"]
    values = await values_for(conn, row)
    have = await db.unlocked(conn, tg_id)
    fresh = []

    for a in ALL:
        value = values.get(a.code, 0)
        tier = a.tier_of(value)
        was = have.get(a.code, 0)
        if tier > was:
            # Могло перескочить сразу несколько ступеней — пишем все,
            # но поздравляем только высшей, чтобы не заваливать чат.
            for t in range(was + 1, tier + 1):
                await db.unlock(conn, tg_id, a.code, t)
            fresh.append((a, tier, value))
    return fresh


async def notify(bot, conn, tg_id: int) -> None:
    """Проверяет достижения и поздравляет с новыми ступенями.

    Вызывается после действий, которые двигают счётчики. Ошибку глушим:
    незакрытое достижение — не повод рушить основной сценарий.
    """
    import logging

    from . import db

    try:
        row = await db.get_user(conn, tg_id)
        if not row or not row["kcal"]:
            return
        for a, tier, value in await check(conn, row):
            await bot.send_message(tg_id, congratulation(a, tier, value))
    except Exception:
        logging.getLogger(__name__).exception(
            "Не смог проверить достижения для %s", tg_id)


def congratulation(a: Achievement, tier: int, value: int) -> str:
    """Сообщение о взятой ступени."""
    icon = tier_icon(tier)
    lines = [
        f"{icon} <b>{a.title}</b> — уровень {tier} из {a.max_tier()}",
        "",
        f"{a.icon} {value} {a.unit}.",
    ]
    nxt = a.next_target(value)
    if nxt is None:
        lines += ["", "Это потолок. Выше некуда — снимаю шляпу."]
    else:
        left = nxt - value
        lines += ["", f"Следующая ступень — {nxt}. Осталось {left}."]
    return "\n".join(lines)


def tier_icon(tier: int) -> str:
    if tier <= 0:
        return "⚪"
    return TIER_ICONS[min(tier, len(TIER_ICONS)) - 1]


def progress_line(a: Achievement, value: int) -> str:
    """Строка достижения для экрана."""
    tier = a.tier_of(value)
    nxt = a.next_target(value)
    icon = tier_icon(tier)
    head = f"{icon} {a.icon} <b>{a.title}</b>"
    if tier:
        head += f" · ур. {tier} из {a.max_tier()}"
    if nxt is None:
        return f"{head}\n     Всё взято: {value} {a.unit}."
    bars = 10
    prev = a.tiers[tier - 1] if tier else 0
    span = max(nxt - prev, 1)
    filled = max(0, min(bars, round((value - prev) / span * bars)))
    bar = "▰" * filled + "▱" * (bars - filled)
    return f"{head}\n     {bar}  {value} / {nxt} {a.unit}"
