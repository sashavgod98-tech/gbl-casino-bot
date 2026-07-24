import asyncio
import logging
import os
import random
from aiogram import Bot, Dispatcher, F, Router, BaseMiddleware
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
)
from dotenv import load_dotenvР¤
from games import (
    active_bw_games, active_crash_games, active_duels, cashout_crash,
    create_bw_game, create_duel, get_waiting_bw_games, get_waiting_duels,
    join_bw_game, join_duel, resolve_duel, run_crash_game,
)
from items import CASES, RARITIES, open_case
from keyboards import (
    bw_kb, cases_kb, crash_kb, duel_kb, inventory_kb, main_menu_kb,
    prefix_color_kb, prefix_shop_kb, tops_kb,
)
from database import db
# РРЅРёС†РёР°Р»РёР·Р°С†РёСЏ РѕРєСЂСѓР¶РµРЅРёСЏ
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

# РќР°СЃС‚СЂРѕР№РєР° Р»РѕРіРёСЂРѕРІР°РЅРёСЏ
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# РРЅРёС†РёР°Р»РёР·Р°С†РёСЏ Р±РѕС‚Р° Рё РґРёСЃРїРµС‚С‡РµСЂР°
bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher(storage=MemoryStorage())
router = Router()

# РҐСЂР°РЅРёР»РёС‰Рµ РїСЂСЏРјС‹С… РґСѓСЌР»РµР№ (РїРѕ РІС‹Р·РѕРІСѓ)
direct_duels = {}
direct_duel_counter = 1


# === РњРР”Р›Р’РђР Р¬: РђР’РўРћР Р•Р“РРЎРўР РђР¦РРЇ Р РўР Р•РљРРќР“ Р§РђРўРћР’ Р РћР‘РќРћР’Р›Р•РќРР• РќРРљРћР’ ===
class AutoRegisterMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user_obj = None

        if isinstance(event, Message):
            if event.chat:
                await db.register_chat(event.chat.id, event.chat.type)
            user_obj = event.from_user
        elif isinstance(event, CallbackQuery):
            if event.message and event.message.chat:
                await db.register_chat(event.message.chat.id, event.message.chat.type)
            user_obj = event.from_user

        # РђРІС‚РѕСЂРµРіРёСЃС‚СЂР°С†РёСЏ Рё РѕР±РЅРѕРІР»РµРЅРёРµ РїСЂРѕС„РёР»СЏ
        if user_obj and not user_obj.is_bot:
            username = user_obj.username
            current_display_name = f"@{username}" if username else user_obj.first_name or "РРіСЂРѕРє"

            user = await db.get_user(user_obj.id)
            if not user:
                await db.create_user(user_obj.id, current_display_name)
            elif user.get("username") != current_display_name:
                await db.update_user_info(user_obj.id, current_display_name)

        return await handler(event, data)


router.message.middleware(AutoRegisterMiddleware())
router.callback_query.middleware(AutoRegisterMiddleware())
dp.include_router(router)


class Form(StatesGroup):
    waiting_custom_crash = State()


# === РђР’РўРћРњРђРўРР§Р•РЎРљРђРЇ Р Р•РљР›РђРњРђ Р’ Р‘Р•РЎР•Р”РђРҐ (Р РђР— Р’ Р§РђРЎ) ===
async def ad_loop(bot_instance: Bot):
    while True:
        await asyncio.sleep(3600)  # 1 С‡Р°СЃ
        try:
            chats = await db.get_all_chats()
            for chat in chats:
                if chat.get('type') in ('group', 'supergroup'):
                    try:
                        await bot_instance.send_message(
                            chat['chat_id'], 
                            "рџ‘‹ <b>РџСЂРёРІРµС‚, РґСЂСѓР¶РёС‰Рµ!</b>\n\n"
                            "РќРµ С…РѕС‡РµС€СЊ РёСЃРїС‹С‚Р°С‚СЊ СѓРґР°С‡Сѓ Рё РїРѕРёРіСЂР°С‚СЊ РІ <b>GBL Casino</b>?\n"
                            "Р—Р°С…РѕРґРё, Р·Р°Р±РёСЂР°Р№ РµР¶РµРґРЅРµРІРЅС‹Р№ Р±РѕРЅСѓСЃ 2,500рџ’°, РѕС‚РєСЂС‹РІР°Р№ РєРµР№СЃС‹ Рё РёРіСЂР°Р№ СЃ РґСЂСѓР·СЊСЏРјРё!",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                InlineKeyboardButton(text="рџЋ® РРіСЂР°С‚СЊ!", url="https://t.me/gbl_games_bot")
                            ]])
                        )
                        await asyncio.sleep(0.1)  # Р—Р°С‰РёС‚Р° РѕС‚ FloodLimit Telegram
                    except Exception as e:
                        logger.warning(f"Failed to send ad to chat {chat['chat_id']}: {e}")
        except Exception as e:
            logger.error(f"Error in ad loop: {e}")


# === РЎРўРђР Рў ===
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id

    user = await db.get_user(user_id)
    ref_link = await db.get_referral_link(user_id)
    user_rank = await db.get_user_rank(user_id)
    pref = f"{user['prefix']} " if user and user.get('prefix') else ""

    text = (
        f"рџЋ® <b>Р”РѕР±СЂРѕ РїРѕР¶Р°Р»РѕРІР°С‚СЊ РІ GBL Casino!</b>\n\n"
        f"рџ‘¤ РРіСЂРѕРє: <b>{pref}{user['username']}</b>\n"
        f"рџ’° Р‘Р°Р»Р°РЅСЃ: <b>{user['balance']}рџ’°</b>\n"
        f"рџЏ† РњРµСЃС‚Рѕ РІ С‚РѕРїРµ: <b>#{user_rank or 'вЂ”'}</b>\n\n"
        f"рџ”— Р РµС„РµСЂР°Р»СЊРЅР°СЏ СЃСЃС‹Р»РєР°:\n<code>{ref_link}</code>\n\n"
        f"Р’С‹Р±РёСЂР°Р№ СЂРµР¶РёРј РёРіСЂС‹ РІ РјРµРЅСЋ РЅРёР¶Рµ рџ‘‡"
    )

    await message.answer(text, reply_markup=main_menu_kb())


