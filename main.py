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
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice,
    Message, PreCheckoutQuery,
)
from dotenv import load_dotenv

from businesses import BUSINESS_CAP_HOURS, BUSINESSES
from database import db
from games import (
    active_bw_games, active_crash_games, active_dice_games, active_duels,
    active_mines_games, calc_roulette_multiplier, cashout_crash,
    cashout_mines, create_bw_game, create_dice_game, create_duel,
    create_mines_game, format_roulette_outcome, get_mines_game,
    get_waiting_bw_games, get_waiting_dice_games, get_waiting_duels,
    join_bw_game, join_dice_game, join_duel, reveal_mines_cell,
    roulette_number_emoji, roll_slots, rps_play, run_crash_game, spin_roulette,
)
from items import CASES, RARITIES, open_case
from keyboards import (
    business_menu_kb, bw_kb, cases_kb, crash_kb, dice_kb, donate_kb, duel_kb,
    inventory_kb, main_menu_kb, mines_bet_kb, mines_board_kb, mines_diff_kb,
    mines_result_kb, prefix_color_kb, prefix_shop_kb, roulette_again_kb,
    roulette_amount_kb, roulette_menu_kb, roulette_number_amount_kb,
    roulette_outcome_kb, rps_bet_kb, rps_choice_kb, slots_again_kb, slots_kb,
    tops_kb,
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

# === ДОНАТ ЗА TELEGRAM STARS ===
# Курс для кастомной суммы: 1⭐ = 100💰
STARS_TO_COINS_RATE = 100
DONATE_PACKAGES = {
    "small": {"stars": 50, "coins": 5500, "label": "50⭐ → 5,500💰"},
    "medium": {"stars": 100, "coins": 12000, "label": "100⭐ → 12,000💰"},
    "large": {"stars": 250, "coins": 32000, "label": "250⭐ → 32,000💰"},
    "mega": {"stars": 500, "coins": 70000, "label": "500⭐ → 70,000💰"},
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher(storage=MemoryStorage())
router = Router()

# Хранилище прямых дуэлей (по вызову)
direct_duels = {}
direct_duel_counter = 1


# === МИДЛВАРЬ: АВТОРЕГИСТРАЦИЯ И ТРЕКИНГ ЧАТОВ И ОБНОВЛЕНИЕ НИКОВ ===
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
    waiting_custom_stars = State()
    waiting_roulette_number = State()


# === ПЛАВНОЕ ОТКРЫТИЕ МЕНЮ ===
async def smooth_open(callback: CallbackQuery):
    """Небольшая анимация загрузки перед сменой экрана, чтобы меню
    открывалось плавно, а не резко перескакивало на новый текст."""
    try:
        for dots in (".", "..", "..."):
            await callback.message.edit_text(f"⏳ Загрузка{dots}")
            await asyncio.sleep(0.12)
    except Exception:
        pass


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

    # Обработка реферальной ссылки: /start ref_XXXXXXXX
    parts = message.text.split(maxsplit=1) if message.text else []
    if len(parts) > 1 and parts[1].startswith("ref_"):
        ref_code = parts[1][4:]
        try:
            referrer_id = await db.apply_referral(message.from_user.id, ref_code)
            if referrer_id:
                await message.answer(
                    "🎉 Ты перешёл по реферальной ссылке и получил бонус <b>500💰</b>!"
                )
        except Exception as e:
            logger.error(f"Ошибка применения реферальной ссылки: {e}")

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

# === СИСТЕМА ПРОМОКОДОВ ===

@router.message(Command("createpromo"))
async def cmd_create_promo(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет прав для создания промокодов!")
        return

    parts = message.text.split()
    
    if len(parts) != 4:
        await message.answer(
            "⚠️ <b>Ошибка формата!</b>\n"
            "Используй: <code>/createpromo [код] [награда] [лимит]</code>\n"
            "Пример: <code>/createpromo GBL2024 5000 100</code>"
        )
        return

    code = parts[1].upper()
    
    try:
        reward = int(parts[2])
        limit = int(parts[3])
    except ValueError:
        await message.answer("❌ Награда и лимит должны быть числами!")
        return

    if reward <= 0 or limit <= 0:
        await message.answer("❌ Награда и лимит должны быть больше нуля!")
        return

    await db.add_promo_code(code, reward, limit)
    
    await message.answer(
        f"✅ <b>Промокод успешно создан!</b>\n\n"
        f"🎟 Код: <b>{code}</b>\n"
        f"💰 Награда: <b>{reward}💰</b>\n"
        f"👥 Лимит активаций: <b>{limit}</b>"
    )

@router.message(Command("promo"))
async def cmd_use_promo(message: Message):
    parts = message.text.split()
    
    if len(parts) < 2:
        await message.answer(
            "⚠️ <b>Как использовать:</b>\n"
            "Напиши <code>/promo [твой_код]</code>\n"
            "Пример: <code>/promo MEGA2024</code>"
        )
        return

    code = parts[1].upper()
    user_id = message.from_user.id

    reward = await db.use_promo_code(user_id, code)
    
    if reward:
        await message.answer(
            f"🎉 <b>Успешно!</b>\n\n"
            f"Ты активировал промокод <b>{code}</b> и получил <b>{reward}💰</b> на свой баланс!"
        )
    else:
        await message.answer(
            "❌ <b>Ошибка!</b>\n"
            "Промокод не существует, его лимит исчерпан, либо ты уже использовал его ранее."
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
        await callback.answer()
        await smooth_open(callback)
        await callback.message.edit_text(text, reply_markup=main_menu_kb())
    else:
        await msg.answer(text, reply_markup=main_menu_kb())


@router.message(Command("top"))
@router.callback_query(F.data == "tops")
async def text_cmd_top(event: CallbackQuery | Message):
    text = "🏆 <b>Рейтинги сервера GBL Casino</b>\nВыбери нужную категорию ниже:"
    if isinstance(event, CallbackQuery):
        await event.answer()
        await smooth_open(event)
        await event.message.edit_text(text, reply_markup=tops_kb())
    else:
        await event.answer(text, reply_markup=tops_kb())


@router.callback_query(F.data.startswith("top_"))
async def show_specific_top(callback: CallbackQuery):
    top_type = callback.data.replace("top_", "")
    top_users = await db.get_top_users(top_type, limit=10)

    title_map = {
        "balance": "💰 ТОП ПО БАЛАНСУ",
        "won": "📈 ТОП ПО ВЫИГРЫШАМ",
        "spent": "📉 ТОП ПО ПОТРАЧЕННОМУ",
        "inventory": "🎒 ТОП ПО ИНВЕНТАРЮ",
    }

    text = f"<b>{title_map.get(top_type, '🏆 ТОП ИГРОКОВ')}</b>\n\n"
    if not top_users:
        text += "Список пока пуст..."
    else:
        for idx, u in enumerate(top_users, start=1):
            pref = f"{u['prefix']} " if u.get('prefix') else ""
            val = u.get('value', 0)
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
        "🎲 <b>Кости</b> — PvP на костях, у кого выпадет больше — забирает банк!\n"
        "🎰 <b>Слоты</b> — крути барабан и лови комбинации символов!\n"
        "✊✋✌️ <b>КНБ</b> — камень-ножницы-бумага против бота\n"
        "💣 <b>Мины</b> — открывай безопасные клетки и копи множитель, вовремя забирай выигрыш!\n"
        "🎡 <b>Рулетка</b> — классика казино: цвет, дюжины, столбцы, чёт/нечет и ставки на число!\n"
        "📦 <b>Кейсы</b> — открывай и продавай лут\n"
        "🏢 <b>Бизнес</b> — покупай заведения и собирай пассивный доход каждый час\n"
        "🎁 <b>Бонус</b> — 2,500💰 каждые 24 часа\n"
        "👑 <b>Префиксы</b> — выделись в общем рейтинге!\n"
        "💸 <b>Перевод денег</b> — ответь командой <code>передать 100</code> на сообщение игрока\n"
        "🎟 <b>Промокоды</b> — используй команду <code>/promo [код]</code> для получения бонусов!\n"
        "⭐ <b>Донат за Stars</b> — пополняй баланс за Telegram Stars через кнопку в меню!\n"
    )
    if isinstance(event, CallbackQuery):
        await event.answer()
        await smooth_open(event)
        await event.message.edit_text(text, reply_markup=main_menu_kb())
    else:
        await event.answer(text, reply_markup=main_menu_kb())


@router.callback_query(F.data == "back_menu")
async def back_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    await smooth_open(callback)
    await callback.message.edit_text(
        "🎰 <b>Главное меню</b>\nВыбери режим:", reply_markup=main_menu_kb()
    )


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

    await callback.answer()
    await smooth_open(callback)
    await callback.message.edit_text(text, reply_markup=prefix_shop_kb())


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
    await callback.answer()
    await smooth_open(callback)
    await callback.message.edit_text(
        "📈 <b>ИГРА КРАШ</b>\n\n"
        "Выбери стандартную ставку или введи свою кастомную сумму:",
        reply_markup=crash_kb("bet"),
    )


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
    await callback.answer()
    await smooth_open(callback)
    await callback.message.edit_text(text, reply_markup=bw_kb())


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
    await callback.answer()
    await smooth_open(callback)
    await callback.message.edit_text(
        "⚔️ <b>PvP Дуэли (Монетка)</b>\n\n"
        "Создай общую дуэль для всех или ответь человеку на сообщение: <code>дуэль 100</code>", 
        reply_markup=duel_kb()
    )


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

    text = "📋 <b>Активные дуэли:</b>\n\n"
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
        await callback.answer(f"❌ Нужно {duel['bet']}💰 для участия!", show_alert=True)
        return

    # Списываем баланс и подключаем к дуэли
    await db.update_balance(callback.from_user.id, -duel["bet"])
    
    try:
        res = join_duel(duel_id, callback.from_user.id)
        
        # Начисляем выигрыш
        await db.update_balance(res["winner_id"], res["prize"])
        
        winner = await db.get_user(res["winner_id"])
        loser = await db.get_user(res["loser_id"])
        
        await callback.message.edit_text(
            f"⚔️ <b>ДУЭЛЬ СОСТОЯЛАСЬ!</b>\n\n"
            f"🏆 Победитель: <b>{winner['username']}</b> (+{res['prize']}💰)!\n"
            f"💀 Повержен: <b>{loser['username']}</b>",
            reply_markup=main_menu_kb()
        )
    except Exception as e:
        logger.error(f"Ошибка в дуэли: {e}")
        await callback.answer("❌ Произошла ошибка при проведении дуэли.", show_alert=True)
        
    await callback.answer()


# === КОСТИ (PvP) ===
@router.callback_query(F.data == "game_dice")
async def show_dice_menu(callback: CallbackQuery):
    text = (
        "🎲 <b>ИГРА «КОСТИ»</b>\n\n"
        "Создай комнату со ставкой, дождись соперника — оба бросают кубик 1-6,"
        " у кого больше, тот забирает банк! При ничьей — переброс.\n\n"
        "Создай игру или выбери из списка активных:"
    )
    await callback.answer()
    await smooth_open(callback)
    await callback.message.edit_text(text, reply_markup=dice_kb())


@router.callback_query(F.data.startswith("dice_create_"))
async def dice_create_handler(callback: CallbackQuery):
    bet = int(callback.data.replace("dice_create_", ""))
    user = await db.get_user(callback.from_user.id)

    if not user or user["balance"] < bet:
        await callback.answer(f"❌ Нужно {bet}💰", show_alert=True)
        return

    await db.update_balance(callback.from_user.id, -bet)
    game_id = create_dice_game(callback.from_user.id, user["username"], bet)

    await callback.message.edit_text(
        f"🎲 <b>Игра «Кости» #{game_id} создана!</b>\n"
        f"Ставка: <b>{bet}💰</b>\n\n"
        f"⏳ Ожидаем соперника...",
        reply_markup=main_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "dice_list")
async def dice_list_handler(callback: CallbackQuery):
    games = get_waiting_dice_games()
    if not games:
        await callback.message.edit_text(
            "📋 <b>Нет активных игр «Кости»</b>\nСоздай свою!", reply_markup=dice_kb()
        )
        await callback.answer()
        return

    text = "📋 <b>Активные игры «Кости»:</b>\n\n"
    kb = []
    for g_id, g_data in list(games.items())[:5]:
        text += f"🎲 Игра #{g_id} — {g_data['creator_name']} | Ставка: <b>{g_data['bet']}💰</b>\n"
        kb.append([
            InlineKeyboardButton(
                text=f"🎲 Сыграть #{g_id} ({g_data['bet']}💰)", callback_data=f"dice_join_{g_id}"
            )
        ])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="game_dice")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()


@router.callback_query(F.data.startswith("dice_join_"))
async def dice_join_handler(callback: CallbackQuery):
    game_id = int(callback.data.replace("dice_join_", ""))
    game = active_dice_games.get(game_id)

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

    res = join_dice_game(game_id, callback.from_user.id)
    await db.update_balance(res["winner_id"], res["prize"])
    winner = await db.get_user(res["winner_id"])
    loser = await db.get_user(res["loser_id"])

    text = (
        f"🎲 <b>РЕЗУЛЬТАТ ИГРЫ «КОСТИ» #{game_id}!</b>\n\n"
        f"Бросок создателя: <b>🎲 {res['creator_roll']}</b>\n"
        f"Бросок соперника: <b>🎲 {res['opponent_roll']}</b>\n\n"
        f"🏆 Победитель: <b>{winner['username']}</b> (+{res['prize']}💰)!\n"
        f"💔 Проигравший: <b>{loser['username']}</b>"
    )
    await callback.message.edit_text(text, reply_markup=main_menu_kb())

    try:
        await bot.send_message(res["winner_id"], f"🎉 Ты победил в игре «Кости»! Выиграно: +{res['prize']}💰")
        await bot.send_message(res["loser_id"], "💀 К сожалению, ты проиграл в игре «Кости».")
    except Exception:
        pass

    await callback.answer()


# === СЛОТЫ ===
@router.callback_query(F.data == "game_slots")
async def show_slots_menu(callback: CallbackQuery):
    text = (
        "🎰 <b>СЛОТЫ</b>\n\n"
        "Три одинаковых символа — большой множитель!\n"
        "Два одинаковых подряд — небольшой утешительный приз.\n\n"
        "Выбери ставку:"
    )
    await callback.answer()
    await smooth_open(callback)
    await callback.message.edit_text(text, reply_markup=slots_kb())


@router.callback_query(F.data.startswith("slots_spin_"))
async def slots_spin_handler(callback: CallbackQuery):
    bet = int(callback.data.replace("slots_spin_", ""))
    user = await db.get_user(callback.from_user.id)

    if not user or user["balance"] < bet:
        await callback.answer(f"❌ Нужно {bet}💰", show_alert=True)
        return

    await db.update_balance(callback.from_user.id, -bet)
    res = roll_slots(bet)

    if res["win"] > 0:
        await db.update_balance(callback.from_user.id, res["win"])
        result_line = f"🎉 <b>Выигрыш: +{res['win']}💰</b> (x{res['multiplier']})"
    else:
        result_line = f"💀 <b>Не повезло, ставка {bet}💰 сгорела.</b>"

    text = (
        f"🎰 <b>[ {' | '.join(res['reels'])} ]</b>\n\n"
        f"{result_line}"
    )
    await callback.message.edit_text(text, reply_markup=slots_again_kb(bet))
    await callback.answer()


# === КАМЕНЬ-НОЖНИЦЫ-БУМАГА ===
@router.callback_query(F.data == "game_rps")
async def show_rps_menu(callback: CallbackQuery):
    await callback.answer()
    await smooth_open(callback)
    await callback.message.edit_text(
        "✊✋✌️ <b>КАМЕНЬ-НОЖНИЦЫ-БУМАГА</b>\n\nСыграй против бота! Выбери ставку:",
        reply_markup=rps_bet_kb(),
    )


@router.callback_query(F.data.startswith("rps_bet_"))
async def rps_bet_handler(callback: CallbackQuery):
    bet = int(callback.data.replace("rps_bet_", ""))
    user = await db.get_user(callback.from_user.id)

    if not user or user["balance"] < bet:
        await callback.answer(f"❌ Нужно {bet}💰", show_alert=True)
        return

    await callback.message.edit_text(
        f"✊✋✌️ <b>Ставка: {bet}💰</b>\n\nВыбери свой ход:", reply_markup=rps_choice_kb(bet)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rps_play_"))
async def rps_play_handler(callback: CallbackQuery):
    parts = callback.data.split("_")
    bet = int(parts[2])
    user_choice = parts[3]

    user = await db.get_user(callback.from_user.id)
    if not user or user["balance"] < bet:
        await callback.answer(f"❌ Нужно {bet}💰", show_alert=True)
        return

    await db.update_balance(callback.from_user.id, -bet)
    res = rps_play(user_choice, bet)

    if res["win"] > 0:
        await db.update_balance(callback.from_user.id, res["win"])

    if res["result"] == "win":
        outcome = f"🎉 <b>Победа! +{res['win']}💰</b>"
    elif res["result"] == "draw":
        outcome = "🤝 <b>Ничья! Ставка возвращена.</b>"
    else:
        outcome = f"💀 <b>Поражение! Потеряно {bet}💰.</b>"

    text = (
        f"✊✋✌️ <b>РЕЗУЛЬТАТ</b>\n\n"
        f"Твой ход: <b>{res['user_choice_label']}</b>\n"
        f"Ход бота: <b>{res['bot_choice_label']}</b>\n\n"
        f"{outcome}"
    )
    await callback.message.edit_text(text, reply_markup=rps_bet_kb())
    await callback.answer()


# === МИНЫ ===
@router.callback_query(F.data == "game_mines")
async def show_mines_menu(callback: CallbackQuery):
    text = (
        "💣 <b>МИНЫ</b>\n\n"
        "Открывай безопасные клетки на поле 5×5, множитель растёт с каждой"
        " клеткой! Чем больше мин, тем выше риск и награда. Забери выигрыш"
        " в любой момент, пока не попал на мину.\n\n"
        "Выбери ставку:"
    )
    await callback.answer()
    await smooth_open(callback)
    await callback.message.edit_text(text, reply_markup=mines_bet_kb())


@router.callback_query(F.data.startswith("mines_bet_"))
async def mines_bet_handler(callback: CallbackQuery):
    bet = int(callback.data.replace("mines_bet_", ""))
    user = await db.get_user(callback.from_user.id)

    if not user or user["balance"] < bet:
        await callback.answer(f"❌ Нужно {bet}💰", show_alert=True)
        return

    await callback.message.edit_text(
        f"💣 <b>Ставка: {bet}💰</b>\n\nВыбери количество мин на поле:",
        reply_markup=mines_diff_kb(bet),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("mines_diff_"))
async def mines_diff_handler(callback: CallbackQuery):
    parts = callback.data.split("_")
    bet = int(parts[2])
    mines_count = int(parts[3])

    user = await db.get_user(callback.from_user.id)
    if not user or user["balance"] < bet:
        await callback.answer(f"❌ Нужно {bet}💰", show_alert=True)
        return

    if callback.from_user.id in active_mines_games:
        await callback.answer("❌ У тебя уже есть активная игра в мины!", show_alert=True)
        return

    await db.update_balance(callback.from_user.id, -bet)
    game = create_mines_game(callback.from_user.id, bet, mines_count)

    await callback.message.edit_text(
        f"💣 <b>МИНЫ</b> | Ставка: <b>{bet}💰</b> | Мин: <b>{mines_count}</b>\n"
        f"Множитель: <b>x1.0</b> | Текущий выигрыш: <b>{bet}💰</b>\n\n"
        f"Открывай клетки 🔲, чтобы поднять множитель!",
        reply_markup=mines_board_kb(game),
    )
    await callback.answer()


@router.callback_query(F.data == "mines_noop")
async def mines_noop_handler(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data.startswith("mines_pick_"))
async def mines_pick_handler(callback: CallbackQuery):
    cell_index = int(callback.data.replace("mines_pick_", ""))
    game = get_mines_game(callback.from_user.id)

    if not game:
        await callback.answer("❌ У тебя нет активной игры в мины!", show_alert=True)
        return

    res = reveal_mines_cell(callback.from_user.id, cell_index)

    if res is None or res["status"] == "already_open":
        await callback.answer()
        return

    if res["status"] == "mine":
        del active_mines_games[callback.from_user.id]
        await callback.message.edit_text(
            f"💥 <b>БУМ! Ты попал на мину!</b>\n\nСтавка <b>{res['bet']}💰</b> потеряна.",
            reply_markup=mines_result_kb(),
        )
        await callback.answer("💥 Мина!", show_alert=True)
        return

    if res["status"] == "cleared":
        del active_mines_games[callback.from_user.id]
        await db.update_balance(callback.from_user.id, res["win"])
        await callback.message.edit_text(
            f"🎉 <b>ВСЕ БЕЗОПАСНЫЕ КЛЕТКИ ОТКРЫТЫ!</b>\n\n"
            f"Множитель: <b>x{res['multiplier']}</b>\n"
            f"Выигрыш: <b>+{res['win']}💰</b>",
            reply_markup=mines_result_kb(),
        )
        await callback.answer("🎉 Джекпот!", show_alert=True)
        return

    game = get_mines_game(callback.from_user.id)
    await callback.message.edit_text(
        f"💣 <b>МИНЫ</b> | Ставка: <b>{game['bet']}💰</b> | Мин: <b>{game['mines_count']}</b>\n"
        f"Множитель: <b>x{res['multiplier']}</b> | Текущий выигрыш: <b>{res['win']}💰</b>\n\n"
        f"Открывай клетки 🔲, чтобы поднять множитель, или забери выигрыш!",
        reply_markup=mines_board_kb(game),
    )
    await callback.answer()


@router.callback_query(F.data == "mines_cashout")
async def mines_cashout_handler(callback: CallbackQuery):
    win = cashout_mines(callback.from_user.id)
    if win is None:
        await callback.answer("❌ Нечего забирать!", show_alert=True)
        return

    await db.update_balance(callback.from_user.id, win)
    user = await db.get_user(callback.from_user.id)

    await callback.message.edit_text(
        f"💰 <b>ВЫИГРЫШ ЗАБРАН!</b>\n\n"
        f"Заработано: <b>+{win}💰</b>\n"
        f"Твой баланс: <b>{user['balance']}💰</b>",
        reply_markup=mines_result_kb(),
    )
    await callback.answer()


# === ДОНАТ ЗА TELEGRAM STARS ===
@router.callback_query(F.data == "donate")
async def show_donate_menu(callback: CallbackQuery):
    text = (
        "⭐ <b>ПОПОЛНЕНИЕ ЗА TELEGRAM STARS</b>\n\n"
        "Покупай игровую валюту 💰 за звёзды Telegram!\n"
        "Выбери пакет или укажи свою сумму:"
    )
    await callback.answer()
    await smooth_open(callback)
    await callback.message.edit_text(text, reply_markup=donate_kb())


@router.callback_query(F.data.startswith("donate_") & ~F.data.in_({"donate_custom"}))
async def donate_package_handler(callback: CallbackQuery):
    package_key = callback.data.replace("donate_", "")
    package = DONATE_PACKAGES.get(package_key)

    if not package:
        await callback.answer("❌ Пакет не найден!", show_alert=True)
        return

    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        title="Пополнение баланса GBL Casino",
        description=f"Пополнение баланса на {package['coins']}💰 игровой валюты",
        payload=f"topup_{package['coins']}_{callback.from_user.id}",
        provider_token="",  # для Telegram Stars всегда пустая строка
        currency="XTR",
        prices=[LabeledPrice(label=package["label"], amount=package["stars"])],
    )
    await callback.answer()


@router.callback_query(F.data == "donate_custom")
async def donate_custom_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Form.waiting_custom_stars)
    await callback.message.edit_text(
        "✍️ <b>Введи количество Stars⭐, которое хочешь потратить:</b>\n\n"
        f"Курс: <b>1⭐ = {STARS_TO_COINS_RATE}💰</b>\n"
        "Пример: <code>150</code>"
    )
    await callback.answer()


@router.message(Form.waiting_custom_stars)
async def donate_custom_process(message: Message, state: FSMContext):
    await state.clear()

    if not message.text or not message.text.isdigit():
        await message.answer("❌ Количество Stars должно быть целым положительным числом!")
        return

    stars = int(message.text)
    if stars <= 0:
        await message.answer("❌ Количество Stars должно быть больше 0!")
        return

    coins = stars * STARS_TO_COINS_RATE

    await bot.send_invoice(
        chat_id=message.chat.id,
        title="Пополнение баланса GBL Casino",
        description=f"Пополнение баланса на {coins}💰 игровой валюты",
        payload=f"topup_{coins}_{message.from_user.id}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"{stars}⭐ → {coins}💰", amount=stars)],
    )


@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    # Подтверждаем платёж — обязательно ответить в течение 10 секунд
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def process_successful_payment(message: Message):
    payment = message.successful_payment
    try:
        coins = int(payment.invoice_payload.split("_")[1])
    except (IndexError, ValueError):
        coins = payment.total_amount * STARS_TO_COINS_RATE  # запасной вариант

    await db.update_balance(message.from_user.id, coins)
    user = await db.get_user(message.from_user.id)

    await message.answer(
        f"✅ <b>Оплата прошла успешно!</b>\n\n"
        f"⭐ Потрачено: <b>{payment.total_amount}</b> Stars\n"
        f"💰 Начислено: <b>+{coins}💰</b>\n"
        f"💳 Текущий баланс: <b>{user['balance']}💰</b>",
        reply_markup=main_menu_kb(),
    )


# === КЕЙСЫ ===
@router.callback_query(F.data == "cases")
async def show_cases_menu(callback: CallbackQuery):
    await callback.answer()
    await smooth_open(callback)
    await callback.message.edit_text(
        "📦 <b>МАГАЗИН КЕЙСОВ</b>\n\n"
        "Испытай удачу и получи крутой дроп!\n"
        "Выбери кейс для открытия:",
        reply_markup=cases_kb(),
    )


@router.callback_query(F.data.startswith("open_case_"))
async def process_open_case(callback: CallbackQuery):
    case_id = callback.data.replace("open_case_", "")
    case_data = CASES.get(case_id)

    if not case_data:
        await callback.answer("❌ Кейс не найден!", show_alert=True)
        return

    user = await db.get_user(callback.from_user.id)
    if not user or user["balance"] < case_data["price"]:
        await callback.answer(
            f"❌ Недостаточно средств! Кейс стоит {case_data['price']}💰", show_alert=True
        )
        return

    await db.update_balance(callback.from_user.id, -case_data["price"])

    drop = open_case(case_id)
    await db.add_item_to_inventory(
        callback.from_user.id, drop["name"], drop["rarity"], drop["price"]
    )

    rarity_color = RARITIES.get(drop["rarity"], {}).get("emoji", "⬜")

    text = (
        f"📦 <b>Ты открыл {case_data['name']}!</b>\n\n"
        f"Тебе выпало:\n"
        f"{rarity_color} <b>{drop['name']}</b>\n"
        f"💰 Стоимость: <b>{drop['price']}💰</b>\n\n"
        f"Предмет добавлен в твой инвентарь!"
    )

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🎒 В инвентарь", callback_data="inventory")],
                [InlineKeyboardButton(text="📦 Открыть ещё раз", callback_data=f"open_case_{case_id}")],
                [InlineKeyboardButton(text="⬅️ К кейсам", callback_data="cases")],
            ]
        ),
    )
    await callback.answer()


