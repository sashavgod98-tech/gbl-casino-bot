from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📈 Краш", callback_data="game_crash"),
            InlineKeyboardButton(text="⚪⚫ Белое/Чёрное", callback_data="game_bw")
        ],
        [
            InlineKeyboardButton(text="⚔️ Дуэли", callback_data="game_duel"),
            InlineKeyboardButton(text="📦 Кейсы", callback_data="game_cases")
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
