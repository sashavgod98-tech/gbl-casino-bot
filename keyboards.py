from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from items import CASES

def main_menu_kb():
  return InlineKeyboardMarkup(
      inline_keyboard=[
          [
              InlineKeyboardButton(text="📈 Краш", callback_data="game_crash"),
              InlineKeyboardButton(text="📦 Кейсы", callback_data="game_cases"),
          ],
          [
              InlineKeyboardButton(text="⚔️ Дуэль", callback_data="game_duel"),
              InlineKeyboardButton(text="⚪/⚫ Белое и Чёрное", callback_data="game_bw"),
          ],
          [
              InlineKeyboardButton(text="🎒 Инвентарь", callback_data="inventory"),
              InlineKeyboardButton(text="🏆 Топы", callback_data="tops"),
          ],
          [
              InlineKeyboardButton(text="🎁 Бонус", callback_data="daily"),
              InlineKeyboardButton(text="👑 Префиксы", callback_data="prefix_shop"),
          ],
          [
              InlineKeyboardButton(text="🎟️ Промокод", callback_data="promo_info"),
              InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
          ],
          [
              InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help"),
          ],
      ]
  )

def cases_kb():
  buttons = []
  for key, case in CASES.items():
    buttons.append([InlineKeyboardButton(text=f"{case['name']} — {case['price']}💰", callback_data=f"open_case_{key}")])
  buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")])
  return InlineKeyboardMarkup(inline_keyboard=buttons)

def crash_kb(action: str = "bet"):
  if action == "bet":
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💰 Ставка 1,000", callback_data="crash_bet_1000")],
            [InlineKeyboardButton(text="💰 Ставка 5,000", callback_data="crash_bet_5000")],
            [InlineKeyboardButton(text="💰 Ставка 10,000", callback_data="crash_bet_10000")],
            [InlineKeyboardButton(text="✍️ Своя ставка", callback_data="crash_custom_bet")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")],
        ]
    )
  elif action == "playing":
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💰 ЗАБРАТЬ ВЫИГРЫШ", callback_data="crash_cashout")]])

def prefix_shop_kb():
  return InlineKeyboardMarkup(
      inline_keyboard=[
          [InlineKeyboardButton(text="[VIP] — 10,000💰", callback_data="color_prefix_[VIP]_10000")],
          [InlineKeyboardButton(text="[BOSS] — 50,000💰", callback_data="color_prefix_[BOSS]_50000")],
          [InlineKeyboardButton(text="[KING] — 150,000💰", callback_data="color_prefix_[KING]_150000")],
          [InlineKeyboardButton(text="[LEGEND] — 500,000💰", callback_data="color_prefix_[LEGEND]_500000")],
          [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")],
      ]
  )

# НОВАЯ КЛАВИАТУРА: ВЫБОР ЦВЕТА
def prefix_color_kb(prefix: str, price: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔴 Красный", callback_data=f"buycolor_{prefix}_red_{price}"),
                InlineKeyboardButton(text="🟢 Зеленый", callback_data=f"buycolor_{prefix}_green_{price}")
            ],
            [
                InlineKeyboardButton(text="🔵 Синий", callback_data=f"buycolor_{prefix}_blue_{price}"),
                InlineKeyboardButton(text="🌈 Радужный", callback_data=f"buycolor_{prefix}_rainbow_{price}")
            ],
            [InlineKeyboardButton(text="⬅️ Назад в магазин", callback_data="prefix_shop")]
        ]
    )

def duel_kb():
  return InlineKeyboardMarkup(
      inline_keyboard=[
          [InlineKeyboardButton(text="⚔️ Дуэль 1,000💰", callback_data="duel_create_1000")],
          [InlineKeyboardButton(text="⚔️ Дуэль 5,000💰", callback_data="duel_create_5000")],
          [InlineKeyboardButton(text="⚔️ Дуэль 25,000💰", callback_data="duel_create_25000")],
          [InlineKeyboardButton(text="📋 Активные дуэли", callback_data="duel_list")],
          [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")],
      ]
  )

def bw_kb():
  return InlineKeyboardMarkup(
      inline_keyboard=[
          [InlineKeyboardButton(text="⚪ Загадать БЕЛОЕ (1,000💰)", callback_data="bw_create_1000_white")],
          [InlineKeyboardButton(text="⚫ Загадать ЧЁРНОЕ (1,000💰)", callback_data="bw_create_1000_black")],
          [InlineKeyboardButton(text="⚪ Загадать БЕЛОЕ (5,000💰)", callback_data="bw_create_5000_white")],
          [InlineKeyboardButton(text="⚫ Загадать ЧЁРНОЕ (5,000💰)", callback_data="bw_create_5000_black")],
          [InlineKeyboardButton(text="📋 Список игр Б/Ч", callback_data="bw_list")],
          [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")],
      ]
  )

def inventory_kb(items: list):
  buttons = []
  for item in items[:8]:
    buttons.append([InlineKeyboardButton(text=f"💸 Продать {item['item_name']} ({item['item_price']}💰)", callback_data=f"sell_item_{item['id']}")])
  if len(items) > 0:
    buttons.append([InlineKeyboardButton(text="💥 ПРОДАТЬ ВСЁ", callback_data="sell_all_items")])
  buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")])
  return InlineKeyboardMarkup(inline_keyboard=buttons)

def tops_kb():
  return InlineKeyboardMarkup(
      inline_keyboard=[
          [InlineKeyboardButton(text="💰 Топ богачей", callback_data="top_balance")],
          [InlineKeyboardButton(text="🎒 Топ коллекционеров", callback_data="top_inventory")],
          [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")],
      ]
  )
