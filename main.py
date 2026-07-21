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
from dotenv import load_dotenv

from database import db
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

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher(storage=MemoryStorage())
router = Router()

# Хранилище прямых дуэлей (по вызову)
direct_duels = {}
direct_duel_counter = 1


# === МИДЛВАРЬ: АВТОРЕГИСТРАЦИЯ, ТРЕКИНГ ЧАТОВ И ОБНОВЛЕНИЕ НИКОВ ===
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

        # Авторегистрация и обновление профиля при любом взаимодействии
        if user_obj and not user_obj.is_bot:
            username = user_obj.username
            current_display_name = (
                f"@{username}" if username else user_obj.first_name or "Игрок"
            )

            user = await db.get_user(user_obj.id)
            if not user:
                await db.create_user(user_obj.id, current_display_name)
            else:
                # Если пользователь поменял ник или имя в Telegram — обновляем БД
                if user.get("username") != current_display_name:
                    await db.update_user_info(user_obj.id, current_display_name)

        return await handler(event, data)


router.message.middleware(AutoRegisterMiddleware())
router.callback_query.middleware(AutoRegisterMiddleware())
dp.include_router(router)


class Form(StatesGroup):
    waiting_custom_crash = State()


# === АВТОМАТИЧЕСКАЯ РЕКЛАМА В БЕСЕДАХ (РАЗ В ЧАС) ===
async def ad_loop(bot_instance: Bot):
    while True:
        await asyncio.sleep(3600)  # 1 час
        try:
            chats = await db.get_all_chats()
            for chat in chats:
                if chat.get('type') in ('group', 'supergroup'):
                    try:
                        await bot_instance.send_message(
                            chat['chat_id'], 
                            "👋 <b>Привет, дружище!</b>\n\n"
                            "Не хочешь испытать удачу и поиграть в <b>GBL Casino</b>?\n"
                            "Заходи, забирай ежедневный бонус 2,500💰, открывай кейсы и играй с друзьями!",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                InlineKeyboardButton(text="🎮 Играть!", url="https://t.me/gbl_games_bot")
                            ]])
                        )
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Error in ad loop: {e}")


# === СТАРТ ===
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()

    user = await db.get_user(message.from_user.id)
    ref_link = await db.get_referral_link(message.from_user.id)
    user_rank = await db.get_user_rank(message.from_user.id)
    pref = f"{user['prefix']} " if user and user.get('prefix') else ""

    text = (
        f"🎮 <b>Добро пожаловать в GBL Casino!</b>\n\n"
        f"👤 Игрок: <b>{pref}{user['username']}</b>\n"
        f"💰 Баланс: <b>{user['balance']}💰</b>\n"
        f"🏆 Место в топе: <b>#{user_rank or '—'}</b>\n\n"
        f"🔗 Реферальная ссылка:\n<code>{ref_link}</code>\n\n"
        f"Выбирай режим игры в меню ниже 👇"
    )

    await message.answer(text, reply_markup=main_menu_kb())


