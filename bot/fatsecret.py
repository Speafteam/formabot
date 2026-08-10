"""Клиент FatSecret Platform API для счётчика БЖУ.

Используется OAuth 1.0 (двухногий): каждый запрос подписывается HMAC-SHA1
парой Consumer Key + Consumer Secret. Никакого токена получать не нужно.

Внимание при смене ключей: у FatSecret есть и OAuth 2.0, где пара называется
Client ID / Client Secret и выглядит точно так же — 32 hex-символа. Схемы
несовместимы. Если API начнёт отвечать invalid_client или Invalid signature,
первым делом проверьте, ключи какого типа лежат в .env.

Порядок работы:
  1. foods.search — ищем продукт по названию, показываем варианты;
  2. food.get.v4 — по выбранному берём порцию в граммах и считаем БЖУ.
"""

import base64
import hashlib
import hmac
import logging
import re
import time
import uuid
from urllib.parse import quote

import httpx

from .config import FATSECRET_CLIENT_ID, FATSECRET_CLIENT_SECRET, FATSECRET_READY

log = logging.getLogger(__name__)

API_URL = "https://platform.fatsecret.com/rest/server.api"


class FoodApiError(Exception):
    """Ошибка, текст которой можно показать пользователю."""


class NotConfigured(FoodApiError):
    pass


def _enc(value) -> str:
    return quote(str(value), safe="~")


def _sign(params: dict) -> str:
    """Подпись запроса по OAuth 1.0. Токена нет, поэтому ключ — секрет и амперсанд."""
    ordered = "&".join(f"{_enc(k)}={_enc(params[k])}" for k in sorted(params))
    base = f"GET&{_enc(API_URL)}&{_enc(ordered)}"
    digest = hmac.new(
        f"{FATSECRET_CLIENT_SECRET}&".encode(), base.encode(), hashlib.sha1
    ).digest()
    return base64.b64encode(digest).decode()


async def _call(method: str, **params) -> dict:
    if not FATSECRET_READY:
        raise NotConfigured(
            "Счётчик еды пока не подключён — не хватает ключей от базы продуктов.\n\n"
            "Это на моей стороне, не на твоей. Всё остальное работает: "
            "тренировки, вода, вес, напоминания."
        )

    query = {
        "method": method,
        "format": "json",
        **{k: v for k, v in params.items() if v is not None},
        "oauth_consumer_key": FATSECRET_CLIENT_ID,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_nonce": uuid.uuid4().hex,
        "oauth_version": "1.0",
    }
    query["oauth_signature"] = _sign(query)

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(API_URL, params=query)

    if resp.status_code != 200:
        raise FoodApiError(f"FatSecret ответил кодом {resp.status_code}.")

    try:
        data = resp.json()
    except ValueError:
        raise FoodApiError("База продуктов ответила ерундой. Попробуй позже.")

    if "error" in data:
        message = data["error"].get("message", "неизвестная ошибка")
        if "IP" in message:
            message += (
                "\n\nВнесите текущий IP в белый список в кабинете FatSecret — "
                "домашний адрес меняется при переподключении."
            )
        raise FoodApiError(f"FatSecret: {message}")
    return data


def _as_list(value) -> list:
    """Одиночную находку FatSecret отдаёт объектом, а не списком из одного."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


async def search(query: str, limit: int = 5) -> list[dict]:
    """Ищет продукт. Возвращает список вариантов для выбора."""
    data = await _call("foods.search", search_expression=query, max_results=limit)
    foods = _as_list((data.get("foods") or {}).get("food"))
    return [
        {
            "id": str(f.get("food_id")),
            "name": (f.get("food_name") or "").strip(),
            "brand": (f.get("brand_name") or "").strip(),
            "hint": f.get("food_description", ""),
        }
        for f in foods
    ]


def _pick_gram_serving(servings: list[dict]) -> dict | None:
    """Ищет порцию, у которой известен вес в граммах."""
    for s in servings:
        unit = (s.get("metric_serving_unit") or "").lower()
        amount = s.get("metric_serving_amount")
        if unit == "g" and amount:
            try:
                if float(amount) > 0:
                    return s
            except (TypeError, ValueError):
                continue
    return None


# Запасной разбор: "Per 100g - Calories: 92kcal | Fat: 0.62g | Carbs: 19.94g | Protein: 3.38g"
_DESC = re.compile(
    r"Per\s+([\d.]+)\s*g.*?Calories:\s*([\d.]+)kcal.*?Fat:\s*([\d.]+)g"
    r".*?Carbs:\s*([\d.]+)g.*?Protein:\s*([\d.]+)g",
    re.IGNORECASE | re.DOTALL,
)


def _from_description(text: str, grams: float) -> dict | None:
    """Считает БЖУ из краткого описания, если подробных порций не дали."""
    m = _DESC.search(text or "")
    if not m:
        return None
    base, kcal, fat, carbs, protein = (float(g) for g in m.groups())
    if base <= 0:
        return None
    k = grams / base
    return {
        "kcal": kcal * k,
        "fat": fat * k,
        "carbs": carbs * k,
        "protein": protein * k,
    }


async def macros(food_id: str, grams: float, fallback_hint: str = "") -> dict:
    """Считает БЖУ выбранного продукта на указанную граммовку."""
    try:
        data = await _call("food.get.v4", food_id=food_id)
        food = data.get("food") or {}
    except FoodApiError:
        # На части тарифов v4 недоступна — пробуем старый метод.
        data = await _call("food.get", food_id=food_id)
        food = data.get("food") or {}

    name = (food.get("food_name") or "").strip()
    brand = (food.get("brand_name") or "").strip()
    servings = _as_list((food.get("servings") or {}).get("serving"))
    serving = _pick_gram_serving(servings)

    if serving is not None:
        base = float(serving["metric_serving_amount"])
        k = grams / base

        def num(key: str) -> float:
            try:
                return float(serving.get(key) or 0) * k
            except (TypeError, ValueError):
                return 0.0

        values = {
            "kcal": num("calories"),
            "protein": num("protein"),
            "fat": num("fat"),
            "carbs": num("carbohydrate"),
        }
    else:
        values = _from_description(fallback_hint, grams)
        if values is None:
            raise FoodApiError(
                f"У «{name}» в базе нет порции в граммах — "
                "на твою граммовку не пересчитать. Возьми другой вариант."
            )

    return {"name": name, "brand": brand, "grams": grams, **values}
