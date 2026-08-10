"""Проверка логики без Telegram: расчёты, программы, база, разбор текста.

Запуск: .venv\\Scripts\\python.exe selfcheck.py
Токен для этого не нужен.
"""

import asyncio
import os
import sys

os.environ.setdefault("BOT_TOKEN", "0:selfcheck")
os.environ.setdefault("ADMIN_ID", "1")

from bot import calc, db, programs  # noqa: E402
from bot.parsing import food_line, time_value, weight_value  # noqa: E402

ok = True


def check(label, got, want):
    global ok
    good = got == want
    ok = ok and good
    print(f"{'ok  ' if good else 'FAIL'} {label}: {got!r}" + ("" if good else f" != {want!r}"))


def approx(label, got, want, tol=1):
    global ok
    good = abs(got - want) <= tol
    ok = ok and good
    print(f"{'ok  ' if good else 'FAIL'} {label}: {got}" + ("" if good else f" != ~{want}"))


print("--- расчёт нормы ---")
# Мужчина 27 лет, 182 см, 88 кг, сидячая работа, похудение.
n = calc.calculate("male", 88, 182, 27, "sedentary", "lose")
approx("базовый обмен", n.bmr, 1888, 2)
approx("коэффициент", n.factor, 1.525, 0.001)
approx("норма ккал", n.kcal, 2303, 5)
approx("белок 2 г/кг", n.protein, 176, 1)
approx("жир 0,9 г/кг", n.fat, 79, 1)
approx("вода", n.water_ml, 3140, 50)
# Углеводы должны добирать остаток калорий.
approx("калории сходятся",
       n.protein * 4 + n.fat * 9 + n.carbs * 4, n.kcal, 6)

w = calc.calculate("female", 60, 165, 30, "on_feet", "gain")
print(f"     женщина, набор: {w.kcal} ккал, Б{w.protein} Ж{w.fat} У{w.carbs}")
approx("калории сходятся (2)",
       w.protein * 4 + w.fat * 9 + w.carbs * 4, w.kcal, 6)

print("\n--- темп и предупреждения ---")
approx("темп 10 кг за 17 недель", calc.weekly_pace(88, 78, 17), 0.588, 0.01)
check("быстрый темп ловится", calc.pace_warning(88, 1.5) is not None, True)
check("нормальный темп молчит", calc.pace_warning(88, 0.6), None)

print("\n--- разбор текста ---")
check("гречка 150 г", food_line("гречка 150 г"), ("гречка", 150.0))
check("куриная грудка 200г", food_line("куриная грудка 200г"), ("куриная грудка", 200.0))
check("творог 5% 180 грамм", food_line("творог 5% 180 грамм"), ("творог 5%", 180.0))
check("голое число не еда", food_line("85"), None)
check("вес 85,4", weight_value("85,4"), 85.4)
check("вес вне диапазона", weight_value("500"), None)
check("время 7:30", time_value("7:30"), "07:30")
check("время 07.30", time_value("07.30"), "07:30")
check("время 25:00", time_value("25:00"), None)

print("\n--- программы тренировок ---")
for place in ("gym", "home", "outdoor"):
    for kind in ("strength", "cardio"):
        for day in (0, 1):
            p = programs.build("lose", place, kind, "am", None, day)
            if day == 0:
                print(f"     {place:8} {kind:8}: {p['minutes']:>3} мин, "
                      f"{len(p['items'])} упражнений")
            if not 100 <= p["minutes"] <= 145:
                ok = False
                print(f"FAIL {place}/{kind}/день {day}: {p['minutes']} мин, "
                      "ждали 100–145")

# Вечером два режима: восстановление и силовой добор по группам.
rec = programs.recovery_block("home")
print(f"     вечер, восстановление: {rec['minutes']} мин")
if not 15 <= rec["minutes"] <= 40:
    ok = False
    print(f"FAIL восстановление вне 15–40 мин: {rec['minutes']}")

short = programs.build("lose", "home", "strength", "pm", ["abs", "glutes"], 0)
print(f"     вечер, силовой добор: {short['minutes']} мин")
if not 15 <= short["minutes"] <= 45:
    ok = False
    print(f"FAIL вечерний силовой вне 15–45 мин: {short['minutes']}")

def names_of(program):
    return [e["name"] for e in program["items"]]


