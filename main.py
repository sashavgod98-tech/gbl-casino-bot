import asyncio
import logging
import os
import random
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineQuery,
    InlineQueryResultArticle, InputTextMessageContent,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from database import db
from items import CASES, RARITIES, open_case
from games import (
    run_crash_game, cashout_crash, active_crash_games,
    create_duel, join_duel, resolve_duel, get_waiting_duels, active_duels
)
from keyboards import (
    main_menu_kb, cases_kb, crash_kb, duel_kb, inventory_kb, tops_kb
)
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

print("🚀 Запуск бота GBL Casino...")


# === СТАРТ ===
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()

    ref_code = None
    if message.text and " " in message.text:
        parts = message.text.split(" ", 1)
        if len(parts) > 1:
            ref_code = parts[1].strip()

    user = await db.get_user(message.from_user.id)
    if not user:
        await db.create_user(message.from_user.id, message.from_user.username or "Игрок")
        user = await db.get_user(message.from_user.id)

        if ref_code:
            referrer = await db.get_user_by_ref_code(ref_code)
            if referrer and referrer['tg_id'] != message.from_user.id:
                await db.add_referral(referrer['tg_id'], message.from_user.id)
                await db.update_balance(referrer['tg_id'], 100)
                try:
                    await bot.send_message(
                        referrer['tg_id'],
                        f"🎉 Твой друг присоединился по твоей ссылке!\nТебе начислено <b>100💰</b>!"
                    )
                except:
                    pass

    ref_link = await db.get_referral_link(message.from_user.id)
    user_rank = await db.get_user_rank(message.from_user.id)

    text = (
        f"🎮 <b>Добро пожаловать в GBL Casino!</b>\n\n"
        f"Тебе начислено <b>1000💰</b> стартового капитала.\n\n"
        f"💰 Баланс: <b>{user['balance']}💰</b>\n"
        f"🏆 Топ: <b>#{user_rank or '—'}</b>\n"
        f"🔗 Реферальная ссылка:\n<code>{ref_link}</code>\n\n"
        f"Крути кейсы, играй в Краш, побеждай в дуэлях!\n"
        f"Используй меню ниже 👇"
    )

    await message.answer(text, reply_markup=main_menu_kb())


# === ПРОФИЛЬ (БЕЗ ФОТО) ===
@router.message(Command("profile"))
@router.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery | Message):
    if isinstance(callback, CallbackQuery):
        user_id = callback.from_user.id
        msg = callback.message
    else:
        user_id = callback.from_user.id
        msg = callback

    user = await db.get_user(user_id)
    if not user:
        await msg.answer("❌ Сначала начни игру /start")
        return

    ref_link = await db.get_referral_link(user_id)
    user_rank = await db.get_user_rank(user_id)

    text = (
        f" <b>ПРОФИЛЬ ИГРОКА</b>\n\n"
        f"🆔 Имя: <b>{user['username']}</b>\n"
        f"💰 Баланс: <b>{user['balance']}💰</b>\n"
        f"🏆 Топ: <b>#{user_rank or '—'}</b>\n"
        f"🎒 Инвентарь: <b>{user['inventory_value']}💰</b>\n"
        f"📈 Всего выиграно: <b>{user['total_won']}💰</b>\n"
        f"📉 Всего потрачено: <b>{user['total_spent']}💰</b>\n\n"
        f"🔗 <b>Твоя реферальная ссылка:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"💡 Приводи друзей и получай <b>100</b> за каждого!"
    )

    if isinstance(callback, CallbackQuery):
        await callback.message.edit_text(text, reply_markup=main_menu_kb())
        await callback.answer()
    else:
        await msg.answer(text, reply_markup=main_menu_kb())


# === НАВИГАЦИЯ ===
@router.callback_query(F.data == "back_menu")
async def back_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎰 <b>Главное меню</b>\nВыбери игру:",
        reply_markup=main_menu_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "help")