# === ИНВЕНТАРЬ ===
@router.callback_query(F.data == "inventory")
async def show_inventory(callback: CallbackQuery):
    items = await db.get_inventory(callback.from_user.id)

    if not items:
        text = "🎒 <b>ТВОЙ ИНВЕНТАРЬ ПУСТ</b>\n\nОткрывай кейсы, чтобы получить предметы!"
    else:
        total_value = sum(i["item_price"] for i in items)
        text = f"🎒 <b>ТВОЙ ИНВЕНТАРЬ</b>\n\nПредметов: <b>{len(items)}</b> | Общая стоимость: <b>{total_value}💰</b>\n\n"
        for i in items[:20]:
            emoji = RARITIES.get(i["item_rarity"], {}).get("emoji", "⬜")
            text += f"{emoji} <b>{i['item_name']}</b> — {i['item_price']}💰\n"
        if len(items) > 20:
            text += f"\n... и ещё {len(items) - 20} предметов"

    await callback.answer()
    await smooth_open(callback)
    await callback.message.edit_text(text, reply_markup=inventory_kb(items))


@router.callback_query(F.data == "sell_all_items")
async def sell_all_items_handler(callback: CallbackQuery):
    total = await db.sell_all_items(callback.from_user.id)

    if not total:
        await callback.answer("❌ У тебя нет предметов для продажи!", show_alert=True)
        return

    await callback.message.edit_text(
        f"💥 <b>Все предметы проданы!</b>\n\nПолучено: <b>+{total}💰</b>",
        reply_markup=main_menu_kb(),
    )
    await callback.answer(f"Продано на {total}💰!")