day_a = programs.build("gain", "gym", "strength", "am", ["chest", "back"], 0)
day_b = programs.build("gain", "gym", "strength", "am", ["chest", "back"], 1)
check("состав меняется день ото дня", names_of(day_a) != names_of(day_b), True)
# Один и тот же день должен давать один и тот же состав, иначе программа
# будет прыгать при каждом открытии.
day_a2 = programs.build("gain", "gym", "strength", "am", ["chest", "back"], 0)
check("в один день состав стабилен", names_of(day_a), names_of(day_a2))
check("есть ссылка на технику",
      programs.build("lose", "gym", "strength", "am")["items"][2]["video"]
      .startswith("http"), True)

print("\n--- выбор групп мышц ---")
for place in ("gym", "home", "outdoor"):
    for code in programs.GROUPS:
        # Считаем только те, где группа основная — по ним идёт подбор.
        pool = [e for e in programs.STRENGTH
                if place in e["places"] and e["groups"][0] == code]
        if len(pool) < 2:
            ok = False
            print(f"FAIL мало упражнений: {place}/{code} — {len(pool)}")
print("ok   на каждую группу есть упражнения во всех трёх местах")

# Программа должна задеть каждую выбранную группу, а не только первую.
for combo in (["chest", "back"], ["legs", "abs"],
              ["chest", "back", "shoulders", "arms"],
              list(programs.GROUPS)):
    for place in ("gym", "home", "outdoor"):
        prog = programs.build("gain", place, "strength", "am", combo, 3)
        covered = set()
        for e in prog["items"]:
            covered |= set(e["groups"])
        missed = set(combo) - covered
        if missed:
            ok = False
            print(f"FAIL {place}, не задеты группы: {missed}")
print("ok   все выбранные группы получают нагрузку")

# Лишние группы попадать не должны — иначе выбор теряет смысл.
# В силовой основная группа каждого упражнения обязана быть из выбранных.
# Побочные допустимы: подтягивания задевают руки, и это нормально.
for combo in (["chest", "arms"], ["back", "legs"], ["abs", "glutes"]):
    for place in ("gym", "home", "outdoor"):
        prog = programs.build("gain", place, "strength", "am", combo, 5)
        wrong = [e["name"] for e in prog["items"]
                 if e["block"] == "Основной блок" and e["groups"]
                 and e["groups"][0] not in combo]
        if wrong:
            ok = False
            print(f"FAIL {place}/{combo}: чужая основная группа у {wrong}")
print("ok   основная группа упражнения всегда из выбранных")

check("две группы — минимум", programs.MIN_GROUPS, 2)
check("в названии видны группы",
      "грудь" in programs.build("gain", "gym", "strength", "am",
                                ["chest", "back"], 0)["title"], True)

# Программа целиком уезжает в базу через JSON — проверяем, что уложится.
import json as _json  # noqa: E402
_json.dumps(programs.build("gain", "gym", "strength", "am",
                           ["chest", "legs"], 0), ensure_ascii=False)
_json.dumps(programs.recovery_block("home"), ensure_ascii=False)
print("ok   программа сохраняется в базу без потерь")

print("\n--- свойские обращения ---")
from bot import banter  # noqa: E402

for sex in ("male", "female"):
    for goal in ("lose", "gain", "stretch", "maintain"):
        pool = banter.NICKNAMES[(sex, goal)]
        if len(pool) < 5:
            ok = False
            print(f"FAIL мало прозвищ для {sex}/{goal}: {len(pool)}")
print("ok   прозвища есть для всех восьми пар пол-цель")

# Обращения не должны пересекаться между целями — иначе смысл теряется.
check("набор и похудение обращаются по-разному",
      set(banter.GAIN_MALE) & set(banter.LOSE_MALE), set())
check("«худышка» не попала в словарь",
      any("худыш" in n for pool in banter.NICKNAMES.values() for n in pool), False)

# Род должен совпадать: женские фразы не говорят «не забыл».
for _ in range(60):
    f = banter.water_opener("female", "lose")
    if "забыл?" in f or "забыл " in f:
        ok = False
        print(f"FAIL мужской род в женской фразе: {f}")
    m = banter.meal_opener("male", "gain", "lunch")
    if "отложила" in m or "забыла" in m:
        ok = False
        print(f"FAIL женский род в мужской фразе: {m}")
print("ok   род в фразах совпадает с полом")