async def help_cmd(callback: CallbackQuery):
    text = (
        "ℹ️ <b>Помощь</b>\n\n"
        "📈 <b>Краш</b> — ставка растёт, забирай до краша!\n"
        "📦 <b>Кейсы</b> — открывай лутбоксы, собирай инвентарь\n"
        "⚔️ <b>Дуэль</b> — играй 1 на 1, победитель забирает всё\n"
        "🎁 <b>Бонус</b> — 500💰 каждый день\n"
        "🎒 <b>Инвентарь</b> — продавай предметы\n"
        "🏆 <b>Топы</b> — топ богачей и коллекционеров\n"
        "🎟️ <b>Промокод</b> — активируй промокоды\n"
        "👤 <b>Профиль</b> — твой профиль с рефералкой\n\n"
        "Комиссия бота на дуэлях: 5%"
    )
    await callback.message.edit_text(text, reply_markup=main_menu_kb())
    await callback.answer()


# === ЕЖЕДНЕВНЫЙ БОНУС ===
@router.callback_query(F.data == "daily")
async def daily_bonus(callback: CallbackQuery):
    if await db.can_claim_daily(callback.from_user.id):
        await db.claim_daily(callback.from_user.id)
        await db.update_balance(callback.from_user.id, 500)
        await callback.message.edit_text(
            "🎁 <b>Ежедневный бонус получен!</b>\n\n"
            "Тебе начислено <b>500💰</b>\n"
            "Возвращайся завтра за следующим!",
            reply_markup=main_menu_kb()
        )
    else:
        await callback.message.edit_text(
            " <b>Бонус уже получен сегодня</b>\n"
            "Возвращайся завтра!",
            reply_markup=main_menu_kb()
        )
    await callback.answer()


# === КЕЙСЫ ===
@router.callback_query(F.data == "game_cases")
async def show_cases(callback: CallbackQuery):
    text = " <b>Выбери кейс:</b>\n\n"
    for key, case in CASES.items():
        text += f"{case['name']} — <b>{case['price']}💰</b>\n"
        text += f"   {case['description']}\n\n"
    await callback.message.edit_text(text, reply_markup=cases_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("open_case_"))
async def open_case_handler(callback: CallbackQuery):
    case_key = callback.data.replace("open_case_", "")
    if case_key not in CASES:
        return

    user = await db.get_user(callback.from_user.id)
    case = CASES[case_key]

    if user['balance'] < case['price']:
        await callback.answer(f" Нужно {case['price']}💰, у тебя {user['balance']}💰", show_alert=True)
        return

    await db.update_balance(callback.from_user.id, -case['price'])

    anim_msg = await callback.message.answer("🎰 <b>Открываем кейс...</b>\n⏳")

    rarity, name, price = open_case(case_key)
    rarity_info = RARITIES[rarity]

    emojis = ['⚪', '', '🟣', '🟡', '🔴']
    for i in range(8):
        await asyncio.sleep(0.3)
        try:
            await bot.edit_message_text(
                f"🎰 <b>Открываем {case['name']}...</b>\n"
                f"{''.join(random.choice(emojis) for _ in range(10))}",
                chat_id=anim_msg.chat.id,
                message_id=anim_msg.message_id
            )
        except:
            pass

    await db.add_item(callback.from_user.id, name, rarity, price)

    await bot.edit_message_text(
        f"🎉 <b>Поздравляем!</b>\n\n"
        f"Из {case['name']} выпало:\n"
        f"{rarity_info['emoji']} <b>{name}</b>\n"
        f"Редкость: {rarity_info['name']}\n"
        f"Цена: <b>{price}💰</b>\n\n"
        f"Предмет добавлен в инвентарь!",
        chat_id=anim_msg.chat.id,
        message_id=anim_msg.message_id
    )
    await callback.answer()


# === КРАШ ===
@router.callback_query(F.data == "game_crash")
async def show_crash(callback: CallbackQuery):
    await callback.message.edit_text(
        "📈 <b>Игра КРАШ</b>\n\n"
        "Множитель растёт — забирай выигрыш до краша!\n"
        "Краш может случиться в любой момент.\n\n"
        "Выбери ставку:",
        reply_markup=crash_kb("bet")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("crash_bet_"))
