"""Свойские обращения в напоминаниях.

Прозвище подбирается по паре «пол + цель»: тому, кто набирает массу, идёт
«здоровяк», тому, кто тянется — «гибкий». Фразы хранятся отдельно для
мужского и женского рода, чтобы не городить согласование в шаблонах:
«не забыл» и «не забыла» — это разные строки, а не подстановка окончания.

Про похудение отдельно. Обращения вида «худышка» сюда намеренно не попали:
человек на дефиците ещё не худой, и такое прозвище бьёт по больному вместо
того, чтобы подбодрить. Для этой цели взяты боевые слова — «боец», «чемпион».
Если решите поддразнивать — допишите их в LOSE_MALE и LOSE_FEMALE.
"""

import random

# --- прозвища по цели ---

GAIN_MALE = ["здоровяк", "богатырь", "шкаф", "амбал", "качок", "титан",
             "медведь", "гора", "бугай", "атлет"]
GAIN_FEMALE = ["воительница", "амазонка", "валькирия", "тигрица", "силачка",
               "атлетка", "пантера", "львица"]

LOSE_MALE = ["боец", "чемпион", "спартанец", "воин", "терминатор", "машина",
             "красавчик", "герой", "кремень", "зверь"]
LOSE_FEMALE = ["чемпионка", "красотка", "звёздочка", "богиня", "пантера",
               "воительница", "умница", "огонь"]

STRETCH_MALE = ["гибкий", "змей", "йог", "кот", "акробат", "пластилин",
                "тянучка", "мастер"]
STRETCH_FEMALE = ["кошечка", "балерина", "гимнастка", "змейка", "пантера",
                  "нимфа", "лоза"]

KEEP_MALE = ["чемпион", "атлет", "спортсмен", "боец", "красавчик", "мастер",
             "командир", "профи"]
KEEP_FEMALE = ["чемпионка", "спортсменка", "красотка", "умница", "звезда",
               "профи", "королева"]

NICKNAMES = {
    ("male", "gain"): GAIN_MALE,
    ("female", "gain"): GAIN_FEMALE,
    ("male", "lose"): LOSE_MALE,
    ("female", "lose"): LOSE_FEMALE,
    ("male", "stretch"): STRETCH_MALE,
    ("female", "stretch"): STRETCH_FEMALE,
    ("male", "maintain"): KEEP_MALE,
    ("female", "maintain"): KEEP_FEMALE,
}

# --- заготовки фраз, {n} подставляется прозвище ---

MEAL_OPENERS = {
    "male": [
        "Эй, {n}, {meal} сам себя не съест.",
        "Ну что, {n}, {meal}?",
        "{n}, время {meal_gen}. Не отвлекайся надолго.",
        "Слышь, {n}, {meal} по расписанию.",
        "{n}, а {meal} кто есть будет?",
        "Так, {n}, отложил дела — {meal}.",
        "{n}, {meal}. Мышцы растут на кухне, если что.",
        "Эй, {n}, не забыл про {meal_acc}?",
    ],
    "female": [
        "Эй, {n}, {meal} сам себя не съест.",
        "Ну что, {n}, {meal}?",
        "{n}, время {meal_gen}. Не отвлекайся надолго.",
        "Слышь, {n}, {meal} по расписанию.",
        "{n}, а {meal} кто есть будет?",
        "Так, {n}, отложила дела — {meal}.",
        "{n}, {meal}. Мышцы растут на кухне, если что.",
        "Эй, {n}, не забыла про {meal_acc}?",
    ],
}

WATER_OPENERS = {
    "male": [
        "Эй, {n}, не забыл попить водички?",
        "{n}, стакан воды — и обратно к делам.",
        "Ну что, {n}, пьём или как?",
        "{n}, вода сама себя не выпьет.",
        "Слышь, {n}, а водичка?",
        "{n}, обезвоженная мышца не растёт. Намекаю.",
        "Так, {n}, отвлекись на стакан воды.",
        "{n}, кофе — это не вода. Проверено.",
    ],
    "female": [
        "Эй, {n}, не забыла попить водички?",
        "{n}, стакан воды — и обратно к делам.",
        "Ну что, {n}, пьём или как?",
        "{n}, вода сама себя не выпьет.",
        "Слышь, {n}, а водичка?",
        "{n}, обезвоженная мышца не растёт. Намекаю.",
        "Так, {n}, отвлекись на стакан воды.",
        "{n}, кофе — это не вода. Проверено.",
    ],
}

