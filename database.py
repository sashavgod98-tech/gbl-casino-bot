import uuid
from datetime import datetime, timedelta

import aiosqlite

DB_NAME = "casino_bot.db"
DAILY_BONUS = 2500
DAILY_COOLDOWN_HOURS = 24
REFERRAL_BONUS_INVITER = 1000
REFERRAL_BONUS_NEWBIE = 500

BOT_USERNAME = "gbl_games_bot"


class Database:
    def __init__(self, db_name: str = DB_NAME):
        self.db_name = db_name

    async def init_db(self):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    tg_id INTEGER PRIMARY KEY,
                    username TEXT,
                    balance INTEGER DEFAULT 1000,
                    total_won INTEGER DEFAULT 0,
                    total_spent INTEGER DEFAULT 0,
                    inventory_value INTEGER DEFAULT 0,
                    last_daily TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ref_code TEXT DEFAULT NULL,
                    referrer_id INTEGER DEFAULT NULL,
                    prefix TEXT DEFAULT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS inventory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    item_name TEXT,
                    item_rarity TEXT,
                    item_price INTEGER
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS promo_codes (
                    code TEXT PRIMARY KEY,
                    reward INTEGER,
                    max_uses INTEGER DEFAULT 1,
                    current_uses INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS used_promos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    promo_code TEXT,
                    used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS chats (
                    chat_id INTEGER PRIMARY KEY,
                    type TEXT
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS user_businesses (
                    user_id INTEGER,
                    business_key TEXT,
                    purchased_at TEXT,
                    last_collect TEXT,
                    PRIMARY KEY (user_id, business_key)
                )
                """
            )
            await db.commit()

            # Мягкая миграция: добавляем недостающие колонки на случай старой БД
            cursor = await db.execute("PRAGMA table_info(users)")
            columns = [row[1] for row in await cursor.fetchall()]

            if "prefix" not in columns:
                await db.execute("ALTER TABLE users ADD COLUMN prefix TEXT DEFAULT NULL")
            if "ref_code" not in columns:
                await db.execute("ALTER TABLE users ADD COLUMN ref_code TEXT DEFAULT NULL")
            if "referrer_id" not in columns:
                await db.execute("ALTER TABLE users ADD COLUMN referrer_id INTEGER DEFAULT NULL")

            await db.commit()

            # Генерируем реферальные коды для пользователей, у которых их нет
            cursor = await db.execute("SELECT tg_id FROM users WHERE ref_code IS NULL")
            old_users = await cursor.fetchall()
            for (tg_id,) in old_users:
                await db.execute(
                    "UPDATE users SET ref_code = ? WHERE tg_id = ?",
                    (str(uuid.uuid4())[:8].upper(), tg_id),
                )
            await db.commit()

    # === ПОЛЬЗОВАТЕЛИ ===
    async def get_user(self, tg_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def create_user(self, tg_id: int, username: str):
        ref_code = str(uuid.uuid4())[:8].upper()
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                "INSERT OR IGNORE INTO users (tg_id, username, ref_code) VALUES (?, ?, ?)",
                (tg_id, username, ref_code),
            )
            await db.commit()

    async def update_user_info(self, tg_id: int, username: str):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                "UPDATE users SET username = ? WHERE tg_id = ?", (username, tg_id)
            )
            await db.commit()

    async def update_balance(self, tg_id: int, amount: int):
        async with aiosqlite.connect(self.db_name) as db:
            if amount >= 0:
                await db.execute(
                    "UPDATE users SET balance = balance + ?, total_won = total_won + ? WHERE tg_id = ?",
                    (amount, amount, tg_id),
                )
            else:
                await db.execute(
                    "UPDATE users SET balance = balance + ?, total_spent = total_spent + ? WHERE tg_id = ?",
                    (amount, -amount, tg_id),
                )
            await db.commit()

    async def set_prefix(self, tg_id: int, prefix: str):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                "UPDATE users SET prefix = ? WHERE tg_id = ?", (prefix, tg_id)
            )
            await db.commit()

    async def get_user_rank(self, tg_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute(
                """
                SELECT COUNT(*) + 1 FROM users
                WHERE balance > (SELECT balance FROM users WHERE tg_id = ?)
                """,
                (tg_id,),
            )
            row = await cursor.fetchone()
            return row[0] if row else None

    async def get_top_users(self, top_type: str, limit: int = 10):
        column_map = {
            "balance": "balance",
            "won": "total_won",
            "spent": "total_spent",
            "inventory": "inventory_value",
        }
        column = column_map.get(top_type, "balance")

        async with aiosqlite.connect(self.db_name) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                f"SELECT tg_id, username, prefix, {column} AS value FROM users "
                f"ORDER BY {column} DESC LIMIT ?",
                (limit,),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # === РЕФЕРАЛЬНАЯ СИСТЕМА ===
    async def get_referral_link(self, tg_id: int) -> str:
        user = await self.get_user(tg_id)
        ref_code = user.get("ref_code") if user else None

        if not ref_code:
            ref_code = str(uuid.uuid4())[:8].upper()
            async with aiosqlite.connect(self.db_name) as db:
                await db.execute(
                    "UPDATE users SET ref_code = ? WHERE tg_id = ?", (ref_code, tg_id)
                )
                await db.commit()

        return f"https://t.me/{BOT_USERNAME}?start=ref_{ref_code}"

    async def apply_referral(self, tg_id: int, ref_code: str):
        """Привязывает нового пользователя к пригласившему и начисляет бонусы.
        Возвращает id реферера при успехе, иначе None."""
        async with aiosqlite.connect(self.db_name) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT tg_id, referrer_id FROM users WHERE tg_id = ?", (tg_id,)
            )
            user_row = await cursor.fetchone()
            if not user_row or user_row["referrer_id"] is not None:
                return None  # уже привязан к рефереру

            cursor = await db.execute(
                "SELECT tg_id FROM users WHERE ref_code = ?", (ref_code,)
            )
            referrer_row = await cursor.fetchone()
            if not referrer_row or referrer_row["tg_id"] == tg_id:
                return None

            referrer_id = referrer_row["tg_id"]

            await db.execute(
                "UPDATE users SET referrer_id = ? WHERE tg_id = ?", (referrer_id, tg_id)
            )
            await db.execute(
                "UPDATE users SET balance = balance + ? WHERE tg_id = ?",
                (REFERRAL_BONUS_INVITER, referrer_id),
            )
            await db.execute(
                "UPDATE users SET balance = balance + ? WHERE tg_id = ?",
                (REFERRAL_BONUS_NEWBIE, tg_id),
            )
            await db.commit()
            return referrer_id

    # === ЧАТЫ (для авторассылки рекламы) ===
    async def register_chat(self, chat_id: int, chat_type: str):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                "INSERT OR REPLACE INTO chats (chat_id, type) VALUES (?, ?)",
                (chat_id, chat_type),
            )
            await db.commit()

    async def get_all_chats(self):
        async with aiosqlite.connect(self.db_name) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT chat_id, type FROM chats")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # === ЕЖЕДНЕВНЫЙ БОНУС ===
    async def can_claim_daily(self, tg_id: int) -> bool:
        user = await self.get_user(tg_id)
        if not user or not user.get("last_daily"):
            return True
        try:
            last = datetime.fromisoformat(user["last_daily"])
        except ValueError:
            return True
        return datetime.utcnow() - last >= timedelta(hours=DAILY_COOLDOWN_HOURS)

    async def claim_daily(self, tg_id: int):
        now = datetime.utcnow().isoformat()
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                "UPDATE users SET balance = balance + ?, last_daily = ? WHERE tg_id = ?",
                (DAILY_BONUS, now, tg_id),
            )
            await db.commit()

    # === ПРОМОКОДЫ ===
    async def add_promo_code(self, code: str, reward: int, limit: int):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                """
                INSERT INTO promo_codes (code, reward, max_uses, current_uses, is_active)
                VALUES (?, ?, ?, 0, 1)
                ON CONFLICT(code) DO UPDATE SET
                    reward = excluded.reward,
                    max_uses = excluded.max_uses,
                    is_active = 1
                """,
                (code, reward, limit),
            )
            await db.commit()

    async def use_promo_code(self, tg_id: int, code: str):
        async with aiosqlite.connect(self.db_name) as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute(
                "SELECT * FROM promo_codes WHERE code = ?", (code,)
            )
            promo = await cursor.fetchone()
            if not promo or not promo["is_active"]:
                return None
            if promo["current_uses"] >= promo["max_uses"]:
                return None

            cursor = await db.execute(
                "SELECT 1 FROM used_promos WHERE user_id = ? AND promo_code = ?",
                (tg_id, code),
            )
            already_used = await cursor.fetchone()
            if already_used:
                return None

            await db.execute(
                "UPDATE promo_codes SET current_uses = current_uses + 1 WHERE code = ?",
                (code,),
            )
            await db.execute(
                "INSERT INTO used_promos (user_id, promo_code) VALUES (?, ?)",
                (tg_id, code),
            )
            await db.execute(
                "UPDATE users SET balance = balance + ? WHERE tg_id = ?",
                (promo["reward"], tg_id),
            )
            await db.commit()
            return promo["reward"]

    # === ИНВЕНТАРЬ ===
    async def add_item_to_inventory(self, user_id: int, item_name: str, item_rarity: str, item_price: int):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                "INSERT INTO inventory (user_id, item_name, item_rarity, item_price) VALUES (?, ?, ?, ?)",
                (user_id, item_name, item_rarity, item_price),
            )
            await db.execute(
                "UPDATE users SET inventory_value = inventory_value + ? WHERE tg_id = ?",
                (item_price, user_id),
            )
            await db.commit()

    async def get_inventory(self, user_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id, item_name, item_rarity, item_price FROM inventory WHERE user_id = ?",
                (user_id,),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def sell_all_items(self, user_id: int) -> int:
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute(
                "SELECT COALESCE(SUM(item_price), 0) FROM inventory WHERE user_id = ?",
                (user_id,),
            )
            total = (await cursor.fetchone())[0]

            if total:
                await db.execute("DELETE FROM inventory WHERE user_id = ?", (user_id,))
                await db.execute(
                    "UPDATE users SET balance = balance + ?, inventory_value = 0 WHERE tg_id = ?",
                    (total, user_id),
                )
                await db.commit()

            return total

    # === БИЗНЕСЫ (ПАССИВНЫЙ ДОХОД) ===
    async def buy_business(self, user_id: int, key: str) -> bool:
        """Покупает бизнес, если у пользователя его ещё нет. True — успех."""
        now = datetime.utcnow().isoformat()
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute(
                "SELECT 1 FROM user_businesses WHERE user_id = ? AND business_key = ?",
                (user_id, key),
            )
            if await cursor.fetchone():
                return False
            await db.execute(
                "INSERT INTO user_businesses (user_id, business_key, purchased_at, last_collect) "
                "VALUES (?, ?, ?, ?)",
                (user_id, key, now, now),
            )
            await db.commit()
            return True

    async def get_user_businesses(self, user_id: int) -> dict:
        """Возвращает {business_key: last_collect_iso} для всех бизнесов пользователя."""
        async with aiosqlite.connect(self.db_name) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT business_key, last_collect FROM user_businesses WHERE user_id = ?",
                (user_id,),
            )
            rows = await cursor.fetchall()
            return {row["business_key"]: row["last_collect"] for row in rows}

    async def get_pending_business_income(self, user_id: int, key: str, hourly_income: int, cap_hours: float) -> int:
        """Считает накопленный, но ещё не собранный доход бизнеса (не списывает)."""
        businesses = await self.get_user_businesses(user_id)
        last_collect = businesses.get(key)
        if not last_collect:
            return 0
        try:
            last = datetime.fromisoformat(last_collect)
        except ValueError:
            return 0
        elapsed_hours = min((datetime.utcnow() - last).total_seconds() / 3600, cap_hours)
        return max(int(elapsed_hours * hourly_income), 0)

    async def collect_business(self, user_id: int, key: str, hourly_income: int, cap_hours: float) -> int:
        """Начисляет накопленный доход бизнеса на баланс и сбрасывает таймер. Возвращает сумму."""
        async with aiosqlite.connect(self.db_name) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT last_collect FROM user_businesses WHERE user_id = ? AND business_key = ?",
                (user_id, key),
            )
            row = await cursor.fetchone()
            if not row:
                return 0

            try:
                last = datetime.fromisoformat(row["last_collect"])
            except (ValueError, TypeError):
                last = datetime.utcnow()

            elapsed_hours = min((datetime.utcnow() - last).total_seconds() / 3600, cap_hours)
            income = max(int(elapsed_hours * hourly_income), 0)
            if income <= 0:
                return 0

            now = datetime.utcnow().isoformat()
            await db.execute(
                "UPDATE user_businesses SET last_collect = ? WHERE user_id = ? AND business_key = ?",
                (now, user_id, key),
            )
            await db.execute(
                "UPDATE users SET balance = balance + ?, total_won = total_won + ? WHERE tg_id = ?",
                (income, income, user_id),
            )
            await db.commit()
            return income


db = Database()