async def crash_bet(callback: CallbackQuery):
    bet = int(callback.data.replace("crash_bet_", ""))
    user = await db.get_user(callback.from_user.id)

    if user['balance'] < bet:
        await callback.answer(f"❌ Недостаточно средств! Нужно {bet}💰", show_alert=True)
        return

    await db.update_balance(callback.from_user.id, -bet)

    msg = await callback.message.answer(
        f"📈 <b>КРАШ запущен!</b>\n\n"
        f"Ставка: <b>{bet}💰</b>\n"
        f"Множитель: <b>1.00x</b>\n"
        f"Выигрыш: <b>{bet}💰</b>\n\n"
        f"⏰ Забирай, пока не поздно!",
        reply_markup=crash_kb("playing")
    )

    success = await run_crash_game(callback.from_user.id, bet, bot, msg)
    if not success:
        await db.update_balance(callback.from_user.id, bet)
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
        f"💰 <b>ТЫ ЗАБРАЛ ВЫИГРЫШ!</b>\n\n"
        f"Выигрыш: <b>{win}💰</b>\n"
        f"Твой баланс: <b>{user['balance']}💰</b>",
        reply_markup=main_menu_kb()
    )
    await callback.answer("✅ Выигрыш зачислен!")


# === ДУЭЛИ ===
@router.callback_query(F.data == "game_duel")
async def show_duel(callback: CallbackQuery):
    await callback.message.edit_text(
        "️ <b>PvP Дуэли (Монетка)</b>\n\n"
        "Создай дуэль или присоединись к существующей.\n"
        "Победитель забирает весь банк (минус 5% комиссии).\n\n"
        "Выбери ставку:",
        reply_markup=duel_kb()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("duel_create_"))
async def duel_create(callback: CallbackQuery):
    bet = int(callback.data.replace("duel_create_", ""))
    user = await db.get_user(callback.from_user.id)

    if user['balance'] < bet:
        await callback.answer(f"❌ Нужно {bet}💰", show_alert=True)
        return

    await db.update_balance(callback.from_user.id, -bet)
    duel_id = create_duel(callback.from_user.id, bet)

    await callback.message.edit_text(
        f"️ <b>Дуэль #{duel_id} создана!</b>\n\n"
        f"Ставка: <b>{bet}💰</b>\n"
        f"Банк: <b>{bet * 2}💰</b>\n"
        f"Ожидание второго игрока...\n"
        f"(автоотмена через 60 сек)",
        reply_markup=main_menu_kb()
    )

    await asyncio.sleep(60)
    if duel_id in active_duels and active_duels[duel_id]['status'] == 'waiting':
        await db.update_balance(callback.from_user.id, bet)
        del active_duels[duel_id]
        try:
            await bot.send_message(
                callback.from_user.id,
                f" Дуэль #{duel_id} отменена — никто не принял вызов. Ставка возвращена."
            )
        except:
            pass
    await callback.answer()


@router.callback_query(F.data == "duel_list")
async def duel_list(callback: CallbackQuery):
    duels = get_waiting_duels()
    if not duels:
        await callback.message.edit_text(
            "📋 <b>Нет активных дуэлей</b>\nСоздай свою!",
            reply_markup=duel_kb()
        )
        await callback.answer()
        return

    text = "📋 <b>Активные дуэли:</b>\n\n"
    kb_buttons = []
    for d in duels[:5]:
        creator = await db.get_user(d['creator_id'])
        name = creator['username'] if creator else "???"
        text += f"️ #{d['id']} — {name} ставит <b>{d['bet']}💰</b>\n"
        kb_buttons.append([InlineKeyboardButton(
            text=f"⚔️ Принять дуэль #{d['id']} ({d['bet']}💰)",
            callback_data=f"duel_join_{d['id']}"
        )])
    kb_buttons.append([InlineKeyboardButton(text="️ Назад", callback_data="game_duel")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons))
    await callback.answer()


