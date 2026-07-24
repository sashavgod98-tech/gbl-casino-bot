import random

RARITIES = {
    "common": {"name": "Обычное", "emoji": "⚪"},
    "rare": {"name": "Редкое", "emoji": "🔵"},
    "legendary": {"name": "Легендарное", "emoji": "🟡"}
}

CASES = {
    "common": {
        "name": "⚪ Обычный кейс",
        "price": 500,
        "items": [
            ("Деревянный меч", "common", 300),
            ("Кожаный шлем", "common", 450),
            ("Железный слиток", "common", 600)
        ]
    },
    "rare": {
        "name": "💎 Редкий кейс",
        "price": 2500,
        "items": [
            ("Алмазное яблоко", "rare", 2000),
            ("Зачарованная кирка", "rare", 3000),
            ("Золотой щит", "rare", 4000)
        ]
    },
    "legendary": {
        "name": "🔥 Легендарный кейс",
        "price": 10000,
        "items": [
            ("Меч Незерита", "legendary", 9000),
            ("Корона Короля", "legendary", 15000),
            ("Драконий эликсир", "legendary", 25000)
        ]
    }
}

def open_case(case_key: str):
    case = CASES.get(case_key)
    if not case:
        return None
    name, rarity, price = random.choice(case["items"])
    return {"name": name, "rarity": rarity, "price": price}