# Шаблоны должны подставляться полностью, без остатков вида {n}.
for sex in ("male", "female"):
    for goal in ("lose", "gain"):
        for meal in ("breakfast", "lunch", "dinner"):
            for text in (banter.meal_opener(sex, goal, meal),
                         banter.water_opener(sex, goal),
                         banter.protein_nudge(sex, goal)):
                if "{" in text or "}" in text:
                    ok = False
                    print(f"FAIL незакрытый шаблон: {text}")
print("ok   шаблоны подставляются без остатков")

print(f"     пример мужчина/масса: {banter.meal_opener('male', 'gain', 'lunch')}")
print(f"     пример женщина/похудение: {banter.water_opener('female', 'lose')}")
print(f"     пример мужчина/растяжка: {banter.meal_opener('male', 'stretch', 'dinner')}")

# Фразы начинают сообщение, поэтому первая буква должна быть заглавной.
for sex in ("male", "female"):
    for goal in ("lose", "gain", "stretch", "maintain"):
        for text in (banter.meal_opener(sex, goal, "lunch"),
                     banter.water_opener(sex, goal),
                     banter.protein_nudge(sex, goal)):
            if text[0].islower():
                ok = False
                print(f"FAIL строчная буква в начале: {text}")
print("ok   фразы начинаются с заглавной")

print("\n--- серии с прощением пропуска ---")
from bot import achievements as ach  # noqa: E402
from datetime import date as _d, timedelta as _td  # noqa: E402

TODAY = _d(2026, 8, 10)


def days_ago(*offsets):
    """Список дат по числу дней назад от опорной даты."""
    return sorted((TODAY - _td(days=o)).isoformat() for o in offsets)


check("пустая история — нуль", ach.streak([], TODAY), 0)
check("только сегодня", ach.streak(days_ago(0), TODAY), 1)
check("три дня подряд", ach.streak(days_ago(0, 1, 2), TODAY), 3)
# Сегодня ещё идёт: его отсутствие серию не рвёт.
check("вчера и позавчера, сегодня пусто",
      ach.streak(days_ago(1, 2, 3), TODAY), 3)
# Один пропуск внутри серии прощается.
check("пропуск на третий день прощён",
      ach.streak(days_ago(1, 2, 4, 5), TODAY), 4)
# Два пропуска подряд рвут серию.
check("два пропуска подряд рвут",
      ach.streak(days_ago(1, 2, 5, 6), TODAY), 2)
# Второй пропуск раньше чем через 7 дней тоже рвёт.
check("два прощения в одном окне не дадим",
      ach.streak(days_ago(1, 3, 5, 7), TODAY), 2)
# А вот через восемь дней прощение снова доступно.
check("прощение обновляется через неделю",
      ach.streak(days_ago(1, 2, 3, 4, 5, 6, 7, 8, 10), TODAY), 9)

print("     недельные серии:")
check("нет взвешиваний", ach.week_streak([], TODAY), 0)
check("три недели подряд",
      ach.week_streak(days_ago(0, 7, 14), TODAY), 3)
# Текущая неделя может быть ещё не закрыта — отсчёт идёт от прошлой.
check("текущая неделя пуста, прошлые есть",
      ach.week_streak(days_ago(7, 14, 21), TODAY), 3)
check("разрыв в неделях",
      ach.week_streak(days_ago(0, 7, 21), TODAY), 2)

print("\n--- серии с выходными по расписанию ---")
# 10 августа 2026 — понедельник. Тренировки только пн, ср, пт.
MON_WED_FRI = {0, 2, 4}
check("опорная дата — понедельник", TODAY.weekday(), 0)
# Тренировался пн, пт, ср прошлой недели — выходные между ними не в счёт.
check("выходные не рвут серию",
      ach.streak(days_ago(0, 3, 5), TODAY, expected=MON_WED_FRI), 3)
# А вот пропуск запланированной среды — уже пропуск, но первый прощается.
check("пропуск запланированного дня прощается",
      ach.streak(days_ago(0, 5, 7), TODAY, expected=MON_WED_FRI), 3)
# Без расписания те же данные дают куда более короткую серию.
check("без расписания серия короче",
      ach.streak(days_ago(0, 3, 5), TODAY), 1)

print("\n--- расписание по дням ---")
import bot.db as dbm  # noqa: E402

