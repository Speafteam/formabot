"""Русско-английский словарь продуктов для поиска в FatSecret.

База FatSecret англоязычная: «гречка» в ней не находится, «buckwheat» находится
мгновенно. Поэтому запрос пользователя переводится перед поиском.

Совпадение ищется по основе слова, чтобы «гречка», «гречки» и «гречку» вели
к одной записи. Многословные названия («куриная грудка») проверяются целиком,
а если целиком не нашлось — по главному слову.

Не нашли нужный продукт? Допишите строку в PRODUCTS — ключ в именительном
падеже, значение английским названием, каким его знает FatSecret.
"""

import re

# Окончания отсекаются от длинных слов, чтобы падежи сходились к одной основе.
_ENDINGS = (
    "ами", "ями", "ого", "его", "ов", "ев", "ей", "ой", "ом", "ем", "ах", "ях",
    "ы", "и", "а", "я", "у", "ю", "е", "о", "ь",
)

PRODUCTS: dict[str, str] = {
    # --- крупы, каши, гарниры ---
    "гречка": "buckwheat", "гречневая крупа": "buckwheat", "рис": "rice",
    "бурый рис": "brown rice", "белый рис": "white rice", "овсянка": "oatmeal",
    "овсяные хлопья": "oats", "геркулес": "oats", "перловка": "pearl barley",
    "пшено": "millet", "пшённая каша": "millet", "манка": "semolina",
    "булгур": "bulgur", "кускус": "couscous", "киноа": "quinoa",
    "макароны": "pasta", "спагетти": "spaghetti", "лапша": "noodles",
    "вермишель": "noodles", "картофельное пюре": "mashed potatoes",
    "кукурузная крупа": "cornmeal", "полба": "spelt", "отруби": "bran",
    "мюсли": "muesli", "гранола": "granola", "каша": "porridge",

    # --- хлеб и выпечка ---
    "хлеб": "bread", "белый хлеб": "white bread",
    "чёрный хлеб": "rye bread", "ржаной хлеб": "rye bread",
    "цельнозерновой хлеб": "whole wheat bread", "батон": "white bread",
    "лаваш": "pita bread", "багет": "baguette", "булка": "bun", "булочка": "bun",
    "сухари": "rusk", "хлебцы": "crispbread", "печенье": "cookies",
    "пряник": "gingerbread", "вафли": "waffles", "блины": "pancakes",
    "оладьи": "pancakes", "сырники": "cottage cheese pancakes",
    "пирожок": "pie", "пирог": "pie", "круассан": "croissant",
    "пицца": "pizza", "мука": "flour", "тесто": "dough", "сухарики": "croutons",

    # --- мясо ---
    "говядина": "beef", "свинина": "pork", "баранина": "lamb",
    "телятина": "veal", "фарш": "ground beef", "говяжий фарш": "ground beef",
    "свиной фарш": "ground pork", "стейк": "beef steak", "котлета": "cutlet",
    "бекон": "bacon", "ветчина": "ham", "колбаса": "sausage",
    "сосиски": "sausages", "сарделька": "sausage", "буженина": "roast pork",
    "печень": "liver", "говяжья печень": "beef liver", "сало": "pork fat",
    "шашлык": "shish kebab", "рёбра": "pork ribs", "язык": "beef tongue",
    "субпродукты": "offal", "холодец": "aspic",

    # --- птица ---
    "курица": "chicken", "куриная грудка": "chicken breast",
    "куриное филе": "chicken breast", "грудка": "chicken breast",
    "куриное бедро": "chicken thigh", "бедро": "chicken thigh",
    "куриная голень": "chicken drumstick", "голень": "chicken drumstick",
    "крылышки": "chicken wings", "куриные крылья": "chicken wings",
    "индейка": "turkey", "филе индейки": "turkey breast", "утка": "duck",
    "гусь": "goose", "куриный фарш": "ground chicken", "печень куриная": "chicken liver",

    # --- рыба и морепродукты ---
    "рыба": "fish", "лосось": "salmon", "сёмга": "salmon", "форель": "trout",
    "тунец": "tuna", "треска": "cod", "минтай": "pollock", "хек": "hake",
    "скумбрия": "mackerel", "сельдь": "herring", "селёдка": "herring",
    "горбуша": "pink salmon", "камбала": "flounder", "судак": "pike perch",
    "щука": "pike", "карп": "carp", "палтус": "halibut", "сардины": "sardines",
    "креветки": "shrimp", "кальмар": "squid", "мидии": "mussels",
    "краб": "crab", "крабовые палочки": "crab sticks", "икра": "caviar",
    "морская капуста": "seaweed", "рыбные консервы": "canned fish",

    # --- молочные продукты и яйца ---
    "молоко": "milk", "кефир": "kefir", "ряженка": "ryazhenka",
    "простокваша": "buttermilk", "йогурт": "yogurt",
    "греческий йогурт": "greek yogurt", "творог": "cottage cheese",
    "творожок": "cottage cheese", "сметана": "sour cream", "сливки": "cream",
    "сыр": "cheese", "твёрдый сыр": "cheddar cheese", "моцарелла": "mozzarella",
    "брынза": "feta cheese", "фета": "feta cheese", "плавленый сыр": "processed cheese",
    "адыгейский сыр": "adyghe cheese", "маскарпоне": "mascarpone",
    "сливочный сыр": "cream cheese", "масло сливочное": "butter",
    "сливочное масло": "butter", "мороженое": "ice cream",
    "сгущёнка": "condensed milk", "сыворотка": "whey",
    "яйцо": "egg", "яйца": "eggs", "куриное яйцо": "chicken egg",
    "яичный белок": "egg white", "яичный желток": "egg yolk",
    "омлет": "omelette", "яичница": "fried eggs", "перепелиные яйца": "quail eggs",

    # --- овощи ---
    "картофель": "potato", "картошка": "potato", "морковь": "carrot",
    "свёкла": "beetroot", "капуста": "cabbage",
    "белокочанная капуста": "white cabbage", "цветная капуста": "cauliflower",
    "брокколи": "broccoli", "брюссельская капуста": "brussels sprouts",
    "помидор": "tomato", "томат": "tomato", "огурец": "cucumber",
    "перец": "bell pepper", "болгарский перец": "bell pepper",
    "лук": "onion", "репчатый лук": "onion", "зелёный лук": "green onion",
    "чеснок": "garlic", "кабачок": "zucchini", "баклажан": "eggplant",
    "тыква": "pumpkin", "редис": "radish", "редька": "radish",
    "сельдерей": "celery", "шпинат": "spinach", "салат": "lettuce",
    "руккола": "arugula", "укроп": "dill", "петрушка": "parsley",
    "кинза": "cilantro", "базилик": "basil", "зелень": "herbs",
    "кукуруза": "corn", "горошек": "green peas", "зелёный горошек": "green peas",
    "стручковая фасоль": "green beans", "спаржа": "asparagus",
    "авокадо": "avocado", "имбирь": "ginger", "хрен": "horseradish",
    "квашеная капуста": "sauerkraut", "оливки": "olives", "маслины": "olives",

    # --- бобовые, грибы, орехи ---
    "фасоль": "beans", "чечевица": "lentils", "нут": "chickpeas",
    "горох": "peas", "соя": "soybeans", "тофу": "tofu",
    "грибы": "mushrooms", "шампиньоны": "champignon mushrooms",
    "вешенки": "oyster mushrooms", "белые грибы": "porcini mushrooms",
    "орехи": "nuts", "грецкий орех": "walnuts", "миндаль": "almonds",
    "фундук": "hazelnuts", "кешью": "cashews", "арахис": "peanuts",
    "фисташки": "pistachios", "кедровые орехи": "pine nuts",
    "семечки": "sunflower seeds", "семена подсолнечника": "sunflower seeds",
    "тыквенные семечки": "pumpkin seeds", "кунжут": "sesame seeds",
    "лён": "flax seeds", "семена льна": "flax seeds", "чиа": "chia seeds",
    "арахисовая паста": "peanut butter", "арахисовое масло": "peanut butter",

    # --- фрукты и ягоды ---
    "яблоко": "apple", "груша": "pear", "банан": "banana",
    "апельсин": "orange", "мандарин": "mandarin", "грейпфрут": "grapefruit",
    "лимон": "lemon", "лайм": "lime", "виноград": "grapes",
    "киви": "kiwi", "ананас": "pineapple", "манго": "mango",
    "персик": "peach", "абрикос": "apricot", "слива": "plum",
    "вишня": "cherry", "черешня": "sweet cherry", "гранат": "pomegranate",
    "хурма": "persimmon", "дыня": "melon", "арбуз": "watermelon",
    "клубника": "strawberry", "малина": "raspberry", "черника": "blueberry",
    "голубика": "blueberry", "смородина": "currant", "ежевика": "blackberry",
    "клюква": "cranberry", "брусника": "lingonberry", "облепиха": "sea buckthorn",
    "изюм": "raisins", "курага": "dried apricots", "чернослив": "prunes",
    "финики": "dates", "инжир": "figs", "сухофрукты": "dried fruit",

    # --- масла, соусы, приправы ---
    "масло": "oil", "растительное масло": "vegetable oil",
    "подсолнечное масло": "sunflower oil", "оливковое масло": "olive oil",
    "льняное масло": "flaxseed oil", "кокосовое масло": "coconut oil",
    "майонез": "mayonnaise", "кетчуп": "ketchup", "горчица": "mustard",
    "соевый соус": "soy sauce", "томатная паста": "tomato paste",
    "уксус": "vinegar", "соль": "salt", "сахар": "sugar", "мёд": "honey",
    "варенье": "jam", "джем": "jam", "сироп": "syrup",

    # --- сладости и снеки ---
    "шоколад": "chocolate", "тёмный шоколад": "dark chocolate",
    "молочный шоколад": "milk chocolate", "конфеты": "candy",
    "торт": "cake", "пирожное": "pastry", "зефир": "marshmallow",
    "мармелад": "marmalade", "халва": "halva", "пастила": "pastila",
    "чипсы": "potato chips", "попкорн": "popcorn", "крекеры": "crackers",
    "протеиновый батончик": "protein bar", "батончик": "protein bar",

    # --- напитки и спортпит ---
    "вода": "water", "чай": "tea", "зелёный чай": "green tea",
    "кофе": "coffee", "капучино": "cappuccino", "латте": "latte",
    "americano": "americano", "сок": "juice",
    "апельсиновый сок": "orange juice", "яблочный сок": "apple juice",
    "компот": "compote", "морс": "fruit drink", "квас": "kvass",
    "какао": "cocoa", "смузи": "smoothie", "пиво": "beer", "вино": "wine",
    "протеин": "whey protein", "сывороточный протеин": "whey protein",
    "гейнер": "mass gainer", "креатин": "creatine", "бцаа": "bcaa",

    # --- готовые блюда ---
    "борщ": "borscht", "суп": "soup", "щи": "cabbage soup",
    "куриный суп": "chicken soup", "бульон": "broth", "уха": "fish soup",
    "солянка": "solyanka", "окрошка": "okroshka", "плов": "pilaf",
    "пельмени": "dumplings", "вареники": "dumplings", "голубцы": "cabbage rolls",
    "гуляш": "goulash", "рагу": "stew", "запеканка": "casserole",
    "винегрет": "vinaigrette salad", "оливье": "olivier salad",
    "греческий салат": "greek salad", "цезарь": "caesar salad",
    "бутерброд": "sandwich", "сэндвич": "sandwich", "бургер": "burger",
    "шаурма": "shawarma", "суши": "sushi", "роллы": "sushi roll",
    "картофель фри": "french fries", "фри": "french fries",
    "наггетсы": "chicken nuggets", "паста болоньезе": "spaghetti bolognese",
}


