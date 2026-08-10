"""Тренировка: выбор места, программа, подходы и отдых."""

import logging
from datetime import date

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message

from .. import achievements, db, keyboards, programs

log = logging.getLogger(__name__)
router = Router()

SLOT_TITLE = {"am": "Полная — около 2 часов", "pm": "Короткий блок — 25 минут"}


@router.message(F.text == "Тренировка")
async def menu_workout(message: Message, conn) -> None:
    row = await db.get_user(conn, message.from_user.id)
    if not row or not row["kcal"]:
        await message.answer("Сначала регистрация. Жми /start.")
        return
    await message.answer(
        "Какую ставим?",
        reply_markup=keyboards.inline(
            [(SLOT_TITLE["am"], "w:slot:am"), (SLOT_TITLE["pm"], "w:slot:pm")]
        ),
    )


@router.callback_query(F.data.startswith("w:slot:"))
async def choose_slot(call: CallbackQuery) -> None:
    slot = call.data.split(":")[2]
    await call.message.edit_text(
        "Где сегодня?",
        reply_markup=keyboards.inline(
            [(label, f"w:place:{k}:{slot}") for k, label in programs.PLACES.items()]
        ),
    )
    await call.answer()


# Незавершённый выбор: место, тип и отмеченные группы. До старта тренировки
# класть это в базу незачем — человек может передумать и уйти.
_choosing: dict[int, dict] = {}


@router.callback_query(F.data.startswith("w:place:"))
async def choose_place(call: CallbackQuery, conn) -> None:
    parts = call.data.split(":")
    place = parts[2]
    slot = parts[3] if len(parts) > 3 else "am"
    _choosing[call.from_user.id] = {"place": place, "slot": slot, "groups": set()}

    if slot == "pm":
        await call.message.edit_text(
            "Вечерний блок. Что ставим?", reply_markup=keyboards.EVENING_MODE
        )
        await call.answer()
        return

    await call.message.edit_text(
        "Что качаем?",
        reply_markup=keyboards.inline(
            [(label, f"w:kind:{k}") for k, label in programs.KINDS.items()],
            per_row=2,
        ),
    )
    await call.answer()


@router.callback_query(F.data.startswith("w:pm:"))
async def choose_evening(call: CallbackQuery, conn) -> None:
    mode = call.data.split(":")[2]
    state = _choosing.get(call.from_user.id)
    if not state:
        await call.answer("Начни заново из меню.", show_alert=True)
        return

    if mode == "recovery":
        program = programs.recovery_block(state["place"])
        await show_program(call, conn, state["place"], "cardio", "pm", program)
        return

    state["kind"] = "strength"
    await ask_groups(call)


@router.callback_query(F.data.startswith("w:kind:"))
async def choose_kind(call: CallbackQuery) -> None:
    state = _choosing.get(call.from_user.id)
    if not state:
        await call.answer("Начни заново из меню.", show_alert=True)
        return
    state["kind"] = call.data.split(":")[2]
    await ask_groups(call)


async def ask_groups(call: CallbackQuery) -> None:
    state = _choosing[call.from_user.id]
    chosen = state["groups"]
    await call.message.edit_text(
        f"Какие группы мышц грузим?\n\n"
        f"Отметь минимум {programs.MIN_GROUPS}, максимум не ограничен — "
        "программа соберётся под твой выбор.",
        reply_markup=keyboards.groups_menu(chosen),
    )
    await call.answer()


@router.callback_query(F.data.startswith("w:grp:"))
async def toggle_group(call: CallbackQuery, conn) -> None:
    code = call.data.split(":")[2]
    state = _choosing.get(call.from_user.id)
    if not state:
        await call.answer("Начни заново из меню.", show_alert=True)
        return

    if code == "cancel":
        _choosing.pop(call.from_user.id, None)
        await call.message.edit_text("Отменил. Возвращайся, когда будешь готов.")
        await call.answer()
        return

    if code == "need":
        await call.answer(
            f"Нужно минимум {programs.MIN_GROUPS} группы.", show_alert=True)
        return

    if code == "done":
        await build_and_show(call, conn, state)
        return

    if code in state["groups"]:
        state["groups"].discard(code)
    else:
        state["groups"].add(code)
    await ask_groups(call)


async def build_and_show(call: CallbackQuery, conn, state: dict) -> None:
    tg_id = call.from_user.id
    row = await db.get_user(conn, tg_id)
    if not row:
        await call.answer("Сначала /start", show_alert=True)
        return

    # Порядок групп фиксируем по словарю, чтобы состав не прыгал при пересборке.
    groups = [g for g in programs.GROUPS if g in state["groups"]]
    program = programs.build(
        goal=row["goal"] or "maintain",
        place=state["place"],
        kind=state["kind"],
        slot=state["slot"],
        groups=groups,
        day_index=date.today().toordinal(),
    )
    await show_program(call, conn, state["place"], state["kind"],
                       state["slot"], program)


async def show_program(call: CallbackQuery, conn, place, kind, slot,
                       program: dict) -> None:
    tg_id = call.from_user.id
    await db.start_session(conn, tg_id, place, kind, slot, program)
    # Запоминаем выбор, чтобы план на неделю знал, где человек занимается.
    prefs = {"pref_place": place}
    if slot == "am":
        prefs["pref_kind"] = kind
    await db.save_user(conn, tg_id, **prefs)
    _choosing.pop(tg_id, None)

    await call.message.edit_text(
        programs.render(program),
        reply_markup=keyboards.program_actions(slot),
        disable_web_page_preview=True,
    )
    await call.answer()


