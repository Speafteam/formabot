"""Сборка программ тренировок под выбранные группы мышц.

Раньше программы были зашиты блоками «низ тела» и «верх тела». Теперь каждое
упражнение помечено группами и местами, где его можно сделать, а состав
собирается под выбор человека: минимум две группы, максимум не ограничен.

Набор идёт по кругу выбранных групп, пока не наберётся нужная длительность.
Так все выбранные группы получают нагрузку, а не только первая из списка.

Про ссылки на технику: здесь поисковые ссылки YouTube, а не конкретные видео.
Так они не протухнут. Отберёте свои ролики — замените video у упражнения.
"""

import random
from urllib.parse import quote_plus

PLACES = {"gym": "В зале", "home": "Дома", "outdoor": "На улице"}
KINDS = {"strength": "Силовая", "cardio": "Кардио"}

GROUPS = {
    "chest": "Грудь",
    "back": "Спина",
    "shoulders": "Плечи",
    "arms": "Руки",
    "legs": "Ноги",
    "glutes": "Ягодицы",
    "abs": "Пресс",
}
MIN_GROUPS = 2

# Сколько минут занимает основной блок. Разминка и заминка сверху.
MAIN_MINUTES = {"am": 82, "pm": 15}

ALL_PLACES = ("gym", "home", "outdoor")


def video(query: str) -> str:
    return "https://www.youtube.com/results?search_query=" + quote_plus(
        query + " техника выполнения")


def E(name, groups, places, sets, reps, note, *, timed=False, cardio=False):
    """Упражнение. Первая группа в списке — основная, по ней идёт подбор.

    Подтягивания задевают и руки, но основная у них спина. Иначе человек,
    выбравший грудь и руки, получил бы в программу упражнение на спину.

    Группы и места держим кортежами, а не множествами: программа целиком
    уезжает в базу через JSON, а множества туда не укладываются.
    """
    return {
        "name": name,
        "groups": tuple(groups),
        "places": tuple(places),
        "sets": sets,
        "reps": reps,
        "note": note,
        "video": video(name),
        "timed": timed,
        "cardio": cardio,
        "block": "Основной блок",
    }


# ---------- силовые упражнения ----------

