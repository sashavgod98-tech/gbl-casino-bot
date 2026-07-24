import asyncio
import random

active_crash_games = {}
active_bw_games = {}
active_duels = {}
active_dice_games = {}
active_mines_games = {}

COMMISSION = 0.95  # 5% комиссия казино на PvP-игры

# === КРАШ ===
async def run_crash_game(user_id: int, bet: int, bot, message):
    multiplier = 1.0
    active_crash_games[user_id] = {"bet": bet, "multiplier": multiplier, "cashed_out": False}
    
    crash_point = round(random.uniform(1.1, 5.0), 2)

    while multiplier < crash_point:
        await asyncio.sleep(1.5)
        if user_id not in active_crash_games or active_crash_games[user_id]["cashed_out"]:
            return
        
        multiplier = round(multiplier + 0.2, 2)
        active_crash_games[user_id]["multiplier"] = multiplier
        
        try:
            await message.edit_text(
                f"📈 <b>КРАШ в процессе!</b>\n\n"
                f"Ставка: <b>{bet}💰</b>\n"
                f"Множитель: <b>{multiplier}x</b>\n"
                f"Текущий выигрыш: <b>{int(bet * multiplier)}💰</b>",
                reply_markup=message.reply_markup
            )
        except Exception:
            pass

    if user_id in active_crash_games and not active_crash_games[user_id]["cashed_out"]:
        del active_crash_games[user_id]
        try:
            await message.edit_text(
                f"💥 <b>КРАШ УПАЛ!</b>\n\n"
                f"Множитель остановился на <b>{multiplier}x</b>\n"
                f"Ты не успел забрать ставку и потерял <b>{bet}💰</b>."
            )
        except Exception:
            pass

def cashout_crash(user_id: int):
    if user_id in active_crash_games and not active_crash_games[user_id]["cashed_out"]:
        active_crash_games[user_id]["cashed_out"] = True
        game = active_crash_games.pop(user_id)
        return int(game["bet"] * game["multiplier"])
    return None


# === БЕЛОЕ / ЧЁРНОЕ ===
def create_bw_game(creator_id: int, username_or_bet, bet_or_choice, choice=None):
    game_id = random.randint(1000, 9999)
    if choice is not None:
        username = username_or_bet
        bet = bet_or_choice
    else:
        username = "Игрок"
        bet = username_or_bet
        choice = bet_or_choice

    active_bw_games[game_id] = {
        "id": game_id,
        "creator_id": creator_id,
        "creator_name": username,
        "bet": bet,
        "secret_choice": choice
    }
    return game_id

def get_waiting_bw_games():
    return active_bw_games

def join_bw_game(game_id: int, guesser_id: int, guess: str):
    game = active_bw_games.pop(game_id, None)
    if not game:
        raise ValueError("Game not found")
    
    secret = game["secret_choice"]
    prize = int(game["bet"] * 2 * 0.95)
    
    if guess == secret:
        winner_id, loser_id = guesser_id, game["creator_id"]
    else:
        winner_id, loser_id = game["creator_id"], guesser_id

    return {
        "winner_id": winner_id,
        "loser_id": loser_id,
        "prize": prize,
        "secret_choice": "⚪ БЕЛОЕ" if secret == "white" else "⚫ ЧЁРНОЕ",
        "guess_choice": "⚪ БЕЛОЕ" if guess == "white" else "⚫ ЧЁРНОЕ"
    }


# === ДУЭЛИ ===
def create_duel(creator_id: int, username_or_bet, bet=None):
    duel_id = random.randint(1000, 9999)
    if bet is not None:
        username = username_or_bet
    else:
        username = "Игрок"
        bet = username_or_bet

    active_duels[duel_id] = {
        "id": duel_id,
        "creator_id": creator_id,
        "creator_name": username,
        "bet": bet,
        "opponent_id": None,
        "opponent_name": None
    }
    return duel_id

def get_waiting_duels():
    return active_duels