default = dbm.default_schedule()
check("по умолчанию семь дней", len(default), 7)
check("по умолчанию всё включено", len(dbm.training_days(default)), 7)
check("выходных по умолчанию нет", dbm.rest_days(default), [])

mine = dbm.default_schedule()
mine[1]["am"] = False            # вторник только короткий
mine[5] = {"am": False, "pm": False}   # суббота выходной
mine[6] = {"am": False, "pm": False}   # воскресенье выходной
check("основных четыре", len(dbm.days_with(mine, "am")), 4)
check("коротких пять", len(dbm.days_with(mine, "pm")), 5)
check("выходных два", dbm.rest_days(mine), [5, 6])
check("тренировочных дней пять", sorted(dbm.training_days(mine)), [0, 1, 2, 3, 4])

empty = {d: {"am": False, "pm": False} for d in range(7)}
check("пустое расписание — ни одного дня", dbm.training_days(empty), set())
check("пустое расписание — все выходные", len(dbm.rest_days(empty)), 7)

print("\n--- ступени достижений ---")
fire = ach.BY_CODE["workout_streak"]
check("ноль — ступеней нет", fire.tier_of(0), 0)
check("шесть дней — первая ступень", fire.tier_of(6), 1)
check("семь дней — вторая", fire.tier_of(7), 2)
check("сто дней — все ступени", fire.tier_of(100), fire.max_tier())
check("следующая планка после 7", fire.next_target(7), 14)
check("выше потолка планки нет", fire.next_target(100), None)
check("прогресс не обнуляется",
      fire.tier_of(14) > fire.tier_of(13), True)

check("проценты к цели", ach.goal_percent(88, 83, 78), 50)
check("цель достигнута", ach.goal_percent(88, 78, 78), 100)
check("ушли ниже цели — не больше ста", ach.goal_percent(88, 70, 78), 100)
check("без цели — ноль", ach.goal_percent(88, 85, None), 0)

for a in ach.ALL:
    if list(a.tiers) != sorted(a.tiers):
        ok = False
        print(f"FAIL ступени не по возрастанию: {a.code}")
    if len(a.tiers) > len(ach.TIER_ICONS):
        ok = False
        print(f"FAIL ступеней больше, чем значков: {a.code}")
print(f"ok   достижений {len(ach.ALL)}, "
      f"всего ступеней {sum(a.max_tier() for a in ach.ALL)}")
line = ach.progress_line(fire, 5)
check("в строке прогресса есть полоса", "▰" in line or "▱" in line, True)
check("поздравление называет уровень",
      "уровень 2" in ach.congratulation(fire, 2, 7), True)

print("\n--- цены на услуги ---")
from bot.config import (  # noqa: E402
    PERIODS, SERVICES, money, period_label, price_for)

check("услуг три", len(SERVICES), 3)
check("консультация бесплатна", SERVICES["consult"]["price_month"], 0)
check("у консультации нет сроков", SERVICES["consult"]["periods"], False)
check("ведение 5000", SERVICES["coaching"]["price_month"], 5000)
check("ведение с питанием 7000", SERVICES["coaching_plus"]["price_month"], 7000)

print("     ведение онлайн:")
for months, want_total, want_disc in ((1, 5000, 0), (3, 13500, 10),
                                      (6, 25500, 15), (12, 45000, 25)):
    p = price_for("coaching", months)
    print(f"       {period_label(months):10} {money(p['total']):>10}"
          f"   скидка {p['discount']}%   экономия {money(p['saved'])}")
    check(f"  {months} мес — сумма", p["total"], want_total)
    check(f"  {months} мес — скидка", p["discount"], want_disc)

print("     ведение с питанием:")
for months, want_total in ((1, 7000), (3, 18900), (6, 35700), (12, 63000)):
    p = price_for("coaching_plus", months)
    print(f"       {period_label(months):10} {money(p['total']):>10}"
          f"   экономия {money(p['saved'])}")
    check(f"  {months} мес — сумма", p["total"], want_total)

check("скидки заданы для всех сроков", len(PERIODS), 4)
check("пакет всегда выгоднее помесячной оплаты",
      all(price_for("coaching", m)["per_month"] < 5000
          for m, d in PERIODS if d), True)
check("формат денег", money(45000), "45 000 ₽")
check("склонение месяцев", period_label(3), "3 месяца")
check("год словом", period_label(12), "год")

print("\n--- свой набор обращений ---")
base = banter.defaults("male", "gain")
check("без правок набор стандартный",
      banter.pool_for("male", "gain", {"banned": [], "custom": []}), base)
