"""Напоминания и таймеры отдыха.

Всё состояние лежит в SQLite, а APScheduler держит только задачи в памяти.
При старте бот перечитывает базу и восстанавливает и напоминания, и
незакрытые таймеры отдыха — включая просроченные, которые дожидались,
пока бот поднимется.
"""

import logging
from datetime import datetime, timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from . import banter, db, keyboards
from .config import (
    REST_SECONDS,
    REST_WARNING_SECONDS,
    TZ,
    WEIGH_IN_TIME,
    WEIGH_IN_WEEKDAY,
)

log = logging.getLogger(__name__)

MEAL_TEXT = {
    "breakfast": "Завтрак.",
    "lunch": "Обед.",
    "dinner": "Ужин.",
}


class Runner:
    """Держит планировщик, бота и соединение с базой в одном месте."""

    def __init__(self, bot: Bot, conn):
        self.bot = bot
        self.conn = conn
        self.sched = AsyncIOScheduler(timezone=TZ)

    # ---------- запуск ----------

    def start(self) -> None:
        self.sched.start()

    async def restore(self) -> None:
        """Поднимает напоминания всех пользователей и незакрытые таймеры."""
        for row in await db.all_users(self.conn):
            self.schedule_user(row)

        for timer in await db.pending_timers(self.conn):
            await self._restore_timer(timer)

    # ---------- ежедневные напоминания ----------

    def _clear_user_jobs(self, tg_id: int) -> None:
        prefix = f"u{tg_id}:"
        for job in self.sched.get_jobs():
            if job.id.startswith(prefix):
                job.remove()

    def schedule_user(self, row) -> None:
        """Пересобирает напоминания одного пользователя из его настроек."""
        tg_id = row["tg_id"]
        self._clear_user_jobs(tg_id)
        times = db.user_times(row)

        for key, value in times.items():
            try:
                hour, minute = (int(p) for p in value.split(":"))
            except ValueError:
                log.warning("Кривое время %r у пользователя %s", value, tg_id)
                continue
            self.sched.add_job(
                self._fire_reminder,
                CronTrigger(hour=hour, minute=minute, timezone=TZ),
                id=f"u{tg_id}:{key}",
                args=[tg_id, key],
                replace_existing=True,
                misfire_grace_time=600,
            )

        weigh = row["weigh_in"] or WEIGH_IN_TIME
        try:
            hour, minute = (int(p) for p in weigh.split(":"))
        except ValueError:
            hour, minute = 9, 0
        self.sched.add_job(
            self._fire_reminder,
            CronTrigger(day_of_week=WEIGH_IN_WEEKDAY, hour=hour, minute=minute,
                        timezone=TZ),
            id=f"u{tg_id}:weigh_in",
            args=[tg_id, "weigh_in"],
            replace_existing=True,
            misfire_grace_time=3600,
        )

    async def reschedule(self, tg_id: int) -> None:
        row = await db.get_user(self.conn, tg_id)
        if row:
            self.schedule_user(row)

    async def _fire_reminder(self, tg_id: int, key: str) -> None:
        try:
            row = await db.get_user(self.conn, tg_id)
            if row is None:
                return
            text, markup = await self._reminder_body(row, key)
            if text:
                await self.bot.send_message(tg_id, text, reply_markup=markup)
        except Exception:
            log.exception("Не смог отправить напоминание %s пользователю %s", key, tg_id)

    async def _reminder_body(self, row, key: str):
        tg_id = row["tg_id"]

        if key in ("workout_am", "workout_pm"):
            slot = "am" if key == "workout_am" else "pm"
            if slot == "am":
                text = ("Подъём. ☀️ Тренировка не отменяется из-за настроения.\n\n"
                        "Где сегодня?")
            else:
                text = ("Вечерний блок. 🌙 25 минут — меньше, чем ты листаешь ленту.\n\n"
                        "Где занимаешься?")
            return text, keyboards.inline(
                [(label, f"w:place:{k}:{slot}") for k, label in
                 keyboards.PLACES.items()]
            )

        if key in MEAL_TEXT:
            totals = await db.day_totals(self.conn, tg_id)
            left_kcal = max(round(row["kcal"] - totals["kcal"]), 0)
            left_protein = max(round(row["protein"] - totals["protein"]), 0)

            prefs = db.user_nicknames(row)
            opener = banter.meal_opener(row["sex"], row["goal"], key, prefs)
            lines = [opener, ""]

            if left_kcal > 0:
                lines.append(f"Осталось <b>{left_kcal} ккал</b>.")
            else:
                lines.append("Норма по калориям на сегодня уже закрыта.")

            # Подначка про белок — только когда его правда сильно не хватает.
            if left_protein >= 30:
                lines.append(
                    f"{banter.protein_nudge(row['sex'], row['goal'], prefs)} "
                    f"Не добрано <b>{left_protein} г</b>."
                )
            elif left_protein > 0:
                lines.append(f"Белка осталось добрать <b>{left_protein} г</b>.")

            lines += ["", "Поел — напиши: «гречка 150 г», остальное моё."]
            return "\n".join(lines), None

        if key.startswith("water"):
            drunk = await db.water_total(self.conn, tg_id)
            norm = row["water_ml"] or 0
            left = max(norm - drunk, 0)
            opener = banter.water_opener(row["sex"], row["goal"],
                                         db.user_nicknames(row))
            tail = ("Норма закрыта, красота."
                    if left <= 0 else f"Осталось {banter.litres(left)} л.")
            text = (
                f"{opener}\n\n"
                f"Выпито <b>{banter.litres(drunk)}</b> из "
                f"<b>{banter.litres(norm)} л</b>. {tail}"
            )
            return text, keyboards.WATER

        if key == "weigh_in":
            return ("Воскресенье. ⚖️ Время сверить, что было на словах, "
                    "а что на весах.\n\n"
                    "Вставай и пришли вес числом."), None

        return None, None

    # ---------- таймер отдыха ----------

    async def arm_rest(self, tg_id: int, payload: dict) -> None:
        """Ставит отдых после закрытого подхода: пуш за 30 секунд и по истечении."""
        await db.cancel_timers(self.conn, tg_id)
        now = db.now()
        fire_at = now + timedelta(seconds=REST_SECONDS)
        warn_at = fire_at - timedelta(seconds=REST_WARNING_SECONDS)
        timer_id = await db.add_timer(self.conn, tg_id, fire_at, warn_at, payload)
        self._arm_jobs(timer_id, tg_id, fire_at, warn_at, payload)

    def _arm_jobs(self, timer_id, tg_id, fire_at, warn_at, payload) -> None:
        now = db.now()
        if warn_at > now:
            self.sched.add_job(
                self._rest_warning,
                DateTrigger(run_date=warn_at, timezone=TZ),
                id=f"rest:{tg_id}:{timer_id}:warn",
                args=[tg_id],
                replace_existing=True,
                misfire_grace_time=30,
            )
        # Просроченный таймер — например, бот лежал дольше отдыха — срабатывает
        # сразу: человек уже отдохнул, ему нужно продолжение, а не тишина.
        run_at = fire_at if fire_at > now else now + timedelta(seconds=1)
        self.sched.add_job(
            self._rest_over,
            DateTrigger(run_date=run_at, timezone=TZ),
            id=f"rest:{tg_id}:{timer_id}:fire",
            args=[timer_id, tg_id, payload],
            replace_existing=True,
            misfire_grace_time=300,
        )

    async def _restore_timer(self, timer: dict) -> None:
        """Поднимает таймер, переживший перезапуск бота."""
        fire_at = datetime.fromisoformat(timer["fire_at"])
        warn_at = datetime.fromisoformat(timer["warn_at"])
        self._arm_jobs(timer["id"], timer["tg_id"], fire_at, warn_at, timer["payload"])
        log.info("Восстановил таймер %s для %s", timer["id"], timer["tg_id"])

    async def cancel_rest(self, tg_id: int) -> None:
        await db.cancel_timers(self.conn, tg_id)
        prefix = f"rest:{tg_id}:"
        for job in self.sched.get_jobs():
            if job.id.startswith(prefix):
                job.remove()

    async def _rest_warning(self, tg_id: int) -> None:
        try:
            await self.bot.send_message(tg_id, "⏱️ 30 секунд. Подходи к снаряду.")
        except Exception:
            log.exception("Не смог предупредить об окончании отдыха: %s", tg_id)

    async def _rest_over(self, timer_id: int, tg_id: int, payload: dict) -> None:
        try:
            await db.close_timer(self.conn, timer_id)
            from .handlers.workout import send_current_step  # поздний импорт: цикл

            await self.bot.send_message(tg_id, "Время. Отдых кончился.")
            await send_current_step(self.bot, self.conn, tg_id)
        except Exception:
            log.exception("Не смог закрыть отдых для %s", tg_id)