def join_duel(duel_id: int, opponent_id: int, opponent_name="Соперник"):
    """Подключает соперника к дуэли и сразу разыгрывает результат.
    Возвращает словарь с winner_id/loser_id/prize или бросает ValueError."""
    duel = active_duels.pop(duel_id, None)
    if not duel:
        raise ValueError("Duel not found")

    duel["opponent_id"] = opponent_id
    duel["opponent_name"] = opponent_name

    winner_id, loser_id = (
        (duel["creator_id"], duel["opponent_id"])
        if random.choice([True, False])
        else (duel["opponent_id"], duel["creator_id"])
    )
    prize = int(duel["bet"] * 2 * 0.95)

    return {
        "winner_id": winner_id,
        "loser_id": loser_id,
        "prize": prize,
        "result": "Орёл" if random.randint(0, 1) == 1 else "Решка",
    }


    return {
        "winner_id": winner_id,
        "loser_id": loser_id,
        "prize": prize,
        "result": "Орёл" if random.randint(0, 1) == 1 else "Решка",
    }


# === КОСТИ (PvP) ===
def create_dice_game(creator_id: int, username: str, bet: int):
    game_id = random.randint(1000, 9999)
    active_dice_games[game_id] = {
        "id": game_id,
        "creator_id": creator_id,
        "creator_name": username,
        "bet": bet,
    }
    return game_id


def get_waiting_dice_games():
    return active_dice_games


def join_dice_game(game_id: int, opponent_id: int):
    game = active_dice_games.pop(game_id, None)
    if not game:
        raise ValueError("Game not found")

    # Бросаем кубики, при ничьей перебрасываем (до 5 раз)
    creator_roll = opponent_roll = 0
    for _ in range(5):
        creator_roll = random.randint(1, 6)
        opponent_roll = random.randint(1, 6)
        if creator_roll != opponent_roll:
            break

    if creator_roll == opponent_roll:
        winner_id, loser_id = random.choice(
            [(game["creator_id"], opponent_id), (opponent_id, game["creator_id"])]
        )
    elif creator_roll > opponent_roll:
        winner_id, loser_id = game["creator_id"], opponent_id
    else:
        winner_id, loser_id = opponent_id, game["creator_id"]

    prize = int(game["bet"] * 2 * COMMISSION)

    return {
        "winner_id": winner_id,
        "loser_id": loser_id,
        "prize": prize,
        "creator_roll": creator_roll,
        "opponent_roll": opponent_roll,
    }


# === СЛОТЫ ===
SLOT_SYMBOLS = ["🍒", "🍋", "🔔", "⭐", "💎", "7️⃣"]
# Множители за три одинаковых символа
SLOT_MULTIPLIERS = {
    "🍒": 2,
    "🍋": 3,
    "🔔": 5,
    "⭐": 8,
    "💎": 15,
    "7️⃣": 30,
}
# Небольшой утешительный множитель за 2 одинаковых символа подряд
SLOT_PAIR_MULTIPLIER = 1.2


def roll_slots(bet: int):
    reels = [random.choice(SLOT_SYMBOLS) for _ in range(3)]

    if reels[0] == reels[1] == reels[2]:
        multiplier = SLOT_MULTIPLIERS[reels[0]]
    elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
        multiplier = SLOT_PAIR_MULTIPLIER
    else:
        multiplier = 0

    win = int(bet * multiplier)
    return {"reels": reels, "multiplier": multiplier, "win": win}


# === КАМЕНЬ-НОЖНИЦЫ-БУМАГА (против бота) ===
RPS_CHOICES = {"rock": "🪨 Камень", "paper": "📄 Бумага", "scissors": "✂️ Ножницы"}
RPS_BEATS = {"rock": "scissors", "paper": "rock", "scissors": "paper"}


def rps_play(user_choice: str, bet: int):
    bot_choice = random.choice(list(RPS_CHOICES.keys()))

    if user_choice == bot_choice:
        result = "draw"
        win = bet  # возврат ставки
    elif RPS_BEATS[user_choice] == bot_choice:
        result = "win"
        win = int(bet * 2 * COMMISSION)
    else:
        result = "lose"
        win = 0

    return {
        "bot_choice": bot_choice,
        "bot_choice_label": RPS_CHOICES[bot_choice],
        "user_choice_label": RPS_CHOICES[user_choice],
        "result": result,
        "win": win,
    }


# === МИНЫ ===
MINES_GRID_SIZE = 25  # 5x5
# Множитель за одну открытую безопасную клетку в зависимости от кол-ва мин
MINES_STEP_MULTIPLIER = {
    3: 1.12,
    5: 1.25,
    7: 1.45,
    10: 1.9,
}