check("убранное исчезает",
      base[0] in banter.pool_for("male", "gain", {"banned": [base[0]]}), False)
check("своё появляется",
      "босс" in banter.pool_for("male", "gain", {"custom": ["босс"]}), True)
check("свои не дублируют стандартные",
      banter.pool_for("male", "gain", {"custom": [base[0]]}).count(base[0]), 1)
check("пустой набор не оставляем",
      banter.pool_for("male", "gain", {"banned": base}), [banter.FALLBACK])
check("выбор идёт из своих",
      banter.nickname("male", "gain", {"banned": base, "custom": ["босс"]}), "босс")

print("     проверка своих обращений:")
for text, want_ok in [("босс", True), ("мой капитан", True), ("qwe", True),
                      ("а", False), ("", False), ("х" * 25, False),
                      ("<b>злой</b>", False), ("босс123", False),
                      ("  БОСС  ", True)]:
    name, err = banter.validate_custom(text)
    got_ok = err is None
    if got_ok != want_ok:
        ok = False
        print(f"FAIL {text!r}: ожидали {'принять' if want_ok else 'отклонить'}")
check("регистр и пробелы чистятся", banter.validate_custom("  БОСС ")[0], "босс")
print("ok   проверка своих обращений отработала")

# Telegram обрывает callback_data длиннее 64 байт — кнопки бы сломались.
longest = "х" * banter.MAX_CUSTOM_LEN
payload = f"nick:del:{longest}".encode("utf-8")
check("кнопка удаления влезает в лимит Telegram", len(payload) <= 64, True)
for pool in banter.NICKNAMES.values():
    for n in pool:
        if len(f"nick:del:{n}".encode("utf-8")) > 64:
            ok = False
            print(f"FAIL слишком длинное прозвище для кнопки: {n}")

print("\n--- дроби не ломают предложения ---")
check("литры с запятой", banter.litres(3150), "3,1")
check("целые литры", banter.litres(2000), "2,0")
check("дробь через запятую", calc.dec(0.588, 2), "0,59")

warn_text = calc.pace_warning(88, 1.5)
# Главное: точки между предложениями остались точками, а не стали запятыми.
check("предложение не разорвано", ". Похудеешь" in warn_text, True)
check("второе предложение цело", ". Растяни срок." in warn_text, True)
check("дробь в предупреждении с запятой", "1,50" in warn_text, True)
gain_warn = calc.pace_warning(88, -1.5)
check("точки во втором предупреждении целы", ". Сбавь темп." in gain_warn, True)

print("\n--- план на неделю ---")
from datetime import date as _date  # noqa: E402
week = programs.week_plan("lose", "gym", "strength", _date.today().toordinal())
check("семь дней", len(week), 7)
check("первый день сегодняшний", week[0]["offset"], 0)
# Состав в плане недели не расписывается: группы выбираются перед стартом.
check("утро помечено как основная", week[0]["am_title"], "Основная")
check("вечер каждый день короткий",
      all(15 <= d["pm_minutes"] <= 40 for d in week), True)
check("названия дней недели различаются",
      len({d["weekday"] for d in week}), 7)
rendered = programs.render_week(week, "gym", "strength")
check("в тексте есть «Сегодня»", "Сегодня" in rendered, True)