# === ПЕРСОНАЛЬНЫЕ ДУЭЛИ В ЧАТЕ (ОТВЕТОМ НА СООБЩЕНИЕ) ===
@router.message(Command("duel"))
@router.message(F.text & F.text.lower().startswith(("дуэль", "дуель")))
async def create_direct_duel(message: Message):
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.answer(
            "⚠️ <b>Как бросить вызов:</b>\n"
            "Ответь (reply) на сообщение игрока текстом:\n"
            "<code>дуэль 100</code>"
        )
        return

    target_user = message.reply_to_message.from_user

    if target_user.id == message.from_user.id:
        await message.answer("❌ Нельзя вызвать на дуэль самого себя!")
        return

    if target_user.is_bot:
        await message.answer("❌ Нельзя вызывать ботов!")
        return

    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("⚠️ Укажи корректную сумму дуэли! Пример: <code>дуэль 500</code>")
        return

    bet = int(parts[1])
    if bet <= 0:
        await message.answer("❌ Ставка должна быть больше 0💰!")
        return

    challenger_db = await db.get_user(message.from_user.id)
    if not challenger_db or challenger_db["balance"] < bet:
        await message.answer(f"❌ У тебя недостаточно средств! Твой баланс: <b>{challenger_db['balance'] if challenger_db else 0}💰</b>")
        return

    target_db = await db.get_user(target_user.id)
    if not target_db:
        t_username = target_user.username
        t_display = f"@{t_username}" if t_username else target_user.first_name or "Игрок"
        await db.create_user(target_user.id, t_display)
        target_db = await db.get_user(target_user.id)

    if target_db["balance"] < bet:
        await message.answer(f"❌ У игрока <b>{target_db['username']}</b> недостаточно средств ({target_db['balance']}💰)!")
        return

    global direct_duel_counter
    duel_id = direct_duel_counter
    direct_duel_counter += 1

    c_name = challenger_db["username"]
    t_name = target_db["username"]

    direct_duels[duel_id] = {
        "challenger_id": message.from_user.id,
        "challenger_name": c_name,
        "target_id": target_user.id,
        "target_name": t_name,
        "bet": bet,
    }

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚔️ Принять", callback_data=f"dduel_accept_{duel_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"dduel_decline_{duel_id}")
        ]
    ])

    target_mention = f"@{target_user.username}" if target_user.username else f"<b>{t_name}</b>"

    await message.answer(
        f"⚔️ <b>ВЫЗОВ НА ДУЭЛЬ!</b>\n\n"
        f"Игрок <b>{c_name}</b> вызывает на дуэль {target_mention}!\n"
        f"💰 Ставка: <b>{bet}💰</b>\n\n"
        f"Ждем ответа соперника...",
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("dduel_accept_"))
async def accept_direct_duel(callback: CallbackQuery):
    duel_id = int(callback.data.replace("dduel_accept_", ""))
    duel = direct_duels.get(duel_id)

    if not duel:
        await callback.answer("❌ Эта дуэль больше недействительна!", show_alert=True)
        return

    if callback.from_user.id != duel["target_id"]:
        await callback.answer("❌ Этот вызов адресован не тебе!", show_alert=True)
        return

    challenger = await db.get_user(duel["challenger_id"])
    target = await db.get_user(duel["target_id"])

    if not challenger or challenger["balance"] < duel["bet"]:
        await callback.answer("❌ У зачинщика дуэли не хватает средств!", show_alert=True)
        del direct_duels[duel_id]
        return

    if not target or target["balance"] < duel["bet"]:
        await callback.answer("❌ У тебя недостаточно средств для принятия дуэли!", show_alert=True)
        return

    # Списание ставок
    await db.update_balance(duel["challenger_id"], -duel["bet"])
    await db.update_balance(duel["target_id"], -duel["bet"])

    # Определение победителя 50/50
    winner_id, loser_id = (
        (duel["challenger_id"], duel["target_id"]) 
        if random.choice([True, False]) 
        else (duel["target_id"], duel["challenger_id"])
    )

    prize = int(duel["bet"] * 2 * 0.95)  # Выигрыш за вычетом 5% комиссии
    await db.update_balance(winner_id, prize)

    winner = await db.get_user(winner_id)
    loser = await db.get_user(loser_id)

    del direct_duels[duel_id]

    await callback.message.edit_text(
        f"⚔️ <b>ДУЭЛЬ СОСТОЯЛАСЬ!</b>\n\n"
        f"🪙 Монетка подброшена...\n\n"
        f"🏆 Победитель: <b>{winner['username']}</b> (+{prize}💰)!\n"
        f"💀 Повержен: <b>{loser['username']}</b>"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("dduel_decline_"))
async def decline_direct_duel(callback: CallbackQuery):
    duel_id = int(callback.data.replace("dduel_decline_", ""))
    duel = direct_duels.get(duel_id)

    if not duel:
        await callback.answer("❌ Дуэль не найдена!", show_alert=True)
        return

    if callback.from_user.id != duel["target_id"] and callback.from_user.id != duel["challenger_id"]:
        await callback.answer("❌ Ты не являешься участником этой дуэли!", show_alert=True)
        return

    del direct_duels[duel_id]

    await callback.message.edit_text("❌ <b>Дуэль отклонена.</b>")
    await callback.answer("Дуэль отменена.")