STRENGTH = [
    # грудь
    E("Жим штанги лёжа", ["chest"], ["gym"], 4, "10",
      "Лопатки сведены, штанга опускается на низ груди."),
    E("Жим гантелей на наклонной", ["chest", "shoulders"], ["gym"], 4, "12",
      "Наклон около 30 градусов, локти не заваливай назад."),
    E("Разведения гантелей", ["chest"], ["gym"], 3, "15",
      "Локти чуть согнуты, вес небольшой."),
    E("Сведения в тренажёре", ["chest"], ["gym"], 3, "15",
      "В конце движения задержка на секунду."),
    E("Отжимания от пола", ["chest", "arms"], ["home", "outdoor"], 4, "12",
      "Корпус прямой, локти под 45 градусов."),
    E("Отжимания с ногами на возвышении", ["chest", "shoulders"],
      ["home", "outdoor"], 3, "12", "Чем выше ноги, тем больше идёт на плечи."),
    E("Отжимания на брусьях", ["chest", "arms"], ["gym", "outdoor"], 4, "10",
      "Наклон корпуса вперёд — больше грудь, вертикально — больше трицепс."),

    # спина
    E("Тяга верхнего блока", ["back"], ["gym"], 4, "12",
      "Тянешь локтями, а не кистями."),
    E("Тяга горизонтального блока", ["back"], ["gym"], 3, "12",
      "Спина не круглится, лопатки сводишь."),
    E("Тяга штанги в наклоне", ["back"], ["gym"], 4, "10",
      "Корпус около 45 градусов, поясница ровная."),
    E("Тяга гантели в наклоне", ["back"], ["gym", "home"], 4, "12 на руку",
      "Корпус зафиксирован, работает спина."),
    E("Подтягивания", ["back", "arms"], ["gym", "outdoor"], 4, "8",
      "Полная амплитуда, без рывков корпусом."),
    E("Австралийские подтягивания", ["back"], ["outdoor", "home"], 4, "12",
      "Тело прямое, тянешься грудью к перекладине."),
    E("Гиперэкстензия", ["back", "glutes"], ["gym"], 3, "15",
      "Поднимаешься до прямой линии, не выше."),
    E("Супермен", ["back"], ["home", "outdoor"], 3, "15",
      "Тянешься руками вперёд, а ногами назад."),

    # плечи
    E("Жим штанги стоя", ["shoulders"], ["gym"], 4, "10",
      "Пресс в тонусе, поясницу не прогибай."),
    E("Жим гантелей сидя", ["shoulders"], ["gym"], 4, "12",
      "Локти чуть впереди корпуса."),
    E("Махи гантелями в стороны", ["shoulders"], ["gym", "home"], 3, "15",
      "Вес небольшой, работают именно плечи."),
    E("Махи в наклоне", ["shoulders", "back"], ["gym", "home"], 3, "15",
      "Задняя дельта любит маленький вес и чистую технику."),
    E("Отжимания домиком", ["shoulders"], ["home", "outdoor"], 3, "12",
      "Таз вверх, макушкой тянешься к полу."),
    E("Отжимания домиком с ногами на возвышении", ["shoulders"],
      ["home", "outdoor"], 3, "10",
      "Чем выше ноги, тем больше нагрузки на плечи."),
    E("Отжимания в стойке у опоры", ["shoulders"], ["home", "outdoor"], 3, "8",
      "Спиной к стене, опускаешься под контролем. Тяжёлое — не спеши."),
    E("Протяжка с гантелями", ["shoulders"], ["gym", "home"], 3, "15",
      "Тянешь локтями вверх, кисти скользят вдоль корпуса."),

    # руки
    E("Подъём штанги на бицепс", ["arms"], ["gym"], 3, "12",
      "Локти прижаты к корпусу, без раскачки."),
    E("Подъём гантелей на бицепс", ["arms"], ["gym", "home"], 3, "12",
      "В верхней точке доворачивай кисть."),
    E("Французский жим", ["arms"], ["gym"], 3, "12",
      "Двигается только предплечье."),
    E("Разгибания на блоке", ["arms"], ["gym"], 3, "15",
      "Локти прижаты, корпус не помогает."),
    E("Отжимания от стула сзади", ["arms"], ["home", "outdoor"], 3, "12",
      "Локти назад, не разводи в стороны."),
    E("Узкие отжимания", ["arms", "chest"], ["home", "outdoor"], 3, "12",
      "Ладони под грудью, локти вдоль корпуса."),

    # ноги
    E("Приседания со штангой", ["legs", "glutes"], ["gym"], 4, "10",
      "Спина прямая, колени по линии стоп, таз назад."),
    E("Жим ногами", ["legs"], ["gym"], 4, "12",
      "Поясницу не отрывай от спинки, колени не своди."),
    E("Румынская тяга", ["legs", "glutes"], ["gym"], 4, "12",
      "Штанга скользит вдоль ног, спина ровная."),
    E("Разгибания ног в тренажёре", ["legs"], ["gym"], 3, "15",
      "В верхней точке задержка на секунду."),
    E("Сгибания ног в тренажёре", ["legs"], ["gym"], 4, "12",
      "Движение только в колене, таз прижат."),
    E("Приседания с собственным весом", ["legs", "glutes"],
      ["home", "outdoor"], 4, "20", "Пятки на полу, колени наружу."),
    E("Выпады", ["legs", "glutes"], ALL_PLACES, 4, "15 на ногу",
      "Колено передней ноги над стопой."),
    E("Приседания у стены", ["legs"], ["home"], 3, "45 сек",
      "Бёдра параллельно полу, спина прижата.", timed=True),
    E("Запрыгивания на скамью", ["legs", "glutes"], ["outdoor", "gym"], 4, "12",
      "Приземляешься мягко, на всю стопу."),
    E("Подъёмы на носки", ["legs"], ALL_PLACES, 4, "20",
      "Полная амплитуда, пауза наверху."),

    # ягодицы
    E("Ягодичный мостик", ["glutes"], ALL_PLACES, 4, "20",
      "Наверху сжимаешь ягодицы на секунду."),
    E("Мостик на одной ноге", ["glutes"], ["home", "outdoor"], 3, "15 на ногу",
      "Таз не заваливается вбок."),
    E("Отведение ноги назад", ["glutes"], ["gym", "home"], 3, "20 на ногу",
      "Движение короткое, без раскачки поясницей."),
    E("Болгарские выпады", ["glutes", "legs"], ["gym", "home"], 3, "12 на ногу",
      "Задняя нога на опоре, вес на передней."),

    # пресс
    E("Скручивания лёжа", ["abs"], ["home", "gym"], 4, "20",
      "Поясница прижата к полу."),
    E("Подъём ног в висе", ["abs"], ["gym", "outdoor"], 3, "12",
      "Без раскачки, работает пресс."),
    E("Планка", ["abs"], ALL_PLACES, 3, "45 сек",
      "Таз не проваливается, шея продолжает линию спины.", timed=True),
    E("Боковая планка", ["abs"], ALL_PLACES, 3, "40 сек",
      "Корпус в одной линии, таз не роняй.", timed=True),
    E("Велосипед", ["abs"], ["home", "gym"], 3, "20",
      "Медленно, поясница прижата."),
    E("Русский твист", ["abs"], ["home", "gym"], 3, "20",
      "Поворачивается корпус, а не только руки."),
]