# === РУЛЕТКА ===
@router.callback_query(F.data == "game_roulette")
async def show_roulette_menu(callback: CallbackQuery):
    text = (
        "🎡 <b>РУЛЕТКА</b>\n\n"
        "Классическая европейская рулетка — числа от 0 до 36.\n"
        "Выбери тип ставки:\n\n"
        "🎨 Цвет — x2\n"
        "🔢 Дюжины / 📊 Столбцы — x3\n"
        "⚖️ Чёт/Нечет, диапазон — x2\n"
        "🎯 Точное число — x36\n\n"
        "⚠️ При выпадении 0 все ставки, кроме ставки на число 0, проигрывают."
    )
    await callback.answer()
    await smooth_open(callback)
    await callback.message.edit_text(text, reply_markup=roulette_menu_kb())


@router.callback_query(F.data.startswith("roul_cat_"))
async def roulette_category_handler(callback: CallbackQuery):
    category = callback.data.replace("roul_cat_", "")
    await callback.message.edit_text(
        f"🎡 <b>Рулетка — выбери исход</b>\n\nКатегория ставки выбрана. Теперь выбери конкретный вариант:",
        reply_markup=roulette_outcome_kb(category),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("roul_outcome_"))
async def roulette_outcome_handler(callback: CallbackQuery):
    parts = callback.data.split("_")
    category = parts[2]
    outcome = "_".join(parts[3:])
    label = format_roulette_outcome(category, outcome)

    await callback.message.edit_text(
        f"🎡 <b>Ставка: {label}</b>\n\nВыбери сумму ставки:",
        reply_markup=roulette_amount_kb(category, outcome),
    )
    await callback.answer()


