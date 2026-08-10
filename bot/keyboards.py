"""Клавиатуры и кнопки."""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from .config import TARIFFS, TIME_LABELS
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
        [KeyboardButton(text="Тренировка"), KeyboardButton(text="Сегодня")],
        [KeyboardButton(text="Вода"), KeyboardButton(text="Вес")],
        [KeyboardButton(text="Ещё")],
    ],
    resize_keyboard=True,
)

MORE = inline(
    [
        ("Профиль", "more:profile"),
        ("План тренировок", "more:plan"),
        ("Напоминания", "more:times"),
        ("Работа с тренером", "more:coach"),
    ]
)

SEX = inline([("Мужской", "reg:sex:male"), ("Женский", "reg:sex:female")], per_row=2)

ACTIVITY = inline([(label, f"reg:act:{key}") for key, label in ACTIVITY_LABELS.items()])

GOAL = inline([(label, f"reg:goal:{key}") for key, label in GOAL_LABELS.items()])

PLACE = inline([(label, f"w:place:{key}") for key, label in PLACES.items()])

KIND = inline([(label, f"w:kind:{key}") for key, label in KINDS.items()], per_row=2)

WATER = inline(
    [("+250 мл", "water:250"), ("+500 мл", "water:500"), ("Своё", "water:custom")],
    per_row=2,
)


def program_actions(slot: str) -> InlineKeyboardMarkup:
    return inline(
        [
            ("Начать тренировку", f"w:go:{slot}"),
            ("Изменить план тренировок", "w:replan"),
            ("Сегодня пропускаю", "w:skip_day"),
        ]
    )


def set_actions(timed: bool) -> InlineKeyboardMarkup:
    label = "Закончил ✅" if timed else "Готово, подход закрыт ✅"
    return inline(
        [(label, "w:done"), ("Пропустить упражнение", "w:next"), ("Завершить", "w:stop")],
        per_row=1,
    )


REST_ACTIONS = inline([("Отдохнул, дальше", "w:skip_rest")])


def tariffs() -> InlineKeyboardMarkup:
    pairs = [
        (f"{t['title']} — {t['price']}", f"coach:{key}")
        for key, t in TARIFFS.items()
    ]
    return inline(pairs)


def confirm_lead(key: str) -> InlineKeyboardMarkup:
    return inline(
        [("Оставить заявку", f"coach:send:{key}"), ("Назад к тарифам", "coach:back")]
    )


def times_menu(times: dict) -> InlineKeyboardMarkup:
    pairs = [
        (f"{times.get(key, '--:--')}  {label}", f"time:{key}")
        for key, label in TIME_LABELS.items()
    ]
    return inline(pairs)


PROFILE_ACTIONS = inline(
    [
        ("Изменить цель по весу", "prof:target"),
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
        ("Пройти регистрацию заново", "prof:redo"),
    ],
    per_row=2,
)

EDIT_SEX = inline(
    [("Мужской", "set:sex:male"), ("Женский", "set:sex:female")], per_row=2
)
EDIT_ACTIVITY = inline([(l, f"set:activity:{k}") for k, l in ACTIVITY_LABELS.items()])
EDIT_GOAL = inline([(l, f"set:goal:{k}") for k, l in GOAL_LABELS.items()])
EDIT_PLACE = inline(
    [(l, f"set:pref_place:{k}") for k, l in PLACES.items()]
    + [(l, f"set:pref_kind:{k}") for k, l in KINDS.items()]
)
