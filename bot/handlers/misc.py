"""Вода, вес, настройка напоминаний и заявка на живого тренера."""

import logging
from datetime import date

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from .. import achievements, banter, calc, db, keyboards, programs
from ..config import ADMIN_ID, TARIFFS, TIME_LABELS
from ..parsing import float_value, int_value, time_value, weight_value

log = logging.getLogger(__name__)
router = Router()


class Ask(StatesGroup):
    time_value = State()
    water_ml = State()
    target_kg = State()
    target_weeks = State()
    edit_height = State()
    edit_weight = State()
    edit_age = State()
    new_nickname = State()


async def apply_norms(conn, tg_id: int) -> tuple[int, int]:
    """Пересчитывает норму по текущим данным профиля.

    Возвращает старую и новую калорийность, чтобы можно было сказать,
    изменилось ли что-нибудь.
    """
    row = await db.get_user(conn, tg_id)
    old = row["kcal"] or 0
    norms = calc.calculate(
        sex=row["sex"], weight_kg=row["weight_kg"], height_cm=row["height_cm"],
        age=row["age"], activity=row["activity"], goal=row["goal"],
    )
    await db.save_user(
        conn, tg_id, kcal=norms.kcal, protein=norms.protein, fat=norms.fat,
        carbs=norms.carbs, water_ml=norms.water_ml,
    )
    return old, norms.kcal


# ---------- вода ----------

async def water_text(conn, row) -> str:
    drunk = await db.water_total(conn, row["tg_id"])
    norm = row["water_ml"] or 0
    left = max(norm - drunk, 0)
    tail = ("Норма закрыта. Молодец."
            if left <= 0 else f"Осталось {banter.litres(left)} л.")
    return (
        f"Выпито <b>{banter.litres(drunk)} л</b> из "
        f"<b>{banter.litres(norm)} л</b>.\n{tail}"
    )


@router.message(F.text == "Вода")
async def water_menu(message: Message, conn) -> None:
    row = await db.get_user(conn, message.from_user.id)
    if not row or not row["kcal"]:
        await message.answer("Сначала регистрация. Жми /start.")
        return
    await message.answer(await water_text(conn, row), reply_markup=keyboards.WATER)


@router.callback_query(F.data.startswith("water:"))
async def water_add(call: CallbackQuery, conn, state: FSMContext, bot: Bot) -> None:
    value = call.data.split(":")[1]
    if value == "custom":
        await state.set_state(Ask.water_ml)
        await call.message.answer("Сколько миллилитров? Пришли число.")
        await call.answer()
        return

    await db.add_water(conn, call.from_user.id, int(value))
    row = await db.get_user(conn, call.from_user.id)
    await call.message.edit_text(
        await water_text(conn, row), reply_markup=keyboards.WATER
    )
    await call.answer(f"Записал {value} мл")
    await achievements.notify(bot, conn, call.from_user.id)


@router.message(Ask.water_ml)
async def water_custom(message: Message, state: FSMContext, conn) -> None:
    ml = int_value(message.text or "", 50, 3000)
    if ml is None:
        await message.answer("Число от 50 до 3000 миллилитров.")
        return
    await state.clear()
    await db.add_water(conn, message.from_user.id, ml)
    row = await db.get_user(conn, message.from_user.id)
    await message.answer(await water_text(conn, row), reply_markup=keyboards.WATER)


# ---------- вес ----------

def progress_text(row, history) -> str:
    lines = []
    current = row["weight_kg"]
    start = row["start_kg"] or current
    lines.append(f"Сейчас: <b>{current:g} кг</b>")
    if start != current:
        delta = current - start
        sign = "−" if delta < 0 else "+"
        lines.append(f"От старта: {sign}{abs(delta):.1f} кг".replace(".", ","))

    if row["target_kg"]:
        left = abs(current - row["target_kg"])
        lines.append(f"До цели ({row['target_kg']:g} кг): <b>{left:.1f} кг</b>"
                     .replace(".", ","))
        if row["target_date"]:
            days = (date.fromisoformat(row["target_date"]) - date.today()).days
            if days > 0:
                lines.append(f"В запасе: {days // 7} нед. {days % 7} дн.")
            else:
                lines.append("Срок вышел. Ставь новый — или признай, что цель была не та.")

    if len(history) > 1:
        lines += ["", "<i>Последние взвешивания</i>"]
        lines += [f"  {h['day']} — {h['kg']:g} кг" for h in history[-6:]]
    return "\n".join(lines)