@router.callback_query(F.data == "roul_number_start")
async def roulette_number_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Form.waiting_roulette_number)
    await callback.message.edit_text(
        "✍️ <b>Введи число от 0 до 36 текстом в чат:</b>\n\n"
        "Выигрыш при точном попадании — x36!"
    )
    await callback.answer()


@router.message(Form.waiting_roulette_number)
async def roulette_number_process(message: Message, state: FSMContext):
    await state.clear()

    if not message.text or not message.text.isdigit():
        await message.answer("❌ Нужно отправить целое число от 0 до 36!")
        return

    number = int(message.text)
    if not (0 <= number <= 36):
        await message.answer("❌ Число должно быть в диапазоне от 0 до 36!")
        return

    await message.answer(
        f"🎯 <b>Ставка на число {number}</b>\n\nВыбери сумму ставки:",
        reply_markup=roulette_number_amount_kb(number),
    )


@router.callback_query(F.data.startswith("roul_spin_"))
async def roulette_spin_handler(callback: CallbackQuery):
    parts = callback.data.split("_")
    category = parts[2]
    outcome = parts[3]
    bet = int(parts[4])

    user = await db.get_user(callback.from_user.id)
    if not user or user["balance"] < bet:
        await callback.answer(f"❌ Нужно {bet}💰", show_alert=True)
        return

    await db.update_balance(callback.from_user.id, -bet)

    number, color = spin_roulette()
    multiplier = calc_roulette_multiplier(category, outcome, number, color)
    win = bet * multiplier

    if win > 0:
        await db.update_balance(callback.from_user.id, win)
        result_line = f"🎉 <b>Победа! +{win}💰</b> (x{multiplier})"
    else:
        result_line = f"💀 <b>Не повезло, ставка {bet}💰 сгорела.</b>"

    bet_label = format_roulette_outcome(category, outcome)
    number_emoji = roulette_number_emoji(number)

    text = (
        f"🎡 <b>РЕЗУЛЬТАТ РУЛЕТКИ</b>\n\n"
        f"Твоя ставка: <b>{bet_label}</b> ({bet}💰)\n"
        f"Выпало число: <b>{number_emoji} {number}</b>\n\n"
        f"{result_line}"
    )
    await callback.message.edit_text(text, reply_markup=roulette_again_kb())
    await callback.answer()


