import asyncio
import logging
import os
import random
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    Message,
)
from database import db
from dotenv import load_dotenv
from games import (
    active_bw_games,
    active_crash_games,
    active_duels,
    cashout_crash,
    create_bw_game,
    create_duel,
    get_waiting_bw_games,
    get_waiting_duels,
    join_bw_game,
    join_duel,
    resolve_duel,
    run_crash_game,
)
from items import CASES, RARITIES, open_case
from keyboards import (
    bw_kb,
    cases_kb,
    crash_kb,
    duel_kb,
    inventory_kb,
    main_menu_kb,
    prefix_shop_kb,
    tops_kb,
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)


class Form(StatesGroup):
  waiting_custom_crash = State()


print("🚀 Запуск обновленного GBL Casino Bot...")


# === СТАРТ ===
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
  await state.clear()

  username = message.from_user.username
  display_name = (
      f"@{username}" if username else message.from_user.first_name or "Игрок"
  )

  user = await db.get_user(message.from_user.id)
  if not user:
    await db.create_user(message.from_user.id, display_name)
    user = await db.get_user(message.from_user.id)

  ref_link = await db.get_referral_link(message.from_user.id)
  user_rank = await db.get_user_rank(message.from_user.id)
  pref = f"{user['prefix']} " if user['prefix'] else ""

  text = (
      f"🎮 <b>Добро пожаловать в GBL Casino!</b>\n\n"
      f"👤 Игрок: <b>{pref}{user['username']}</b>\n"
      f"💰 Баланс: <b>{user['balance']}💰</b>\n"
      f"🏆 Место в топе: <b>#{user_rank or '—'}</b>\n\n"
      f"🔗 Реферальная ссылка:\n<code>{ref_link}</code>\n\n"
      f"Выбирай режим игры в меню ниже 👇"
  )

  await message.answer(text, reply_markup=main_menu_kb())


# === ПРОФИЛЬ ===
@router.message(Command("profile"))
@router.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery | Message):
  user_id = callback.from_user.id
  msg = callback.message if isinstance(callback, CallbackQuery) else callback

  user = await db.get_user(user_id)
  if not user:
    await msg.answer("❌ Сначала начни игру /start")
    return

  ref_link = await db.get_referral_link(user_id)
  user_rank = await db.get_user_rank(user_id)
  pref = f"{user['prefix']} " if user['prefix'] else ""

  text = (
      f"👤 <b>ПРОФИЛЬ ИГРОКА</b>\n\n"
      f"🏷️ Префикс + Ник: <b>{pref}{user['username']}</b>\n"
      f"💰 Баланс: <b>{user['balance']}💰</b>\n"
      f"🏆 Топ: <b>#{user_rank or '—'}</b>\n"
      f"🎒 Инвентарь: <b>{user['inventory_value']}💰</b>\n"
      f"📈 Выиграно: <b>{user['total_won']}💰</b>\n"
      f"📉 Потрачено: <b>{user['total_spent']}💰</b>\n\n"
      f"🔗 <b>Реферальная ссылка:</b>\n<code>{ref_link}</code>"
  )

  if isinstance(callback, CallbackQuery):
    await callback.message.edit_text(text, reply_markup=main_menu_kb())
    await callback.answer()
  else:
    await msg.answer(text, reply_markup=main_menu_kb())


# === МАГАЗИН ПРЕФИКСОВ ===
@router.callback_query(F.data == "prefix_shop")
async def show_prefix_shop(callback: CallbackQuery):
  user = await db.get_user(callback.from_user.id)
  curr_prefix = user["prefix"] if user["prefix"] else "Отсутствует"

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

  if user["balance"] < price:
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


# === НАВИГАЦИЯ И ПОМОЩЬ ===
@router.callback_query(F.data == "back_menu")
async def back_menu(callback: CallbackQuery, state: FSMContext):
  await state.clear()
  await callback.message.edit_text(
      "🎰 <b>Главное меню</b>\nВыбери режим:", reply_markup=main_menu_kb()
  )
  await callback.answer()