@router.message(F.text == "Вес")
async def weight_menu(message: Message, conn) -> None:
    row = await db.get_user(conn, message.from_user.id)
    if not row or not row["kcal"]:
        await message.answer("Сначала регистрация. Жми /start.")
        return
    history = await db.weight_history(conn, message.from_user.id)
    await message.answer(
        progress_text(row, history) + "\n\nПришли вес числом — запишу и пересчитаю норму.",
        reply_markup=keyboards.PROFILE_ACTIONS,
    )


# StateFilter(None) обязателен: иначе голое число перехватывается здесь, даже
# когда бот ждёт ответ на вопрос — например, целевой вес или объём воды.
@router.message(
    StateFilter(None),
    F.text.func(lambda t: bool(t) and weight_value(t) is not None),
)
async def weight_entry(message: Message, conn, runner, bot: Bot) -> None:
    row = await db.get_user(conn, message.from_user.id)
    if not row or not row["kcal"]:
        await message.answer("Сначала регистрация. Жми /start.")
        return

    kg = weight_value(message.text)
    old_kcal = row["kcal"]
    await db.add_weight(conn, message.from_user.id, kg)

    # Норма зависит от веса, поэтому пересчитываем её при каждом взвешивании.
    norms = calc.calculate(
        sex=row["sex"], weight_kg=kg, height_cm=row["height_cm"],
        age=row["age"], activity=row["activity"], goal=row["goal"],
    )
    await db.save_user(
        conn, message.from_user.id,
        kcal=norms.kcal, protein=norms.protein, fat=norms.fat,
        carbs=norms.carbs, water_ml=norms.water_ml,
    )

    row = await db.get_user(conn, message.from_user.id)
    history = await db.weight_history(conn, message.from_user.id)
    parts = [f"Записал: <b>{kg:g} кг</b>.", "", progress_text(row, history)]
    if abs(norms.kcal - old_kcal) >= 20:
        parts += ["", f"Норму пересчитал: <b>{norms.kcal} ккал</b>, "
                      f"белка {norms.protein} г."]
    await message.answer("\n".join(parts))
    await achievements.notify(bot, conn, message.from_user.id)


# ---------- «Ещё», профиль и план на неделю ----------

@router.message(F.text == "Ещё")
async def more_menu(message: Message) -> None:
    await message.answer("Что открыть?", reply_markup=keyboards.MORE)


def profile_text(row) -> str:
    sex = "мужской" if row["sex"] == "male" else "женский"
    lines = [
        "<b>Профиль</b>",
        "",
        f"Рост: <b>{row['height_cm']:g} см</b>",
        f"Вес: <b>{row['weight_kg']:g} кг</b>",
        f"Возраст: <b>{row['age']}</b>",
        f"Пол: {sex}",
        f"Образ жизни: {calc.ACTIVITY_LABELS.get(row['activity'], '—')}",
        f"Цель занятий: <b>{calc.GOAL_LABELS.get(row['goal'], '—')}</b>",
    ]
    if row["target_kg"]:
        line = f"Цель по весу: <b>{row['target_kg']:g} кг</b>"
        if row["target_date"]:
            days = (date.fromisoformat(row["target_date"]) - date.today()).days
            line += f", осталось {days} дн." if days > 0 else ", срок прошёл"
        lines.append(line)

    place = row["pref_place"] or "gym"
    kind = row["pref_kind"] or "strength"
    lines += [
        f"Тренировки: {programs.PLACES[place]}, {programs.KINDS[kind].lower()}",
        "",
        "<b>Суточная норма</b>",
        f"{row['kcal']} ккал · Б {row['protein']} · Ж {row['fat']} · У {row['carbs']}",
        f"Вода: {row['water_ml'] / 1000:.1f} л".replace(".", ","),
        "",
        "<i>Меняешь любое поле — норму пересчитываю сразу.</i>",
    ]
    return "\n".join(lines)


async def show_profile(message: Message, conn, tg_id: int, edit: bool = False) -> None:
    row = await db.get_user(conn, tg_id)
    if not row or not row["kcal"]:
        await message.answer("Сначала регистрация. Жми /start.")
        return
    text = profile_text(row)
    if edit:
        await message.edit_text(text, reply_markup=keyboards.PROFILE_EDIT)
    else:
        await message.answer(text, reply_markup=keyboards.PROFILE_EDIT)


