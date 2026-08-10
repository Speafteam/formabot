"""Вода, вес, настройка напоминаний и заявка на живого тренера."""

import logging
from datetime import date

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from .. import calc, db, keyboards, programs
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
    return (
        f"Выпито <b>{drunk / 1000:.1f} л</b> из <b>{norm / 1000:.1f} л</b>.\n"
        f"Осталось {left / 1000:.1f} л."
    ).replace(".", ",")


@router.message(F.text == "Вода")
async def water_menu(message: Message, conn) -> None:
    row = await db.get_user(conn, message.from_user.id)
    if not row or not row["kcal"]:
        await message.answer("Сначала пройдём регистрацию — отправьте /start.")
        return
    await message.answer(await water_text(conn, row), reply_markup=keyboards.WATER)


@router.callback_query(F.data.startswith("water:"))
async def water_add(call: CallbackQuery, conn, state: FSMContext) -> None:
    value = call.data.split(":")[1]
    if value == "custom":
        await state.set_state(Ask.water_ml)
        await call.message.answer("Сколько миллилитров добавить? Пришлите число.")
        await call.answer()
        return

    await db.add_water(conn, call.from_user.id, int(value))
    row = await db.get_user(conn, call.from_user.id)
    await call.message.edit_text(
        await water_text(conn, row), reply_markup=keyboards.WATER
    )
    await call.answer(f"Записал {value} мл")


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
                lines.append("Срок цели уже прошёл — поставьте новый.")

    if len(history) > 1:
        lines += ["", "<i>Последние взвешивания</i>"]
        lines += [f"  {h['day']} — {h['kg']:g} кг" for h in history[-6:]]
    return "\n".join(lines)


@router.message(F.text == "Вес")
async def weight_menu(message: Message, conn) -> None:
    row = await db.get_user(conn, message.from_user.id)
    if not row or not row["kcal"]:
        await message.answer("Сначала пройдём регистрацию — отправьте /start.")
        return
    history = await db.weight_history(conn, message.from_user.id)
    await message.answer(
        progress_text(row, history) + "\n\nПришли новый вес числом, чтобы записать.",
        reply_markup=keyboards.PROFILE_ACTIONS,
    )


# StateFilter(None) обязателен: иначе голое число перехватывается здесь, даже
# когда бот ждёт ответ на вопрос — например, целевой вес или объём воды.
@router.message(
    StateFilter(None),
    F.text.func(lambda t: bool(t) and weight_value(t) is not None),
)
async def weight_entry(message: Message, conn, runner) -> None:
    row = await db.get_user(conn, message.from_user.id)
    if not row or not row["kcal"]:
        await message.answer("Сначала пройдём регистрацию — отправьте /start.")
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
    parts = [f"Записал <b>{kg:g} кг</b>.", "", progress_text(row, history)]
    if abs(norms.kcal - old_kcal) >= 20:
        parts += ["", f"Норма пересчитана: <b>{norms.kcal} ккал</b>, "
                      f"белка {norms.protein} г."]
    await message.answer("\n".join(parts))


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
        "<i>Меняете любое поле — норма пересчитывается сразу.</i>",
    ]
    return "\n".join(lines)


async def show_profile(message: Message, conn, tg_id: int, edit: bool = False) -> None:
    row = await db.get_user(conn, tg_id)
    if not row or not row["kcal"]:
        await message.answer("Сначала пройдём регистрацию — отправьте /start.")
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
        row["goal"] or "maintain", place, kind, date.today().toordinal()
    )
    await call.message.edit_text(
        programs.render_week(days, place, kind),
        reply_markup=keyboards.inline(
            [("Сменить место и тип", "edit:place"), ("Начать тренировку", "w:slot:am")]
        ),
    )
    await call.answer()


@router.callback_query(F.data == "more:times")
async def times_open(call: CallbackQuery, conn) -> None:
    row = await db.get_user(conn, call.from_user.id)
    if not row:
        await call.answer("Сначала /start", show_alert=True)
        return
    await call.message.edit_text(
        "Ваше расписание. Нажмите на строку, чтобы поменять время.",
        reply_markup=keyboards.times_menu(db.user_times(row)),
    )
    await call.answer()


