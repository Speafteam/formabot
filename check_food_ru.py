"""Проверка словаря продуктов: перевод плюс реальный поиск в FatSecret."""

import asyncio

from bot import fatsecret, food_ru
from bot.parsing import food_line

# Как люди действительно пишут в чат.
CASES = [
    "гречка 150 г", "гречки 200г", "куриная грудка 200 г", "грудка 180г",
    "творог 5% 180 грамм", "овсянка 60 г", "банан 120 г", "яйцо 60 г",
    "рис отварной 200 г", "лосось 150 г", "греческий йогурт 150 г",
    "оливковое масло 15 г", "грецкий орех 30 г", "помидоры 100 г",
    "картошка 250 г", "хлеб цельнозерновой 40 г", "борщ 300 г",
    "протеин 30 г", "миндаль 25 г", "яблоко 180 г",
    "chicken breast 200 г",
    "шаурма 350 г", "квашеная капуста 100 г", "тыквенные семечки 20 г",
]

MISSES = ["крокодил 100 г", "штука непонятная 50 г"]


async def main() -> None:
    print("=== Перевод ===\n")
    untranslated = []
    for case in CASES:
        name, grams = food_line(case)
        query, ok = food_ru.translate(name)
        mark = "ok  " if ok else "MISS"
        print(f"{mark} {name!r} → {query!r}")
        if not ok:
            untranslated.append(name)
    print()

    print("=== Должны НЕ переводиться ===\n")
    for case in MISSES:
        name, _ = food_line(case)
        query, ok = food_ru.translate(name)
        status = "ПЛОХО: перевёл" if ok else "ok   не знает, как и ожидалось"
        print(f"{status} — {name!r}")
        if not ok:
            hints = food_ru.suggestions(name)
            if hints:
                print(f"     подсказки: {', '.join(hints)}")
    print()

    print("=== Реальный поиск в FatSecret ===\n")
    checks = ["гречка 150 г", "куриная грудка 200 г", "творог 5% 180 г",
              "овсянка 60 г", "банан 120 г", "борщ 300 г"]
    failed = []
    for case in checks:
        name, grams = food_line(case)
        query, _ = food_ru.translate(name)
        try:
            found = await fatsecret.search(query, limit=1)
        except fatsecret.FoodApiError as err:
            print(f"MISS {name}: ошибка {err}")
            failed.append(name)
            continue
        if not found:
            print(f"MISS {name} → {query!r}: ничего не найдено")
            failed.append(name)
            continue
        try:
            m = await fatsecret.macros(found[0]["id"], grams, found[0]["hint"])
        except fatsecret.FoodApiError as err:
            print(f"MISS {name}: {err}")
            failed.append(name)
            continue
        print(f"ok   {name}, {grams:g} г → {m['name']}")
        print(f"     Б {m['protein']:.1f} · Ж {m['fat']:.1f} · "
              f"У {m['carbs']:.1f} · {m['kcal']:.0f} ккал")
    print()

    if untranslated:
        print(f"Не переведено: {untranslated}")
    if failed:
        print(f"Не найдено в базе: {failed}")
    if not untranslated and not failed:
        print("ВСЁ ПРОШЛО")


asyncio.run(main())