@router.message(F.text == "Профиль")
@router.message(Command("profile"))
async def profile_cmd(message: Message, conn) -> None:
    await show_profile(message, conn, message.from_user.id)


@router.callback_query(F.data == "more:profile")
async def profile_open(call: CallbackQuery, conn) -> None:
    await show_profile(call.message, conn, call.from_user.id, edit=True)
    await call.answer()


@router.callback_query(F.data == "more:plan")
async def plan_open(call: CallbackQuery, conn) -> None:
    row = await db.get_user(conn, call.from_user.id)
    if not row or not row["kcal"]:
        await call.answer("Сначала /start", show_alert=True)
        return
    place = row["pref_place"] or "gym"
    kind = row["pref_kind"] or "strength"
    days = programs.week_plan(
        row["goal"] or "maintain", place, kind, date.today().toordinal(),
        db.user_schedule(row),
    )
    await call.message.edit_text(
        programs.render_week(days, place, kind),
        reply_markup=keyboards.inline([
            ("Сменить дни тренировок", "sched:menu"),
            ("Сменить место и тип", "edit:place"),
            ("Начать тренировку", "w:slot:am"),
        ]),
    )
    await call.answer()


@router.callback_query(F.data == "more:times")
async def times_open(call: CallbackQuery, conn) -> None:
    row = await db.get_user(conn, call.from_user.id)
    if not row:
        await call.answer("Сначала /start", show_alert=True)
        return
    await call.message.edit_text(
        "Твоё расписание. Жми на строку, чтобы поменять время.",
        reply_markup=keyboards.times_menu(db.user_times(row)),
    )
    await call.answer()


@router.callback_query(F.data == "more:coach")
async def coach_open(call: CallbackQuery) -> None:
    await call.message.edit_text(COACH_TEXT, reply_markup=keyboards.tariffs())
    await call.answer()


# ---------- дни тренировок ----------

def schedule_text(schedule: dict) -> str:
    lines = [
        "<b>Дни тренировок</b>",
        "",
        "🏋️ основная, около двух часов.  ⚡ короткий блок, 25 минут.",
        "Жми на ячейку, чтобы включить или выключить. Можно оба, можно одно, "
        "можно выходной — как удобно.",
        "",
    ]
    for day in range(7):
        marks = schedule[day]
        if marks["am"] and marks["pm"]:
            what = "основная + короткий"
        elif marks["am"]:
            what = "основная"
        elif marks["pm"]:
            what = "короткий блок"
        else:
            what = "выходной"
        lines.append(f"<b>{db.WEEKDAYS[day]}</b> — {what}")

    total_am = len(db.days_with(schedule, "am"))
    total_pm = len(db.days_with(schedule, "pm"))
    idle = len(db.rest_days(schedule))
    lines += [
        "",
        f"<i>За неделю: основных {total_am}, коротких {total_pm}, "
        f"выходных {idle}.</i>",
    ]
    if not db.training_days(schedule):
        lines += ["", "<i>Сейчас пусто. Напоминаний о тренировках не будет, "
                      "серия стоит на месте.</i>"]
    else:
        lines += ["", "<i>Серия тренировок считается только по этим дням — "
                      "выходной её не рвёт.</i>"]
    return "\n".join(lines)


async def show_schedule(message: Message, conn, tg_id: int,
                        edit: bool = False) -> None:
    row = await db.get_user(conn, tg_id)
    if not row or not row["kcal"]:
        await message.answer("Сначала регистрация. Жми /start.")
        return
    schedule = db.user_schedule(row)
    text = schedule_text(schedule)
    markup = keyboards.schedule_menu(schedule)
    if edit:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "sched:menu")
async def schedule_open(call: CallbackQuery, conn) -> None:
    await show_schedule(call.message, conn, call.from_user.id, edit=True)
    await call.answer()


@router.message(Command("days"))
async def schedule_cmd(message: Message, conn) -> None:
    await show_schedule(message, conn, message.from_user.id)


@router.callback_query(F.data.startswith("sched:t:"))
async def schedule_toggle(call: CallbackQuery, conn, runner) -> None:
    _, _, day, slot = call.data.split(":")
    await db.toggle_slot(conn, call.from_user.id, int(day), slot)
    await runner.reschedule(call.from_user.id)
    await show_schedule(call.message, conn, call.from_user.id, edit=True)
    await call.answer()