@router.callback_query(F.data.startswith("duel_join_"))
async def duel_join(callback: CallbackQuery):
    duel_id = int(callback.data.replace("duel_join_", ""))
    duel = active_duels.get(duel_id)

    if not duel:
        await callback.answer(" Дуэль не найдена", show_alert=True)
        return

    user = await db.get_user(callback.from_user.id)
    if user['balance'] < duel['bet']:
        await callback.answer(f"❌ Нужно {duel['bet']}💰", show_alert=True)
        return

    await db.update_balance(callback.from_user.id, -duel['bet'])
    duel = join_duel(duel_id, callback.from_user.id)

    msg = await callback.message.answer("🪙 <b>Бросаем монетку...</b>\n⏳")
    await asyncio.sleep(2)

    result = resolve_duel(duel_id)
    await db.update_balance(result['winner_id'], result['prize'])

    winner = await db.get_user(result['winner_id'])
    loser = await db.get_user(result['loser_id'])

    await bot.edit_message_text(
        f" <b>Результат дуэли #{duel_id}</b>\n\n"
        f"Монета: <b>{result['result'].upper()}</b>\n"
        f"Выбор создателя: {result['creator_choice']}\n\n"
        f"🏆 Победитель: <b>{winner['username']}</b>\n"
        f"Выигрыш: <b>{result['prize']}💰</b>\n\n"
        f"💀 Проигравший: {loser['username']}\n"
        f"🏦 Комиссия бота: {result['commission']}💰",
        chat_id=msg.chat.id,
        message_id=msg.message_id,
        reply_markup=main_menu_kb()
    )

    try:
        await bot.send_message(
            result['winner_id'],
            f" Ты выиграл дуэль #{duel_id}! +{result['prize']}💰"
        )
        if result['loser_id'] != result['winner_id']:
            await bot.send_message(
                result['loser_id'],
                f" Ты проиграл дуэль #{duel_id}. -{duel['bet']}💰"
            )
    except:
        pass

    await callback.answer()


# === ИНВЕНТАРЬ ===
@router.callback_query(F.data == "inventory")
async def show_inventory(callback: CallbackQuery):
    items = await db.get_inventory(callback.from_user.id)
    if not items:
        await callback.message.edit_text(
            "🎒 <b>Инвентарь пуст</b>\nОткрой кейсы, чтобы получить предметы!",
            reply_markup=main_menu_kb()
        )
        await callback.answer()
        return

    text = "🎒 <b>Твой инвентарь:</b>\n\n"
    total = 0
    for item in items[:15]:
        rarity = RARITIES.get(item['item_rarity'], {})
        emoji = rarity.get('emoji', '')
        text += f"{emoji} {item['item_name']} — <b>{item['item_price']}💰</b>\n"
        total += item['item_price']
    text += f"\n💼 <b>Общая стоимость: {total}💰</b>"

    await callback.message.edit_text(text, reply_markup=inventory_kb(items))
    await callback.answer()


@router.callback_query(F.data.startswith("sell_item_"))
async def sell_item(callback: CallbackQuery):
    item_id = int(callback.data.replace("sell_item_", ""))
    price = await db.sell_item(item_id, callback.from_user.id)

    if price == 0:
        await callback.answer("❌ Предмет не найден", show_alert=True)
        return

    await callback.answer(f"✅ Продано за {price}💰!", show_alert=True)
    await show_inventory(callback)


# === ТОПЫ ===
@router.callback_query(F.data == "tops")
async def show_tops(callback: CallbackQuery):
    await callback.message.edit_text(
        "🏆 <b>Рейтинги</b>\nВыбери категорию:",
        reply_markup=tops_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "top_balance")
async def top_balance(callback: CallbackQuery):
    players = await db.get_top_balance(10)
    text = "💰 <b>Топ богачей:</b>\n\n"
    for i, p in enumerate(players, 1):
        medal = ['🥇','🥈','🥉'][i-1] if i <= 3 else f'{i}.'
        text += f"{medal} {p['username']} — <b>{p['balance']}💰</b>\n"

    await callback.message.edit_text(text, reply_markup=tops_kb())
    await callback.answer()


@router.callback_query(F.data == "top_inventory")
async def top_inventory(callback: CallbackQuery):
    players = await db.get_top_inventory(10)
    text = "🎒 <b>Топ коллекционеров:</b>\n\n"
    for i, p in enumerate(players, 1):
        medal = ['🥇','🥈',''][i-1] if i <= 3 else f'{i}.'
        text += f"{medal} {p['username']} — <b>{p['inventory_value']}💰</b>\n"

    await callback.message.edit_text(text, reply_markup=tops_kb())
    await callback.answer()