# === ПЕРЕВОД ДЕНЕГ ИГРОКУ ===
@router.message(Command("pay"))
@router.message(Command("give"))
@router.message(F.text & F.text.lower().startswith(("передать", "pay", "give")))
async def transfer_money_cmd(message: Message):
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.answer(
            "⚠️ <b>Как передать деньги:</b>\n"
            "Ответь (reply) на сообщение игрока текстом:\n"
            "<code>передать 100</code>"
        )
        return

    target_user = message.reply_to_message.from_user
    if target_user.id == message.from_user.id:
        await message.answer("❌ Нельзя переводить деньги самому себе!")
        return

    if target_user.is_bot:
        await message.answer("❌ Нельзя переводить деньги ботам!")
        return

    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("⚠️ Укажи корректную сумму для перевода! Пример: <code>передать 500</code>")
        return

    amount = int(parts[1])
    if amount <= 0:
        await message.answer("❌ Сумма перевода должна быть больше 0💰!")
        return

    sender_db = await db.get_user(message.from_user.id)
    if not sender_db or sender_db["balance"] < amount:
        await message.answer(f"❌ У тебя недостаточно средств! Твой баланс: <b>{sender_db['balance'] if sender_db else 0}💰</b>")
        return

    target_db = await db.get_user(target_user.id)
    if not target_db:
        t_username = target_user.username
        t_display = f"@{t_username}" if t_username else target_user.first_name or "Игрок"
        await db.create_user(target_user.id, t_display)
        target_db = await db.get_user(target_user.id)

    # Перевод средств
    await db.update_balance(message.from_user.id, -amount)
    await db.update_balance(target_user.id, amount)

    await message.answer(
        f"✅ <b>Успешный перевод!</b>\n\n"
        f"Ты перевел <b>{amount}💰</b> игроку <b>{target_db['username']}</b>."
    )


# === ПРОФИЛЬ, ТОПЫ, ХЕЛП ===
@router.message(Command("profile"))
@router.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery | Message):
    user_id = callback.from_user.id
    msg = callback.message if isinstance(callback, CallbackQuery) else callback

    user = await db.get_user(user_id)
    if not user:
        await msg.answer("❌ Ошибка получения профиля.")
        return

    ref_link = await db.get_referral_link(user_id)
    user_rank = await db.get_user_rank(user_id)
    pref = f"{user['prefix']} " if user.get('prefix') else ""

    text = (
        f"👤 <b>ПРОФИЛЬ ИГРОКА</b>\n\n"
        f"🏷️ Префикс + Ник: <b>{pref}{user['username']}</b>\n"
        f"💰 Баланс: <b>{user['balance']}💰</b>\n"
        f"🏆 Топ: <b>#{user_rank or '—'}</b>\n"
        f"🎒 Инвентарь: <b>{user.get('inventory_value', 0)}💰</b>\n"
        f"📈 Выиграно: <b>{user.get('total_won', 0)}💰</b>\n"
        f"📉 Потрачено: <b>{user.get('total_spent', 0)}💰</b>\n\n"
        f"🔗 <b>Реферальная ссылка:</b>\n<code>{ref_link}</code>"
    )

    if isinstance(callback, CallbackQuery):
        await callback.message.edit_text(text, reply_markup=main_menu_kb())
        await callback.answer()
    else:
        await msg.answer(text, reply_markup=main_menu_kb())


@router.message(Command("top"))
@router.callback_query(F.data == "tops")
async def text_cmd_top(event: CallbackQuery | Message):
    text = "🏆 <b>Рейтинги сервера GBL Casino</b>\nВыбери нужную категорию ниже:"
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
        "balance": "💰 ТОП ПО БАЛАНСУ",
        "won": "📈 ТОП ПО ВЫИГРЫШАМ",
        "spent": "📉 ТОП ПО ПОТРАЧЕННОМУ"
    }

    text = f"<b>{title_map.get(top_type, '🏆 ТОП ИГРОКОВ')}</b>\n\n"
    if not top_users:
        text += "Список пока пуст..."
    else:
        for idx, u in enumerate(top_users, start=1):
            pref = f"{u['prefix']} " if u.get('prefix') else ""
            val = u.get(top_type, u.get('balance', 0))
            text += f"{idx}. <b>{pref}{u['username']}</b> — {val}💰\n"

    await callback.message.edit_text(text, reply_markup=tops_kb())
    await callback.answer()


