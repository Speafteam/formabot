"""Счётчик БЖУ: разбор сообщений вида «гречка 150 г»."""

import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery, Message

from .. import achievements, db, fatsecret, food_ru, keyboards
from ..parsing import food_line

log = logging.getLogger(__name__)
router = Router()

# Найденные варианты ждут выбора пользователя. Живут до следующего запроса,
# поэтому в базу их класть незачем.
_pending: dict[int, dict] = {}


def totals_block(row, totals) -> str:
    def line(label, eaten, norm, unit="г"):
        left = max(round(norm - eaten), 0)
        return f"{label}: <b>{round(eaten)}</b> из {round(norm)} {unit}, осталось {left}"

    return "\n".join(
        [
            line("Калории", totals["kcal"], row["kcal"], "ккал"),
            line("Белки", totals["protein"], row["protein"]),
            line("Жиры", totals["fat"], row["fat"]),
            line("Углеводы", totals["carbs"], row["carbs"]),
        ]
    )


def unknown_food_text(name: str, translated: bool) -> str:
    """Объясняет, почему продукт не нашёлся, и что с этим делать."""
    if not translated:
        text = f"Не знаю, как «{name}» по-английски, а база англоязычная.\n\n"
        similar = food_ru.suggestions(name)
        if similar:
            text += "Может, это: " + ", ".join(similar) + "?\n\n"
        text += "Назови проще — «творог» вместо «творожок». Или сразу по-английски."
        return text
    return (
        f"«{name}» перевёл, а в базе такого нет.\n\n"
        "Попробуй конкретнее: «куриная грудка» вместо «курица»."
    )


@router.message(
    StateFilter(None),
    F.text.func(lambda t: bool(t) and food_line(t) is not None),
)
async def add_food(message: Message, conn) -> None:
    row = await db.get_user(conn, message.from_user.id)
    if not row or not row["kcal"]:
        await message.answer("Сначала регистрация. Жми /start.")
        return

    name, grams = food_line(message.text)

    # База FatSecret англоязычная, поэтому русское название переводим.
    query, translated = food_ru.translate(name)

    try:
        found = await fatsecret.search(query)
    except fatsecret.FoodApiError as err:
        await message.answer(str(err))
        return
    except Exception:
        log.exception("Поиск продукта сорвался")
        await message.answer(
            "База продуктов не отвечает. Не моя вина, но и не твоя — "
            "попробуй через минуту."
        )
        return

    if not found:
        await message.answer(unknown_food_text(name, translated))
        return

    _pending[message.from_user.id] = {
        "grams": grams, "items": found, "asked": name,
    }
    pairs = [
        (f"{f['name']}{' · ' + f['brand'] if f['brand'] else ''}", f"food:{i}")
        for i, f in enumerate(found)
    ]
    await message.answer(
        f"Что из этого, {grams:g} г?\n\n"
        "<i>Смотри внимательно: варёное и сухое различаются втрое.</i>",
        reply_markup=keyboards.inline(pairs),
    )


@router.callback_query(F.data.startswith("food:"))
async def pick_food(call: CallbackQuery, conn, bot) -> None:
    tg_id = call.from_user.id
    pending = _pending.get(tg_id)
    if not pending:
        await call.answer("Список устарел. Напиши продукт заново.", show_alert=True)
        return

    index = int(call.data.split(":")[1])
    if index >= len(pending["items"]):
        await call.answer("Такого варианта нет.", show_alert=True)
        return

    item = pending["items"][index]
    grams = pending["grams"]
    try:
        result = await fatsecret.macros(item["id"], grams, item.get("hint", ""))
    except fatsecret.FoodApiError as err:
        await call.message.answer(str(err))
        await call.answer()
        return

    # В дневник пишем то, как продукт назвал человек: «гречка» понятнее,
    # чем «Buckwheat Groats (Cooked, Roasted)».
    label = pending.get("asked") or result["name"]
    await db.add_meal(
        conn,
        tg_id,
        label,
        grams,
        result["kcal"],
        result["protein"],
        result["fat"],
        result["carbs"],
    )
    _pending.pop(tg_id, None)

    row = await db.get_user(conn, tg_id)
    totals = await db.day_totals(conn, tg_id)
    await call.message.edit_text(
        f"<b>{label.capitalize()}, {grams:g} г</b>\n"
        f"<i>{result['name']}</i>\n"
        f"<code>Б {result['protein']:.1f} · Ж {result['fat']:.1f} · "
        f"У {result['carbs']:.1f} · {result['kcal']:.0f} ккал</code>\n\n"
        f"{totals_block(row, totals)}",
        reply_markup=keyboards.inline([("Убрать запись", "food:undo")]),
    )
    await call.answer()
    await achievements.notify(bot, conn, tg_id)


@router.callback_query(F.data == "food:undo")
async def undo(call: CallbackQuery, conn) -> None:
    removed = await db.undo_last_meal(conn, call.from_user.id)
    if not removed:
        await call.answer("Сегодня записей нет.", show_alert=True)
        return
    await call.message.edit_text(f"Убрал «{removed['name']}».")
    await call.answer()


@router.message(F.text == "Сегодня")
async def day_report(message: Message, conn) -> None:
    row = await db.get_user(conn, message.from_user.id)
    if not row or not row["kcal"]:
        await message.answer("Сначала регистрация. Жми /start.")
        return

    totals = await db.day_totals(conn, message.from_user.id)
    meals = await db.day_meals(conn, message.from_user.id)
    drunk = await db.water_total(conn, message.from_user.id)

    lines = [totals_block(row, totals), ""]
    lines.append(
        f"Вода: <b>{drunk / 1000:.1f}</b> из {row['water_ml'] / 1000:.1f} л".replace(
            ".", ","
        )
    )
    if meals:
        lines += ["", "<i>Съедено за день</i>"]
        lines += [f"  • {m['name']}, {m['grams']:g} г — {m['kcal']:.0f} ккал"
                  for m in meals]
    else:
        lines += ["", "Записей ноль. Что не посчитано — то не контролируется.\n"
                      "Начни: «овсянка 60 г»."]

    await message.answer("\n".join(lines))
