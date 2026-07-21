import asyncio
import random

active_crash_games = {}
active_bw_games = {}
active_duels = {}

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
    if duel_id in active_duels:
        active_duels[duel_id]["opponent_id"] = opponent_id
        active_duels[duel_id]["opponent_name"] = opponent_name

def resolve_duel(duel_id: int):
    duel = active_duels.pop(duel_id, None)
    if not duel:
        return None

    winner_id = random.choice([duel["creator_id"], duel["opponent_id"]])
    prize = int(duel["bet"] * 2 * 0.95)
    
    if winner_id == duel["creator_id"]:
        w_name, l_name = duel["creator_name"], duel["opponent_name"]
        loser_id = duel["opponent_id"]
    else:
        w_name, l_name = duel["opponent_name"], duel["creator_name"]
        loser_id = duel["creator_id"]

    return {
        "winner_id": winner_id,
        "loser_id": loser_id,
        "prize": prize,
        "result": "Орёл" if random.randint(0, 1) == 1 else "Решка"
    }
