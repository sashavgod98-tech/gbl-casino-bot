from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📈 Краш", callback_data="game_crash"),
            InlineKeyboardButton(text="⚪⚫ Белое/Чёрное", callback_data="game_bw")
        ],
        [
            InlineKeyboardButton(text="⚔️ Дуэли", callback_data="game_duel"),
            InlineKeyboardButton(text="🎲 Кости", callback_data="game_dice")
        ],
        [
            InlineKeyboardButton(text="🎰 Слоты", callback_data="game_slots"),
            InlineKeyboardButton(text="✊✋✌️ КНБ", callback_data="game_rps")
        ],
        [
            InlineKeyboardButton(text="💣 Мины", callback_data="game_mines"),
            InlineKeyboardButton(text="🎡 Рулетка", callback_data="game_roulette")
        ],
        [
            InlineKeyboardButton(text="📦 Кейсы", callback_data="cases"),
            InlineKeyboardButton(text="🏢 Бизнес", callback_data="business_menu")
        ],
        [
            InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
            InlineKeyboardButton(text="🎒 Инвентарь", callback_data="inventory")
        ],
        [
            InlineKeyboardButton(text="👑 Префиксы", callback_data="prefix_shop"),
            InlineKeyboardButton(text="🎁 Бонус", callback_data="daily")
        ],
        [
            InlineKeyboardButton(text="🏆 Топ", callback_data="tops"),
            InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")
        ],
        [
            InlineKeyboardButton(text="⭐ Донат за Stars", callback_data="donate")
        ]
    ])

def prefix_shop_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="[VIP] — 10,000💰", callback_data="color_prefix_[VIP]_10000"),
            InlineKeyboardButton(text="[BOSS] — 50,000💰", callback_data="color_prefix_[BOSS]_50000")
        ],
        [
            InlineKeyboardButton(text="[KING] — 150,000💰", callback_data="color_prefix_[KING]_150000"),
            InlineKeyboardButton(text="[LEGEND] — 500,000💰", callback_data="color_prefix_[LEGEND]_500000")
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")]
    ])

def prefix_color_kb(prefix: str, price: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔴 Красный", callback_data=f"buycolor_{prefix}_red_{price}"),
            InlineKeyboardButton(text="🟢 Зеленый", callback_data=f"buycolor_{prefix}_green_{price}")
        ],
        [
            InlineKeyboardButton(text="🔵 Синий", callback_data=f"buycolor_{prefix}_blue_{price}"),
            InlineKeyboardButton(text="🌈 Радужный", callback_data=f"buycolor_{prefix}_rainbow_{price}")
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="prefix_shop")]
    ])

def crash_kb(state="bet"):
    if state == "bet":
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="100💰", callback_data="crash_bet_100"),
                InlineKeyboardButton(text="500💰", callback_data="crash_bet_500"),
                InlineKeyboardButton(text="1,000💰", callback_data="crash_bet_1000")
            ],
            [InlineKeyboardButton(text="✍️ Своя ставка", callback_data="crash_custom_bet")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")]
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 ЗАБРАТЬ ВЫИГРЫШ", callback_data="crash_cashout")]
        ])

def bw_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚪ Белое (1,000💰)", callback_data="bw_create_1000_white"),
            InlineKeyboardButton(text="⚫ Чёрное (1,000💰)", callback_data="bw_create_1000_black")
        ],
        [
            InlineKeyboardButton(text="⚪ Белое (5,000💰)", callback_data="bw_create_5000_white"),
            InlineKeyboardButton(text="⚫ Чёрное (5,000💰)", callback_data="bw_create_5000_black")
        ],
        [InlineKeyboardButton(text="📋 Список активных игр", callback_data="bw_list")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")]
    ])

def duel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚔️ Дуэль 500💰", callback_data="duel_create_500"),
            InlineKeyboardButton(text="⚔️ Дуэль 2,500💰", callback_data="duel_create_2500")
        ],
        [InlineKeyboardButton(text="📋 Активные дуэли", callback_data="duel_list")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")]
    ])