# ---------- кардио с уклоном в группы ----------

CARDIO = [
    E("Бег в среднем темпе", [], ["outdoor"], 1, "20 мин",
      "Темп, при котором можешь говорить.", timed=True, cardio=True),
    E("Дорожка, интервалы", [], ["gym"], 1, "20 мин",
      "Минуту быстро, две спокойно, по кругу.", timed=True, cardio=True),
    E("Бег на месте", [], ["home"], 1, "12 мин",
      "Колени повыше, темп ровный.", timed=True, cardio=True),
    E("Велотренажёр", ["legs"], ["gym"], 1, "15 мин",
      "Спокойный темп, дыхание не сбивается.", timed=True, cardio=True),
    E("Гребной тренажёр", ["back", "legs"], ["gym"], 1, "12 мин",
      "Толчок ногами, потом тяга руками.", timed=True, cardio=True),
    E("Скакалка", ["legs"], ["home", "outdoor", "gym"], 4, "2 мин",
      "Прыжок невысокий, работают кисти.", timed=True, cardio=True),
    E("Бёрпи", ["legs", "chest", "abs"], ALL_PLACES, 5, "10",
      "Темп ровный, поясницу не прогибай.", cardio=True),
    E("Выпрыгивания из приседа", ["legs", "glutes"], ALL_PLACES, 4, "15",
      "Приземляешься мягко.", cardio=True),
    E("Выпады в прыжке", ["legs", "glutes"], ALL_PLACES, 4, "12 на ногу",
      "Приземляешься через носок.", cardio=True),
    E("Высокие колени", ["legs", "abs"], ALL_PLACES, 4, "45 сек",
      "Корпус ровный, работаешь в темпе.", timed=True, cardio=True),
    E("Скалолаз", ["abs", "legs"], ALL_PLACES, 4, "40 сек",
      "Таз не подпрыгивает.", timed=True, cardio=True),
    E("Джампинг джек", ["shoulders", "legs"], ALL_PLACES, 4, "60 сек",
      "Ровный ритм, руки полностью над головой.", timed=True, cardio=True),
    E("Бёрпи с отжиманием", ["chest", "arms", "abs"], ALL_PLACES, 4, "10",
      "Внизу полноценное отжимание.", cardio=True),
    E("Ускорения", ["legs"], ["outdoor"], 6, "100 м",
      "Между ускорениями — ходьба до восстановления.", cardio=True),
]


# ---------- разминка и заминка ----------

