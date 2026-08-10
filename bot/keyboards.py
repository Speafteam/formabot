"""Клавиатуры и кнопки."""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from .config import (
    PERIODS,
    SERVICES,
    TIME_LABELS,
    money,
    period_label,
    price_for,
)
from .calc import ACTIVITY_LABELS, GOAL_LABELS
from .programs import PLACES, KINDS


def _rows(pairs, per_row=1):
    rows, row = [], []
    for text, data in pairs:
        row.append(InlineKeyboardButton(text=text, callback_data=data))
        if len(row) == per_row:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return rows


def inline(pairs, per_row=1) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=_rows(pairs, per_row))


MAIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Тренировка"), KeyboardButton(text="Еда")],
        [KeyboardButton(text="Вода"), KeyboardButton(text="Вес")],
        [KeyboardButton(text="Ещё")],
    ],
    resize_keyboard=True,
)

# Возврат в меню «Ещё». Стоит на каждом экране второго уровня, чтобы из
# любого раздела можно было выйти, не гадая, какая кнопка вернёт назад.
BACK = ("← Назад", "more:back")

MORE = inline(
    [
        ("🏆 Достижения", "more:achievements"),
        ("Профиль", "more:profile"),
        ("Дни тренировок", "sched:menu"),
        ("План на неделю", "more:plan"),
        ("Напоминания", "more:times"),
        ("Как ко мне обращаться", "nick:menu"),
        ("Живой тренер", "more:coach"),
    ]
)


def groups_menu(chosen: set[str]) -> InlineKeyboardMarkup:
    """Выбор групп мышц. Отмеченные помечены галочкой, порядок фиксирован."""
    from .programs import GROUPS, MIN_GROUPS

    pairs = [
        (f"{'✅' if code in chosen else '➖'} {label}", f"w:grp:{code}")
        for code, label in GROUPS.items()
    ]
    rows = _rows(pairs, per_row=2)
    if len(chosen) >= MIN_GROUPS:
        rows += _rows([(f"Собрать программу ({len(chosen)})", "w:grp:done")])
    else:
        need = MIN_GROUPS - len(chosen)
        rows += _rows([(f"Выбери ещё {need}", "w:grp:need")])
    rows += _rows([("← Назад", "w:grp:back"), ("Отмена", "w:grp:cancel")],
                  per_row=2)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def schedule_menu(schedule: dict) -> InlineKeyboardMarkup:
    """Семь строк по две кнопки: основная и короткий блок на каждый день.

    Нажатие переключает одну ячейку — состояние видно сразу на кнопке,
    гадать не приходится.
    """
    from .db import WEEKDAYS_SHORT

    rows = []
    for day in range(7):
        marks = schedule[day]
        rows.append([
            InlineKeyboardButton(
                text=f"{WEEKDAYS_SHORT[day]}  🏋️ {'✅' if marks['am'] else '➖'}",
                callback_data=f"sched:t:{day}:am",
            ),
            InlineKeyboardButton(
                text=f"⚡ {'✅' if marks['pm'] else '➖'}",
                callback_data=f"sched:t:{day}:pm",
            ),
        ])
    rows += _rows([
        ("Всё включить", "sched:all"),
        ("Только будни", "sched:weekdays"),
        ("Сбросить в ноль", "sched:none"),
        BACK,
    ], per_row=1)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def nicknames_menu(pool: list[str], custom: list[str],
                   has_changes: bool) -> InlineKeyboardMarkup:
    """Список обращений: нажатие на строку убирает её из набора."""
    pairs = [
        (f"✕  {name}" + ("  ·  своё" if name in custom else ""), f"nick:del:{name}")
        for name in pool
    ]
    pairs.append(("➕ Добавить своё", "nick:add"))
    if has_changes:
        pairs.append(("↩️ Вернуть стандартные", "nick:reset"))
    pairs.append(BACK)
    return inline(pairs)

SEX = inline([("Мужской", "reg:sex:male"), ("Женский", "reg:sex:female")], per_row=2)

ACTIVITY = inline([(label, f"reg:act:{key}") for key, label in ACTIVITY_LABELS.items()])