@router.message(Command("help"))
@router.callback_query(F.data == "help")
async def help_cmd(event: CallbackQuery | Message):
    text = (
        "ℹ️ <b>ПОМОЩЬ И ИГРЫ</b>\n\n"
        "📈 <b>Краш</b> — растущий множитель с кастомными ставками!\n"
        "⚪/⚫ <b>Белое и Чёрное</b> — PvP угадайка с другими игроками\n"
        "⚔️ <b>Дуэль</b> — создай дуэль в меню или напиши <code>дуэль [сумма]</code> в ответ на сообщение человека!\n"
        "📦 <b>Кейсы</b> — открывай и продавай лут\n"
        "🎁 <b>Бонус</b> — 2,500💰 каждые 24 часа\n"
        "👑 <b>Префиксы</b> — выделись в общем рейтинге!\n"
        "💸 <b>Перевод денег</b> — ответь командой <code>передать 100</code> на сообщение игрока\n"
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
        "🎰 <b>Главное меню</b>\nВыбери режим:", reply_markup=main_menu_kb()
    )
    await callback.answer()


# === МАГАЗИН ПРЕФИКСОВ (ОБЫЧНЫЕ И ЦВЕТНЫЕ) ===
@router.callback_query(F.data == "prefix_shop")
async def show_prefix_shop(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    curr_prefix = user["prefix"] if user and user.get("prefix") else "Отсутствует"

    text = (
        f"👑 <b>МАГАЗИН ПРЕФИКСОВ</b>\n\n"
        f"Твой текущий префикс: <b>{curr_prefix}</b>\n\n"
        f"Купленный префикс будет показываться в топе и в твоем профиле!\n"
        f"Выбери префикс для покупки:"
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
        await callback.answer(
            f"❌ Недостаточно средств! Нужно {price}💰", show_alert=True
        )
        return

    await db.update_balance(callback.from_user.id, -price)
    await db.set_prefix(callback.from_user.id, prefix)

    await callback.answer(
        f"🎉 Ты успешно купил префикс {prefix}!", show_alert=True
    )
    await show_prefix_shop(callback)


@router.callback_query(F.data.startswith("color_prefix_"))
async def choose_prefix_color(callback: CallbackQuery):
    parts = callback.data.split("_")
    prefix = parts[2]
    price = int(parts[3])

    await callback.message.edit_text(
        f"🎨 <b>Выбери цвет для {prefix}</b> (Стоимость: {price}💰):",
        reply_markup=prefix_color_kb(prefix, price)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("buycolor_"))
async def final_buy_prefix(callback: CallbackQuery):
    parts = callback.data.split("_")
    base_prefix = parts[1]
    color = parts[2]
    price = int(parts[3])

    color_map = {
        "red": f"🔴 {base_prefix} 🔴",
        "green": f"🟢 {base_prefix} 🟢",
        "blue": f"🔵 {base_prefix} 🔵",
        "rainbow": f"🌈✨{base_prefix}✨🌈"
    }
    actual_prefix = color_map.get(color, base_prefix)

    user = await db.get_user(callback.from_user.id)
    if not user or user["balance"] < price:
        await callback.answer(f"❌ Недостаточно средств! Нужно {price}💰", show_alert=True)
        return

    await db.update_balance(callback.from_user.id, -price)
    await db.set_prefix(callback.from_user.id, actual_prefix)

    await callback.answer(f"🎉 Успешно куплен префикс {actual_prefix}!", show_alert=True)
    await show_prefix_shop(callback)


# === ЕЖЕДНЕВНЫЙ БОНУС 2500💰 ===
@router.callback_query(F.data == "daily")
async def daily_bonus(callback: CallbackQuery):
    if await db.can_claim_daily(callback.from_user.id):
        await db.claim_daily(callback.from_user.id)
        await callback.message.edit_text(
            "🎁 <b>Ежедневный бонус получен!</b>\n\n"
            "Тебе начислено <b>2,500💰</b>!\n"
            "Возвращайся за следующим через 24 часа.",
            reply_markup=main_menu_kb(),
        )
    else:
        await callback.message.edit_text(
            "🎁 <b>Бонус уже получен!</b>\nПриходи завтра!",
            reply_markup=main_menu_kb(),
        )
    await callback.answer()


# === КРАШ И СВОЯ СТАВКА ===
@router.callback_query(F.data == "game_crash")
async def show_crash(callback: CallbackQuery):
    await callback.message.edit_text(
        "📈 <b>ИГРА КРАШ</b>\n\n"
        "Выбери стандартную ставку или введи свою кастомную сумму:",
        reply_markup=crash_kb("bet"),
    )
    await callback.answer()


@router.callback_query(F.data == "crash_custom_bet")
async def crash_custom_bet_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Form.waiting_custom_crash)
    await callback.message.edit_text(
        "✍️ <b>Введи сумму ставки текстом в чат:</b>\n\n"
        "Пример: <code>2500</code>"
    )
    await callback.answer()


@router.message(Form.waiting_custom_crash)
async def crash_custom_bet_process(message: Message, state: FSMContext):
    await state.clear()

    if not message.text or not message.text.isdigit():
        await message.answer("❌ Сумма должна быть целым положительным числом!")
        return

    bet = int(message.text)
    if bet <= 0:
        await message.answer("❌ Ставка должна быть больше 0!")
        return

    user = await db.get_user(message.from_user.id)
    if not user or user["balance"] < bet:
        await message.answer(
            f"❌ Недостаточно баланса! У тебя: {user['balance'] if user else 0}💰"
        )
        return

    await db.update_balance(message.from_user.id, -bet)

    msg = await message.answer(
        f"📈 <b>КРАШ запущен!</b>\n\n"
        f"Ставка: <b>{bet}💰</b>\n"
        f"Множитель: <b>1.00x</b>\n"
        f"Выигрыш: <b>{bet}💰</b>\n\n"
        f"⏰ Забирай, пока не поздно!",
        reply_markup=crash_kb("playing"),
    )

    await run_crash_game(message.from_user.id, bet, bot, msg)


@router.callback_query(F.data.startswith("crash_bet_"))
async def crash_preset_bet(callback: CallbackQuery):
    bet = int(callback.data.replace("crash_bet_", ""))
    user = await db.get_user(callback.from_user.id)

    if not user or user["balance"] < bet:
        await callback.answer(f"❌ Нужно {bet}💰", show_alert=True)
        return

    await db.update_balance(callback.from_user.id, -bet)

    msg = await callback.message.answer(
        f"📈 <b>КРАШ запущен!</b>\n\n"
        f"Ставка: <b>{bet}💰</b>\n"
        f"Множитель: <b>1.00x</b>\n"
        f"Выигрыш: <b>{bet}💰</b>\n\n"
        f"⏰ Забирай, пока не поздно!",
        reply_markup=crash_kb("playing"),
    )

    await run_crash_game(callback.from_user.id, bet, bot, msg)
    await callback.answer()


@router.callback_query(F.data == "crash_cashout")
async def crash_cashout_handler(callback: CallbackQuery):
    win = cashout_crash(callback.from_user.id)
    if win is None:
        await callback.answer("❌ Игра уже завершена!", show_alert=True)
        return

    await db.update_balance(callback.from_user.id, win)
    user = await db.get_user(callback.from_user.id)

    await callback.message.edit_text(
        f"💰 <b>ВЫИГРЫШ ЗАБРАН!</b>\n\n"
        f"Заработано: <b>+{win}💰</b>\n"
        f"Твой баланс: <b>{user['balance']}💰</b>",
        reply_markup=main_menu_kb(),
    )
    await callback.answer()


# === ИГРА "БЕЛОЕ ИЛИ ЧЁРНОЕ" (PvP) ===
@router.callback_query(F.data == "game_bw")
async def show_bw_menu(callback: CallbackQuery):
    text = (
        "⚪/⚫ <b>ИГРА «БЕЛОЕ ИЛИ ЧЁРНОЕ»</b>\n\n"
        "<b>Правила:</b>\n"
        "1. Создатель загадывает цвет (Белое или Чёрное) и ставит деньги.\n"
        "2. Соперник подключается и пытается отгадать цвет.\n"
        "3. Если соперник <b>отгадал</b> — он забрал банк!\n"
        "4. Если соперник <b>не угадал</b> — банк забирает Создатель!\n\n"
        "Создай игру или выбери из списка активных:"
    )
    await callback.message.edit_text(text, reply_markup=bw_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("bw_create_"))
async def bw_create_game_handler(callback: CallbackQuery):
    parts = callback.data.split("_")
    bet = int(parts[2])
    choice = parts[3]

    user = await db.get_user(callback.from_user.id)
    if not user or user["balance"] < bet:
        await callback.answer(f"❌ Нужно {bet}💰", show_alert=True)
        return

    await db.update_balance(callback.from_user.id, -bet)

    try:
        game_id = create_bw_game(callback.from_user.id, user["username"], bet, choice)
    except Exception:
        game_id = create_bw_game(callback.from_user.id, bet, choice)

    choice_str = "⚪ БЕЛОЕ" if choice == "white" else "⚫ ЧЁРНОЕ"

    await callback.message.edit_text(
        f"🎲 <b>Комната «Белое/Чёрное» #{game_id} создана!</b>\n\n"
        f"Твой секретный выбор: <b>{choice_str}</b>\n"
        f"Ставка: <b>{bet}💰</b>\n\n"
        f"⏳ Ожидаем второго игрока...",
        reply_markup=main_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "bw_list")
async def bw_list_handler(callback: CallbackQuery):
    games = get_waiting_bw_games()
    if not games:
        await callback.message.edit_text(
            "📋 <b>Нет доступных комнат «Белое/Чёрное»</b>\nСоздай свою!",
            reply_markup=bw_kb(),
        )
        await callback.answer()
        return

    text = "📋 <b>Активные дуэли Белое/Чёрное:</b>\n\n"
    kb = []

    if isinstance(games, dict):
        for g_id, g_data in list(games.items())[:5]:
            text += f"🎮 Комната #{g_id} — {g_data.get('creator_name', 'Игрок')} | Ставка: <b>{g_data['bet']}💰</b>\n"
            kb.append([
                InlineKeyboardButton(
                    text=f"⚪ Попробовать ⚪ ({g_data['bet']}💰)",
                    callback_data=f"bw_join_{g_id}_white",
                ),
                InlineKeyboardButton(
                    text=f"⚫ Попробовать ⚫ ({g_data['bet']}💰)",
                    callback_data=f"bw_join_{g_id}_black",
                ),
            ])
    else:
        for g in games[:5]:
            creator = await db.get_user(g["creator_id"])
            c_name = creator["username"] if creator else "Игрок"
            text += f"🎮 Комната #{g['id']} — {c_name} | Ставка: <b>{g['bet']}💰</b>\n"
            kb.append([
                InlineKeyboardButton(
                    text=f"⚪ Попробовать ⚪ ({g['id']}💰)",
                    callback_data=f"bw_join_{g['id']}_white",
                ),
                InlineKeyboardButton(
                    text=f"⚫ Попробовать ⚫ ({g['id']}💰)",
                    callback_data=f"bw_join_{g['id']}_black",
                ),
            ])

    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="game_bw")])

    await callback.message.edit_text(
        text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("bw_join_"))