def create_mines_game(user_id: int, bet: int, mines_count: int):
    mine_positions = set(random.sample(range(MINES_GRID_SIZE), mines_count))
    active_mines_games[user_id] = {
        "bet": bet,
        "mines_count": mines_count,
        "mine_positions": mine_positions,
        "revealed": set(),
        "multiplier": 1.0,
        "finished": False,
    }
    return active_mines_games[user_id]


def get_mines_game(user_id: int):
    return active_mines_games.get(user_id)


def reveal_mines_cell(user_id: int, cell_index: int):
    game = active_mines_games.get(user_id)
    if not game or game["finished"]:
        return None

    if cell_index in game["revealed"]:
        return {"status": "already_open"}

    if cell_index in game["mine_positions"]:
        game["finished"] = True
        return {"status": "mine", "bet": game["bet"]}

    game["revealed"].add(cell_index)
    step = MINES_STEP_MULTIPLIER.get(game["mines_count"], 1.2)
    game["multiplier"] = round(game["multiplier"] * step, 3)
    current_win = int(game["bet"] * game["multiplier"])

    # Если открыты все безопасные клетки — авто-кэшаут
    safe_cells = MINES_GRID_SIZE - game["mines_count"]
    if len(game["revealed"]) >= safe_cells:
        game["finished"] = True
        return {"status": "cleared", "multiplier": game["multiplier"], "win": current_win}

    return {"status": "safe", "multiplier": game["multiplier"], "win": current_win}


def cashout_mines(user_id: int):
    game = active_mines_games.get(user_id)
    if not game or game["finished"] or not game["revealed"]:
        return None

    win = int(game["bet"] * game["multiplier"])
    del active_mines_games[user_id]
    return win


# === РУЛЕТКА (европейская, 0-36) ===
ROULETTE_RED = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}


def spin_roulette():
    """Крутит колесо и возвращает (номер, цвет)."""
    number = random.randint(0, 36)
    if number == 0:
        color = "green"
    elif number in ROULETTE_RED:
        color = "red"
    else:
        color = "black"
    return number, color


def roulette_number_color(number: int) -> str:
    if number == 0:
        return "green"
    return "red" if number in ROULETTE_RED else "black"


def _roulette_dozen(number: int):
    if number == 0:
        return None
    return (number - 1) // 12 + 1


def _roulette_column(number: int):
    if number == 0:
        return None
    mod = number % 3
    return mod if mod != 0 else 3


def calc_roulette_multiplier(category: str, outcome: str, number: int, color: str) -> int:
    """Возвращает множитель ставки (полная сумма к зачислению = bet * multiplier).
    0 — ставка проиграна."""
    if category == "number":
        return 36 if int(outcome) == number else 0

    # Зеро — все внешние ставки (цвет/чёт-нечет/дюжина/столбец/диапазон) проигрывают
    if number == 0:
        return 0

    if category == "color":
        return 2 if outcome == color else 0
    if category == "dozen":
        return 3 if _roulette_dozen(number) == int(outcome) else 0
    if category == "column":
        return 3 if _roulette_column(number) == int(outcome) else 0
    if category == "evenodd":
        is_even = number % 2 == 0
        return 2 if (outcome == "even") == is_even else 0
    if category == "highlow":
        if outcome == "low":
            return 2 if number <= 18 else 0
        return 2 if number >= 19 else 0
    return 0


def format_roulette_outcome(category: str, outcome: str) -> str:
    """Человекочитаемое название выбранной ставки."""
    if category == "color":
        return "🔴 Красное" if outcome == "red" else "⚫ Чёрное"
    if category == "dozen":
        ranges = {"1": "1-12", "2": "13-24", "3": "25-36"}
        return f"{outcome}-я дюжина ({ranges.get(outcome, '')})"
    if category == "column":
        return f"{outcome}-й столбец"
    if category == "evenodd":
        return "Чётное" if outcome == "even" else "Нечётное"
    if category == "highlow":
        return "1-18" if outcome == "low" else "19-36"
    if category == "number":
        return f"число {outcome}"
    return outcome


def roulette_number_emoji(number: int) -> str:
    color = roulette_number_color(number)
    return {"red": "🔴", "black": "⚫", "green": "🟢"}[color]