async def db_check():
    global ok
    print("\n--- база ---")
    db.DB_PATH = ":memory:"
    import bot.db as m
    m.DB_PATH = ":memory:"
    conn = await m.connect()
    await m.init(conn)

    await m.save_user(conn, 1, sex="male", age=27, height_cm=182, weight_kg=88,
                      start_kg=88, activity="sedentary", goal="lose",
                      kcal=2300, protein=176, fat=79, carbs=221, water_ml=3150)
    row = await m.get_user(conn, 1)
    check("пользователь сохранён", row["kcal"], 2300)

    await m.save_user(conn, 1, weight_kg=85.4)
    row = await m.get_user(conn, 1)
    check("обновление поля", row["weight_kg"], 85.4)
    check("остальное не затёрлось", row["age"], 27)

    await m.add_meal(conn, 1, "гречка", 150, 185, 6.2, 1.7, 37.5)
    await m.add_meal(conn, 1, "грудка", 200, 220, 46.4, 3.6, 0)
    totals = await m.day_totals(conn, 1)
    approx("сумма калорий", totals["kcal"], 405, 0.1)
    approx("сумма белка", totals["protein"], 52.6, 0.1)

    removed = await m.undo_last_meal(conn, 1)
    check("отмена записи", removed["name"], "грудка")
    totals = await m.day_totals(conn, 1)
    approx("после отмены", totals["kcal"], 185, 0.1)

    total = await m.add_water(conn, 1, 250)
    total = await m.add_water(conn, 1, 500)
    check("вода суммируется", total, 750)

    await m.add_weight(conn, 1, 85.4)
    await m.add_weight(conn, 1, 85.0)   # то же число — перезапись за день
    hist = await m.weight_history(conn, 1)
    check("одна запись веса за день", len(hist), 1)
    check("вес перезаписан", hist[0]["kg"], 85.0)

    prog = programs.build("lose", "gym", "strength", "am")
    await m.start_session(conn, 1, "gym", "strength", "am", prog)
    s = await m.get_session(conn, 1)
    check("сессия читается", s["program"]["title"], prog["title"])
    check("сессия с нуля", (s["ex_index"], s["set_index"]), (0, 0))
    await m.update_session(conn, 1, 2, 1)
    s = await m.get_session(conn, 1)
    check("прогресс сессии", (s["ex_index"], s["set_index"]), (2, 1))

    from datetime import timedelta
    now = m.now()
    tid = await m.add_timer(conn, 1, now + timedelta(seconds=120),
                            now + timedelta(seconds=90), {"ex_index": 2})
    pend = await m.pending_timers(conn)
    check("таймер в базе", len(pend), 1)
    check("payload читается", pend[0]["payload"]["ex_index"], 2)
    await m.close_timer(conn, tid)
    check("таймер закрыт", len(await m.pending_timers(conn)), 0)

    times = await m.set_time(conn, 1, "lunch", "13:15")
    check("время сохранено", times["lunch"], "13:15")
    row = await m.get_user(conn, 1)
    check("время читается обратно", m.user_times(row)["lunch"], "13:15")
    check("остальные времена на месте", m.user_times(row)["workout_am"], "07:30")

    await m.save_user(conn, 1, pref_place="home", pref_kind="cardio")
    row = await m.get_user(conn, 1)
    check("место тренировок сохранено", row["pref_place"], "home")
    check("тип тренировок сохранён", row["pref_kind"], "cardio")

    row = await m.get_user(conn, 1)
    check("правок обращений сначала нет",
          m.user_nicknames(row), {"banned": [], "custom": []})
    await m.ban_nickname(conn, 1, "бугай")
    await m.add_nickname(conn, 1, "босс")
    row = await m.get_user(conn, 1)
    prefs = m.user_nicknames(row)
    check("убранное записалось", prefs["banned"], ["бугай"])
    check("своё записалось", prefs["custom"], ["босс"])
    # Своё убирается насовсем, а не прячется в список убранных.
    await m.ban_nickname(conn, 1, "босс")
    prefs = m.user_nicknames(await m.get_user(conn, 1))
    check("своё удаляется полностью", prefs["custom"], [])
    check("и не попадает в убранные", "босс" in prefs["banned"], False)
    # Возврат ранее убранного стандартного.
    await m.add_nickname(conn, 1, "бугай")
    prefs = m.user_nicknames(await m.get_user(conn, 1))
    check("убранное возвращается", prefs["banned"], [])
    await m.ban_nickname(conn, 1, "шкаф")
    await m.reset_nicknames(conn, 1)
    prefs = m.user_nicknames(await m.get_user(conn, 1))
    check("сброс чистит всё", prefs, {"banned": [], "custom": []})

    print("     расписание:")
    row = await m.get_user(conn, 1)
    check("новичку доступны все дни", len(m.training_days(m.user_schedule(row))), 7)
    await m.toggle_slot(conn, 1, 1, "am")      # вторник без основной
    await m.toggle_slot(conn, 1, 5, "am")
    await m.toggle_slot(conn, 1, 5, "pm")      # суббота выходной
    row = await m.get_user(conn, 1)
    sched = m.user_schedule(row)
    check("вторник без основной", sched[1]["am"], False)
    check("вторник с коротким", sched[1]["pm"], True)
    check("суббота выходной", m.rest_days(sched), [5])
    check("остальные дни целы", sched[0], {"am": True, "pm": True})
    # Повторное нажатие возвращает как было.
    await m.toggle_slot(conn, 1, 1, "am")
    check("переключатель работает в обе стороны",
          m.user_schedule(await m.get_user(conn, 1))[1]["am"], True)

    print("     тренировки и достижения:")
    await m.log_workout(conn, 1, "am", "gym", "strength", 112)
    await m.log_workout(conn, 1, "pm", "home", "cardio", 25)
    counts = await m.counters(conn, 1)
    check("тренировки посчитаны", counts["workouts"], 2)
    check("минуты сложены", counts["minutes"], 137)
    check("места посчитаны", counts["places"], 2)
    check("дней с тренировкой один", len(await m.workout_days(conn, 1)), 1)

    # Белковый день засчитывается от 90% нормы, не раньше.
    await m.add_meal(conn, 1, "творог", 200, 200, 36.0, 2.0, 6.0)
    days = await m.protein_days(conn, 1, 40)
    check("белок 42 из 40 — день в зачёте", len(days), 1)
    days = await m.protein_days(conn, 1, 200)
    check("белок 42 из 200 — не в зачёте", len(days), 0)

    await m.add_water(conn, 1, 2500)
    check("день воды в зачёте", len(await m.water_days(conn, 1, 3000)), 1)
    check("день воды не добран", len(await m.water_days(conn, 1, 5000)), 0)

    check("взятых ступеней пока нет", await m.unlocked(conn, 1), {})
    await m.unlock(conn, 1, "workout_streak", 1)
    await m.unlock(conn, 1, "workout_streak", 1)   # повтор не должен дублировать
    await m.unlock(conn, 1, "workout_streak", 2)
    check("держим наивысшую ступень",
          (await m.unlocked(conn, 1))["workout_streak"], 2)

    # Сквозной сценарий: check находит новые ступени и не выдаёт их дважды.
    row = await m.get_user(conn, 1)
    fresh = await ach.check(conn, row)
    codes = {a.code for a, _, _ in fresh}
    check("новые ступени найдены", bool(codes), True)
    check("повторно те же не выдаются", await ach.check(conn, row), [])

    await m.add_lead(conn, 1, "anatoly", "coaching", "@anatoly")
    cur = await conn.execute("SELECT COUNT(*) c FROM leads")
    check("заявка записана", (await cur.fetchone())["c"], 1)

    await conn.close()


