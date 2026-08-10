"""Тренировка: выбор места, программа, подходы и отдых."""

import logging
from datetime import date

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message

from .. import db, keyboards, programs

log = logging.getLogger(__name__)
router = Router()

SLOT_TITLE = {"am": "Полная тренировка, около 2 часов", "pm": "Короткий блок, 25 минут"}


@router.message(F.text == "Тренировка")
async def menu_workout(message: Message, conn) -> None:
    row = await db.get_user(conn, message.from_user.id)
    if not row or not row["kcal"]:
        await message.answer("Сначала пройдём регистрацию — отправьте /start.")
        return
    await message.answer(
        "Какую тренировку ставим?",
        reply_markup=keyboards.inline(
            [(SLOT_TITLE["am"], "w:slot:am"), (SLOT_TITLE["pm"], "w:slot:pm")]
        ),
    )


@router.callback_query(F.data.startswith("w:slot:"))
async def choose_slot(call: CallbackQuery) -> None:
    slot = call.data.split(":")[2]
    await call.message.edit_text(
        "Где сегодня занимаетесь?",
        reply_markup=keyboards.inline(
            [(label, f"w:place:{k}:{slot}") for k, label in programs.PLACES.items()]
        ),
    )
    await call.answer()


@router.callback_query(F.data.startswith("w:place:"))
async def choose_place(call: CallbackQuery, conn) -> None:
    parts = call.data.split(":")
    place = parts[2]
    slot = parts[3] if len(parts) > 3 else "am"

    if slot == "pm":
        # Вечером тип не спрашиваем — там всегда кардио и растяжка.
        await build_and_show(call, conn, place, "cardio", "pm")
        return

    await call.message.edit_text(
        "Что ставим на сегодня?",
        reply_markup=keyboards.inline(
            [(label, f"w:kind:{k}:{place}") for k, label in programs.KINDS.items()],
            per_row=2,
        ),
    )
    await call.answer()


@router.callback_query(F.data.startswith("w:kind:"))
async def choose_kind(call: CallbackQuery, conn) -> None:
    _, _, kind, place = call.data.split(":")
    await build_and_show(call, conn, place, kind, "am")


async def build_and_show(call: CallbackQuery, conn, place, kind, slot) -> None:
    tg_id = call.from_user.id
    row = await db.get_user(conn, tg_id)
    if not row:
        await call.answer("Сначала /start", show_alert=True)
        return

    program = programs.build(
        goal=row["goal"] or "maintain",
        place=place,
        kind=kind,
        slot=slot,
        day_index=date.today().toordinal(),
    )
    await db.start_session(conn, tg_id, place, kind, slot, program)
    # Запоминаем выбор, чтобы план на неделю знал, где человек занимается.
    prefs = {"pref_place": place}
    if slot == "am":
        prefs["pref_kind"] = kind
    await db.save_user(conn, tg_id, **prefs)

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
        "Собираем заново. Какую тренировку ставим?",
        reply_markup=keyboards.inline(
            [(SLOT_TITLE["am"], "w:slot:am"), (SLOT_TITLE["pm"], "w:slot:pm")]
        ),
    )
    await call.answer()


@router.callback_query(F.data == "w:skip_day")
async def skip_day(call: CallbackQuery, conn) -> None:
    await db.end_session(conn, call.from_user.id)
    await call.message.edit_text(
        "Хорошо, сегодня пропускаем. Напомню в следующий раз."
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
        "😮‍💨 Отдых <b>2:00</b>. Напишу за полминуты до конца — "
        "можно убрать телефон.",
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
        "Тренировка завершена досрочно. Отдыхайте — даже неполная работа лучше, "
        "чем пропущенная. 👍"
    )
    await call.answer()


async def finish_workout(bot: Bot, conn, tg_id: int) -> None:
    session = await db.get_session(conn, tg_id)
    title = session["program"]["title"] if session else "Тренировка"
    minutes = session["program"]["minutes"] if session else 0
    await db.cancel_timers(conn, tg_id)
    await db.end_session(conn, tg_id)
    await bot.send_message(
        tg_id,
        f"🎉 <b>{title}</b> закрыта. Примерно {minutes} минут работы — отличная работа!\n\n"
        "Не забудьте про воду и белок в ближайший приём пищи.",
        reply_markup=keyboards.MAIN_MENU,
    )