def warmup(place: str, minutes: int = 12) -> list[dict]:
    cardio = {"gym": "Велотренажёр или дорожка",
              "home": "Прыжки на месте и бег на месте",
              "outdoor": "Лёгкий бег"}[place]
    items = [
        dict(E(cardio, [], [place], 1, f"{minutes} мин",
               "Пульс до разговорного темпа, не выше.", timed=True),
             block="Разминка"),
        dict(E("Суставная разминка", [], [place], 1, "3 мин",
               "Сверху вниз: шея, плечи, локти, таз, колени, голеностоп.",
               timed=True), block="Разминка"),
    ]
    return items


def cooldown(minutes: int = 18) -> list[dict]:
    return [dict(E("Растяжка после тренировки", [], ALL_PLACES, 1,
                   f"{minutes} мин",
                   "Каждое положение держи 30–40 секунд, без рывков и боли.",
                   timed=True), block="Заминка")]


# ---------- сборка ----------

def _tune(item: dict, goal: str) -> dict:
    e = dict(item)
    if goal == "gain":
        e["note"] += " Работаешь в тяжёлом весе, последние повторы трудные."
    elif goal == "lose":
        e["note"] += " Отдых короткий, темп держишь."
    elif goal == "stretch":
        e["sets"] = max(2, e["sets"] - 1)
        e["note"] += " Амплитуда важнее веса."
    return e


def _matches(e: dict, group: str, by_primary: bool) -> bool:
    if not e["groups"]:
        return False
    return e["groups"][0] == group if by_primary else group in e["groups"]


def _pick(pool: list[dict], groups: list[str], place: str, target: int,
          goal: str, rng: random.Random, by_primary: bool = True) -> list[dict]:
    """Набирает упражнения по кругу групп, пока не наберётся target минут.

    by_primary — брать упражнение только если выбранная группа у него
    основная. Для силовой это правильно, а для кардио слишком узко:
    бёрпи и скалолаз работают на всё тело сразу.
    """
    available = {
        g: [e for e in pool
            if place in e["places"] and _matches(e, g, by_primary)]
        for g in groups
    }
    for items in available.values():
        rng.shuffle(items)

    # Упражнения без групп (общее кардио) идут первыми как база.
    chosen = [e for e in pool if place in e["places"] and not e["groups"]]
    if chosen:
        chosen = [rng.choice(chosen)]

    used = {e["name"] for e in chosen}
    minutes = sum(_minutes_of(e) for e in chosen)
    index = 0
    idle = 0

    while minutes < target and idle < len(groups):
        group = groups[index % len(groups)]
        index += 1
        nxt = next((e for e in available[group] if e["name"] not in used), None)
        if nxt is None:
            idle += 1
            continue
        idle = 0
        used.add(nxt["name"])
        chosen.append(nxt)
        minutes += _minutes_of(nxt)

    return [_tune(e, goal) for e in chosen]


def _minutes_of(e: dict) -> float:
    if e["timed"]:
        num = "".join(c for c in e["reps"] if c.isdigit())
        value = int(num) if num else 1
        per_set = value if "мин" in e["reps"] else value / 60
        return per_set * e["sets"] + 0.5 * max(e["sets"] - 1, 0)
    return e["sets"] * 0.75 + (e["sets"] - 1) * 2 + 1.5


def estimate_minutes(items: list[dict]) -> int:
    return round(sum(_minutes_of(e) for e in items))


def build(goal: str, place: str, kind: str, slot: str,
          groups: list[str] | None = None, day_index: int = 0) -> dict:
    """Собирает программу под выбранные группы мышц.

    groups — коды из GROUPS. Пусто означает «все» (для предпросмотра недели).
    """
    groups = [g for g in (groups or list(GROUPS)) if g in GROUPS]
    if not groups:
        groups = list(GROUPS)

    # Один и тот же день даёт один и тот же состав, разные дни — разный.
    rng = random.Random(f"{day_index}:{place}:{kind}:{slot}:{','.join(groups)}")

    pool = CARDIO if kind == "cardio" else STRENGTH
    target = MAIN_MINUTES.get(slot, MAIN_MINUTES["am"])
    main = _pick(pool, groups, place, target, goal, rng,
                 by_primary=(kind != "cardio"))

    if slot == "pm":
        items = warmup(place, 5)[:1] + main + cooldown(5)
    else:
        items = warmup(place) + main + cooldown()

    names = ", ".join(GROUPS[g] for g in groups).lower()
    title = f"{KINDS[kind]}: {names}"
    return {
        "title": title,
        "place": place,
        "kind": kind,
        "slot": slot,
        "groups": groups,
        "items": items,
        "minutes": estimate_minutes(items),
    }