async def bw_join_handler(callback: CallbackQuery):
    parts = callback.data.split("_")
    game_id = int(parts[2])
    guess = parts[3] if len(parts) > 3 else "white"

    game = active_bw_games.get(game_id)
    if not game:
        await callback.answer("❌ Игра уже завершена или отменена!", show_alert=True)
        return

    if game.get("creator_id") == callback.from_user.id:
        await callback.answer("❌ Нельзя играть с самим собой!", show_alert=True)
        return

    user = await db.get_user(callback.from_user.id)
    if not user or user["balance"] < game["bet"]:
        await callback.answer(f"❌ Нужно {game['bet']}💰", show_alert=True)
        return

    await db.update_balance(callback.from_user.id, -game["bet"])

    try:
        res = join_bw_game(game_id, callback.from_user.id, guess)
        await db.update_balance(res["winner_id"], res["prize"])
        winner = await db.get_user(res["winner_id"])
        loser = await db.get_user(res["loser_id"])

        winner_id, loser_id, win_amount = res["winner_id"], res["loser_id"], res["prize"]
        color_str = "⚪ БЕЛОЕ" if res.get('secret_choice') == "white" else "⚫ ЧЁРНОЕ"
        guesser_str = "⚪ БЕЛОЕ" if res.get('guess_choice') == "white" else "⚫ ЧЁРНОЕ"

        text = (
            f"🎲 <b>РЕЗУЛЬТАТ ИГРЫ Б/Ч #{game_id}!</b>\n\n"
            f"Загаданный цвет: <b>{color_str}</b>\n"
            f"Выбор соперника: <b>{guesser_str}</b>\n\n"
            f"🏆 Победитель: <b>{winner['username']}</b> (+{win_amount}💰)!\n"
            f"💔 Проигравший: <b>{loser['username']}</b>"
        )
    except Exception:
        guesser_choice = guess
        win_amount = int(game["bet"] * 2 * 0.95)
        secret = game.get("secret_color", game.get("secret_choice", "white"))

        if guesser_choice == secret:
            winner_id = callback.from_user.id
            loser_id = game["creator_id"]
        else:
            winner_id = game["creator_id"]
            loser_id = callback.from_user.id

        await db.update_balance(winner_id, win_amount)
        winner = await db.get_user(winner_id)
        loser = await db.get_user(loser_id)

        if game_id in active_bw_games:
            del active_bw_games[game_id]

        color_str = "⚪ БЕЛОЕ" if secret == "white" else "⚫ ЧЁРНОЕ"
        guesser_str = "⚪ БЕЛОЕ" if guesser_choice == "white" else "⚫ ЧЁРНОЕ"

        text = (
            f"🎲 <b>РЕЗУЛЬТАТ ИГРЫ Б/Ч #{game_id}!</b>\n\n"
            f"Загаданный цвет: <b>{color_str}</b>\n"
            f"Выбор соперника: <b>{guesser_str}</b>\n\n"
            f"🏆 Победитель: <b>{winner['username']}</b> (+{win_amount}💰)!\n"
            f"💔 Проигравший: <b>{loser['username']}</b>"
        )

    await callback.message.edit_text(text, reply_markup=main_menu_kb())

    try:
        await bot.send_message(winner_id, f"🎉 Ты Победил в игре Белое/Чёрное! Выиграно: +{win_amount}💰")
        await bot.send_message(loser_id, "💀 К сожалению, ты проиграл в игре Белое/Чёрное.")
    except Exception:
        pass

    await callback.answer()