# === БИЗНЕСЫ (ПАССИВНЫЙ ДОХОД) ===
async def _build_business_status(user_id: int):
    owned = await db.get_user_businesses(user_id)
    status = []
    for key, data in BUSINESSES.items():
        is_owned = key in owned
        pending = 0
        if is_owned:
            pending = await db.get_pending_business_income(
                user_id, key, data["hourly"], BUSINESS_CAP_HOURS
            )
        status.append({
            "key": key,
            "name": data["name"],
            "price": data["price"],
            "hourly": data["hourly"],
            "owned": is_owned,
            "pending": pending,
        })
    return status


@router.callback_query(F.data == "business_menu")
async def show_business_menu(callback: CallbackQuery):
    status = await _build_business_status(callback.from_user.id)
    text = (
        "🏢 <b>ТВОЙ БИЗНЕС</b>\n\n"
        "Покупай заведения — они приносят пассивный доход каждый час!\n"
        f"Доход копится, пока тебя нет, но не больше {BUSINESS_CAP_HOURS} часов — "
        "не забывай заходить и забирать прибыль.\n\n"
        "Твои заведения:"
    )
    await callback.answer()
    await smooth_open(callback)
    await callback.message.edit_text(text, reply_markup=business_menu_kb(status))


@router.callback_query(F.data.startswith("biz_buy_"))
async def business_buy_handler(callback: CallbackQuery):
    key = callback.data.replace("biz_buy_", "")
    data = BUSINESSES.get(key)
    if not data:
        await callback.answer("❌ Бизнес не найден!", show_alert=True)
        return

    user = await db.get_user(callback.from_user.id)
    if not user or user["balance"] < data["price"]:
        await callback.answer(f"❌ Нужно {data['price']}💰", show_alert=True)
        return

    bought = await db.buy_business(callback.from_user.id, key)
    if not bought:
        await callback.answer("❌ У тебя уже есть этот бизнес!", show_alert=True)
        return

    await db.update_balance(callback.from_user.id, -data["price"])
    await callback.answer(f"🎉 Куплено: {data['name']}!", show_alert=True)

    status = await _build_business_status(callback.from_user.id)
    await callback.message.edit_text(
        "🏢 <b>ТВОЙ БИЗНЕС</b>\n\nТвои заведения:",
        reply_markup=business_menu_kb(status),
    )