def recovery_block(place: str) -> dict:
    """Вечерний блок на восстановление: лёгкое кардио и растяжка."""
    run = {"gym": "Дорожка в спокойном темпе",
           "home": "Бег на месте и прыжки",
           "outdoor": "Быстрая ходьба или лёгкий бег"}[place]
    items = [
        dict(E(run, [], [place], 1, "15 мин", "Ровный темп, пульс средний.",
               timed=True), block="Кардио"),
        dict(E("Планка", ["abs"], ALL_PLACES, 3, "45 сек",
               "Таз не проваливается.", timed=True)),
        dict(E("Растяжка бёдер и спины", [], ALL_PLACES, 1, "7 мин",
               "Каждое положение по 30–40 секунд.", timed=True), block="Заминка"),
    ]
    return {
        "title": "Восстановление",
        "place": place,
        "kind": "cardio",
        "slot": "pm",
        "groups": [],
        "items": items,
        "minutes": estimate_minutes(items),
    }


WEEKDAYS = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница",
            "Суббота", "Воскресенье"]


def week_plan(goal: str, place: str, kind: str, start_ordinal: int,
              schedule: dict | None = None) -> list[dict]:
    """Расписание на семь дней вперёд. Группы здесь неизвестны, берём все."""
    days = []
    for offset in range(7):
        index = start_ordinal + offset
        weekday = (start_ordinal + offset - 1) % 7
        marks = schedule[weekday] if schedule else {"am": True, "pm": True}
        morning = build(goal, place, kind, "am", None, index) if marks["am"] else None
        evening = recovery_block(place) if marks["pm"] else None
        days.append({
            "offset": offset,
            "weekday": WEEKDAYS[weekday],
            "am_title": "Основная" if morning else None,
            "am_minutes": morning["minutes"] if morning else 0,
            "pm_title": "Короткий блок" if evening else None,
            "pm_minutes": evening["minutes"] if evening else 0,
        })
    return days


def render_week(days: list[dict], place: str, kind: str) -> str:
    lines = [f"<b>План на неделю</b>\n{PLACES[place]} · {KINDS[kind]}", ""]
    total = 0
    for day in days:
        mark = "Сегодня" if day["offset"] == 0 else day["weekday"]
        if not day["am_title"] and not day["pm_title"]:
            lines.append(f"<b>{mark}</b>\n  выходной")
            continue
        rows = [f"<b>{mark}</b>"]
        if day["am_title"]:
            rows.append(f"  утро — {day['am_title']}, около {day['am_minutes']} мин")
            total += day["am_minutes"]
        if day["pm_title"]:
            rows.append(f"  вечер — {day['pm_title']}, {day['pm_minutes']} мин")
            total += day["pm_minutes"]
        lines.append("\n".join(rows))
    hours, minutes = divmod(total, 60)
    lines += ["", f"<i>За неделю — {hours} ч {minutes} мин работы. "
                  "Группы мышц выбираются перед стартом.</i>"]
    return "\n".join(lines)


def render(program: dict) -> str:
    lines = [f"<b>{program['title']}</b>\n{PLACES[program['place']]} · "
             f"около {program['minutes']} мин", ""]
    block = None
    for e in program["items"]:
        if e["block"] != block:
            block = e["block"]
            lines.append(f"<i>{block}</i>")
        count = f"{e['sets']} × {e['reps']}" if e["sets"] > 1 else e["reps"]
        lines.append(f"  • {e['name']} — {count}")
    return "\n".join(lines)