# === РџР•Р РЎРћРќРђР›Р¬РќР«Р• Р”РЈР­Р›Р Р’ Р§РђРўР• (РћРўР’Р•РўРћРњ РќРђ РЎРћРћР‘Р©Р•РќРР•) ===
@router.message(Command("duel"))
@router.message(F.text & F.text.lower().startswith(("РґСѓСЌР»СЊ", "РґСѓРµР»СЊ")))
async def create_direct_duel(message: Message):
    if not message.reply_to_message or not message.reply_to_message.from_user:
        return await message.answer(
            "вљ пёЏ <b>РљР°Рє Р±СЂРѕСЃРёС‚СЊ РІС‹Р·РѕРІ:</b>\n"
            "РћС‚РІРµС‚СЊ (reply) РЅР° СЃРѕРѕР±С‰РµРЅРёРµ РёРіСЂРѕРєР° С‚РµРєСЃС‚РѕРј:\n"
            "<code>РґСѓСЌР»СЊ 100</code>"
        )

    target_user = message.reply_to_message.from_user

    if target_user.id == message.from_user.id:
        return await message.answer("вќЊ РќРµР»СЊР·СЏ РІС‹Р·РІР°С‚СЊ РЅР° РґСѓСЌР»СЊ СЃР°РјРѕРіРѕ СЃРµР±СЏ!")
    
    if target_user.is_bot:
        return await message.answer("вќЊ РќРµР»СЊР·СЏ РІС‹Р·С‹РІР°С‚СЊ Р±РѕС‚РѕРІ!")

    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        return await message.answer("вљ пёЏ РЈРєР°Р¶Рё РєРѕСЂСЂРµРєС‚РЅСѓСЋ СЃСѓРјРјСѓ РґСѓСЌР»Рё! РџСЂРёРјРµСЂ: <code>РґСѓСЌР»СЊ 500</code>")

    bet = int(parts[1])
    if bet <= 0:
        return await message.answer("вќЊ РЎС‚Р°РІРєР° РґРѕР»Р¶РЅР° Р±С‹С‚СЊ Р±РѕР»СЊС€Рµ 0рџ’°!")

    challenger_db = await db.get_user(message.from_user.id)
    if not challenger_db or challenger_db["balance"] < bet:
        return await message.answer(f"вќЊ РЈ С‚РµР±СЏ РЅРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ СЃСЂРµРґСЃС‚РІ! РўРІРѕР№ Р±Р°Р»Р°РЅСЃ: <b>{challenger_db['balance'] if challenger_db else 0}рџ’°</b>")

    target_db = await db.get_user(target_user.id)
    if not target_db:
        t_display = f"@{target_user.username}" if target_user.username else target_user.first_name or "РРіСЂРѕРє"
        await db.create_user(target_user.id, t_display)
        target_db = await db.get_user(target_user.id)

    if target_db["balance"] < bet:
        return await message.answer(f"вќЊ РЈ РёРіСЂРѕРєР° <b>{target_db['username']}</b> РЅРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ СЃСЂРµРґСЃС‚РІ ({target_db['balance']}рџ’°)!")

    global direct_duel_counter
    duel_id = direct_duel_counter
    direct_duel_counter += 1

    direct_duels[duel_id] = {
        "challenger_id": message.from_user.id,
        "challenger_name": challenger_db["username"],
        "target_id": target_user.id,
        "target_name": target_db["username"],
        "bet": bet,
    }

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="вљ”пёЏ РџСЂРёРЅСЏС‚СЊ", callback_data=f"dduel_accept_{duel_id}"),
            InlineKeyboardButton(text="вќЊ РћС‚РєР»РѕРЅРёС‚СЊ", callback_data=f"dduel_decline_{duel_id}")
        ]
    ])

    target_mention = f"@{target_user.username}" if target_user.username else f"<b>{target_db['username']}</b>"

    await message.answer(
        f"вљ”пёЏ <b>Р’Р«Р—РћР’ РќРђ Р”РЈР­Р›Р¬!</b>\n\n"
        f"РРіСЂРѕРє <b>{challenger_db['username']}</b> РІС‹Р·С‹РІР°РµС‚ РЅР° РґСѓСЌР»СЊ {target_mention}!\n"
        f"рџ’° РЎС‚Р°РІРєР°: <b>{bet}рџ’°</b>\n\n"
        f"Р–РґРµРј РѕС‚РІРµС‚Р° СЃРѕРїРµСЂРЅРёРєР°...",
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("dduel_accept_"))
async def accept_direct_duel(callback: CallbackQuery):
    duel_id = int(callback.data.replace("dduel_accept_", ""))
    duel = direct_duels.pop(duel_id, None)

    if not duel:
        return await callback.answer("вќЊ Р­С‚Р° РґСѓСЌР»СЊ Р±РѕР»СЊС€Рµ РЅРµРґРµР№СЃС‚РІРёС‚РµР»СЊРЅР°!", show_alert=True)

    if callback.from_user.id != duel["target_id"]:
        direct_duels[duel_id] = duel # Р’РѕР·РІСЂР°С‰Р°РµРј РѕР±СЂР°С‚РЅРѕ, РµСЃР»Рё РЅР°Р¶Р°Р» РЅРµ С‚РѕС‚
        return await callback.answer("вќЊ Р­С‚РѕС‚ РІС‹Р·РѕРІ Р°РґСЂРµСЃРѕРІР°РЅ РЅРµ С‚РµР±Рµ!", show_alert=True)

    challenger = await db.get_user(duel["challenger_id"])
    target = await db.get_user(duel["target_id"])

    if not challenger or challenger["balance"] < duel["bet"]:
        return await callback.answer("вќЊ РЈ Р·Р°С‡РёРЅС‰РёРєР° РґСѓСЌР»Рё РЅРµ С…РІР°С‚Р°РµС‚ СЃСЂРµРґСЃС‚РІ!", show_alert=True)

    if not target or target["balance"] < duel["bet"]:
        direct_duels[duel_id] = duel # Р’РѕР·РІСЂР°С‰Р°РµРј РѕР±СЂР°С‚РЅРѕ
        return await callback.answer("вќЊ РЈ С‚РµР±СЏ РЅРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ СЃСЂРµРґСЃС‚РІ РґР»СЏ РїСЂРёРЅСЏС‚РёСЏ РґСѓСЌР»Рё!", show_alert=True)

    # РЎРїРёСЃР°РЅРёРµ СЃС‚Р°РІРѕРє
    await db.update_balance(duel["challenger_id"], -duel["bet"])
    await db.update_balance(duel["target_id"], -duel["bet"])

    # РћРїСЂРµРґРµР»РµРЅРёРµ РїРѕР±РµРґРёС‚РµР»СЏ 50/50
    winner_id, loser_id = random.choice([
        (duel["challenger_id"], duel["target_id"]),
        (duel["target_id"], duel["challenger_id"])
    ])

    prize = int(duel["bet"] * 2 * 0.95)  # Р’С‹РёРіСЂС‹С€ Р·Р° РІС‹С‡РµС‚РѕРј 5% РєРѕРјРёСЃСЃРёРё
    await db.update_balance(winner_id, prize)

    winner = await db.get_user(winner_id)
    loser = await db.get_user(loser_id)

    await callback.message.edit_text(
        f"вљ”пёЏ <b>Р”РЈР­Р›Р¬ РЎРћРЎРўРћРЇР›РђРЎР¬!</b>\n\n"
        f"рџЄ™ РњРѕРЅРµС‚РєР° РїРѕРґР±СЂРѕС€РµРЅР°...\n\n"
        f"рџЏ† РџРѕР±РµРґРёС‚РµР»СЊ: <b>{winner['username']}</b> (+{prize}рџ’°)!\n"
        f"рџ’Ђ РџРѕРІРµСЂР¶РµРЅ: <b>{loser['username']}</b>"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("dduel_decline_"))
async def decline_direct_duel(callback: CallbackQuery):
    duel_id = int(callback.data.replace("dduel_decline_", ""))
    duel = direct_duels.get(duel_id)

    if not duel:
        return await callback.answer("вќЊ Р”СѓСЌР»СЊ РЅРµ РЅР°Р№РґРµРЅР°!", show_alert=True)

    if callback.from_user.id not in (duel["target_id"], duel["challenger_id"]):
        return await callback.answer("вќЊ РўС‹ РЅРµ СЏРІР»СЏРµС€СЊСЃСЏ СѓС‡Р°СЃС‚РЅРёРєРѕРј СЌС‚РѕР№ РґСѓСЌР»Рё!", show_alert=True)

    del direct_duels[duel_id]
    await callback.message.edit_text("вќЊ <b>Р”СѓСЌР»СЊ РѕС‚РєР»РѕРЅРµРЅР°.</b>")
    await callback.answer("Р”СѓСЌР»СЊ РѕС‚РјРµРЅРµРЅР°.")