async def migration_check():
    """База, созданная старой версией, должна доехать до новой схемы."""
    global ok
    print("\n--- миграция старой базы ---")
    import aiosqlite
    import bot.db as m

    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    # Схема без pref_place и pref_kind — как было до этой правки.
    await conn.execute(
        "CREATE TABLE users (tg_id INTEGER PRIMARY KEY, kcal INTEGER,"
        " times_json TEXT, weigh_in TEXT, created_at TEXT)"
    )
    await conn.execute("INSERT INTO users (tg_id, kcal) VALUES (1, 2300)")
    await conn.commit()

    await m.init(conn)
    cur = await conn.execute("PRAGMA table_info(users)")
    columns = {r["name"] for r in await cur.fetchall()}
    check("колонка pref_place добавлена", "pref_place" in columns, True)
    check("колонка pref_kind добавлена", "pref_kind" in columns, True)
    check("колонка nicknames_json добавлена", "nicknames_json" in columns, True)
    check("колонка schedule_json добавлена", "schedule_json" in columns, True)

    cur = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r["name"] for r in await cur.fetchall()}
    check("таблица workouts создана", "workouts" in tables, True)
    check("таблица achievements создана", "achievements" in tables, True)
    cur = await conn.execute("SELECT kcal FROM users WHERE tg_id = 1")
    check("старые данные на месте", (await cur.fetchone())["kcal"], 2300)

    await m.init(conn)   # повторный запуск не должен падать
    print("ok   повторная миграция проходит")
    await conn.close()


asyncio.run(db_check())
asyncio.run(migration_check())

print("\n--- импорт обработчиков ---")
try:
    from bot.handlers import build_router
    router = build_router()
    print("ok   роутеры собираются")
except Exception as err:
    ok = False
    print(f"FAIL роутеры не собрались: {err!r}")

print("\n" + ("ВСЁ ПРОШЛО" if ok else "ЕСТЬ ОШИБКИ — см. строки FAIL"))
sys.exit(0 if ok else 1)
