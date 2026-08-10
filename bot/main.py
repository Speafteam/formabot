"""Точка входа. Запуск: python -m bot.main"""

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from . import db
from .config import BOT_TOKEN, TZ_NAME, missing_settings
from .handlers import build_router
from .scheduler import Runner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("formabot")


async def run() -> None:
    problems = missing_settings()
    if problems:
        print("Бот не запущен. Не хватает настроек:\n")
        for item in problems:
            print(f"  • {item}")
        print("\nСкопируйте .env.example в .env и заполните значения.")
        sys.exit(1)

    conn = await db.connect()
    await db.init(conn)

    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    runner = Runner(bot, conn)

    dp = Dispatcher(storage=MemoryStorage())
    dp["conn"] = conn
    dp["runner"] = runner
    dp.include_router(build_router())

    runner.start()
    await runner.restore()

    me = await bot.get_me()
    log.info("Запустился как @%s, часовой пояс %s", me.username, TZ_NAME)
    log.info("Открой в Telegram: https://t.me/%s", me.username)

    try:
        await dp.start_polling(bot)
    finally:
        runner.sched.shutdown(wait=False)
        await conn.close()
        await bot.session.close()


def main() -> None:
    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit):
        log.info("Остановлен")


if __name__ == "__main__":
    main()