GOAL = inline([(label, f"reg:goal:{key}") for key, label in GOAL_LABELS.items()])

WATER = inline(
    [("+250 мл", "water:250"), ("+500 мл", "water:500"), ("Своё", "water:custom")],
    per_row=2,
)


def program_actions(slot: str) -> InlineKeyboardMarkup:
    return inline(
        [
            ("Погнали 💪", f"w:go:{slot}"),
            ("Не то, пересобери", "w:replan"),
            ("Сегодня пропускаю", "w:skip_day"),
        ]
    )


def set_actions(timed: bool) -> InlineKeyboardMarkup:
    label = "Закончил ✅" if timed else "Подход закрыт ✅"
    return inline(
        [(label, "w:done"), ("Пропустить упражнение", "w:next"), ("Хватит", "w:stop")],
        per_row=1,
    )


REST_ACTIONS = inline([("Отдохнул, дальше", "w:skip_rest")])


def services() -> InlineKeyboardMarkup:
    pairs = []
    for key, s in SERVICES.items():
        tag = "бесплатно" if not s["price_month"] else (
            money(s["price_month"]) + " / мес")
        pairs.append((f"{s['title']} — {tag}", f"coach:{key}"))
    pairs.append(BACK)
    return inline(pairs)


def periods_menu(key: str) -> InlineKeyboardMarkup:
    """Сроки со скидками. Экономия видна прямо на кнопке."""
    pairs = []
    for months, discount in PERIODS:
        p = price_for(key, months)
        label = f"{period_label(months)} — {money(p['total'])}"
        if discount:
            label += f"  −{discount}%"
        pairs.append((label, f"coach:period:{key}:{months}"))
    pairs.append(("Назад", "coach:back"))
    return inline(pairs)


def confirm_lead(key: str, months: int = 0) -> InlineKeyboardMarkup:
    return inline([
        ("Оставить заявку", f"coach:send:{key}:{months}"),
        ("Добавить комментарий", f"coach:note:{key}:{months}"),
        ("Назад", "coach:back"),
    ])


SKIP_COMMENT = inline([("Без комментария", "coach:nonote"),
                       ("← Назад", "coach:back")])


def times_menu(times: dict) -> InlineKeyboardMarkup:
    pairs = [
        (f"{times.get(key, '--:--')}  {label}", f"time:{key}")
        for key, label in TIME_LABELS.items()
    ]
    pairs.append(BACK)
    return inline(pairs)


PROFILE_ACTIONS = inline(
    [
        ("Сменить цель по весу", "prof:target"),
        ("Открыть профиль", "more:profile"),
    ]
)

# Профиль: у каждого поля своя кнопка правки.
PROFILE_EDIT = inline(
    [
        ("Рост", "edit:height"),
        ("Вес", "edit:weight"),
        ("Возраст", "edit:age"),
        ("Пол", "edit:sex"),
        ("Образ жизни", "edit:activity"),
        ("Цель занятий", "edit:goal"),
        ("Цель по весу и срок", "prof:target"),
        ("Место тренировок", "edit:place"),
        ("Как ко мне обращаться", "nick:menu"),
        ("Начать всё заново", "prof:redo"),
        BACK,
    ],
    per_row=2,
)

# Возврат в профиль: эти экраны открываются из него и больше ниоткуда.
TO_PROFILE = ("← Назад", "more:profile")

EDIT_SEX = inline(
    [("Мужской", "set:sex:male"), ("Женский", "set:sex:female"), TO_PROFILE],
    per_row=2,
)
EDIT_ACTIVITY = inline(
    [(l, f"set:activity:{k}") for k, l in ACTIVITY_LABELS.items()] + [TO_PROFILE]
)
EDIT_GOAL = inline(
    [(l, f"set:goal:{k}") for k, l in GOAL_LABELS.items()] + [TO_PROFILE]
)
EDIT_PLACE = inline(
    [(l, f"set:pref_place:{k}") for k, l in PLACES.items()]
    + [(l, f"set:pref_kind:{k}") for k, l in KINDS.items()]
    + [TO_PROFILE]
)
