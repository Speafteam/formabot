"""Регистрация: семь вопросов и расчёт нормы."""

from datetime import date, timedelta

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from .. import calc, db, keyboards
from ..config import TIME_LABELS
from ..parsing import float_value, int_value

router = Router()


class Reg(StatesGroup):
    age = State()
    sex = State()
    height = State()
    weight = State()
    activity = State()
    goal = State()
    target_kg = State()
    target_weeks = State()


HELLO = (
    "У новичка две беды: не знает, что делать в зале, и жрёт как попало.\n\n"
    "Обе закрываю.\n\n"
    "🏋️ <b>Тренировки</b> — две в день. Программа под твою цель и под то, "
    "что под рукой: дом, зал, площадка.\n\n"
    "⏱️ <b>Отдых между подходами</b> — считаю сам, скажу когда вставать. "
    "Телефон можешь убрать.\n\n"
    "🍽️ <b>Еда</b> — пишешь «гречка 150 г», БЖУ мои.\n\n"
    "💧 <b>Вода и приёмы пищи</b> — напомню тогда, когда удобно тебе, "
    "а не когда мне.\n\n"
    "📉 <b>Вес</b> — покажу, идёшь ты к цели или топчешься.\n\n"
    "Время любого напоминания ставишь сам. Бот подстраивается под твой день, "
    "а не наоборот.\n\n"
    "Семь вопросов, меньше минуты. Погнали.\n\n"
    "<b>Сколько тебе лет?</b>"
)


def next_reminder(row) -> str | None:
    """Ближайшее напоминание, которое ещё будет сегодня."""
    times = db.user_times(row)
    now = db.now()
    current = now.hour * 60 + now.minute
    best = None
    for key, value in times.items():
        try:
            hour, minute = (int(p) for p in value.split(":"))
        except ValueError:
            continue
        at = hour * 60 + minute
        if at > current and (best is None or at < best[0]):
            best = (at, key, value)
    if best is None:
        return None
    return f"{TIME_LABELS[best[1]]} в {best[2]}"


async def welcome_back(message: Message, conn, row) -> None:
    """Короткая сводка дня — чтобы заходить в бота было зачем."""
    tg_id = row["tg_id"]
    totals = await db.day_totals(conn, tg_id)
    drunk = await db.water_total(conn, tg_id)

    name = message.from_user.first_name or ""
    lines = [f"О, вернулся{', ' + name if name else ''}. Что по сегодня:", ""]

    left_kcal = round(row["kcal"] - totals["kcal"])
    nothing_logged = totals["kcal"] <= 0
    if nothing_logged:
        lines.append(f"🔥 Норма {row['kcal']} ккал. Записей ноль.")
    else:
        lines.append(
            f"🔥 {round(totals['kcal'])} из {row['kcal']} ккал"
            + (f", осталось {left_kcal}" if left_kcal > 0 else ". Норма закрыта.")
        )

    lines.append(
        f"💧 {drunk / 1000:.1f} из {row['water_ml'] / 1000:.1f} л".replace(".", ",")
    )

    upcoming = next_reminder(row)
    if upcoming:
        lines.append(f"⏰ Дальше — {upcoming.lower()}")

    if row["target_kg"]:
        left = abs(row["weight_kg"] - row["target_kg"])
        line = f"📉 До цели {left:.1f} кг".replace(".", ",")
        if row["target_date"]:
            days = (date.fromisoformat(row["target_date"]) - date.today()).days
            if days > 0:
                line += f", в запасе {days // 7} нед."
        lines.append(line)

    # Слабый ведёт дневник по настроению, сильный — каждый день.
    lines += ["", "Дневник пустой. Так цель не берут." if nothing_logged
              else "Идём по плану. Не сбавляй."]
    await message.answer("\n".join(lines), reply_markup=keyboards.MAIN_MENU)


async def start_registration(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(Reg.age)
    await message.answer(HELLO)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, conn) -> None:
    row = await db.get_user(conn, message.from_user.id)
    if row and row["kcal"]:
        await welcome_back(message, conn, row)
        return
    # Первый заход: показываем, за что взялись.
    await db.save_user(conn, message.from_user.id, username=message.from_user.username)
    await start_registration(message, state)


@router.message(Command("reset"))
async def cmd_reset(message: Message, state: FSMContext, conn) -> None:
    await start_registration(message, state)


@router.message(Reg.age)
async def got_age(message: Message, state: FSMContext) -> None:
    age = int_value(message.text or "", 10, 100)
    if age is None:
        await message.answer("Число от 10 до 100. Сколько тебе лет?")
        return
    await state.update_data(age=age)
    await state.set_state(Reg.sex)
    await message.answer("Пол?", reply_markup=keyboards.SEX)