# === РџР•Р Р•Р’РћР” Р”Р•РќР•Р“ РР“Р РћРљРЈ ===
@router.message(Command("pay", "give"))
@router.message(F.text & F.text.lower().startswith(("РїРµСЂРµРґР°С‚СЊ", "pay", "give")))
async def transfer_money_cmd(message: Message):
    if not message.reply_to_message or not message.reply_to_message.from_user:
        return await message.answer(
            "вљ пёЏ <b>РљР°Рє РїРµСЂРµРґР°С‚СЊ РґРµРЅСЊРіРё:</b>\n"
            "РћС‚РІРµС‚СЊ (reply) РЅР° СЃРѕРѕР±С‰РµРЅРёРµ РёРіСЂРѕРєР° С‚РµРєСЃС‚РѕРј:\n"
            "<code>РїРµСЂРµРґР°С‚СЊ 100</code>"
        )

    target_user = message.reply_to_message.from_user
    
    if target_user.id == message.from_user.id:
        return await message.answer("вќЊ РќРµР»СЊР·СЏ РїРµСЂРµРІРѕРґРёС‚СЊ РґРµРЅСЊРіРё СЃР°РјРѕРјСѓ СЃРµР±Рµ!")
    if target_user.is_bot:
        return await message.answer("вќЊ РќРµР»СЊР·СЏ РїРµСЂРµРІРѕРґРёС‚СЊ РґРµРЅСЊРіРё Р±РѕС‚Р°Рј!")

    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        return await message.answer("вљ пёЏ РЈРєР°Р¶Рё РєРѕСЂСЂРµРєС‚РЅСѓСЋ СЃСѓРјРјСѓ РґР»СЏ РїРµСЂРµРІРѕРґР°! РџСЂРёРјРµСЂ: <code>РїРµСЂРµРґР°С‚СЊ 500</code>")

    amount = int(parts[1])
    if amount <= 0:
        return await message.answer("вќЊ РЎСѓРјРјР° РїРµСЂРµРІРѕРґР° РґРѕР»Р¶РЅР° Р±С‹С‚СЊ Р±РѕР»СЊС€Рµ 0рџ’°!")

    sender_db = await db.get_user(message.from_user.id)
    if not sender_db or sender_db["balance"] < amount:
        return await message.answer(f"вќЊ РЈ С‚РµР±СЏ РЅРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ СЃСЂРµРґСЃС‚РІ! РўРІРѕР№ Р±Р°Р»Р°РЅСЃ: <b>{sender_db['balance'] if sender_db else 0}рџ’°</b>")

    target_db = await db.get_user(target_user.id)
    if not target_db:
        t_display = f"@{target_user.username}" if target_user.username else target_user.first_name or "РРіСЂРѕРє"
        await db.create_user(target_user.id, t_display)
        target_db = await db.get_user(target_user.id)

    # РџРµСЂРµРІРѕРґ СЃСЂРµРґСЃС‚РІ
    await db.update_balance(message.from_user.id, -amount)
    await db.update_balance(target_user.id, amount)

    await message.answer(
        f"вњ… <b>РЈСЃРїРµС€РЅС‹Р№ РїРµСЂРµРІРѕРґ!</b>\n\n"
        f"РўС‹ РїРµСЂРµРІРµР» <b>{amount}рџ’°</b> РёРіСЂРѕРєСѓ <b>{target_db['username']}</b>."
    )


# === РЎРРЎРўР•РњРђ РџР РћРњРћРљРћР”РћР’ ===
@router.message(Command("createpromo"))
async def cmd_create_promo(message: Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("вќЊ РЈ РІР°СЃ РЅРµС‚ РїСЂР°РІ РґР»СЏ СЃРѕР·РґР°РЅРёСЏ РїСЂРѕРјРѕРєРѕРґРѕРІ!")

    parts = message.text.split()
    if len(parts) != 4:
        return await message.answer(
            "вљ пёЏ <b>РћС€РёР±РєР° С„РѕСЂРјР°С‚Р°!</b>\n"
            "РСЃРїРѕР»СЊР·СѓР№: <code>/createpromo [РєРѕРґ] [РЅР°РіСЂР°РґР°] [Р»РёРјРёС‚]</code>\n"
            "РџСЂРёРјРµСЂ: <code>/createpromo GBL2024 5000 100</code>"
        )

    code = parts[1].upper()
    try:
        reward = int(parts[2])
        limit = int(parts[3])
    except ValueError:
        return await message.answer("вќЊ РќР°РіСЂР°РґР° Рё Р»РёРјРёС‚ РґРѕР»Р¶РЅС‹ Р±С‹С‚СЊ С‡РёСЃР»Р°РјРё!")

    if reward <= 0 or limit <= 0:
        return await message.answer("вќЊ РќР°РіСЂР°РґР° Рё Р»РёРјРёС‚ РґРѕР»Р¶РЅС‹ Р±С‹С‚СЊ Р±РѕР»СЊС€Рµ РЅСѓР»СЏ!")

    await db.add_promo_code(code, reward, limit)
    await message.answer(
        f"вњ… <b>РџСЂРѕРјРѕРєРѕРґ СѓСЃРїРµС€РЅРѕ СЃРѕР·РґР°РЅ!</b>\n\n"
        f"рџЋџ РљРѕРґ: <b>{code}</b>\n"
        f"рџ’° РќР°РіСЂР°РґР°: <b>{reward}рџ’°</b>\n"
        f"рџ‘Ґ Р›РёРјРёС‚ Р°РєС‚РёРІР°С†РёР№: <b>{limit}</b>"
    )

@router.message(Command("promo"))
async def cmd_use_promo(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        return await message.answer(
            "вљ пёЏ <b>РљР°Рє РёСЃРїРѕР»СЊР·РѕРІР°С‚СЊ:</b>\n"
            "РќР°РїРёС€Рё <code>/promo [С‚РІРѕР№_РєРѕРґ]</code>\n"
            "РџСЂРёРјРµСЂ: <code>/promo MEGA2024</code>"
        )

    code = parts[1].upper()
    reward = await db.use_promo_code(message.from_user.id, code)
    
    if reward:
        await message.answer(
            f"рџЋ‰ <b>РЈСЃРїРµС€РЅРѕ!</b>\n\n"
            f"РўС‹ Р°РєС‚РёРІРёСЂРѕРІР°Р» РїСЂРѕРјРѕРєРѕРґ <b>{code}</b> Рё РїРѕР»СѓС‡РёР» <b>{reward}рџ’°</b> РЅР° СЃРІРѕР№ Р±Р°Р»Р°РЅСЃ!"
        )
    else:
        await message.answer(
            "вќЊ <b>РћС€РёР±РєР°!</b>\n"
            "РџСЂРѕРјРѕРєРѕРґ РЅРµ СЃСѓС‰РµСЃС‚РІСѓРµС‚, РµРіРѕ Р»РёРјРёС‚ РёСЃС‡РµСЂРїР°РЅ, Р»РёР±Рѕ С‚С‹ СѓР¶Рµ РёСЃРїРѕР»СЊР·РѕРІР°Р» РµРіРѕ СЂР°РЅРµРµ."
        )


# === РџР РћР¤РР›Р¬, РўРћРџР«, РҐР•Р›Рџ ===
@router.message(Command("profile"))
@router.callback_query(F.data == "profile")
async def show_profile(event: CallbackQuery | Message):
    user_id = event.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        error_msg = "вќЊ РћС€РёР±РєР° РїРѕР»СѓС‡РµРЅРёСЏ РїСЂРѕС„РёР»СЏ."
        if isinstance(event, CallbackQuery):
            await event.message.answer(error_msg)
            return await event.answer()
        return await event.answer(error_msg)

    ref_link = await db.get_referral_link(user_id)
    user_rank = await db.get_user_rank(user_id)
    pref = f"{user['prefix']} " if user.get('prefix') else ""

    text = (
        f"рџ‘¤ <b>РџР РћР¤РР›Р¬ РР“Р РћРљРђ</b>\n\n"
        f"рџЏ·пёЏ РџСЂРµС„РёРєСЃ + РќРёРє: <b>{pref}{user['username']}</b>\n"
        f"рџ’° Р‘Р°Р»Р°РЅСЃ: <b>{user['balance']}рџ’°</b>\n"
        f"рџЏ† РўРѕРї: <b>#{user_rank or 'вЂ”'}</b>\n"
        f"рџЋ’ РРЅРІРµРЅС‚Р°СЂСЊ: <b>{user.get('inventory_value', 0)}рџ’°</b>\n"
        f"рџ“€ Р’С‹РёРіСЂР°РЅРѕ: <b>{user.get('total_won', 0)}рџ’°</b>\n"
        f"рџ“‰ РџРѕС‚СЂР°С‡РµРЅРѕ: <b>{user.get('total_spent', 0)}рџ’°</b>\n\n"
        f"рџ”— <b>Р РµС„РµСЂР°Р»СЊРЅР°СЏ СЃСЃС‹Р»РєР°:</b>\n<code>{ref_link}</code>"
    )

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=main_menu_kb())
        await event.answer()
    else:
        await event.answer(text, reply_markup=main_menu_kb())


@router.message(Command("top"))
@router.callback_query(F.data == "tops")
async def text_cmd_top(event: CallbackQuery | Message):
    text = "рџЏ† <b>Р РµР№С‚РёРЅРіРё СЃРµСЂРІРµСЂР° GBL Casino</b>\nР’С‹Р±РµСЂРё РЅСѓР¶РЅСѓСЋ РєР°С‚РµРіРѕСЂРёСЋ РЅРёР¶Рµ:"
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=tops_kb())
        await event.answer()
    else:
        await event.answer(text, reply_markup=tops_kb())