# === ДУЭЛИ (ОБЩИЕ) ===
@router.callback_query(F.data == "game_duel")
async def show_duel(callback: CallbackQuery):
    await callback.message.edit_text(
        "⚔️ <b>PvP Дуэли (Монетка)</b>\n\n"
        "Создай общую дуэль для всех или ответь человеку на сообщение: <code>дуэль 100</code>", 
        reply_markup=duel_kb()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("duel_create_"))
async def duel_create(callback: CallbackQuery):
    bet = int(callback.data.replace("duel_create_", ""))
    user = await db.get_user(callback.from_user.id)

    if not user or user["balance"] < bet:
        await callback.answer(f"❌ Нужно {bet}💰", show_alert=True)
        return

    await db.update_balance(callback.from_user.id, -bet)

    try:
        duel_id = create_duel(callback.from_user.id, user["username"], bet)
    except Exception:
        duel_id = create_duel(callback.from_user.id, bet)

    await callback.message.edit_text(
        f"⚔️ <b>Дуэль #{duel_id} создана!</b>\n"
        f"Ставка: <b>{bet}💰</b>\n\n"
        f"Ожидаем соперника...",
        reply_markup=main_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "duel_list")
async def duel_list(callback: CallbackQuery):
    duels = get_waiting_duels()
    if not duels:
        await callback.message.edit_text(
            "📋 <b>Нет активных дуэлей</b>", reply_markup=duel_kb()
        )
        await callback.answer()
        return

    text = "📋 <b>Активные дуэлей:</b>\n\n"
    kb_buttons = []

    if isinstance(duels, dict):
        for d_id, d_data in list(duels.items())[:5]:
            text += f"⚔️ #{d_id} — {d_data.get('creator_name', 'Игрок')} ({d_data['bet']}💰)\n"
            kb_buttons.append([
                InlineKeyboardButton(
                    text=f"Принять #{d_id} ({d_data['bet']}💰)",
                    callback_data=f"duel_join_{d_id}",
                )
            ])
    else:
        for d in duels[:5]:
            creator = await db.get_user(d["creator_id"])
            name = creator["username"] if creator else "???"
            text += f"⚔️ #{d['id']} — {name} ({d['bet']}💰)\n"
            kb_buttons.append([
                InlineKeyboardButton(
                    text=f"Принять #{d['id']} ({d['bet']}💰)",
                    callback_data=f"duel_join_{d['id']}",
                )
            ])

    kb_buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="game_duel")])

    await callback.message.edit_text(
        text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("duel_join_"))
