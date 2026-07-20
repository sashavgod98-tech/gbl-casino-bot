import random

RARITIES = {
    'common':    {'name': 'Обычный',     'emoji': '⚪', 'color': 'gray',   'chance': 60},
    'rare':      {'name': 'Редкий',      'emoji': '🔵', 'color': 'blue',   'chance': 25},
    'epic':      {'name': 'Эпический',   'emoji': '🟣', 'color': 'purple', 'chance': 10},
    'legendary': {'name': 'Легендарный', 'emoji': '🟡', 'color': 'gold',   'chance': 4},
    'mythic':    {'name': 'Мифический',  'emoji': '🔴', 'color': 'red',    'chance': 1},
}

ITEMS = {
    'common': [
        ('Игральная карта', 50),
        ('Фишка 10$', 60),
        ('Кости для игры', 55),
        ('Старый жетон', 45),
        ('Сломанная рулетка', 70),
        ('Картонная фишка', 40),
    ],
    'rare': [
        ('Золотая фишка 100$', 200),
        ('Колода карт Premium', 250),
        ('Рулетка Deluxe', 220),
        ('Набор для покера', 280),
        ('Счастливая семёрка', 300),
        ('Браслет победителя', 260),
    ],
    'epic': [
        ('Алмазная фишка 1000$', 600),
        ('Золотая рулетка', 700),
        ('Королевская колода', 650),
        ('Кристалл удачи', 800),
        ('Золотые кости', 750),
        ('VIP жетон', 680),
    ],
    'legendary': [
        ('Корона казино', 2000),
        ('Золотой слиток', 2500),
        ('Алмазный браслет', 2200),
        ('Платиновая фишка', 3000),
        ('Трофей джекпота', 2800),
        ('Золотая карта Туз', 2400),
    ],
    'mythic': [
        ('Ключ от хранилища', 10000),
        ('Золотой чемодан денег', 12000),
        ('Корона владельца казино', 15000),
        ('Алмазный чип', 11000),
        ('Легендарный джекпот', 13000),
    ],
}

CASES = {
    'beggar': {
        'name': '🎰 Новичок Кейс',
        'price': 100,
        'description': 'Базовый кейс для старта',
        'weights': {'common': 70, 'rare': 25, 'epic': 5, 'legendary': 0, 'mythic': 0},
    },
    'army': {
        'name': '💎 Игрок Кейс',
        'price': 500,
        'description': 'Средний кейс с хорошим лутом',
        'weights': {'common': 40, 'rare': 40, 'epic': 15, 'legendary': 5, 'mythic': 0},
    },
    'secret': {
        'name': '🔒 VIP Кейс',
        'price': 2000,
        'description': 'Шанс на мифический предмет!',
        'weights': {'common': 20, 'rare': 35, 'epic': 30, 'legendary': 12, 'mythic': 3},
    },
    'god': {
        'name': ' Магнат Кейс',
        'price': 10000,
        'description': 'Только для олигархов. Максимальные шансы на топ.',
        'weights': {'common': 5, 'rare': 20, 'epic': 40, 'legendary': 25, 'mythic': 10},
    },
}

def roll_rarity(weights: dict) -> str:
    total = sum(weights.values())
    roll = random.randint(1, total)
    cumulative = 0
    for rarity, weight in weights.items():
        cumulative += weight
        if roll <= cumulative:
            return rarity
    return 'common'

def roll_item(rarity: str) -> tuple:
    items = ITEMS.get(rarity, ITEMS['common'])
    return random.choice(items)

def open_case(case_key: str) -> tuple:
    case = CASES[case_key]
    rarity = roll_rarity(case['weights'])
    name, price = roll_item(rarity)
    return rarity, name, price