def _stem(word: str) -> str:
    """Отрезает падежное окончание, чтобы «гречки» и «гречку» сошлись к «гречк»."""
    w = word.lower().replace("ё", "е")
    for ending in _ENDINGS:
        if len(w) - len(ending) >= 4 and w.endswith(ending):
            return w[: -len(ending)]
    return w


def _key(phrase: str) -> str:
    return " ".join(_stem(part) for part in phrase.split())


# Словарь, приведённый к основам: строится один раз при импорте.
_INDEX: dict[str, str] = {_key(ru): en for ru, en in PRODUCTS.items()}

_CLEAN = re.compile(r"[^а-яёa-z\s-]+", re.IGNORECASE)
_LATIN = re.compile(r"[a-z]", re.IGNORECASE)


def translate(query: str) -> tuple[str, bool]:
    """Переводит название продукта на английский.

    Возвращает пару: строка для поиска и признак, что перевод удался.
    Если в запросе латиница — считаем, что он уже английский, и не трогаем.
    """
    text = _CLEAN.sub(" ", query).strip()
    if not text:
        return query, False

    # «chicken breast» переводить не надо.
    if _LATIN.search(text) and not re.search(r"[а-яё]", text, re.IGNORECASE):
        return text, True

    words = text.split()

    # Сначала пробуем фразу целиком: «куриная грудка» точнее, чем «курица».
    whole = _INDEX.get(_key(text))
    if whole:
        return whole, True

    # Затем пары соседних слов — на случай «масло оливковое холодного отжима».
    for size in (3, 2):
        for i in range(len(words) - size + 1):
            hit = _INDEX.get(_key(" ".join(words[i : i + size])))
            if hit:
                return hit, True

    # И наконец отдельные слова. Последнее слово обычно главное:
    # в «отварная гречка» смысл несёт «гречка».
    for word in reversed(words):
        hit = _INDEX.get(_stem(word))
        if hit:
            return hit, True

    return query, False


def suggestions(query: str, limit: int = 5) -> list[str]:
    """Похожие русские названия — подсказать, когда перевода не нашлось."""
    stem = _stem(query.split()[0]) if query.split() else ""
    if len(stem) < 3:
        return []
    found = [ru for ru in PRODUCTS if _key(ru).startswith(stem[:3])]
    return sorted(found)[:limit]