def cases_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📦 Обычный (500💰)", callback_data="open_case_common"),
            InlineKeyboardButton(text="💎 Редкий (2,500💰)", callback_data="open_case_rare")
        ],
        [InlineKeyboardButton(text="🔥 Легендарный (10,000💰)", callback_data="open_case_legendary")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")]
    ])

def inventory_kb(items):
    kb = []
    if items:
        kb.append([InlineKeyboardButton(text="💥 Продать всё", callback_data="sell_all_items")])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def tops_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💰 Топ по балансу", callback_data="top_balance"),
            InlineKeyboardButton(text="🎒 Топ по инвентарю", callback_data="top_inventory")
        ],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="back_menu")]
    ])


# === КОСТИ (PvP) ===
def dice_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎲 Дуэль 500💰", callback_data="dice_create_500"),
            InlineKeyboardButton(text="🎲 Дуэль 2,500💰", callback_data="dice_create_2500")
        ],
        [InlineKeyboardButton(text="📋 Активные игры", callback_data="dice_list")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")]
    ])


# === СЛОТЫ ===
def slots_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="100💰", callback_data="slots_spin_100"),
            InlineKeyboardButton(text="500💰", callback_data="slots_spin_500"),
            InlineKeyboardButton(text="1,000💰", callback_data="slots_spin_1000")
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")]
    ])


def slots_again_kb(bet: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Крутить ещё раз", callback_data=f"slots_spin_{bet}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="game_slots")]
    ])


# === КАМЕНЬ-НОЖНИЦЫ-БУМАГА ===
def rps_bet_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="100💰", callback_data="rps_bet_100"),
            InlineKeyboardButton(text="500💰", callback_data="rps_bet_500"),
            InlineKeyboardButton(text="1,000💰", callback_data="rps_bet_1000")
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")]
    ])


def rps_choice_kb(bet: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🪨 Камень", callback_data=f"rps_play_{bet}_rock"),
            InlineKeyboardButton(text="📄 Бумага", callback_data=f"rps_play_{bet}_paper"),
            InlineKeyboardButton(text="✂️ Ножницы", callback_data=f"rps_play_{bet}_scissors")
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="game_rps")]
    ])


# === МИНЫ ===
def mines_bet_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="500💰", callback_data="mines_bet_500"),
            InlineKeyboardButton(text="2,000💰", callback_data="mines_bet_2000"),
            InlineKeyboardButton(text="5,000💰", callback_data="mines_bet_5000")
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")]
    ])


def mines_diff_kb(bet: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💣 3 мины", callback_data=f"mines_diff_{bet}_3"),
            InlineKeyboardButton(text="💣 5 мин", callback_data=f"mines_diff_{bet}_5")
        ],
        [
            InlineKeyboardButton(text="💣 7 мин", callback_data=f"mines_diff_{bet}_7"),
            InlineKeyboardButton(text="💣 10 мин", callback_data=f"mines_diff_{bet}_10")
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="game_mines")]
    ])


def mines_board_kb(game):
    kb = []
    for row in range(5):
        row_buttons = []
        for col in range(5):
            idx = row * 5 + col
            if idx in game["revealed"]:
                row_buttons.append(InlineKeyboardButton(text="✅", callback_data="mines_noop"))
            else:
                row_buttons.append(InlineKeyboardButton(text="🔲", callback_data=f"mines_pick_{idx}"))
        kb.append(row_buttons)

    if game["revealed"]:
        kb.append([InlineKeyboardButton(text="💰 Забрать выигрыш", callback_data="mines_cashout")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def mines_result_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Сыграть ещё раз", callback_data="game_mines")],
        [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_menu")]
    ])


# === РУЛЕТКА ===
def roulette_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Цвет (x2)", callback_data="roul_cat_color")],
        [InlineKeyboardButton(text="🔢 Дюжины (x3)", callback_data="roul_cat_dozen")],
        [InlineKeyboardButton(text="📊 Столбцы (x3)", callback_data="roul_cat_column")],
        [InlineKeyboardButton(text="⚖️ Чёт/Нечет (x2)", callback_data="roul_cat_evenodd")],
        [InlineKeyboardButton(text="⬆️⬇️ 1-18 / 19-36 (x2)", callback_data="roul_cat_highlow")],
        [InlineKeyboardButton(text="🎯 Число 0-36 (x36)", callback_data="roul_number_start")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")]
    ])