@router.callback_query(F.data.in_({"sched:all", "sched:weekdays", "sched:none"}))
async def schedule_preset(call: CallbackQuery, conn, runner) -> None:
    preset = call.data.split(":")[1]
    if preset == "all":
        schedule = db.default_schedule()
    elif preset == "weekdays":
        schedule = {d: {"am": d < 5, "pm": d < 5} for d in range(7)}
    else:
        schedule = {d: {"am": False, "pm": False} for d in range(7)}
    await db.save_schedule(conn, call.from_user.id, schedule)
    await runner.reschedule(call.from_user.id)
    await show_schedule(call.message, conn, call.from_user.id, edit=True)
    await call.answer()


# ---------- достижения ----------

@router.message(F.text == "Достижения")
@router.message(Command("achievements"))
async def achievements_cmd(message: Message, conn) -> None:
    await show_achievements(message, conn, message.from_user.id)


@router.callback_query(F.data == "more:achievements")
async def achievements_open(call: CallbackQuery, conn) -> None:
    await show_achievements(call.message, conn, call.from_user.id, edit=True)
    await call.answer()


async def show_achievements(message: Message, conn, tg_id: int,
                            edit: bool = False) -> None:
    row = await db.get_user(conn, tg_id)
    if not row or not row["kcal"]:
        await message.answer("Сначала регистрация. Жми /start.")
        return

    values = await achievements.values_for(conn, row)
    taken = sum(a.tier_of(values.get(a.code, 0)) for a in achievements.ALL)
    total = sum(a.max_tier() for a in achievements.ALL)

    lines = [f"<b>Достижения</b> — {taken} из {total}", ""]

    # Сначала то, что уже идёт: по нему приятнее смотреть прогресс.
    started = [a for a in achievements.ALL if values.get(a.code, 0) > 0]
    untouched = [a for a in achievements.ALL if values.get(a.code, 0) == 0]

    for a in started:
        lines.append(achievements.progress_line(a, values.get(a.code, 0)))
    if untouched:
        lines += ["", "<i>Ещё не начато</i>"]
        for a in untouched:
            lines.append(f"⚪ {a.icon} <b>{a.title}</b>\n     {a.hint}")

    lines += ["", "<i>Один пропущенный день на неделю серия прощает. "
                  "Два подряд — начинаем сначала.</i>"]

    text = "\n".join(lines)
    if edit:
        await message.edit_text(text, reply_markup=keyboards.MORE)
    else:
        await message.answer(text)


# ---------- свой набор обращений ----------

def nicknames_text(row, pool: list[str], prefs: dict) -> str:
    goal = calc.GOAL_LABELS.get(row["goal"], "").lower()
    lines = [
        "<b>Как ко мне обращаться</b>",
        "",
        f"Так я зову тебя в напоминаниях. Набор подобран под цель "
        f"«{goal}» — если сменишь цель, обновится сам.",
        "",
        "Жми на строку, чтобы убрать обращение. Можно добавить своё "
        "и собрать набор с нуля.",
    ]
    if prefs["banned"]:
        lines += ["", f"<i>Убрано: {', '.join(prefs['banned'])}</i>"]
    if len(pool) == 1:
        lines += ["", "<i>Осталось одно — последнее убрать не дам, "
                      "иначе звать будет нечем.</i>"]
    return "\n".join(lines)


async def show_nicknames(message: Message, conn, tg_id: int,
                         edit: bool = False, note: str = "") -> None:
    row = await db.get_user(conn, tg_id)
    if not row or not row["kcal"]:
        await message.answer("Сначала регистрация. Жми /start.")
        return
    prefs = db.user_nicknames(row)
    pool = banter.pool_for(row["sex"], row["goal"], prefs)
    text = nicknames_text(row, pool, prefs)
    if note:
        text = f"{note}\n\n{text}"
    markup = keyboards.nicknames_menu(
        pool, prefs["custom"], bool(prefs["banned"] or prefs["custom"])
    )
    if edit:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "nick:menu")
async def nick_menu(call: CallbackQuery, conn) -> None:
    await show_nicknames(call.message, conn, call.from_user.id, edit=True)
    await call.answer()


