from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from items import CASES

def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=" Краш", callback_data="game_crash"),
            InlineKeyboardButton(text="📦 Кейсы", callback_data="game_cases"),
        ],
        [
            InlineKeyboardButton(text="⚔️ Дуэль", callback_data="game_duel"),
            InlineKeyboardButton(text="🎁 Бонус", callback_data="daily"),
        ],
        [
            InlineKeyboardButton(text="🎒 Инвентарь", callback_data="inventory"),
            InlineKeyboardButton(text="🏆 Топы", callback_data="tops"),
        ],
        [
            InlineKeyboardButton(text="🎟️ Промокод", callback_data="promo"),
            InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
        ],
        [
            InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help"),
        ],
    ])

def cases_kb():
    buttons = []
    for key, case in CASES.items():
        buttons.append([InlineKeyboardButton(
            text=f"{case['name']} — {case['price']}💰",
            callback_data=f"open_case_{key}"
        )])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def crash_kb(action: str = "bet"):
    if action == "bet":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=" Ставка 100", callback_data="crash_bet_100")],
            [InlineKeyboardButton(text="💰 Ставка 500", callback_data="crash_bet_500")],
            [InlineKeyboardButton(text="💰 Ставка 1000", callback_data="crash_bet_1000")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")],
        ])
    elif action == "playing":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 ЗАБРАТЬ ВЫИГРЫШ", callback_data="crash_cashout")],
        ])

def duel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ Создать дуэль (500)", callback_data="duel_create_500")],
        [InlineKeyboardButton(text="️ Создать дуэль (1000)", callback_data="duel_create_1000")],
        [InlineKeyboardButton(text="️ Создать дуэль (5000)", callback_data="duel_create_5000")],
        [InlineKeyboardButton(text="📋 Активные дуэли", callback_data="duel_list")],
        [InlineKeyboardButton(text="️ Назад", callback_data="back_menu")],
    ])

def inventory_kb(items: list):
    buttons = []
    for item in items[:10]:
        buttons.append([InlineKeyboardButton(
            text=f"💸 Продать {item['item_name']} ({item['item_price']}💰)",
            callback_data=f"sell_item_{item['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def tops_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Топ богачей", callback_data="top_balance")],
        [InlineKeyboardButton(text="🎒 Топ коллекционеров", callback_data="top_inventory")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")],
    ])