@router.callback_query(F.data.startswith("top_"))
async def show_specific_top(callback: CallbackQuery):
    top_type = callback.data.replace("top_", "")
    top_users = await db.get_top_users(top_type, limit=10)

    title_map = {
        "balance": "рџ’° РўРћРџ РџРћ Р‘РђР›РђРќРЎРЈ",
        "won": "рџ“€ РўРћРџ РџРћ Р’Р«РР“Р Р«РЁРђРњ",
        "spent": "рџ“‰ РўРћРџ РџРћ РџРћРўР РђР§Р•РќРќРћРњРЈ"
    }

    text = f"<b>{title_map.get(top_type, 'рџЏ† РўРћРџ РР“Р РћРљРћР’')}</b>\n\n"
    if not top_users:
        text += "РЎРїРёСЃРѕРє РїРѕРєР° РїСѓСЃС‚..."
    else:
        for idx, u in enumerate(top_users, start=1):
            pref = f"{u['prefix']} " if u.get('prefix') else ""
            val = u.get(top_type, u.get('balance', 0))
            text += f"{idx}. <b>{pref}{u['username']}</b> вЂ” {val}рџ’°\n"

    await callback.message.edit_text(text, reply_markup=tops_kb())
    await callback.answer()


@router.message(Command("help"))
@router.callback_query(F.data == "help")
async def help_cmd(event: CallbackQuery | Message):
    text = (
        "в„№пёЏ <b>РџРћРњРћР©Р¬ Р РР“Р Р«</b>\n\n"
        "рџ“€ <b>РљСЂР°С€</b> вЂ” СЂР°СЃС‚СѓС‰РёР№ РјРЅРѕР¶РёС‚РµР»СЊ СЃ РєР°СЃС‚РѕРјРЅС‹РјРё СЃС‚Р°РІРєР°РјРё!\n"
        "вљЄ/вљ« <b>Р‘РµР»РѕРµ Рё Р§С‘СЂРЅРѕРµ</b> вЂ” PvP СѓРіР°РґР°Р№РєР° СЃ РґСЂСѓРіРёРјРё РёРіСЂРѕРєР°РјРё\n"
        "вљ”пёЏ <b>Р”СѓСЌР»СЊ</b> вЂ” СЃРѕР·РґР°Р№ РґСѓСЌР»СЊ РІ РјРµРЅСЋ РёР»Рё РЅР°РїРёС€Рё <code>РґСѓСЌР»СЊ [СЃСѓРјРјР°]</code> РІ РѕС‚РІРµС‚ РЅР° СЃРѕРѕР±С‰РµРЅРёРµ С‡РµР»РѕРІРµРєР°!\n"
        "рџ“¦ <b>РљРµР№СЃС‹</b> вЂ” РѕС‚РєСЂС‹РІР°Р№ Рё РїСЂРѕРґР°РІР°Р№ Р»СѓС‚\n"
        "рџЋЃ <b>Р‘РѕРЅСѓСЃ</b> вЂ” 2,500рџ’° РєР°Р¶РґС‹Рµ 24 С‡Р°СЃР°\n"
        "рџ‘‘ <b>РџСЂРµС„РёРєСЃС‹</b> вЂ” РІС‹РґРµР»РёСЃСЊ РІ РѕР±С‰РµРј СЂРµР№С‚РёРЅРіРµ!\n"
        "рџ’ё <b>РџРµСЂРµРІРѕРґ РґРµРЅРµРі</b> вЂ” РѕС‚РІРµС‚СЊ РєРѕРјР°РЅРґРѕР№ <code>РїРµСЂРµРґР°С‚СЊ 100</code> РЅР° СЃРѕРѕР±С‰РµРЅРёРµ РёРіСЂРѕРєР°\n"
        "рџЋџ <b>РџСЂРѕРјРѕРєРѕРґС‹</b> вЂ” РёСЃРїРѕР»СЊР·СѓР№ РєРѕРјР°РЅРґСѓ <code>/promo [РєРѕРґ]</code> РґР»СЏ РїРѕР»СѓС‡РµРЅРёСЏ Р±РѕРЅСѓСЃРѕРІ!\n"
    )
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=main_menu_kb())
        await event.answer()
    else:
        await event.answer(text, reply_markup=main_menu_kb())


@router.callback_query(F.data == "back_menu")
async def back_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "рџЋ° <b>Р“Р»Р°РІРЅРѕРµ РјРµРЅСЋ</b>\nР’С‹Р±РµСЂРё СЂРµР¶РёРј:", reply_markup=main_menu_kb()
    )
    await callback.answer()


