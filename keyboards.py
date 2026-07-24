from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="рџ“€ РљСЂР°С€", callback_data="game_crash"),
            InlineKeyboardButton(text="вљЄвљ« Р‘РµР»РѕРµ/Р§С‘СЂРЅРѕРµ", callback_data="game_bw")
        ],
        [
            InlineKeyboardButton(text="вљ”пёЏ Р”СѓСЌР»Рё", callback_data="game_duel"),
            InlineKeyboardButton(text="рџ“¦ РљРµР№СЃС‹", callback_data="game_cases")
        ],
        [
            InlineKeyboardButton(text="рџ‘¤ РџСЂРѕС„РёР»СЊ", callback_data="profile"),
            InlineKeyboardButton(text="рџЋ’ РРЅРІРµРЅС‚Р°СЂСЊ", callback_data="inventory")
        ],
        [
            InlineKeyboardButton(text="рџ‘‘ РџСЂРµС„РёРєСЃС‹", callback_data="prefix_shop"),
            InlineKeyboardButton(text="рџЋЃ Р‘РѕРЅСѓСЃ", callback_data="daily")
        ],
        [
            InlineKeyboardButton(text="рџЏ† РўРѕРї", callback_data="tops"),
            InlineKeyboardButton(text="в„№пёЏ РџРѕРјРѕС‰СЊ", callback_data="help")
        ]
    ])

def prefix_shop_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="[VIP] вЂ” 10,000рџ’°", callback_data="color_prefix_[VIP]_10000"),
            InlineKeyboardButton(text="[BOSS] вЂ” 50,000рџ’°", callback_data="color_prefix_[BOSS]_50000")
        ],
        [
            InlineKeyboardButton(text="[KING] вЂ” 150,000рџ’°", callback_data="color_prefix_[KING]_150000"),
            InlineKeyboardButton(text="[LEGEND] вЂ” 500,000рџ’°", callback_data="color_prefix_[LEGEND]_500000")
        ],
        [InlineKeyboardButton(text="в¬…пёЏ РќР°Р·Р°Рґ", callback_data="back_menu")]
    ])

def prefix_color_kb(prefix: str, price: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="рџ”ґ РљСЂР°СЃРЅС‹Р№", callback_data=f"buycolor_{prefix}_red_{price}"),
            InlineKeyboardButton(text="рџџў Р—РµР»РµРЅС‹Р№", callback_data=f"buycolor_{prefix}_green_{price}")
        ],
        [
            InlineKeyboardButton(text="рџ”µ РЎРёРЅРёР№", callback_data=f"buycolor_{prefix}_blue_{price}"),
            InlineKeyboardButton(text="рџЊ€ Р Р°РґСѓР¶РЅС‹Р№", callback_data=f"buycolor_{prefix}_rainbow_{price}")
        ],
        [InlineKeyboardButton(text="в¬…пёЏ РќР°Р·Р°Рґ", callback_data="prefix_shop")]
    ])

def crash_kb(state="bet"):
    if state == "bet":
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="100рџ’°", callback_data="crash_bet_100"),
                InlineKeyboardButton(text="500рџ’°", callback_data="crash_bet_500"),
                InlineKeyboardButton(text="1,000рџ’°", callback_data="crash_bet_1000")
            ],
            [InlineKeyboardButton(text="вњЌпёЏ РЎРІРѕСЏ СЃС‚Р°РІРєР°", callback_data="crash_custom_bet")],
            [InlineKeyboardButton(text="в¬…пёЏ РќР°Р·Р°Рґ", callback_data="back_menu")]
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="рџ’° Р—РђР‘Р РђРўР¬ Р’Р«РР“Р Р«РЁ", callback_data="crash_cashout")]
        ])

def bw_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="вљЄ Р‘РµР»РѕРµ (1,000рџ’°)", callback_data="bw_create_1000_white"),
            InlineKeyboardButton(text="вљ« Р§С‘СЂРЅРѕРµ (1,000рџ’°)", callback_data="bw_create_1000_black")
        ],
        [
            InlineKeyboardButton(text="вљЄ Р‘РµР»РѕРµ (5,000рџ’°)", callback_data="bw_create_5000_white"),
            InlineKeyboardButton(text="вљ« Р§С‘СЂРЅРѕРµ (5,000рџ’°)", callback_data="bw_create_5000_black")
        ],
        [InlineKeyboardButton(text="рџ“‹ РЎРїРёСЃРѕРє Р°РєС‚РёРІРЅС‹С… РёРіСЂ", callback_data="bw_list")],
        [InlineKeyboardButton(text="в¬…пёЏ РќР°Р·Р°Рґ", callback_data="back_menu")]
    ])

def duel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="вљ”пёЏ Р”СѓСЌР»СЊ 500рџ’°", callback_data="duel_create_500"),
            InlineKeyboardButton(text="вљ”пёЏ Р”СѓСЌР»СЊ 2,500рџ’°", callback_data="duel_create_2500")
        ],
        [InlineKeyboardButton(text="рџ“‹ РђРєС‚РёРІРЅС‹Рµ РґСѓСЌР»Рё", callback_data="duel_list")],
        [InlineKeyboardButton(text="в¬…пёЏ РќР°Р·Р°Рґ", callback_data="back_menu")]
    ])

def cases_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="рџ“¦ РћР±С‹С‡РЅС‹Р№ (500рџ’°)", callback_data="open_case_common"),
            InlineKeyboardButton(text="рџ’Ћ Р РµРґРєРёР№ (2,500рџ’°)", callback_data="open_case_rare")
        ],
        [InlineKeyboardButton(text="рџ”Ґ Р›РµРіРµРЅРґР°СЂРЅС‹Р№ (10,000рџ’°)", callback_data="open_case_legendary")],
        [InlineKeyboardButton(text="в¬…пёЏ РќР°Р·Р°Рґ", callback_data="back_menu")]
    ])

def inventory_kb(items):
    kb = []
    if items:
        kb.append([InlineKeyboardButton(text="рџ’Ґ РџСЂРѕРґР°С‚СЊ РІСЃС‘", callback_data="sell_all_items")])
    kb.append([InlineKeyboardButton(text="в¬…пёЏ РќР°Р·Р°Рґ", callback_data="back_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def tops_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="рџ’° РўРѕРї РїРѕ Р±Р°Р»Р°РЅСЃСѓ", callback_data="top_balance"),
            InlineKeyboardButton(text="рџЋ’ РўРѕРї РїРѕ РёРЅРІРµРЅС‚Р°СЂСЋ", callback_data="top_inventory")
        ],
        [InlineKeyboardButton(text="в¬…пёЏ Р’ РіР»Р°РІРЅРѕРµ РјРµРЅСЋ", callback_data="back_menu")]
    ])
