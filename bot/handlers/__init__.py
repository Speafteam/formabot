from aiogram import Router

from . import registration, workout, food, misc


def build_router() -> Router:
    """Порядок важен: сначала команды и кнопки меню, свободный текст — в конце."""
    router = Router()
    router.include_router(registration.router)
    router.include_router(misc.router)
    router.include_router(workout.router)
    router.include_router(food.router)
    return router