# === РњРђР“РђР—РРќ РџР Р•Р¤РРљРЎРћР’ (РћР‘Р«Р§РќР«Р• Р Р¦Р’Р•РўРќР«Р•) ===
@router.callback_query(F.data == "prefix_shop")
async def show_prefix_shop(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    curr_prefix = user["prefix"] if user and user.get("prefix") else "РћС‚СЃСѓС‚СЃС‚РІСѓРµС‚"

    text = (
        f"рџ‘‘ <b>РњРђР“РђР—РРќ РџР Р•Р¤РРљРЎРћР’</b>\n\n"
        f"РўРІРѕР№ С‚РµРєСѓС‰РёР№ РїСЂРµС„РёРєСЃ: <b>{curr_prefix}</b>\n\n"
        f"РљСѓРїР»РµРЅРЅС‹Р№ РїСЂРµС„РёРєСЃ Р±СѓРґРµС‚ РїРѕРєР°Р·С‹РІР°С‚СЊСЃСЏ РІ С‚РѕРїРµ Рё РІ С‚РІРѕРµРј РїСЂРѕС„РёР»Рµ!\n"
        f"Р’С‹Р±РµСЂРё РїСЂРµС„РёРєСЃ РґР»СЏ РїРѕРєСѓРїРєРё:"
    )

    await callback.message.edit_text(text, reply_markup=prefix_shop_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("buy_prefix_"))
async def buy_prefix(callback: CallbackQuery):
    prefix = callback.data.replace("buy_prefix_", "")
    prices = {
        "[VIP]": 10000,
        "[BOSS]": 50000,
        "[KING]": 150000,
        "[LEGEND]": 500000,
    }

    price = prices.get(prefix, 0)
    user = await db.get_user(callback.from_user.id)

    if not user or user["balance"] < price:
        return await callback.answer(f"вќЊ РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ СЃСЂРµРґСЃС‚РІ! РќСѓР¶РЅРѕ {price}рџ’°", show_alert=True)

    await db.update_balance(callback.from_user.id, -price)
    await db.set_prefix(callback.from_user.id, prefix)

    await callback.answer(f"рџЋ‰ РўС‹ СѓСЃРїРµС€РЅРѕ РєСѓРїРёР» РїСЂРµС„РёРєСЃ {prefix}!", show_alert=True)
    await show_prefix_shop(callback)


@router.callback_query(F.data.startswith("color_prefix_"))
async def choose_prefix_color(callback: CallbackQuery):
    _, _, prefix, price_str = callback.data.split("_")
    
    await callback.message.edit_text(
        f"рџЋЁ <b>Р’С‹Р±РµСЂРё С†РІРµС‚ РґР»СЏ {prefix}</b> (РЎС‚РѕРёРјРѕСЃС‚СЊ: {price_str}рџ’°):",
        reply_markup=prefix_color_kb(prefix, int(price_str))
    )
    await callback.answer()


@router.callback_query(F.data.startswith("buycolor_"))
async def final_buy_prefix(callback: CallbackQuery):
    _, base_prefix, color, price_str = callback.data.split("_")
    price = int(price_str)

    color_map = {
        "red": f"рџ”ґ {base_prefix} рџ”ґ",
        "green": f"рџџў {base_prefix} рџџў",
        "blue": f"рџ”µ {base_prefix} рџ”µ",
        "rainbow": f"рџЊ€вњЁ{base_prefix}вњЁрџЊ€"
    }
    actual_prefix = color_map.get(color, base_prefix)

    user = await db.get_user(callback.from_user.id)
    if not user or user["balance"] < price:
        return await callback.answer(f"вќЊ РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ СЃСЂРµРґСЃС‚РІ! РќСѓР¶РЅРѕ {price}рџ’°", show_alert=True)

    await db.update_balance(callback.from_user.id, -price)
    await db.set_prefix(callback.from_user.id, actual_prefix)

    await callback.answer(f"рџЋ‰ РЈСЃРїРµС€РЅРѕ РєСѓРїР»РµРЅ РїСЂРµС„РёРєСЃ {actual_prefix}!", show_alert=True)
    await show_prefix_shop(callback)


# === Р•Р–Р•Р”РќР•Р’РќР«Р™ Р‘РћРќРЈРЎ 2500рџ’° ===
@router.callback_query(F.data == "daily")
async def daily_bonus(callback: CallbackQuery):
    if await db.can_claim_daily(callback.from_user.id):
        await db.claim_daily(callback.from_user.id)
        await callback.message.edit_text(
            "рџЋЃ <b>Р•Р¶РµРґРЅРµРІРЅС‹Р№ Р±РѕРЅСѓСЃ РїРѕР»СѓС‡РµРЅ!</b>\n\n"
            "РўРµР±Рµ РЅР°С‡РёСЃР»РµРЅРѕ <b>2,500рџ’°</b>!\n"
            "Р’РѕР·РІСЂР°С‰Р°Р№СЃСЏ Р·Р° СЃР»РµРґСѓСЋС‰РёРј С‡РµСЂРµР· 24 С‡Р°СЃР°.",
            reply_markup=main_menu_kb(),
        )
    else:
        await callback.message.edit_text(
            "рџЋЃ <b>Р‘РѕРЅСѓСЃ СѓР¶Рµ РїРѕР»СѓС‡РµРЅ!</b>\nРџСЂРёС…РѕРґРё Р·Р°РІС‚СЂР°!",
            reply_markup=main_menu_kb(),
        )
    await callback.answer()


# === РљР РђРЁ Р РЎР’РћРЇ РЎРўРђР’РљРђ ===
@router.callback_query(F.data == "game_crash")
async def show_crash(callback: CallbackQuery):
    await callback.message.edit_text(
        "рџ“€ <b>РР“Р Рђ РљР РђРЁ</b>\n\n"
        "Р’С‹Р±РµСЂРё СЃС‚Р°РЅРґР°СЂС‚РЅСѓСЋ СЃС‚Р°РІРєСѓ РёР»Рё РІРІРµРґРё СЃРІРѕСЋ РєР°СЃС‚РѕРјРЅСѓСЋ СЃСѓРјРјСѓ:",
        reply_markup=crash_kb("bet"),
    )
    await callback.answer()


@router.callback_query(F.data == "crash_custom_bet")
async def crash_custom_bet_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Form.waiting_custom_crash)
    await callback.message.edit_text(
        "вњЌпёЏ <b>Р’РІРµРґРё СЃСѓРјРјСѓ СЃС‚Р°РІРєРё С‚РµРєСЃС‚РѕРј РІ С‡Р°С‚:</b>\n\n"
        "РџСЂРёРјРµСЂ: <code>2500</code>"
    )
    await callback.answer()


@router.message(Form.waiting_custom_crash)
async def crash_custom_bet_process(message: Message, state: FSMContext):
    await state.clear()

    if not message.text or not message.text.isdigit():
        return await message.answer("вќЊ РЎСѓРјРјР° РґРѕР»Р¶РЅР° Р±С‹С‚СЊ С†РµР»С‹Рј РїРѕР»РѕР¶РёС‚РµР»СЊРЅС‹Рј С‡РёСЃР»РѕРј!")

    bet = int(message.text)
    if bet <= 0:
        return await message.answer("вќЊ РЎС‚Р°РІРєР° РґРѕР»Р¶РЅР° Р±С‹С‚СЊ Р±РѕР»СЊС€Рµ 0!")

    user = await db.get_user(message.from_user.id)
    if not user or user["balance"] < bet:
        return await message.answer(f"вќЊ РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ Р±Р°Р»Р°РЅСЃР°! РЈ С‚РµР±СЏ: {user['balance'] if user else 0}рџ’°")

    await db.update_balance(message.from_user.id, -bet)

    msg = await message.answer(
        f"рџ“€ <b>РљР РђРЁ Р·Р°РїСѓС‰РµРЅ!</b>\n\n"
        f"РЎС‚Р°РІРєР°: <b>{bet}рџ’°</b>\n"
        f"РњРЅРѕР¶РёС‚РµР»СЊ: <b>1.00x</b>\n"
        f"Р’С‹РёРіСЂС‹С€: <b>{bet}рџ’°</b>\n\n"
        f"вЏ° Р—Р°Р±РёСЂР°Р№, РїРѕРєР° РЅРµ РїРѕР·РґРЅРѕ!",
        reply_markup=crash_kb("playing"),
    )

    await run_crash_game(message.from_user.id, bet, bot, msg)


@router.callback_query(F.data.startswith("crash_bet_"))
async def crash_preset_bet(callback: CallbackQuery):
    bet = int(callback.data.replace("crash_bet_", ""))
    user = await db.get_user(callback.from_user.id)

    if not user or user["balance"] < bet:
        return await callback.answer(f"вќЊ РќСѓР¶РЅРѕ {bet}рџ’°", show_alert=True)

    await db.update_balance(callback.from_user.id, -bet)

    msg = await callback.message.answer(
        f"рџ“€ <b>РљР РђРЁ Р·Р°РїСѓС‰РµРЅ!</b>\n\n"
        f"РЎС‚Р°РІРєР°: <b>{bet}рџ’°</b>\n"
        f"РњРЅРѕР¶РёС‚РµР»СЊ: <b>1.00x</b>\n"
        f"Р’С‹РёРіСЂС‹С€: <b>{bet}рџ’°</b>\n\n"
        f"вЏ° Р—Р°Р±РёСЂР°Р№, РїРѕРєР° РЅРµ РїРѕР·РґРЅРѕ!",
        reply_markup=crash_kb("playing"),
    )

    await run_crash_game(callback.from_user.id, bet, bot, msg)
    await callback.answer()


@router.callback_query(F.data == "crash_cashout")
async def crash_cashout_handler(callback: CallbackQuery):
    win = cashout_crash(callback.from_user.id)
    if win is None:
        return await callback.answer("вќЊ РРіСЂР° СѓР¶Рµ Р·Р°РІРµСЂС€РµРЅР°!", show_alert=True)

    await db.update_balance(callback.from_user.id, win)
    user = await db.get_user(callback.from_user.id)

    await callback.message.edit_text(
        f"рџ’° <b>Р’Р«РР“Р Р«РЁ Р—РђР‘Р РђРќ!</b>\n\n"
        f"Р—Р°СЂР°Р±РѕС‚Р°РЅРѕ: <b>+{win}рџ’°</b>\n"
        f"РўРІРѕР№ Р±Р°Р»Р°РЅСЃ: <b>{user['balance']}рџ’°</b>",
        reply_markup=main_menu_kb(),
    )
    await callback.answer()