# === ПРОМОКОДЫ ===
@router.message(Command("createpromo"))
async def create_promo(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Только админ может создавать промокоды!")
        return

    args = message.text.split()
    if len(args) != 4:
        await message.answer(
            " Неправильный формат!\n"
            "Используй: /createpromo КОД НАГРАДА МАКС_ИСПОЛЬЗОВАНИЙ\n"
            "Пример: /createpromo GIFT2026 500 10"
        )
        return

    code = args[1]
    reward = int(args[2])
    max_uses = int(args[3])

    await db.add_promo_code(code, reward, max_uses)
    await message.answer(f"✅ Промокод <b>{code.upper()}</b> создан!\nНаграда: {reward}💰\nМакс. использований: {max_uses}")


@router.message(Command("promo"))
async def activate_promo(message: Message):
    args = message.text.split()
    if len(args) != 2:
        await message.answer("❌ Неправильный формат!\nИспользуй: /promo КОД")
        return

    code = args[1]
    result = await db.use_promo_code(message.from_user.id, code)

    if result is False:
        await message.answer("❌ Промокод недействителен или уже использован!")
    else:
        await message.answer(f"✅ Промокод активирован!\nПолучено: <b>{result}💰</b>")


@router.callback_query(F.data == "promo")
async def promo_callback(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎟️ <b>Активация промокода</b>\n\n"
        "Введи промокод командой:\n"
        "<code>/promo КОД</code>\n\n"
        "Пример: /promo GIFT2026",
        reply_markup=main_menu_kb()
    )
    await callback.answer()


# === INLINE РЕЖИМ ===
@router.inline_query()
async def inline_handler(inline_query: InlineQuery):
    query = inline_query.query.lower()
    user = await db.get_user(inline_query.from_user.id)

    if not user:
        results = [
            InlineQueryResultArticle(
                id="error",
                title="❌ Ты не зарегистрирован",
                description="Напиши боту /start чтобы начать",
                input_message_content=InputTextMessageContent(
                    message_text="🎰 <b>GBL Casino</b>\nНапиши /start чтобы начать игру!"
                )
            )
        ]
        await inline_query.answer(results)
        return

    if query == "" or query == "stats":
        results = [
            InlineQueryResultArticle(
                id="stats",
                title="📊 Моя статистика",
                description=f"Баланс: {user['balance']}💰",
                input_message_content=InputTextMessageContent(
                    message_text=(
                        f"📊 <b>Статистика {user['username']}</b>\n"
                        f"💰 Баланс: <b>{user['balance']}💰</b>\n"
                        f"🎒 Стоимость инвентаря: <b>{user['inventory_value']}💰</b>"
                    )
                )
            )
        ]
    elif query == "top":
        top_players = await db.get_top_balance(5)
        text = "🏆 <b>Топ 5 богачей:</b>\n\n"
        for i, p in enumerate(top_players, 1):
            medal = ['🥇','🥈','🥉'][i-1] if i <= 3 else f'{i}.'
            text += f"{medal} {p['username']} — <b>{p['balance']}💰</b>\n"

        results = [
            InlineQueryResultArticle(
                id="top",
                title="🏆 Топ игроков",
                description="Топ 5 богачей сервера",
                input_message_content=InputTextMessageContent(message_text=text)
            )
        ]
    else:
        results = [
            InlineQueryResultArticle(
                id="help",
                title="ℹ️ Помощь",
                description="Используй: stats, top",
                input_message_content=InputTextMessageContent(
                    message_text=(
                        " <b>GBL Casino - Inline режим</b>\n"
                        "Введи:\n"
                        "• <code>stats</code> - твоя статистика\n"
                        "• <code>top</code> - топ игроков"
                    )
                )
            )
        ]

    await inline_query.answer(results, cache_time=60)


async def main():
    await db.init_db()
    logger.info(" GBL Casino запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())