def roulette_outcome_kb(category: str):
    options_map = {
        "color": [("🔴 Красное", "red"), ("⚫ Чёрное", "black")],
        "dozen": [("1️⃣ 1-12", "1"), ("2️⃣ 13-24", "2"), ("3️⃣ 25-36", "3")],
        "column": [("1-й столбец", "1"), ("2-й столбец", "2"), ("3-й столбец", "3")],
        "evenodd": [("Чётное", "even"), ("Нечётное", "odd")],
        "highlow": [("⬇️ 1-18", "low"), ("⬆️ 19-36", "high")],
    }
    options = options_map.get(category, [])
    buttons = [
        InlineKeyboardButton(text=label, callback_data=f"roul_outcome_{category}_{value}")
        for label, value in options
    ]
    kb = [buttons] if len(buttons) <= 2 else [buttons[:2], buttons[2:]]
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="game_roulette")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def roulette_amount_kb(category: str, outcome: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="100💰", callback_data=f"roul_spin_{category}_{outcome}_100"),
            InlineKeyboardButton(text="500💰", callback_data=f"roul_spin_{category}_{outcome}_500"),
            InlineKeyboardButton(text="1,000💰", callback_data=f"roul_spin_{category}_{outcome}_1000")
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="game_roulette")]
    ])


def roulette_number_amount_kb(number: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="100💰", callback_data=f"roul_spin_number_{number}_100"),
            InlineKeyboardButton(text="500💰", callback_data=f"roul_spin_number_{number}_500"),
            InlineKeyboardButton(text="1,000💰", callback_data=f"roul_spin_number_{number}_1000")
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="game_roulette")]
    ])


def roulette_again_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Крутить ещё раз", callback_data="game_roulette")],
        [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_menu")]
    ])


# === БИЗНЕСЫ (ПАССИВНЫЙ ДОХОД) ===
def business_menu_kb(businesses_status):
    """businesses_status: список словарей {key, name, price, owned, pending}"""
    kb = []
    for b in businesses_status:
        if not b["owned"]:
            price_str = f"{b['price']:,}".replace(",", " ")
            kb.append([InlineKeyboardButton(
                text=f"{b['name']} — купить за {price_str}💰",
                callback_data=f"biz_buy_{b['key']}"
            )])
        elif b["pending"] > 0:
            pending_str = f"{b['pending']:,}".replace(",", " ")
            kb.append([InlineKeyboardButton(
                text=f"{b['name']} | Собрать {pending_str}💰",
                callback_data=f"biz_collect_{b['key']}"
            )])
        else:
            kb.append([InlineKeyboardButton(
                text=f"{b['name']} | ✅ Куплено, доход копится...",
                callback_data="biz_noop"
            )])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


# === ДОНАТ ЗА TELEGRAM STARS ===
def donate_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="50⭐ → 5,500💰", callback_data="donate_small")],
        [InlineKeyboardButton(text="100⭐ → 12,000💰", callback_data="donate_medium")],
        [InlineKeyboardButton(text="250⭐ → 32,000💰", callback_data="donate_large")],
        [InlineKeyboardButton(text="500⭐ → 70,000💰", callback_data="donate_mega")],
        [InlineKeyboardButton(text="✍️ Своя сумма", callback_data="donate_custom")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")]
    ])