@router.callback_query(F.data == "more:coach")
async def coach_open(call: CallbackQuery) -> None:
    await call.message.edit_text(COACH_TEXT, reply_markup=keyboards.tariffs())
    await call.answer()


# ---------- правка отдельных полей профиля ----------

FIELD_PROMPT = {
    "height": ("Рост в сантиметрах?", Ask.edit_height),
    "weight": ("Текущий вес в килограммах?", Ask.edit_weight),
    "age": ("Сколько вам лет?", Ask.edit_age),
}
FIELD_CHOICE = {
    "sex": ("Пол?", keyboards.EDIT_SEX),
    "activity": ("Чем занят день помимо тренировок?", keyboards.EDIT_ACTIVITY),
    "goal": ("Ради чего занимаемся?", keyboards.EDIT_GOAL),
    "place": ("Где обычно занимаетесь и какой тип нагрузки?", keyboards.EDIT_PLACE),
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
        note = "Настройка сохранена."

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
    await message.answer(f"Записал. {note}")
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
    await call.message.answer("До какого веса идём? Пришлите число в килограммах.")
    await call.answer()


@router.message(Ask.target_kg)
async def set_target(message: Message, state: FSMContext) -> None:
    target = float_value(message.text or "", 30, 300)
    if target is None:
        await message.answer("Целевой вес числом, от 30 до 300.")
        return
    await state.update_data(target_kg=target)
    await state.set_state(Ask.target_weeks)
    await message.answer("За сколько недель? Пришлите число недель.")


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
        f"Это {abs(pace):.2f} кг в неделю.".replace(".", ","),
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
        await message.answer("Сначала пройдём регистрацию — отправьте /start.")
        return
    await message.answer(
        "Ваше расписание. Нажмите на строку, чтобы поменять время.",
        reply_markup=keyboards.times_menu(db.user_times(row)),
    )


@router.callback_query(F.data.startswith("time:"))
async def ask_time(call: CallbackQuery, state: FSMContext) -> None:
    key = call.data.split(":")[1]
    await state.set_state(Ask.time_value)
    await state.update_data(time_key=key)
    await call.message.answer(
        f"Во сколько напоминать про «{TIME_LABELS[key]}»?\n"
        "Пришлите время в виде 07:30."
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
    "<b>Работа с живым тренером</b>\n\n"
    "Бот ведёт вас по программе, но не заменит человека, который смотрит "
    "ваше видео и правит технику. Если нужен такой — выберите формат, "
    "мы свяжемся и подберём тренера под вашу цель.\n\n"
    "Оплата обсуждается напрямую с тренером после знакомства."
)


@router.message(F.text == "Тренер")
async def coach_menu(message: Message) -> None:
    await message.answer(COACH_TEXT, reply_markup=keyboards.tariffs())


@router.callback_query(F.data == "coach:back")
async def coach_back(call: CallbackQuery) -> None:
    await call.message.edit_text(
        "Выберите формат работы:", reply_markup=keyboards.tariffs()
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
        f"Заявка принята: <b>{tariff['title']}</b>.\n\n"
        "Мы напишем вам в течение дня и подберём тренера под вашу цель. "
        "Ответьте ему прямо здесь, в Telegram."
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
        "Оставите заявку — передадим её тренеру вместе с вашей целью и весом.",
        reply_markup=keyboards.confirm_lead(key),
    )
    await call.answer()


@router.message(Command("help"))
async def help_cmd(message: Message) -> None:
    await message.answer(
        "<b>Что я умею</b>\n\n"
        "• Тренировка — собираю программу под цель, место и инвентарь, "
        "веду по подходам и держу отдых\n"
        "• Еда — напишите «гречка 150 г», посчитаю БЖУ и вычту из нормы\n"
        "• Сегодня — сводка по калориям, БЖУ и воде\n"
        "• Вода — добавить выпитое\n"
        "• Вес — записать вес числом, посмотреть путь к цели\n"
        "• Ещё — профиль, план на неделю, напоминания, тренер\n\n"
        "В профиле правится любое поле: рост, вес, возраст, пол, образ жизни, "
        "цель и место тренировок. Норма пересчитывается сразу.\n\n"
        "/profile — профиль, /times — напоминания, /reset — регистрация заново",
        reply_markup=keyboards.MAIN_MENU,
    )