# === РР“Р Рђ "Р‘Р•Р›РћР• РР›Р Р§РЃР РќРћР•" (PvP) ===
@router.callback_query(F.data == "game_bw")
async def show_bw_menu(callback: CallbackQuery):
    text = (
        "вљЄ/вљ« <b>РР“Р Рђ В«Р‘Р•Р›РћР• РР›Р Р§РЃР РќРћР•В»</b>\n\n"
        "<b>РџСЂР°РІРёР»Р°:</b>\n"
        "1. РЎРѕР·РґР°С‚РµР»СЊ Р·Р°РіР°РґС‹РІР°РµС‚ С†РІРµС‚ (Р‘РµР»РѕРµ РёР»Рё Р§С‘СЂРЅРѕРµ) Рё СЃС‚Р°РІРёС‚ РґРµРЅСЊРіРё.\n"
        "2. РЎРѕРїРµСЂРЅРёРє РїРѕРґРєР»СЋС‡Р°РµС‚СЃСЏ Рё РїС‹С‚Р°РµС‚СЃСЏ РѕС‚РіР°РґР°С‚СЊ С†РІРµС‚.\n"
        "3. Р•СЃР»Рё СЃРѕРїРµСЂРЅРёРє <b>РѕС‚РіР°РґР°Р»</b> вЂ” РѕРЅ Р·Р°Р±СЂР°Р» Р±Р°РЅРє!\n"
        "4. Р•СЃР»Рё СЃРѕРїРµСЂРЅРёРє <b>РЅРµ СѓРіР°РґР°Р»</b> вЂ” Р±Р°РЅРє Р·Р°Р±РёСЂР°РµС‚ РЎРѕР·РґР°С‚РµР»СЊ!\n\n"
        "РЎРѕР·РґР°Р№ РёРіСЂСѓ РёР»Рё РІС‹Р±РµСЂРё РёР· СЃРїРёСЃРєР° Р°РєС‚РёРІРЅС‹С…:"
    )
    await callback.message.edit_text(text, reply_markup=bw_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("bw_create_"))
async def bw_create_game_handler(callback: CallbackQuery):
    _, _, bet_str, choice = callback.data.split("_")
    bet = int(bet_str)

    user = await db.get_user(callback.from_user.id)
    if not user or user["balance"] < bet:
        return await callback.answer(f"вќЊ РќСѓР¶РЅРѕ {bet}рџ’°", show_alert=True)

    await db.update_balance(callback.from_user.id, -bet)

    # Fallback to older game API if needed
    try:
        game_id = create_bw_game(callback.from_user.id, user["username"], bet, choice)
    except Exception:
        game_id = create_bw_game(callback.from_user.id, bet, choice)

    choice_str = "вљЄ Р‘Р•Р›РћР•" if choice == "white" else "вљ« Р§РЃР РќРћР•"

    await callback.message.edit_text(
        f"рџЋІ <b>РљРѕРјРЅР°С‚Р° В«Р‘РµР»РѕРµ/Р§С‘СЂРЅРѕРµВ» #{game_id} СЃРѕР·РґР°РЅР°!</b>\n\n"
        f"РўРІРѕР№ СЃРµРєСЂРµС‚РЅС‹Р№ РІС‹Р±РѕСЂ: <b>{choice_str}</b>\n"
        f"РЎС‚Р°РІРєР°: <b>{bet}рџ’°</b>\n\n"
        f"вЏі РћР¶РёРґР°РµРј РІС‚РѕСЂРѕРіРѕ РёРіСЂРѕРєР°...",
        reply_markup=main_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "bw_list")