async def duel_join_handler(callback: CallbackQuery):
    duel_id = int(callback.data.replace("duel_join_", ""))
    duel = active_duels.get(duel_id)

    if not duel:
        await callback.answer("❌ Дуэль не найдена или уже завершена", show_alert=True)
        return

    if duel.get("creator_id") == callback.from_user.id:
        await callback.answer("❌ Нельзя играть с самим собой!", show_alert=True)
        return

    user = await db.get_user(callback.from_user.id)
    if not user or user["balance"] < duel["bet"]:
        await callback.answer(f"❌ Нужно {duel['bet']}💰", show_alert=True)
        return

    # Списание ставки
    await db.update_balance(callback.from_user.id, -duel["bet"])

    try:
        # Проведение дуэли через games.py
        res = resolve_duel(duel_id, callback.from_user.id)
        
        # Начисляем победителю
        await db.update_balance(res["winner_id"], res["prize"])
        
        winner = await db.get_user(res["winner_id"])
        loser = await db.get_user(res["loser_id"])

        text = (
            f"⚔️ <b>ДУЭЛЬ СОСТОЯЛАСЬ!</b>\n\n"
            f"🏆 Победитель: <b>{winner['username']}</b> (+{res['prize']}💰)!\n"
            f"💀 Повержен: <b>{loser['username']}</b>"
        )
        
        await callback.message.edit_text(text, reply_markup=main_menu_kb())
        
        # Пытаемся уведомить игроков в ЛС (если бот может им писать)
        try:
            if res["winner_id"] == callback.from_user.id:
                await bot.send_message(res["loser_id"], f"💀 Игрок {winner['username']} принял твою дуэль и победил.")
            else:
                await bot.send_message(res["loser_id"], f"💀 Ты проиграл дуэль против {winner['username']}.")
                await bot.send_message(res["winner_id"], f"🎉 Ты победил в дуэли! Твой выигрыш: +{res['prize']}💰")
        except Exception as e:
            pass
            
    except Exception as e:
        logger.error(f"Error resolving duel: {e}")
        await callback.message.edit_text("❌ Произошла ошибка при завершении дуэли.", reply_markup=main_menu_kb())

    await callback.answer()


# === ЗАПУСК БОТА ===
async def main():
    logger.info("Бот запускается...")
    
    # Запуск фоновой задачи рассылки (рекламы)
    asyncio.create_task(ad_loop(bot))
    
    # Сбрасываем webhook (если был установлен) и запускаем polling
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен вручную.")