@router.callback_query(F.data == "nick:add")
async def nick_add(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Ask.new_nickname)
    await call.message.answer(
        "Как тебя звать? Пришли одно слово.\n\n"
        "Подставляется в фразы вроде «Эй, <b>босс</b>, не забыл попить водички?» — "
        f"так что выбирай то, что там прозвучит. До {banter.MAX_CUSTOM_LEN} символов."
    )
    await call.answer()


@router.message(Ask.new_nickname)
async def nick_save(message: Message, state: FSMContext, conn) -> None:
    name, error = banter.validate_custom(message.text or "")
    if error:
        await message.answer(error)
        return
    await state.clear()
    await db.add_nickname(conn, message.from_user.id, name)
    await show_nicknames(message, conn, message.from_user.id,
                         note=f"Добавил: <b>{name}</b>.")


@router.callback_query(F.data.startswith("nick:del:"))
async def nick_delete(call: CallbackQuery, conn) -> None:
    name = call.data.split(":", 2)[2]
    row = await db.get_user(conn, call.from_user.id)
    prefs = db.user_nicknames(row)
    pool = banter.pool_for(row["sex"], row["goal"], prefs)

    # Пустой набор оставил бы бота без обращений, поэтому последнее держим.
    if len(pool) <= 1:
        await call.answer("Последнее не отдам — звать будет нечем.",
                          show_alert=True)
        return

    await db.ban_nickname(conn, call.from_user.id, name)
    await show_nicknames(call.message, conn, call.from_user.id, edit=True)
    await call.answer(f"Убрал «{name}»")


@router.callback_query(F.data == "nick:reset")
async def nick_reset(call: CallbackQuery, conn) -> None:
    await db.reset_nicknames(conn, call.from_user.id)
    await show_nicknames(call.message, conn, call.from_user.id, edit=True)
    await call.answer("Вернул стандартные")


# ---------- правка отдельных полей профиля ----------

FIELD_PROMPT = {
    "height": ("Рост в сантиметрах?", Ask.edit_height),
    "weight": ("Вес сейчас, в килограммах?", Ask.edit_weight),
    "age": ("Сколько тебе лет?", Ask.edit_age),
}
FIELD_CHOICE = {
    "sex": ("Пол?", keyboards.EDIT_SEX),
    "activity": ("Чем занят день, кроме тренировок?", keyboards.EDIT_ACTIVITY),
    "goal": ("Ради чего всё это?", keyboards.EDIT_GOAL),
    "place": ("Где обычно занимаешься и что качаешь?", keyboards.EDIT_PLACE),
}


@router.callback_query(F.data.startswith("edit:"))
async def edit_field(call: CallbackQuery, state: FSMContext) -> None:
    field = call.data.split(":")[1]
    if field in FIELD_PROMPT:
        prompt, target = FIELD_PROMPT[field]
        await state.set_state(target)
        await call.message.answer(prompt)
    elif field in FIELD_CHOICE:
        prompt, markup = FIELD_CHOICE[field]
        await call.message.answer(prompt, reply_markup=markup)
    await call.answer()


@router.callback_query(F.data.startswith("set:"))
async def set_field(call: CallbackQuery, conn, runner) -> None:
    _, field, value = call.data.split(":")
    await db.save_user(conn, call.from_user.id, **{field: value})

    if field in ("sex", "activity", "goal"):
        old, new = await apply_norms(conn, call.from_user.id)
        note = (f"Норма: <b>{new} ккал</b>"
                + (f" (было {old})" if old != new else ", без изменений"))
    else:
        note = "Запомнил."

    await call.message.edit_text(f"Готово. {note}")
    await show_profile(call.message, conn, call.from_user.id)
    await call.answer()


async def _save_number(message: Message, state: FSMContext, conn, field, value) -> None:
    await state.clear()
    await db.save_user(conn, message.from_user.id, **{field: value})
    if field == "weight_kg":
        await db.add_weight(conn, message.from_user.id, value)
    old, new = await apply_norms(conn, message.from_user.id)
    note = f"Норма: <b>{new} ккал</b>" + (f" (было {old})" if old != new else "")
    await message.answer(f"Принял. {note}")
    await show_profile(message, conn, message.from_user.id)


@router.message(Ask.edit_height)
async def edit_height(message: Message, state: FSMContext, conn) -> None:
    value = float_value(message.text or "", 100, 250)
    if value is None:
        await message.answer("Рост в сантиметрах, число от 100 до 250.")
        return
    await _save_number(message, state, conn, "height_cm", value)


