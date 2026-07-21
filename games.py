import asyncio
import random
import time
from typing import Dict

active_crash_games: Dict[int, dict] = {}
active_duels: Dict[int, dict] = {}
active_bw_games: Dict[int, dict] = {}  # Игра Белое/Черное

duel_id_counter = 1
bw_id_counter = 1


# === КРАШ ===
async def run_crash_game(user_id: int, bet: int, bot, message):
  if user_id in active_crash_games:
    await message.answer("❌ У тебя уже идёт игра Краш!")
    return False

  if random.random() < 0.01:
    crash_point = 1.00
  else:
    r = random.random()
    crash_point = max(1.00, 0.99 / (1 - r))
    crash_point = min(crash_point, 100.0)
  crash_point = round(crash_point, 2)

  game_data = {
      'user_id': user_id,
      'bet': bet,
      'crash_point': crash_point,
      'current_mult': 1.00,
      'cashed_out': False,
      'task': None,
      'message': message,
  }
  active_crash_games[user_id] = game_data
  game_data['task'] = asyncio.create_task(crash_tick(user_id, bot))
  return True


async def crash_tick(user_id: int, bot):
  start = time.time()

  while user_id in active_crash_games:
    game = active_crash_games[user_id]
    if game['cashed_out']:
      break

    elapsed = time.time() - start
    multiplier = round(1.00 * (1.05 ** (elapsed * 2)), 2)

    if multiplier >= game['crash_point']:
      game['cashed_out'] = True
      try:
        from keyboards import main_menu_kb

        await bot.edit_message_text(
            chat_id=game['message'].chat.id,
            message_id=game['message'].message_id,
            text=(
                f"💥 <b>КРАШ на {game['crash_point']}x!</b>\n"
                f"Ты не успел забрать и потерял {game['bet']}💰"
            ),
            parse_mode="HTML",
            reply_markup=main_menu_kb(),
        )
      except Exception:
        pass

      if user_id in active_crash_games:
        del active_crash_games[user_id]
      break

    game['current_mult'] = multiplier
    try:
      from keyboards import crash_kb

      await bot.edit_message_text(
          chat_id=game['message'].chat.id,
          message_id=game['message'].message_id,
          text=(
              f"📈 <b>КРАШ</b>\n\n"
              f"Множитель: <b>{multiplier}x</b>\n"
              f"Твой выигрыш: <b>{int(game['bet'] * multiplier)}💰</b>\n"
              f"Ставка: <b>{game['bet']}💰</b>\n\n"
              f"⏰ Забирай, пока не поздно!"
          ),
          parse_mode="HTML",
          reply_markup=crash_kb("playing"),
      )
    except Exception:
      pass

    await asyncio.sleep(0.5)


def cashout_crash(user_id: int):
  if user_id not in active_crash_games:
    return None
  game = active_crash_games[user_id]
  if game['cashed_out']:
    return None
  game['cashed_out'] = True
  if game['task']:
    game['task'].cancel()
  win_amount = int(game['bet'] * game['current_mult'])
  del active_crash_games[user_id]
  return win_amount


# === ДУЭЛИ МОНЕТКА ===
def create_duel(creator_id: int, bet: int) -> int:
  global duel_id_counter
  duel_id = duel_id_counter
  duel_id_counter += 1
  active_duels[duel_id] = {
      'id': duel_id,
      'creator_id': creator_id,
      'challenger_id': None,
      'bet': bet,
      'creator_choice': random.choice(['орел', 'решка']),
      'status': 'waiting',
  }
  return duel_id


def join_duel(duel_id: int, challenger_id: int):
  if duel_id not in active_duels:
    return None
  duel = active_duels[duel_id]
  if duel['status'] != 'waiting':
    return None
  if duel['creator_id'] == challenger_id:
    return None
  duel['challenger_id'] = challenger_id
  duel['status'] = 'playing'
  return duel


def resolve_duel(duel_id: int) -> dict:
  duel = active_duels[duel_id]
  result = random.choice(['орел', 'решка'])
  creator_wins = duel['creator_choice'] == result
  winner_id = duel['creator_id'] if creator_wins else duel['challenger_id']
  loser_id = duel['challenger_id'] if creator_wins else duel['creator_id']
  commission = int(duel['bet'] * 2 * 0.05)
  prize = duel['bet'] * 2 - commission
  del active_duels[duel_id]
  return {
      'winner_id': winner_id,
      'loser_id': loser_id,
      'prize': prize,
      'commission': commission,
      'result': result,
      'creator_choice': duel['creator_choice'],
      'bet': duel['bet'],
  }


def get_waiting_duels() -> list:
  return [d for d in active_duels.values() if d['status'] == 'waiting']


# === ИГРА "БЕЛОЕ ИЛИ ЧЁРНОЕ" ===
def create_bw_game(creator_id: int, bet: int, secret_choice: str) -> int:
  """secret_choice: 'white' или 'black'"""
  global bw_id_counter
  game_id = bw_id_counter
  bw_id_counter += 1
  active_bw_games[game_id] = {
      'id': game_id,
      'creator_id': creator_id,
      'challenger_id': None,
      'bet': bet,
      'secret_choice': secret_choice,
      'status': 'waiting',
  }
  return game_id


def join_bw_game(game_id: int, challenger_id: int, guess_choice: str):
  if game_id not in active_bw_games:
    return None
  game = active_bw_games[game_id]
  if game['status'] != 'waiting' or game['creator_id'] == challenger_id:
    return None

  game['challenger_id'] = challenger_id
  game['status'] = 'finished'

  # Если соперник отгадал то, что загадал создатель — выиграл соперник.
  # Если не отгадал — выиграл создатель!
  challenger_won = guess_choice == game['secret_choice']
  winner_id = challenger_id if challenger_won else game['creator_id']
  loser_id = game['creator_id'] if challenger_won else challenger_id

  commission = int(game['bet'] * 2 * 0.05)
  prize = game['bet'] * 2 - commission

  secret_name = "⚪ БЕЛОЕ" if game['secret_choice'] == 'white' else "⚫ ЧЁРНОЕ"
  guess_name = "⚪ БЕЛОЕ" if guess_choice == 'white' else "⚫ ЧЁРНОЕ"

  del active_bw_games[game_id]

  return {
      'winner_id': winner_id,
      'loser_id': loser_id,
      'prize': prize,
      'commission': commission,
      'secret_choice': secret_name,
      'guess_choice': guess_name,
      'bet': game['bet'],
  }


def get_waiting_bw_games() -> list:
  return [g for g in active_bw_games.values() if g['status'] == 'waiting']
