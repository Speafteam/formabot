"""Проверка ключей FatSecret: токен, поиск продукта, расчёт БЖУ.

Запуск: .venv\\Scripts\\python.exe check_fatsecret.py
Значения ключей не печатаются — только результат.
"""

import asyncio
import socket

import httpx

from bot import fatsecret
from bot.config import FATSECRET_READY

QUERY = "buckwheat"
GRAMS = 150


async def show_ip() -> None:
    """FatSecret на бесплатном тарифе пускает только IP из белого списка."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://api.ipify.org")
            print(f"Ваш внешний IP: {resp.text.strip()}")
            print("Он должен быть в белом списке в кабинете FatSecret.\n")
    except Exception as err:
        print(f"IP определить не удалось ({err.__class__.__name__}), пропускаю.\n")


async def main() -> None:
    print("=== Проверка FatSecret ===\n")

    if not FATSECRET_READY:
        print("Ключи не заданы в .env — проверять нечего.")
        return

    await show_ip()

    print(f"1. Ищу продукт «{QUERY}»...")
    try:
        found = await fatsecret.search(QUERY, limit=3)
    except fatsecret.FoodApiError as err:
        print(f"   ОШИБКА: {err}\n")
        return

    if not found:
        print("   Ничего не найдено — ключи рабочие, но выдача пустая.\n")
        return

    for i, item in enumerate(found, 1):
        brand = f" ({item['brand']})" if item["brand"] else ""
        print(f"   {i}. {item['name']}{brand}")
    print()

    print(f"2. Считаю БЖУ на {GRAMS} г для первого варианта...")
    try:
        result = await fatsecret.macros(found[0]["id"], GRAMS, found[0]["hint"])
    except fatsecret.FoodApiError as err:
        print(f"   ОШИБКА: {err}\n")
        return

    print(f"   {result['name']}, {GRAMS} г")
    print(f"   Б {result['protein']:.1f} · Ж {result['fat']:.1f} · "
          f"У {result['carbs']:.1f} · {result['kcal']:.0f} ккал\n")

    print("3. Проверяю русский запрос «гречка»...")
    try:
        ru = await fatsecret.search("гречка", limit=3)
        if ru:
            for item in ru:
                print(f"   • {item['name']}")
        else:
            print("   Пусто. База FatSecret англоязычная — "
                  "русские названия ищутся плохо.")
    except fatsecret.FoodApiError as err:
        print(f"   ОШИБКА: {err}")
    print()

    print("=== Ключи рабочие ===")


asyncio.run(main())