@router.message(Ask.edit_weight)
async def edit_weight(message: Message, state: FSMContext, conn) -> None:
    value = float_value(message.text or "", 30, 300)
    if value is None:
        await message.answer("Вес в килограммах, число от 30 до 300.")
        return
    await _save_number(message, state, conn, "weight_kg", value)


@router.message(Ask.edit_age)
async def edit_age(message: Message, state: FSMContext, conn) -> None:
    value = int_value(message.text or "", 10, 100)
    if value is None:
        await message.answer("Возраст числом, от 10 до 100.")
        return
    await _save_number(message, state, conn, "age", value)


@router.callback_query(F.data == "prof:target")
async def change_target(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Ask.target_kg)
    await call.message.answer("До какого веса идём? Пришли число в килограммах.")
    await call.answer()


@router.message(Ask.target_kg)
async def set_target(message: Message, state: FSMContext) -> None:
    target = float_value(message.text or "", 30, 300)
    if target is None:
        await message.answer("Целевой вес числом, от 30 до 300.")
        return
    await state.update_data(target_kg=target)
    await state.set_state(Ask.target_weeks)
    await message.answer("За сколько недель? Пришли число недель.")


@router.message(Ask.target_weeks)
async def set_weeks(message: Message, state: FSMContext, conn) -> None:
    weeks = int_value(message.text or "", 2, 104)
    if weeks is None:
        await message.answer("Число недель, от 2 до 104.")
        return
    data = await state.get_data()
    await state.clear()

    from datetime import timedelta
    target_date = (date.today() + timedelta(weeks=weeks)).isoformat()
    await db.save_user(
        conn, message.from_user.id,
        target_kg=data["target_kg"], target_date=target_date,
    )
    row = await db.get_user(conn, message.from_user.id)
    pace = calc.weekly_pace(row["weight_kg"], data["target_kg"], weeks)
    text = [
        f"Цель обновлена: <b>{data['target_kg']:g} кг</b> за {weeks} нед.",
        f"Это {calc.dec(abs(pace), 2)} кг в неделю.",
    ]
    warning = calc.pace_warning(row["weight_kg"], pace)
    if warning:
        text += ["", f"⚠️ {warning}"]
    await message.answer("\n".join(text))


@router.callback_query(F.data == "prof:redo")
async def redo_profile(call: CallbackQuery, state: FSMContext) -> None:
    from .registration import start_registration
    await call.answer()
    await start_registration(call.message, state)


# ---------- напоминания ----------

@router.message(F.text == "Напоминания")
@router.message(Command("times"))
async def times_menu(message: Message, conn) -> None:
    row = await db.get_user(conn, message.from_user.id)
    if not row or not row["kcal"]:
        await message.answer("Сначала регистрация. Жми /start.")
        return
    await message.answer(
        "Твоё расписание. Жми на строку, чтобы поменять время.",
        reply_markup=keyboards.times_menu(db.user_times(row)),
    )


@router.callback_query(F.data.startswith("time:"))
async def ask_time(call: CallbackQuery, state: FSMContext) -> None:
    key = call.data.split(":")[1]
    await state.set_state(Ask.time_value)
    await state.update_data(time_key=key)
    await call.message.answer(
        f"Во сколько напоминать про «{TIME_LABELS[key]}»?\n"
        "Пришли время в виде 07:30."
    )
    await call.answer()


@router.message(Ask.time_value)
async def save_time(message: Message, state: FSMContext, conn, runner) -> None:
    value = time_value(message.text or "")
    if value is None:
        await message.answer("Время в виде 07:30, от 00:00 до 23:59.")
        return
    data = await state.get_data()
    await state.clear()
    times = await db.set_time(conn, message.from_user.id, data["time_key"], value)
    await runner.reschedule(message.from_user.id)
    await message.answer(
        f"Готово: «{TIME_LABELS[data['time_key']]}» теперь в {value}.",
        reply_markup=keyboards.times_menu(times),
    )


# ---------- работа с живым тренером ----------

COACH_TEXT = (
    "<b>Живой тренер</b>\n\n"
    "Я веду по программе и считаю цифры. Но я не вижу, как ты приседаешь.\n\n"
    "Человек видит. Смотрит твоё видео, правит технику, вытаскивает "
    "из плато — там, где бот уже бессилен.\n\n"
    "Нужен такой — выбирай формат. Свяжемся и подберём под твою цель.\n\n"
    "<i>Оплата напрямую с тренером, после знакомства. Сначала смотришь, "
    "потом решаешь.</i>"
)