@router.callback_query(F.data == "help")
async def help_cmd(callback: CallbackQuery):
  text = (
      "ℹ️ <b>ПОМОЩЬ И ИГРЫ</b>\n\n"
      "📈 <b>Краш</b> — растущий множитель с кастомными ставками!\n"
      "⚪/⚫ <b>Белое и Чёрное</b> — PvP угадайка с другими игроками\n"
      "⚔️ <b>Дуэль</b> — классическая монетка на двоих\n"
      "📦 <b>Кейсы</b> — открывай и продавай лут\n"
      "🎁 <b>Бонус</b> — 2,500💰 каждые 24 часа\n"
      "👑 <b>Префиксы</b> — выделись в общем рейтинге!\n"
      "💸 <b>Перевод денег</b> — ответь командой `/pay 100` на сообщение"
      " игрока\n"
  )
  await callback.message.edit_text(text, reply_markup=main_menu_kb())
  await callback.answer()


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

  if not message.text.isdigit():
    await message.answer("❌ Сумма должна быть целым положительным числом!")
    return

  bet = int(message.text)
  if bet <= 0:
    await message.answer("❌ Ставка должна быть больше 0!")
    return

  user = await db.get_user(message.from_user.id)
  if user["balance"] < bet:
    await message.answer(
        f"❌ Недостаточно баланса! У тебя: {user['balance']}💰"
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

  if user["balance"] < bet:
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
      "2. Соперник подключается и пытаться отгадать цвет.\n"
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
  choice = parts[3]  # 'white' or 'black'

  user = await db.get_user(callback.from_user.id)
  if user["balance"] < bet:
    await callback.answer(f"❌ Нужно {bet}💰", show_alert=True)
    return

  await db.update_balance(callback.from_user.id, -bet)
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
  for g in games[:5]:
    creator = await db.get_user(g["creator_id"])
    c_name = creator["username"] if creator else "Игрок"
    text += f"🎮 Комната #{g['id']} — {c_name} | Ставка: <b>{g['bet']}💰</b>\n"

    kb.append([
        InlineKeyboardButton(
            text=f"⚪ Попробовать ⚪ ({g['bet']}💰)",
            callback_data=f"bw_join_{g['id']}_white",
        ),
        InlineKeyboardButton(
            text=f"⚫ Попробовать ⚫ ({g['bet']}💰)",
            callback_data=f"bw_join_{g['id']}_black",
        ),
    ])

  kb.append(
      [InlineKeyboardButton(text="⬅️ Назад", callback_data="game_bw")]
  )

  await callback.message.edit_text(
      text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
  )
  await callback.answer()


@router.callback_query(F.data.startswith("bw_join_"))
async def bw_join_handler(callback: CallbackQuery):
  parts = callback.data.split("_")
  game_id = int(parts[2])
  guess = parts[3]  # 'white' or 'black'

  game = active_bw_games.get(game_id)
  if not game:
    await callback.answer("❌ Игра уже завершена или отменена!", show_alert=True)
    return

  user = await db.get_user(callback.from_user.id)
  if user["balance"] < game["bet"]:
    await callback.answer(f"❌ Нужно {game['bet']}💰", show_alert=True)
    return

  await db.update_balance(callback.from_user.id, -game["bet"])
  res = join_bw_game(game_id, callback.from_user.id, guess)

  await db.update_balance(res["winner_id"], res["prize"])

  winner = await db.get_user(res["winner_id"])
  loser = await db.get_user(res["loser_id"])

  text = (
      f"🏁 <b>ИТОГИ ИГРЫ «БЕЛОЕ ИЛИ ЧЁРНОЕ»</b>\n\n"
      f"Загаданный цвет: <b>{res['secret_choice']}</b>\n"
      f"Выбор соперника: <b>{res['guess_choice']}</b>\n\n"
      f"🏆 Победитель: <b>{winner['username']}</b> (+{res['prize']}💰)\n"
      f"💀 Проигравший: {loser['username']}\n"
      f"🏦 Комиссия: {res['commission']}💰"
  )

  await callback.message.edit_text(text, reply_markup=main_menu_kb())

  try:
    await bot.send_message(
        res["winner_id"],
        f"🎉 Ты Победил в игре Белое/Чёрное! Выиграно: +{res['prize']}💰",
    )
    await bot.send_message(
        res["loser_id"], "💀 К сожалению, ты проиграл в игре Белое/Чёрное."
    )
  except Exception:
    pass

  await callback.answer()


# === ДУЭЛИ ===
@router.callback_query(F.data == "game_duel")
async def show_duel(callback: CallbackQuery):
  await callback.message.edit_text(
      "⚔️ <b>PvP Дуэли (Монетка)</b>\nВыбери ставку:", reply_markup=duel_kb()
  )
  await callback.answer()


@router.callback_query(F.data.startswith("duel_create_"))
async def duel_create(callback: CallbackQuery):
  bet = int(callback.data.replace("duel_create_", ""))
  user = await db.get_user(callback.from_user.id)

  if user["balance"] < bet:
    await callback.answer(f"❌ Нужно {bet}💰", show_alert=True)
    return

  await db.update_balance(callback.from_user.id, -bet)
  duel_id = create_duel(callback.from_user.id, bet)

  await callback.message.edit_text(
      f"⚔️ <b>Дуэль #{duel_id} создана!</b>\n"
      f"Ставка: <b>{bet}💰</b>\n"
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
  kb_buttons.append(
      [InlineKeyboardButton(text="⬅️ Назад", callback_data="game_duel")]
  )

  await callback.message.edit_text(
      text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons)
  )
  await callback.answer()


@router.callback_query(F.data.startswith("duel_join_"))
async def duel_join_handler(callback: CallbackQuery):
  duel_id = int(callback.data.replace("duel_join_", ""))
  duel = active_duels.get(duel_id)

  if not duel:
    await callback.answer("❌ Дуэль не найдена", show_alert=True)
    return

  user = await db.get_user(callback.from_user.id)
  if user["balance"] < duel["bet"]:
    await callback.answer(f"❌ Нужно {duel['bet']}💰", show_alert=True)
    return

  await db.update_balance(callback.from_user.id, -duel["bet"])
  join_duel(duel_id, callback.from_user.id)

  res = resolve_duel(duel_id)
  await db.update_balance(res["winner_id"], res["prize"])

  winner = await db.get_user(res["winner_id"])
  loser = await db.get_user(res["loser_id"])

  await callback.message.edit_text(
      f"🏆 <b>Итоги Дуэли #{duel_id}</b>\n\n"
      f"Монета: <b>{res['result'].upper()}</b>\n"
      f"🏆 Победитель: <b>{winner['username']}</b> (+{res['prize']}💰)\n"
      f"💀 Проигравший: {loser['username']}",
      reply_markup=main_menu_kb(),
  )
  await callback.answer()


# === КЕЙСЫ И ИНВЕНТАРЬ ===
@router.callback_query(F.data == "game_cases")
async def show_cases(callback: CallbackQuery):
  text = "📦 <b>Кейсы с предметами:</b>\n\n"
  for key, case in CASES.items():
    text += f"{case['name']} — <b>{case['price']}💰</b>\n"
  await callback.message.edit_text(text, reply_markup=cases_kb())
  await callback.answer()


@router.callback_query(F.data.startswith("open_case_"))
async def open_case_handler(callback: CallbackQuery):
  case_key = callback.data.replace("open_case_", "")
  if case_key not in CASES:
    return

  user = await db.get_user(callback.from_user.id)
  case = CASES[case_key]

  if user["balance"] < case["price"]:
    await callback.answer(
        f"❌ Недостаточно монет! Нужно {case['price']}💰", show_alert=True
    )
    return

  await db.update_balance(callback.from_user.id, -case["price"])
  rarity, name, price = open_case(case_key)
  await db.add_item(callback.from_user.id, name, rarity, price)

  rarity_info = RARITIES[rarity]

  await callback.message.edit_text(
      f"🎉 <b>Открыт {case['name']}!</b>\n\n"
      f"Предмет: {rarity_info['emoji']} <b>{name}</b>\n"
      f"Редкость: {rarity_info['name']}\n"
      f"Стоимость предмета: <b>{price}💰</b>\n\n"
      f"Предмет помещен в инвентарь!",
      reply_markup=main_menu_kb(),
  )
  await callback.answer()


@router.callback_query(F.data == "inventory")
async def show_inventory(callback: CallbackQuery):
  items = await db.get_inventory(callback.from_user.id)
  if not items:
    await callback.message.edit_text(
        "🎒 <b>Инвентарь пуст!</b>", reply_markup=main_menu_kb()
    )
    await callback.answer()
    return

  text = f"🎒 <b>Твой инвентарь ({len(items)} предметов):</b>\n\n"
  total = 0
  for item in items[:10]:
    rarity = RARITIES.get(item["item_rarity"], {})
    emoji = rarity.get("emoji", "⚪")
    text += f"{emoji} {item['item_name']} — <b>{item['item_price']}💰</b>\n"
    total += item["item_price"]

  text += f"\n💼 <b>Общая ценность: {total}💰</b>"
  await callback.message.edit_text(text, reply_markup=inventory_kb(items))
  await callback.answer()


@router.callback_query(F.data.startswith("sell_item_"))
async def sell_item_handler(callback: CallbackQuery):
  item_id = int(callback.data.replace("sell_item_", ""))
  price = await db.sell_item(item_id, callback.from_user.id)
  if price > 0:
    await callback.answer(f"✅ Продано за +{price}💰!", show_alert=True)
  await show_inventory(callback)


@router.callback_query(F.data == "sell_all_items")
async def sell_all_handler(callback: CallbackQuery):
  total = await db.sell_all_items(callback.from_user.id)
  if total > 0:
    await callback.answer(
        f"💥 Все предметы проданы на сумму +{total}💰!", show_alert=True
    )
  else:
    await callback.answer("❌ Инвентарь уже пуст!", show_alert=True)
  await show_inventory(callback)


# === ТОПЫ С ЮЗЕРНЕЙМАМИ И ПРЕФИКСАМИ ===
@router.callback_query(F.data == "tops")
async def show_tops(callback: CallbackQuery):
  await callback.message.edit_text(
      "🏆 <b>Рейтинги сервера</b>", reply_markup=tops_kb()
  )
  await callback.answer()


@router.callback_query(F.data == "top_balance")
async def top_balance_handler(callback: CallbackQuery):
  players = await db.get_top_balance(10)
  text = "💰 <b>ТОП 10 БОГАЧЕЙ:</b>\n\n"

  for i, p in enumerate(players, 1):
    medal = ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else f"<b>{i}.</b>"
    pref = f"{p['prefix']} " if p["prefix"] else ""
    text += f"{medal} {pref}{p['username']} — <b>{p['balance']}💰</b>\n"

  await callback.message.edit_text(text, reply_markup=tops_kb())
  await callback.answer()


@router.callback_query(F.data == "top_inventory")
async def top_inventory_handler(callback: CallbackQuery):
  players = await db.get_top_inventory(10)
  text = "🎒 <b>ТОП 10 КОЛЛЕКЦИОНЕРОВ:</b>\n\n"

  for i, p in enumerate(players, 1):
    medal = ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else f"<b>{i}.</b>"
    pref = f"{p['prefix']} " if p["prefix"] else ""
    text += (
        f"{medal} {pref}{p['username']} — <b>{p['inventory_value']}💰</b>\n"
    )

  await callback.message.edit_text(text, reply_markup=tops_kb())
  await callback.answer()


# === АДМИНКА И ЗАЩИТА (ОБЫЧНЫЕ ИГРОКИ НЕ МОГУТ ВЫДАВАТЬ) ===
@router.message(Command("givemoney"))
async def admin_give_money(message: Message):
  if message.from_user.id != ADMIN_ID:
    await message.answer("⛔ <b>Ошибка доступа!</b> У вас нет прав админа.")
    return

  args = message.text.split()
  if len(args) != 3:
    await message.answer("⚠️ Формат: `/givemoney TG_ID СУММА`")
    return

  target_id = int(args[1])
  amount = int(args[2])

  await db.update_balance(target_id, amount)
  await message.answer(f"✅ Успешно выдано <b>{amount}💰</b> игроку {target_id}")


@router.message(Command("setprefix"))
async def admin_set_prefix(message: Message):
  if message.from_user.id != ADMIN_ID:
    await message.answer("⛔ <b>Ошибка доступа!</b> У вас нет прав админа.")
    return

  args = message.text.split(maxsplit=2)
  if len(args) != 3:
    await message.answer("⚠️ Формат: `/setprefix TG_ID ПРЕФИКС`")
    return

  target_id = int(args[1])
  prefix = args[2]

  await db.set_prefix(target_id, prefix)
  await message.answer(f"✅ Игроку {target_id} установлен префикс {prefix}")


@router.message(Command("createpromo"))
async def admin_create_promo(message: Message):
  if message.from_user.id != ADMIN_ID:
    await message.answer("⛔ <b>Ошибка доступа!</b> У вас нет прав админа.")
    return

  args = message.text.split()
  if len(args) != 4:
    await message.answer(
        "⚠️ Формат: `/createpromo КОД НАГРАДА ИСПОЛЬЗОВАНИЙ`"
    )
    return

  await db.add_promo_code(args[1], int(args[2]), int(args[3]))
  await message.answer(f"✅ Промокод {args[1].upper()} создан!")


@router.message(Command("promo"))
async def activate_promo(message: Message):
  args = message.text.split()
  if len(args) != 2:
    await message.answer("⚠️ Введи: `/promo КОД`")
    return

  res = await db.use_promo_code(message.from_user.id, args[1])
  if res:
    await message.answer(f"🎉 Промокод активирован! Получено: +{res}💰")
  else:
    await message.answer("❌ Промокод не существует или уже активирован!")


@router.callback_query(F.data == "promo")
async def promo_callback(callback: CallbackQuery):
  await callback.message.edit_text(
      "🎟️ Для активации промокода напиши:\n`/promo ВАШ_КОД`",
      reply_markup=main_menu_kb(),
  )
  await callback.answer()


# === ПЕРЕДАЧА ДЕНЕГ МЕЖДУ ИГРОКАМИ ===
@router.message(Command("pay"))
@router.message(
    F.reply_to_message
    & F.text.lower().startswith(("передать", "pay", "дать", "перевод"))
)
async def transfer_money(message: Message):
  if not message.reply_to_message:
    await message.answer("⚠️ Ответь на сообщение игрока с командой `/pay 100`!")
    return

  sender_id = message.from_user.id
  target = message.reply_to_message.from_user

  if target.is_bot or target.id == sender_id:
    await message.answer("❌ Нельзя переводить деньги ботам или самому себе!")
    return

  words = message.text.split()
  amount = next((int(w) for w in words if w.isdigit()), None)

  if not amount or amount <= 0:
    await message.answer("⚠️ Укажи корректную сумму числом!")
    return

  sender = await db.get_user(sender_id)
  recipient = await db.get_user(target.id)

  if not recipient:
    await message.answer("❌ Этот игрок еще не запускал бота!")
    return

  if sender["balance"] < amount:
    await message.answer(f"❌ Недостаточно денег на балансе ({sender['balance']}💰)!")
    return

  await db.update_balance(sender_id, -amount)
  await db.update_balance(target.id, amount)

  await message.answer(
      f"💸 <b>Перевод выполнен!</b>\n\n"
      f"От: {message.from_user.full_name}\n"
      f"Кому: {target.full_name}\n"
      f"Сумма: <b>{amount}💰</b>"
  )


async def main():
  await db.init_db()
  await dp.start_polling(bot)


if __name__ == "__main__":
  asyncio.run(main())