PROTEIN_NUDGE = {
    "male": [
        "Ну что, {n}, белок добирать собираешься?",
        "{n}, белка не хватает. Мясо, рыба, творог — выбирай.",
        "Эй, {n}, без белка вся работа в зале коту под хвост.",
    ],
    "female": [
        "Ну что, {n}, белок добирать собираешься?",
        "{n}, белка не хватает. Мясо, рыба, творог — выбирай.",
        "Эй, {n}, без белка вся работа в зале коту под хвост.",
    ],
}

# Падежи названий приёмов пищи для подстановки в разные шаблоны.
MEALS = {
    "breakfast": {"nom": "завтрак", "gen": "завтрака", "acc": "завтрак"},
    "lunch": {"nom": "обед", "gen": "обеда", "acc": "обед"},
    "dinner": {"nom": "ужин", "gen": "ужина", "acc": "ужин"},
}


def litres(ml: float) -> str:
    """Литры с запятой в дробной части: 3150 -> «3,1»."""
    from .calc import dec
    return dec(ml / 1000)


MAX_CUSTOM_LEN = 20
FALLBACK = "друг"


def defaults(sex: str | None, goal: str | None) -> list[str]:
    """Стандартный набор обращений под пол и цель."""
    key = (sex or "male", goal or "maintain")
    pool = NICKNAMES.get(key)
    if not pool:
        pool = KEEP_FEMALE if sex == "female" else KEEP_MALE
    return list(pool)


def pool_for(sex: str | None, goal: str | None, prefs: dict | None = None) -> list[str]:
    """Набор обращений с учётом правок пользователя."""
    prefs = prefs or {}
    banned = set(prefs.get("banned") or [])
    custom = list(prefs.get("custom") or [])
    pool = [n for n in defaults(sex, goal) if n not in banned]
    # Свои идут следом и не дублируют стандартные.
    pool += [n for n in custom if n not in pool]
    return pool or [FALLBACK]


def validate_custom(text: str) -> tuple[str | None, str | None]:
    """Проверяет своё прозвище. Возвращает (прозвище, текст ошибки)."""
    name = " ".join((text or "").split()).lower()
    if not name:
        return None, "Пусто. Напиши слово."
    if len(name) < 2:
        return None, "Слишком коротко — минимум две буквы."
    if len(name) > MAX_CUSTOM_LEN:
        return None, f"Слишком длинно — не больше {MAX_CUSTOM_LEN} символов."
    # Угловые скобки и амперсанд сломали бы разметку сообщений.
    if any(ch in name for ch in "<>&"):
        return None, "Без символов < > и & — они ломают оформление."
    allowed = set("абвгдеёжзийклмнопрстуфхцчшщъыьэюяabcdefghijklmnopqrstuvwxyz -")
    if not set(name) <= allowed:
        return None, "Только буквы, пробел и дефис."
    return name, None


def nickname(sex: str | None, goal: str | None, prefs: dict | None = None) -> str:
    """Прозвище под пол, цель и правки пользователя."""
    return random.choice(pool_for(sex, goal, prefs))


def _form(sex: str | None) -> str:
    return "female" if sex == "female" else "male"


def _cap(text: str) -> str:
    """Первая буква заглавная.

    Прозвища хранятся строчными, а часть шаблонов начинается прямо с них:
    «бугай, обед» надо превратить в «Бугай, обед». Обычный capitalize() не
    подходит — он опустит регистр у остальной строки.
    """
    return text[:1].upper() + text[1:] if text else text


def meal_opener(sex: str | None, goal: str | None, meal_key: str,
                prefs: dict | None = None) -> str:
    """Шутливый зачин напоминания о еде."""
    meal = MEALS.get(meal_key, MEALS["lunch"])
    template = random.choice(MEAL_OPENERS[_form(sex)])
    return _cap(template.format(
        n=nickname(sex, goal, prefs),
        meal=meal["nom"],
        meal_gen=meal["gen"],
        meal_acc=meal["acc"],
    ))


def water_opener(sex: str | None, goal: str | None,
                 prefs: dict | None = None) -> str:
    """Шутливый зачин напоминания о воде."""
    return _cap(random.choice(WATER_OPENERS[_form(sex)]).format(
        n=nickname(sex, goal, prefs)))


def protein_nudge(sex: str | None, goal: str | None,
                  prefs: dict | None = None) -> str:
    """Подначка, когда белка сильно не хватает."""
    return _cap(random.choice(PROTEIN_NUDGE[_form(sex)]).format(
        n=nickname(sex, goal, prefs)))