@router.callback_query(F.data.startswith("biz_collect_"))
async def business_collect_handler(callback: CallbackQuery):
    key = callback.data.replace("biz_collect_", "")
    data = BUSINESSES.get(key)
    if not data:
        await callback.answer("❌ Бизнес не найден!", show_alert=True)
        return

    income = await db.collect_business(
        callback.from_user.id, key, data["hourly"], BUSINESS_CAP_HOURS
    )
    if income <= 0:
        await callback.answer("⏳ Доход ещё не накопился, загляни позже!", show_alert=True)
        return

    await callback.answer(f"💰 Собрано: +{income}💰!", show_alert=True)

    status = await _build_business_status(callback.from_user.id)
    await callback.message.edit_text(
        "🏢 <b>ТВОЙ БИЗНЕС</b>\n\nТвои заведения:",
        reply_markup=business_menu_kb(status),
    )


@router.callback_query(F.data == "biz_noop")
async def business_noop_handler(callback: CallbackQuery):
    await callback.answer("⏳ Доход ещё копится, загляни позже!")


# === ЗАПУСК БОТА И БАЗЫ ДАННЫХ ===
async def main():
    logger.info("Initializing database...")
    await db.init_db()
    
    logger.info("Starting bot...")
    
    # Запускаем цикл с авторекламой в фоне, если нужно
    asyncio.create_task(ad_loop(bot))
    
    # Запускаем самого бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped!")