@router.callback_query(F.data == "w:replan")
async def replan(call: CallbackQuery, conn) -> None:
    """Пересобирает программу: возвращаемся к выбору места."""
    await db.end_session(conn, call.from_user.id)
    await call.message.edit_text(
        "Собираю заново. Какую ставим?",
        reply_markup=keyboards.inline(
            [(SLOT_TITLE["am"], "w:slot:am"), (SLOT_TITLE["pm"], "w:slot:pm")]
        ),
    )
    await call.answer()


@router.callback_query(F.data == "w:skip_day")
async def skip_day(call: CallbackQuery, conn) -> None:
    await db.end_session(conn, call.from_user.id)
    await call.message.edit_text(
        "Ладно, сегодня без тренировки.\n\n"
        "Один пропуск ничего не решает. Решает второй подряд."
    )
    await call.answer()


@router.callback_query(F.data.startswith("w:go:"))
async def start_workout(call: CallbackQuery, conn, bot: Bot) -> None:
    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer()
    await send_current_step(bot, conn, call.from_user.id)


def step_text(session: dict) -> str | None:
    """Текст текущего шага тренировки. None — программа закончилась."""
    items = session["program"]["items"]
    if session["ex_index"] >= len(items):
        return None
    e = items[session["ex_index"]]
    done = session["set_index"]
    total = e["sets"]
    head = f"<b>{e['name']}</b>"
    if total > 1:
        head += f"\nПодход {done + 1} из {total} · {e['reps']}"
    else:
        head += f"\n{e['reps']}"
    return (
        f"Упражнение {session['ex_index'] + 1} из {len(items)}\n\n"
        f"{head}\n\n{e['note']}\n\n"
        f'<a href="{e["video"]}">Разбор техники</a>'
    )


async def send_current_step(bot: Bot, conn, tg_id: int) -> None:
    session = await db.get_session(conn, tg_id)
    if not session:
        return
    text = step_text(session)
    if text is None:
        await finish_workout(bot, conn, tg_id)
        return
    e = session["program"]["items"][session["ex_index"]]
    await bot.send_message(
        tg_id,
        text,
        reply_markup=keyboards.set_actions(e["timed"]),
        disable_web_page_preview=True,
    )


@router.callback_query(F.data == "w:done")
async def set_done(call: CallbackQuery, conn, runner, bot: Bot) -> None:
    tg_id = call.from_user.id
    session = await db.get_session(conn, tg_id)
    if not session:
        await call.answer("Тренировка не запущена.", show_alert=True)
        return

    items = session["program"]["items"]
    e = items[session["ex_index"]]
    ex_index, set_index = session["ex_index"], session["set_index"] + 1

    if set_index >= e["sets"]:
        ex_index += 1
        set_index = 0

    await db.update_session(conn, tg_id, ex_index, set_index)
    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer()

    if ex_index >= len(items):
        await finish_workout(bot, conn, tg_id)
        return

    # Отсчёт идёт на сервере: человек кладёт телефон в карман и ждёт пуша.
    await runner.arm_rest(tg_id, {"ex_index": ex_index, "set_index": set_index})
    await bot.send_message(
        tg_id,
        "😮‍💨 Отдых <b>2:00</b>. Свистну за полминуты — телефон можешь убрать.",
        reply_markup=keyboards.REST_ACTIONS,
    )


@router.callback_query(F.data == "w:skip_rest")
async def skip_rest(call: CallbackQuery, conn, runner, bot: Bot) -> None:
    await runner.cancel_rest(call.from_user.id)
    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer("Отдых пропущен")
    await send_current_step(bot, conn, call.from_user.id)


@router.callback_query(F.data == "w:next")
async def skip_exercise(call: CallbackQuery, conn, runner, bot: Bot) -> None:
    tg_id = call.from_user.id
    session = await db.get_session(conn, tg_id)
    if not session:
        await call.answer("Тренировка не запущена.", show_alert=True)
        return
    await runner.cancel_rest(tg_id)
    await db.update_session(conn, tg_id, session["ex_index"] + 1, 0)
    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer("Пропустили")
    await send_current_step(bot, conn, tg_id)


@router.callback_query(F.data == "w:stop")
async def stop_workout(call: CallbackQuery, conn, runner) -> None:
    await runner.cancel_rest(call.from_user.id)
    await db.end_session(conn, call.from_user.id)
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer(
        "Свернули раньше времени.\n\n"
        "Половина работы — это всё равно работа. Ноль — это ноль. Отдыхай."
    )
    await call.answer()


async def finish_workout(bot: Bot, conn, tg_id: int) -> None:
    session = await db.get_session(conn, tg_id)
    title = session["program"]["title"] if session else "Тренировка"
    minutes = session["program"]["minutes"] if session else 0

    # Записываем факт тренировки: на этом строятся серии и достижения.
    if session:
        await db.log_workout(
            conn, tg_id, session["slot"], session["place"], session["kind"],
            minutes,
        )

    await db.cancel_timers(conn, tg_id)
    await db.end_session(conn, tg_id)
    await bot.send_message(
        tg_id,
        f"🎉 <b>{title}</b> закрыта. {minutes} минут работы — не зря пришёл.\n\n"
        "Теперь вода и белок в ближайший приём пищи. Иначе всё это впустую.",
        reply_markup=keyboards.MAIN_MENU,
    )
    await achievements.notify(bot, conn, tg_id)