@router.message(F.text == "Тренер")
async def coach_menu(message: Message) -> None:
    await message.answer(COACH_TEXT, reply_markup=keyboards.tariffs())


@router.callback_query(F.data == "coach:back")
async def coach_back(call: CallbackQuery) -> None:
    await call.message.edit_text(
        "Выбирай формат:", reply_markup=keyboards.tariffs()
    )
    await call.answer()


@router.callback_query(F.data.startswith("coach:send:"))
async def coach_send(call: CallbackQuery, conn, bot: Bot) -> None:
    key = call.data.split(":")[2]
    tariff = TARIFFS.get(key)
    if not tariff:
        await call.answer("Такого тарифа нет.", show_alert=True)
        return

    user = call.from_user
    contact = f"@{user.username}" if user.username else f"id{user.id}"
    await db.add_lead(conn, user.id, user.username, key, contact)

    row = await db.get_user(conn, user.id)
    if ADMIN_ID:
        goal = calc.GOAL_LABELS.get(row["goal"] if row else "", "не указана")
        details = (
            f"<b>Заявка на тренера</b>\n\n"
            f"Тариф: {tariff['title']} — {tariff['price']}\n"
            f"Клиент: {contact} ({user.full_name})\n"
        )
        if row and row["kcal"]:
            details += (
                f"Цель: {goal}\n"
                f"Вес: {row['weight_kg']:g} кг"
                + (f", цель {row['target_kg']:g} кг" if row["target_kg"] else "")
                + f"\nРост: {row['height_cm']:g} см, возраст: {row['age']}\n"
                f"Норма: {row['kcal']} ккал"
            )
        try:
            await bot.send_message(ADMIN_ID, details)
        except Exception:
            log.exception("Не смог отправить заявку админу")

    await call.message.edit_text(
        f"Принял: <b>{tariff['title']}</b>.\n\n"
        "Напишем в течение дня и подберём тренера под твою цель. "
        "Отвечать будешь прямо здесь, в Telegram."
    )
    await call.answer()


@router.callback_query(F.data.startswith("coach:"))
async def coach_details(call: CallbackQuery) -> None:
    key = call.data.split(":")[1]
    tariff = TARIFFS.get(key)
    if not tariff:
        await call.answer()
        return
    await call.message.edit_text(
        f"<b>{tariff['title']}</b> — {tariff['price']}\n\n{tariff['about']}\n\n"
        "Оставишь заявку — тренер получит её вместе с твоей целью, весом и нормой. "
        "Не придётся объяснять всё заново.",
        reply_markup=keyboards.confirm_lead(key),
    )
    await call.answer()


@router.message(Command("help"))
async def help_cmd(message: Message) -> None:
    await message.answer(
        "<b>Что я умею</b>\n\n"
        "• <b>Тренировка</b> — собираю программу под цель, место и инвентарь, "
        "веду по подходам, держу отдых\n"
        "• <b>Еда</b> — пишешь «гречка 150 г», БЖУ и остаток нормы мои\n"
        "• <b>Сегодня</b> — сводка по калориям, БЖУ и воде\n"
        "• <b>Вода</b> — добавить выпитое\n"
        "• <b>Вес</b> — прислать число, посмотреть путь к цели\n"
        "• <b>Ещё</b> — достижения, профиль, дни тренировок, план на неделю, "
        "напоминания, тренер\n\n"
        "Дни тренировок настраиваются как удобно: в один день основная плюс "
        "короткий блок, в другой только короткий, в третий выходной. "
        "Серия считается только по выбранным дням.\n\n"
        "Достижения растут ступенями: взял 7 дней подряд — значок повысился, "
        "планка сдвинулась на 14, и семь уже в зачёте.\n\n"
        "В профиле правится любое поле: рост, вес, возраст, пол, образ жизни, "
        "цель, место тренировок. Норму пересчитываю сразу.\n\n"
        "Не нравится, как я тебя зову? «Ещё» → «Как ко мне обращаться». "
        "Лишнее убирается, своё добавляется.\n\n"
        "/profile — профиль, /times — напоминания, /reset — начать заново",
        reply_markup=keyboards.MAIN_MENU,
    )