async def bw_list_handler(callback: CallbackQuery):
    games = get_waiting_bw_games()
    if not games:
        await callback.message.edit_text(
            "рџ“‹ <b>РќРµС‚ РґРѕСЃС‚СѓРїРЅС‹С… РєРѕРјРЅР°С‚ В«Р‘РµР»РѕРµ/Р§С‘СЂРЅРѕРµВ»</b>\nРЎРѕР·РґР°Р№ СЃРІРѕСЋ!",
            reply_markup=bw_kb(),
        )
        return await callback.answer()

    text = "рџ“‹ <b>РђРєС‚РёРІРЅС‹Рµ РґСѓСЌР»Рё Р‘РµР»РѕРµ/Р§С‘СЂРЅРѕРµ:</b>\n\n"
    kb = []

    if isinstance(games, dict):
        for g_id, g_data in list(games.items())[:5]:
            text += f"рџЋ® РљРѕРјРЅР°С‚Р° #{g_id} вЂ” {g_data.get('creator_name', 'РРіСЂРѕРє')} | РЎС‚Р°РІРєР°: <b>{g_data['bet']}рџ’°</b>\n"
            kb.append([
                InlineKeyboardButton(text=f"вљЄ РџРѕРїСЂРѕР±РѕРІР°С‚СЊ вљЄ ({g_data['bet']}рџ’°)", callback_data=f"bw_join_{g_id}_white"),
                InlineKeyboardButton(text=f"вљ« РџРѕРїСЂРѕР±РѕРІР°С‚СЊ вљ« ({g_data['bet']}рџ’°)", callback_data=f"bw_join_{g_id}_black"),
            ])
    else:
        for g in games[:5]:
            creator = await db.get_user(g["creator_id"])
            c_name = creator["username"] if creator else "РРіСЂРѕРє"
            text += f"рџЋ® РљРѕРјРЅР°С‚Р° #{g['id']} вЂ” {c_name} | РЎС‚Р°РІРєР°: <b>{g['bet']}рџ’°</b>\n"
            kb.append([
                InlineKeyboardButton(text=f"вљЄ РџРѕРїСЂРѕР±РѕРІР°С‚СЊ вљЄ ({g['bet']}рџ’°)", callback_data=f"bw_join_{g['id']}_white"),
                InlineKeyboardButton(text=f"вљ« РџРѕРїСЂРѕР±РѕРІР°С‚СЊ вљ« ({g['bet']}рџ’°)", callback_data=f"bw_join_{g['id']}_black"),
            ])

    kb.append([InlineKeyboardButton(text="в¬…пёЏ РќР°Р·Р°Рґ", callback_data="game_bw")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()


@router.callback_query(F.data.startswith("bw_join_"))
async def bw_join_handler(callback: CallbackQuery):
    parts = callback.data.split("_")
    game_id = int(parts[2])
    guess = parts[3] if len(parts) > 3 else "white"

    game = active_bw_games.get(game_id)
    if not game:
        return await callback.answer("вќЊ РРіСЂР° СѓР¶Рµ Р·Р°РІРµСЂС€РµРЅР° РёР»Рё РѕС‚РјРµРЅРµРЅР°!", show_alert=True)

    if game.get("creator_id") == callback.from_user.id:
        return await callback.answer("вќЊ РќРµР»СЊР·СЏ РёРіСЂР°С‚СЊ СЃ СЃР°РјРёРј СЃРѕР±РѕР№!", show_alert=True)

    user = await db.get_user(callback.from_user.id)
    if not user or user["balance"] < game["bet"]:
        return await callback.answer(f"вќЊ РќСѓР¶РЅРѕ {game['bet']}рџ’°", show_alert=True)

    await db.update_balance(callback.from_user.id, -game["bet"])

    try:
        res = join_bw_game(game_id, callback.from_user.id, guess)
        winner_id, loser_id, win_amount = res["winner_id"], res["loser_id"], res["prize"]
        color_str = "вљЄ Р‘Р•Р›РћР•" if res.get('secret_choice') == "white" else "вљ« Р§РЃР РќРћР•"
        guesser_str = "вљЄ Р‘Р•Р›РћР•" if res.get('guess_choice') == "white" else "вљ« Р§РЃР РќРћР•"
    except Exception:
        # Р РµР·РµСЂРІРЅС‹Р№ Р±Р»РѕРє РѕР±СЂР°Р±РѕС‚РєРё РёРіСЂС‹ (РµСЃР»Рё СЃС‚Р°СЂС‹Р№ API РІ games.py)
        win_amount = int(game["bet"] * 2 * 0.95)
        secret = game.get("secret_color", game.get("secret_choice", "white"))

        if guess == secret:
            winner_id, loser_id = callback.from_user.id, game["creator_id"]
        else:
            winner_id, loser_id = game["creator_id"], callback.from_user.id

        if game_id in active_bw_games:
            del active_bw_games[game_id]

        color_str = "вљЄ Р‘Р•Р›РћР•" if secret == "white" else "вљ« Р§РЃР РќРћР•"
        guesser_str = "вљЄ Р‘Р•Р›РћР•" if guess == "white" else "вљ« Р§РЃР РќРћР•"

    await db.update_balance(winner_id, win_amount)
    winner = await db.get_user(winner_id)
    loser = await db.get_user(loser_id)

    text = (
        f"рџЋІ <b>Р Р•Р—РЈР›Р¬РўРђРў РР“Р Р« Р‘/Р§ #{game_id}!</b>\n\n"
        f"Р—Р°РіР°РґР°РЅРЅС‹Р№ С†РІРµС‚: <b>{color_str}</b>\n"
        f"Р’С‹Р±РѕСЂ СЃРѕРїРµСЂРЅРёРєР°: <b>{guesser_str}</b>\n\n"
        f"рџЏ† РџРѕР±РµРґРёС‚РµР»СЊ: <b>{winner['username']}</b> (+{win_amount}рџ’°)!\n"
        f"рџ’” РџСЂРѕРёРіСЂР°РІС€РёР№: <b>{loser['username']}</b>"
    )

    await callback.message.edit_text(text, reply_markup=main_menu_kb())

    # РџРѕРїС‹С‚РєР° РѕРїРѕРІРµСЃС‚РёС‚СЊ РёРіСЂРѕРєРѕРІ
    for p_id, msg in [(winner_id, f"рџЋ‰ РўС‹ РџРѕР±РµРґРёР» РІ РёРіСЂРµ Р‘РµР»РѕРµ/Р§С‘СЂРЅРѕРµ! Р’С‹РёРіСЂР°РЅРѕ: +{win_amount}рџ’°"),
                      (loser_id, "рџ’Ђ Рљ СЃРѕР¶Р°Р»РµРЅРёСЋ, С‚С‹ РїСЂРѕРёРіСЂР°Р» РІ РёРіСЂРµ Р‘РµР»РѕРµ/Р§С‘СЂРЅРѕРµ.")]:
        try:
            await bot.send_message(p_id, msg)
        except Exception:
            pass

    await callback.answer()


# === Р”РЈР­Р›Р (РћР‘Р©РР•) ===
@router.callback_query(F.data == "game_duel")
async def show_duel(callback: CallbackQuery):
    await callback.message.edit_text(
        "вљ”пёЏ <b>PvP Р”СѓСЌР»Рё (РњРѕРЅРµС‚РєР°)</b>\n\n"
        "РЎРѕР·РґР°Р№ РѕР±С‰СѓСЋ РґСѓСЌР»СЊ РґР»СЏ РІСЃРµС… РёР»Рё РѕС‚РІРµС‚СЊ С‡РµР»РѕРІРµРєСѓ РЅР° СЃРѕРѕР±С‰РµРЅРёРµ: <code>РґСѓСЌР»СЊ 100</code>", 
        reply_markup=duel_kb()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("duel_create_"))
async def duel_create(callback: CallbackQuery):
    bet = int(callback.data.replace("duel_create_", ""))
    user = await db.get_user(callback.from_user.id)

    if not user or user["balance"] < bet:
        return await callback.answer(f"вќЊ РќСѓР¶РЅРѕ {bet}рџ’°", show_alert=True)

    await db.update_balance(callback.from_user.id, -bet)

    try:
        duel_id = create_duel(callback.from_user.id, user["username"], bet)
    except Exception:
        duel_id = create_duel(callback.from_user.id, bet)

    await callback.message.edit_text(
        f"вљ”пёЏ <b>Р”СѓСЌР»СЊ #{duel_id} СЃРѕР·РґР°РЅР°!</b>\n"
        f"РЎС‚Р°РІРєР°: <b>{bet}рџ’°</b>\n\n"
        f"РћР¶РёРґР°РµРј СЃРѕРїРµСЂРЅРёРєР°...",
        reply_markup=main_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "duel_list")
async def duel_list(callback: CallbackQuery):
    duels = get_waiting_duels()
    if not duels:
        await callback.message.edit_text("рџ“‹ <b>РќРµС‚ Р°РєС‚РёРІРЅС‹С… РґСѓСЌР»РµР№</b>", reply_markup=duel_kb())
        return await callback.answer()

    text = "рџ“‹ <b>РђРєС‚РёРІРЅС‹Рµ РґСѓСЌР»Рё:</b>\n\n"
    kb_buttons = []

    if isinstance(duels, dict):
        for d_id, d_data in list(duels.items())[:5]:
            text += f"вљ”пёЏ #{d_id} вЂ” {d_data.get('creator_name', 'РРіСЂРѕРє')} ({d_data['bet']}рџ’°)\n"
            kb_buttons.append([InlineKeyboardButton(text=f"РџСЂРёРЅСЏС‚СЊ #{d_id} ({d_data['bet']}рџ’°)", callback_data=f"duel_join_{d_id}")])
    else:
        for d in duels[:5]:
            creator = await db.get_user(d["creator_id"])
            name = creator["username"] if creator else "???"
            text += f"вљ”пёЏ #{d['id']} вЂ” {name} ({d['bet']}рџ’°)\n"
            kb_buttons.append([InlineKeyboardButton(text=f"РџСЂРёРЅСЏС‚СЊ #{d['id']} ({d['bet']}рџ’°)", callback_data=f"duel_join_{d['id']}")])

    kb_buttons.append([InlineKeyboardButton(text="в¬…пёЏ РќР°Р·Р°Рґ", callback_data="game_duel")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons))
    await callback.answer()


@router.callback_query(F.data.startswith("duel_join_"))
async def duel_join_handler(callback: CallbackQuery):
    duel_id = int(callback.data.replace("duel_join_", ""))
    duel = active_duels.get(duel_id)

    if not duel:
        return await callback.answer("вќЊ Р”СѓСЌР»СЊ РЅРµ РЅР°Р№РґРµРЅР° РёР»Рё СѓР¶Рµ Р·Р°РІРµСЂС€РµРЅР°", show_alert=True)

    if duel.get("creator_id") == callback.from_user.id:
        return await callback.answer("вќЊ РќРµР»СЊР·СЏ РёРіСЂР°С‚СЊ СЃ СЃР°РјРёРј СЃРѕР±РѕР№!", show_alert=True)

    user = await db.get_user(callback.from_user.id)
    if not user or user["balance"] < duel["bet"]:
        return await callback.answer(f"вќЊ РќСѓР¶РЅРѕ {duel['bet']}рџ’° РґР»СЏ СѓС‡Р°СЃС‚РёСЏ!", show_alert=True)

    await db.update_balance(callback.from_user.id, -duel["bet"])
    
    try:
        res = join_duel(duel_id, callback.from_user.id)
        await db.update_balance(res["winner_id"], res["prize"])
        
        winner = await db.get_user(res["winner_id"])
        loser = await db.get_user(res["loser_id"])
        
        await callback.message.edit_text(
            f"вљ”пёЏ <b>Р”РЈР­Р›Р¬ РЎРћРЎРўРћРЇР›РђРЎР¬!</b>\n\n"
            f"рџЏ† РџРѕР±РµРґРёС‚РµР»СЊ: <b>{winner['username']}</b> (+{res['prize']}рџ’°)!\n"
            f"рџ’Ђ РџРѕРІРµСЂР¶РµРЅ: <b>{loser['username']}</b>",
            reply_markup=main_menu_kb()
        )
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РІ РґСѓСЌР»Рё: {e}")
        await callback.answer("вќЊ РџСЂРѕРёР·РѕС€Р»Р° РѕС€РёР±РєР° РїСЂРё РїСЂРѕРІРµРґРµРЅРёРё РґСѓСЌР»Рё.", show_alert=True)
        
    await callback.answer()


# === Р—РђРџРЈРЎРљ Р‘РћРўРђ Р Р‘РђР—Р« Р”РђРќРќР«РҐ ===
async def main():
    logger.info("Initializing database...")
    await db.init_db()
    
    logger.info("Starting bot...")
    
    # Р—Р°РїСѓСЃРєР°РµРј С†РёРєР» СЃ Р°РІС‚РѕСЂРµРєР»Р°РјРѕР№ РІ С„РѕРЅРµ
    asyncio.create_task(ad_loop(bot))
    
    # Р—Р°РїСѓСЃРєР°РµРј РїРѕР»Р»РёРЅРі
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped!")
kb_buttons.append([InlineKeyboardButton(text=f"РџСЂРёРЅСЏС‚СЊ #{d['id']} ({d['bet']}рџ’°)", callback_data=f"duel_join_{d['id']}")])

    kb_buttons.append([InlineKeyboardButton(text="в¬…пёЏ РќР°Р·Р°Рґ", callback_data="game_duel")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons))
    await callback.answer()


@router.callback_query(F.data.startswith("duel_join_"))
async def duel_join_handler(callback: CallbackQuery):
    duel_id = int(callback.data.replace("duel_join_", ""))
    
    duel = active_duels.get(duel_id)
    if not duel:
        return await callback.answer("вќЊ Р­С‚Р° РґСѓСЌР»СЊ Р±РѕР»СЊС€Рµ РЅРµ СЃСѓС‰РµСЃС‚РІСѓРµС‚!", show_alert=True)

    if duel.get("creator_id") == callback.from_user.id:
        return await callback.answer("вќЊ РќРµР»СЊР·СЏ РїСЂРёРЅСЏС‚СЊ СЃРІРѕСЋ Р¶Рµ РґСѓСЌР»СЊ!", show_alert=True)

    user = await db.get_user(callback.from_user.id)
    if not user or user["balance"] < duel["bet"]:
        return await callback.answer(f"вќЊ РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ СЃСЂРµРґСЃС‚РІ! РќСѓР¶РЅРѕ {duel['bet']}рџ’°", show_alert=True)

    await db.update_balance(callback.from_user.id, -duel["bet"])

    try:
        res = join_duel(duel_id, callback.from_user.id)
        winner_id = res["winner_id"]
        loser_id = res["loser_id"]
        win_amount = res["prize"]
    except Exception:
        # Р РµР·РµСЂРІРЅР°СЏ Р»РѕРіРёРєР°, РµСЃР»Рё API РІ games.py СЂР°Р±РѕС‚Р°РµС‚ РёРЅР°С‡Рµ
        win_amount = int(duel["bet"] * 2 * 0.95)
        winner_id, loser_id = random.choice([
            (duel["creator_id"], callback.from_user.id),
            (callback.from_user.id, duel["creator_id"])
        ])
        if duel_id in active_duels:
            del active_duels[duel_id]

    await db.update_balance(winner_id, win_amount)
    winner = await db.get_user(winner_id)
    loser = await db.get_user(loser_id)

    text = (
        f"вљ”пёЏ <b>Р Р•Р—РЈР›Р¬РўРђРў Р”РЈР­Р›Р #{duel_id}!</b>\n\n"
        f"рџЄ™ РњРѕРЅРµС‚РєР° РїРѕРґР±СЂРѕС€РµРЅР°...\n\n"
        f"рџЏ† РџРѕР±РµРґРёС‚РµР»СЊ: <b>{winner['username']}</b> (+{win_amount}рџ’°)!\n"
        f"рџ’Ђ РџСЂРѕРёРіСЂР°РІС€РёР№: <b>{loser['username']}</b>"
    )

    await callback.message.edit_text(text, reply_markup=main_menu_kb())

    # РЈРІРµРґРѕРјР»РµРЅРёРµ РёРіСЂРѕРєРѕРІ Рѕ СЂРµР·СѓР»СЊС‚Р°С‚Рµ
    for p_id, msg in [
        (winner_id, f"рџЋ‰ РўС‹ РїРѕР±РµРґРёР» РІ РґСѓСЌР»Рё! Р’С‹РёРіСЂС‹С€: +{win_amount}рџ’°"),
        (loser_id, "рџ’Ђ Рљ СЃРѕР¶Р°Р»РµРЅРёСЋ, С‚С‹ РїСЂРѕРёРіСЂР°Р» РІ РґСѓСЌР»Рё.")
    ]:
        try:
            await bot.send_message(p_id, msg)
        except Exception:
            pass

    await callback.answer()


# === РљР•Р™РЎР« Р РРќР’Р•РќРўРђР Р¬ (РћРїРёСЂР°СЏСЃСЊ РЅР° РёРјРїРѕСЂС‚С‹ РёР· items.py) ===
@router.callback_query(F.data == "cases")
async def show_cases_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "рџ“¦ <b>РњРђР“РђР—РРќ РљР•Р™РЎРћР’</b>\n\n"
        "РСЃРїС‹С‚Р°Р№ СѓРґР°С‡Сѓ Рё РїРѕР»СѓС‡Рё РєСЂСѓС‚РѕР№ РґСЂРѕРї!\n"
        "Р’С‹Р±РµСЂРё РєРµР№СЃ РґР»СЏ РѕС‚РєСЂС‹С‚РёСЏ:",
        reply_markup=cases_kb()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("open_case_"))
async def process_open_case(callback: CallbackQuery):
    case_id = callback.data.replace("open_case_", "")
    case_data = CASES.get(case_id)
    
    if not case_data:
        return await callback.answer("вќЊ РљРµР№СЃ РЅРµ РЅР°Р№РґРµРЅ!", show_alert=True)
    
    user = await db.get_user(callback.from_user.id)
    if not user or user["balance"] < case_data["price"]:
        return await callback.answer(f"вќЊ РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ СЃСЂРµРґСЃС‚РІ! РљРµР№СЃ СЃС‚РѕРёС‚ {case_data['price']}рџ’°", show_alert=True)
    
    await db.update_balance(callback.from_user.id, -case_data["price"])
    
    drop = open_case(case_id)
    await db.add_item_to_inventory(callback.from_user.id, drop["name"], drop["price"])
    
    rarity_color = RARITIES.get(drop["rarity"], "в¬њ")
    
    text = (
        f"рџ“¦ <b>РўС‹ РѕС‚РєСЂС‹Р» {case_data['name']}!</b>\n\n"
        f"РўРµР±Рµ РІС‹РїР°Р»Рѕ:\n"
        f"{rarity_color} <b>{drop['name']}</b>\n"
        f"рџ’° РЎС‚РѕРёРјРѕСЃС‚СЊ: <b>{drop['price']}рџ’°</b>\n\n"
        f"РџСЂРµРґРјРµС‚ РґРѕР±Р°РІР»РµРЅ РІ С‚РІРѕР№ РёРЅРІРµРЅС‚Р°СЂСЊ!"
    )
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="рџЋ’ Р’ РёРЅРІРµРЅС‚Р°СЂСЊ", callback_data="inventory")],
            [InlineKeyboardButton(text="рџ“¦ РћС‚РєСЂС‹С‚СЊ РµС‰С‘ СЂР°Р·", callback_data=f"open_case_{case_id}")],
            [InlineKeyboardButton(text="в¬…пёЏ Рљ РєРµР№СЃР°Рј", callback_data="cases")]
        ]
    ))
    await callback.answer()


# === Р—РђРџРЈРЎРљ Р‘РћРўРђ ===
async def main():
    logger.info("Р—Р°РїСѓСЃРє Р±РѕС‚Р° GBL Casino...")
    
    # Р—Р°РїСѓСЃРєР°РµРј С„РѕРЅРѕРІСѓСЋ Р·Р°РґР°С‡Сѓ РґР»СЏ СЂРµРєР»Р°РјС‹ РІ Р±РµСЃРµРґР°С…
    asyncio.create_task(ad_loop(bot))
    
    # РџСЂРѕРїСѓСЃРєР°РµРј РЅР°РєРѕРїР»РµРЅРЅС‹Рµ Р·Р° РІСЂРµРјСЏ РїСЂРѕСЃС‚РѕСЏ Р°РїРґРµР№С‚С‹ Рё Р·Р°РїСѓСЃРєР°РµРј РїРѕР»Р»РёРЅРі
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Р‘РѕС‚ РѕСЃС‚Р°РЅРѕРІР»РµРЅ РІСЂСѓС‡РЅСѓСЋ.")
