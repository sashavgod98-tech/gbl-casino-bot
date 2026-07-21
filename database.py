from datetime import datetime, timedelta
import aiosqlite


class Database:

    def __init__(self, db_path="casino_bot.db"):
        self.db_path = db_path

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            # 1. Пользователи
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    tg_id INTEGER PRIMARY KEY,
                    username TEXT,
                    balance INTEGER DEFAULT 1000,
                    total_won INTEGER DEFAULT 0,
                    total_spent INTEGER DEFAULT 0,
                    inventory_value INTEGER DEFAULT 0,
                    last_daily TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ref_code TEXT UNIQUE DEFAULT NULL,
                    referrer_id INTEGER DEFAULT NULL,
                    prefix TEXT DEFAULT ''
                )
            """)

            # 2. Инвентарь
            await db.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    item_name TEXT,
                    item_rarity TEXT,
                    item_price INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users(tg_id)
                )
            """)

            # 3. Чаты (для рассылки и авто-рекламы)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS chats (
                    chat_id INTEGER PRIMARY KEY,
                    type TEXT
                )
            """)

            # 4. Промокоды
            await db.execute("""
                CREATE TABLE IF NOT EXISTS promo_codes (
                    code TEXT PRIMARY KEY,
                    reward INTEGER,
                    max_uses INTEGER DEFAULT 1,
                    current_uses INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1
                )
            """)

            # 5. Использованные промокоды
            await db.execute("""
                CREATE TABLE IF NOT EXISTS used_promos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    promo_code TEXT,
                    used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(tg_id),
                    FOREIGN KEY (promo_code) REFERENCES promo_codes(code)
                )
            """)

            # 6. Дуэли
            await db.execute("""
                CREATE TABLE IF NOT EXISTS duels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    creator_id INTEGER,
                    challenger_id INTEGER,
                    bet INTEGER,
                    creator_choice TEXT,
                    status TEXT DEFAULT 'waiting',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Проверка наличия колонки prefix для старых баз
            async with db.execute("PRAGMA table_info(users)") as cursor:
                columns = [row[1] for row in await cursor.fetchall()]
                if "prefix" not in columns:
                    await db.execute(
                        "ALTER TABLE users ADD COLUMN prefix TEXT DEFAULT ''"
                    )

            await db.commit()

    # === РЕГИСТРАЦИЯ И ПОЛУЧЕНИЕ ЧАТОВ ===
    async def register_chat(self, chat_id: int, chat_type: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO chats (chat_id, type) VALUES (?, ?)",
                (chat_id, chat_type),
            )
            await db.commit()

    async def get_all_chats(self):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT chat_id, type FROM chats") as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    # === РАБОТА С ПОЛЬЗОВАТЕЛЯМИ ===
    async def get_user(self, tg_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM users WHERE tg_id = ?", (tg_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                user_dict = dict(row)

                # Подсчет актуальной стоимости инвентаря
                async with db.execute(
                    "SELECT SUM(item_price) FROM inventory WHERE user_id = ?",
                    (tg_id,),
                ) as inv_cur:
                    inv_val = await inv_cur.fetchone()
                    user_dict["inventory_value"] = (
                        inv_val[0] if inv_val[0] else 0
                    )

                return user_dict

    async def create_user(self, tg_id: int, username: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO users (tg_id, username, balance) VALUES"
                " (?, ?, 10000)",
                (tg_id, username),
            )
            await db.commit()

    async def update_balance(self, tg_id: int, amount: int):
        async with aiosqlite.connect(self.db_path) as db:
            if amount > 0:
                await db.execute(
                    "UPDATE users SET balance = balance + ?, total_won ="
                    " total_won + ? WHERE tg_id = ?",
                    (amount, amount, tg_id),
                )
            else:
                await db.execute(
                    "UPDATE users SET balance = balance + ?, total_spent ="
                    " total_spent + ? WHERE tg_id = ?",
                    (amount, abs(amount), tg_id),
                )
            await db.commit()

    async def set_prefix(self, tg_id: int, prefix: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET prefix = ? WHERE tg_id = ?", (prefix, tg_id)
            )
            await db.commit()

    async def get_referral_link(self, tg_id: int):
        return f"https://t.me/gbl_games_bot?start={tg_id}"

    async def get_user_rank(self, tg_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT tg_id, 
                       RANK() OVER (ORDER BY balance DESC) as rank 
                FROM users
            """) as cursor:
                rows = await cursor.fetchall()
                for uid, rank in rows:
                    if uid == tg_id:
                        return rank
        return None

    # === ЕЖЕДНЕВНЫЙ БОНУС С ТАЙМЕРОМ 24 ЧАСА ===
    async def can_claim_daily(self, tg_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT last_daily FROM users WHERE tg_id = ?", (tg_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row or not row[0]:
                    return True

                try:
                    last_daily = datetime.fromisoformat(row[0])
                    return datetime.now() - last_daily >= timedelta(hours=24)
                except ValueError:
                    return True

    async def claim_daily(self, tg_id: int):
        now_str = datetime.now().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET balance = balance + 2500, last_daily = ?"
                " WHERE tg_id = ?",
                (now_str, tg_id),
            )
            await db.commit()

    # === ИНВЕНТАРЬ ===
    async def add_item(self, user_id: int, name: str, rarity: str, price: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO inventory (user_id, item_name, item_rarity,"
                " item_price) VALUES (?, ?, ?, ?)",
                (user_id, name, rarity, price),
            )
            await db.commit()

    async def get_inventory(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT id, item_name, item_rarity, item_price FROM inventory"
                " WHERE user_id = ?",
                (user_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def sell_item(self, item_id: int, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT item_price FROM inventory WHERE id = ? AND user_id = ?",
                (item_id, user_id),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    price = row[0]
                    await db.execute(
                        "DELETE FROM inventory WHERE id = ?", (item_id,)
                    )
                    await db.execute(
                        "UPDATE users SET balance = balance + ? WHERE tg_id ="
                        " ?",
                        (price, user_id),
                    )
                    await db.commit()
                    return price
        return 0

    async def sell_all_items(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT SUM(item_price) FROM inventory WHERE user_id = ?",
                (user_id,),
            ) as cursor:
                row = await cursor.fetchone()
                total = row[0] if row and row[0] else 0
                if total > 0:
                    await db.execute(
                        "DELETE FROM inventory WHERE user_id = ?", (user_id,)
                    )
                    await db.execute(
                        "UPDATE users SET balance = balance + ? WHERE tg_id ="
                        " ?",
                        (total, user_id),
                    )
                    await db.commit()
                    return total
        return 0

    # === ТОПЫ ===
    async def get_top_balance(self, limit: int = 10):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT username, prefix, balance FROM users ORDER BY balance"
                " DESC LIMIT ?",
                (limit,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_top_inventory(self, limit: int = 10):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT u.username, u.prefix, COALESCE(SUM(i.item_price), 0) as inventory_value 
                FROM users u 
                LEFT JOIN inventory i ON u.tg_id = i.user_id 
                GROUP BY u.tg_id 
                ORDER BY inventory_value DESC LIMIT ?
            """,
                (limit,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    # === ПРОМОКОДЫ ===
    async def add_promo_code(self, code: str, reward: int, limit: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO promo_codes (code, reward, max_uses,"
                " current_uses, is_active) VALUES (?, ?, ?, 0, 1)",
                (code, reward, limit),
            )
            await db.commit()

    async def use_promo_code(self, user_id: int, code: str):
        code = code.upper()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT reward, max_uses, current_uses FROM promo_codes WHERE"
                " code = ? AND is_active = 1",
                (code,),
            ) as cursor:
                promo = await cursor.fetchone()
                if not promo:
                    return None

                reward, max_uses, current_uses = promo
                if current_uses >= max_uses:
                    return None

            async with db.execute(
                "SELECT 1 FROM used_promos WHERE user_id = ? AND promo_code ="
                " ?",
                (user_id, code),
            ) as cursor:
                if await cursor.fetchone():
                    return None

            await db.execute(
                "INSERT INTO used_promos (user_id, promo_code) VALUES (?, ?)",
                (user_id, code),
            )
            await db.execute(
                "UPDATE promo_codes SET current_uses = current_uses + 1 WHERE"
                " code = ?",
                (code,),
            )
            await db.execute(
                "UPDATE users SET balance = balance + ? WHERE tg_id = ?",
                (reward, user_id),
            )
            await db.commit()
            return reward


db = Database()
