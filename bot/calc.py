"""Расчёт суточной нормы калорий, БЖУ и воды.

Формулы согласованы с заказчиком:
  базовый обмен  — Миффлин–Сан Жеор
  коэффициент    — образ жизни + 0.15 за две тренировки в день
  цель           — похудение -20%, набор +15%, растяжка и поддержание без правки
"""

from dataclasses import dataclass

# Коэффициенты образа жизни (без учёта тренировок).
ACTIVITY = {
    "sedentary": 1.375,   # сидячая работа
    "on_feet": 1.55,      # весь день на ногах
    "hard_labor": 1.725,  # тяжёлый физический труд
}
ACTIVITY_LABELS = {
    "sedentary": "Сидячая работа",
    "on_feet": "Весь день на ногах",
    "hard_labor": "Тяжёлый физический труд",
}

# Надбавка за две тренировки в день.
TRAINING_BONUS = 0.15

# Поправка калорий под цель.
GOAL_FACTOR = {
    "lose": 0.80,
    "gain": 1.15,
    "stretch": 1.00,
    "maintain": 1.00,
}
GOAL_LABELS = {
    "lose": "Сбросить вес",
    "gain": "Набрать мышечную массу",
    "stretch": "Растяжка и подвижность",
    "maintain": "Поддержание формы",
}

# Белок, г на кг веса. На дефиците выше — он защищает мышцы.
PROTEIN_PER_KG = {"lose": 2.0, "gain": 1.8, "stretch": 1.6, "maintain": 1.6}

FAT_PER_KG = 0.9
KCAL_PROTEIN = 4
KCAL_FAT = 9
KCAL_CARB = 4

WATER_ML_PER_KG = 30
WATER_TRAINING_BONUS_ML = 500


def dec(value: float, digits: int = 1) -> str:
    """Число с запятой в дробной части: 3.15 -> «3,2».

    Форматируем поштучно, а не заменой точек во всей строке: иначе замена
    портит обычные точки в предложениях вокруг числа.
    """
    return f"{value:.{digits}f}".replace(".", ",")


@dataclass
class Norms:
    bmr: int          # базовый обмен
    tdee: int         # обмен с учётом активности, до поправки на цель
    kcal: int         # суточная норма под цель
    protein: int
    fat: int
    carbs: int
    water_ml: int
    factor: float     # итоговый коэффициент активности

    def as_text(self) -> str:
        return (
            f"<b>{self.kcal} ккал</b> в день\n"
            f"<code>обмен {self.bmr} × {self.factor:.3f}".rstrip("0").rstrip(".")
            + f" → {self.tdee}, поправка на цель → {self.kcal}</code>\n\n"
            f"<b>Белки</b> {self.protein} г\n"
            f"<b>Жиры</b> {self.fat} г\n"
            f"<b>Углеводы</b> {self.carbs} г\n"
            f"<b>Вода</b> {dec(self.water_ml / 1000)} л"
        )


def bmr_mifflin(sex: str, weight_kg: float, height_cm: float, age: int) -> float:
    """Базовый обмен по Миффлину–Сан Жеору."""
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + 5 if sex == "male" else base - 161


def calculate(
    sex: str,
    weight_kg: float,
    height_cm: float,
    age: int,
    activity: str,
    goal: str,
) -> Norms:
    bmr = bmr_mifflin(sex, weight_kg, height_cm, age)
    factor = ACTIVITY.get(activity, 1.375) + TRAINING_BONUS
    tdee = bmr * factor
    kcal = tdee * GOAL_FACTOR.get(goal, 1.0)

    protein = PROTEIN_PER_KG.get(goal, 1.6) * weight_kg
    fat = FAT_PER_KG * weight_kg
    # Углеводы забирают то, что осталось от калорий после белка и жира.
    carbs_kcal = kcal - protein * KCAL_PROTEIN - fat * KCAL_FAT
    carbs = max(carbs_kcal, 0) / KCAL_CARB

    water = weight_kg * WATER_ML_PER_KG + WATER_TRAINING_BONUS_ML

    return Norms(
        bmr=round(bmr),
        tdee=round(tdee),
        kcal=round(kcal),
        protein=round(protein),
        fat=round(fat),
        carbs=round(carbs),
        water_ml=round(water / 50) * 50,
        factor=round(factor, 3),
    )


def weekly_pace(current_kg: float, target_kg: float, weeks: int) -> float:
    """Сколько килограммов в неделю нужно сбрасывать или набирать."""
    if weeks <= 0:
        return 0.0
    return (current_kg - target_kg) / weeks


def pace_warning(current_kg: float, pace_per_week: float) -> str | None:
    """Предупреждение, если выбранный темп вредный.

    Безопасный потолок для похудения — около 1% массы тела в неделю.
    """
    if current_kg <= 0:
        return None
    limit = current_kg * 0.01
    if pace_per_week > limit:
        return (
            f"{dec(pace_per_week, 2)} кг в неделю — быстрее безопасного "
            f"({dec(limit, 2)} кг).\n"
            "На таком темпе уходит мышца, а не жир. Похудеешь и будешь выглядеть "
            "хуже, чем сейчас. Растяни срок."
        )
    if pace_per_week < -limit:
        return (
            f"{dec(abs(pace_per_week), 2)} кг в неделю — это не масса, это заплыв.\n"
            "Большая часть прироста будет жиром. Сбавь темп."
        )
    return None