@router.callback_query(Reg.sex, F.data.startswith("reg:sex:"))
async def got_sex(call: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(sex=call.data.split(":")[2])
    await state.set_state(Reg.height)
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer("Рост в сантиметрах?")
    await call.answer()


@router.message(Reg.height)
async def got_height(message: Message, state: FSMContext) -> None:
    height = float_value(message.text or "", 100, 250)
    if height is None:
        await message.answer("Рост в сантиметрах, число от 100 до 250.")
        return
    await state.update_data(height=height)
    await state.set_state(Reg.weight)
    await message.answer("Вес сейчас, в килограммах? Честно — цифры для тебя, не для меня.")


@router.message(Reg.weight)
async def got_weight(message: Message, state: FSMContext) -> None:
    weight = float_value(message.text or "", 30, 300)
    if weight is None:
        await message.answer("Вес в килограммах, число от 30 до 300.")
        return
    await state.update_data(weight=weight)
    await state.set_state(Reg.activity)
    await message.answer(
        "Чем занят день, кроме тренировок?", reply_markup=keyboards.ACTIVITY
    )


@router.callback_query(Reg.activity, F.data.startswith("reg:act:"))
async def got_activity(call: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(activity=call.data.split(":")[2])
    await state.set_state(Reg.goal)
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer("Ради чего всё это?", reply_markup=keyboards.GOAL)
    await call.answer()


@router.callback_query(Reg.goal, F.data.startswith("reg:goal:"))
async def got_goal(call: CallbackQuery, state: FSMContext, conn, runner) -> None:
    goal = call.data.split(":")[2]
    await state.update_data(goal=goal)
    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer()

    if goal in ("lose", "gain"):
        await state.set_state(Reg.target_kg)
        word = "сбросить" if goal == "lose" else "набрать"
        await call.message.answer(
            f"До какого веса {word}? Пришли число в килограммах.\n\n"
            "Цель без цифры — это мечта."
        )
        return

    await finish(call.message, state, conn, runner, call.from_user.id)


@router.message(Reg.target_kg)
async def got_target(message: Message, state: FSMContext) -> None:
    target = float_value(message.text or "", 30, 300)
    if target is None:
        await message.answer("Целевой вес в килограммах, число от 30 до 300.")
        return
    data = await state.get_data()
    if data["goal"] == "lose" and target >= data["weight"]:
        await message.answer("Худеем — значит цель меньше текущего веса. Сколько ставим?")
        return
    if data["goal"] == "gain" and target <= data["weight"]:
        await message.answer("Набираем — значит цель больше текущего веса. Сколько ставим?")
        return
    await state.update_data(target_kg=target)
    await state.set_state(Reg.target_weeks)
    await message.answer("За сколько недель дойдём? Пришли число недель.")


@router.message(Reg.target_weeks)
async def got_weeks(message: Message, state: FSMContext, conn, runner) -> None:
    weeks = int_value(message.text or "", 2, 104)
    if weeks is None:
        await message.answer("Число недель, от 2 до 104.")
        return
    await state.update_data(target_weeks=weeks)
    await finish(message, state, conn, runner, message.from_user.id)


async def finish(message: Message, state: FSMContext, conn, runner, tg_id: int) -> None:
    data = await state.get_data()
    await state.clear()

    norms = calc.calculate(
        sex=data["sex"],
        weight_kg=data["weight"],
        height_cm=data["height"],
        age=data["age"],
        activity=data["activity"],
        goal=data["goal"],
    )

    target_kg = data.get("target_kg")
    weeks = data.get("target_weeks")
    target_date = (
        (date.today() + timedelta(weeks=weeks)).isoformat() if weeks else None
    )

    await db.save_user(
        conn,
        tg_id,
        username=message.chat.username,
        sex=data["sex"],
        age=data["age"],
        height_cm=data["height"],
        weight_kg=data["weight"],
        start_kg=data["weight"],
        activity=data["activity"],
        goal=data["goal"],
        target_kg=target_kg,
        target_date=target_date,
        kcal=norms.kcal,
        protein=norms.protein,
        fat=norms.fat,
        carbs=norms.carbs,
        water_ml=norms.water_ml,
    )
    await db.add_weight(conn, tg_id, data["weight"])
    await runner.reschedule(tg_id)

    text = ["Посчитал. Твоя норма на день:", "", norms.as_text()]

    if target_kg and weeks:
        pace = calc.weekly_pace(data["weight"], target_kg, weeks)
        delta = abs(data["weight"] - target_kg)
        text += [
            "",
            f"Цель: <b>{delta:.1f} кг за {weeks} нед.</b> — "
            f"{abs(pace):.2f} кг в неделю.".replace(".", ","),
        ]
        warning = calc.pace_warning(data["weight"], pace)
        if warning:
            text += ["", f"⚠️ {warning}"]

    text += [
        "",
        "Норму пересчитываю сам при каждом взвешивании — следить не нужно.",
        "Напоминания уже стоят. Время любого правится: «Ещё» → «Напоминания».",
        "",
        "Дальше просто. Слабый ищет мотивацию, сильный открывает план и делает.",
        "Жми «Тренировка».",
    ]

    await message.answer("\n".join(text), reply_markup=keyboards.MAIN_MENU)
