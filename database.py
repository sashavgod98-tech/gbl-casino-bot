import aiosqlite

class Database:
    def __init__(self, db_path="casino.db"):
        self.db_path = db_path

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            # Пользователи
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    balance INTEGER DEFAULT 10000,
                    prefix TEXT DEFAULT '',
                    total_won INTEGER DEFAULT 0,
                    total_spent INTEGER DEFAULT 0,
                    last_daily TIMESTAMP
                )
            """)
            # Инвентарь
            await db.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    item_name TEXT,
                    item_rarity TEXT,
                    item_price INTEGER
                )
            """)
            # Чаты (группы и лс) для рассылки
            await db.execute("""
                CREATE TABLE IF NOT EXISTS chats (
                    chat_id INTEGER PRIMARY KEY,
                    type TEXT
                )
            """)
            # Промокоды
            await db.execute("""
                CREATE TABLE IF NOT EXISTS promo_codes (
                    code TEXT PRIMARY KEY,
                    reward INTEGER,
                    uses_left INTEGER
                )
            """)
            # Использование промокодов
            await db.execute("""
                CREATE TABLE IF NOT EXISTS promo_uses (
                    user_id INTEGER,
                    code TEXT,
                    PRIMARY KEY (user_id, code)
                )
            """)
            await db.commit()

    async def register_chat(self, chat_id: int, chat_type: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO chats (chat_id, type) VALUES (?, ?)",
                (chat_id, chat_type)
            )
            await db.commit()

    async def get_all_chats(self):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT chat_id, type FROM chats") as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_user(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                user_dict = dict(row)
                
                # Подсчет стоимости инвентаря
                async with db.execute("SELECT SUM(item_price) FROM inventory WHERE user_id = ?", (user_id,)) as inv_cur:
                    inv_val = await inv_cur.fetchone()
                    user_dict['inventory_value'] = inv_val[0] if inv_val[0] else 0
                    
                return user_dict

    async def create_user(self, user_id: int, username: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
                (user_id, username)
            )
            await db.commit()

    async def update_balance(self, user_id: int, amount: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (amount, user_id)
            )
            await db.commit()

    async def set_prefix(self, user_id: int, prefix: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET prefix = ? WHERE user_id = ?",
                (prefix, user_id)
            )
            await db.commit()

    async def get_referral_link(self, user_id: int):
        return f"https://t.me/gbl_games_bot?start={user_id}"

    async def get_user_rank(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT user_id, 
                       RANK() OVER (ORDER BY balance DESC) as rank 
                FROM users
            """) as cursor:
                rows = await cursor.fetchall()
                for uid, rank in rows:
                    if uid == user_id:
                        return rank
        return None

    async def can_claim_daily(self, user_id: int):
        # Простая заглушка/проверка 24ч
        return True

    async def claim_daily(self, user_id: int):
        await self.update_balance(user_id, 2500)

    async def add_item(self, user_id: int, name: str, rarity: str, price: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO inventory (user_id, item_name, item_rarity, item_price) VALUES (?, ?, ?, ?)",
                (user_id, name, rarity, price)
            )
            await db.commit()

    async def get_inventory(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT id, item_name, item_rarity, item_price FROM inventory WHERE user_id = ?", (user_id,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def sell_item(self, item_id: int, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT item_price FROM inventory WHERE id = ? AND user_id = ?", (item_id, user_id)) as cursor:
                row = await cursor.fetchone()
                if row:
                    price = row[0]
                    await db.execute("DELETE FROM inventory WHERE id = ?", (item_id,))
                    await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (price, user_id))
                    await db.commit()
                    return price
        return 0

    async def sell_all_items(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT SUM(item_price) FROM inventory WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                total = row[0] if row and row[0] else 0
                if total > 0:
                    await db.execute("DELETE FROM inventory WHERE user_id = ?", (user_id,))
                    await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (total, user_id))
                    await db.commit()
                    return total
        return 0

    async def get_top_balance(self, limit: int = 10):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT username, prefix, balance FROM users ORDER BY balance DESC LIMIT ?", (limit,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_top_inventory(self, limit: int = 10):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT u.username, u.prefix, COALESCE(SUM(i.item_price), 0) as inventory_value 
                FROM users u 
                LEFT JOIN inventory i ON u.user_id = i.user_id 
                GROUP BY u.user_id 
                ORDER BY inventory_value DESC LIMIT ?
            """, (limit,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def add_promo_code(self, code: str, reward: int, limit: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO promo_codes (code, reward, uses_left) VALUES (?, ?, ?)",
                (code, reward, limit)
            )
            await db.commit()

    async def use_promo_code(self, user_id: int, code: str):
        code = code.upper()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT reward, uses_left FROM promo_codes WHERE code = ?", (code,)) as cursor:
                promo = await cursor.fetchone()
                if not promo or promo[1] <= 0:
                    return None

            async with db.execute("SELECT 1 FROM promo_uses WHERE user_id = ? AND code = ?", (user_id, code)) as cursor:
                if await cursor.fetchone():
                    return None

            reward, uses_left = promo
            await db.execute("INSERT INTO promo_uses (user_id, code) VALUES (?, ?)", (user_id, code))
            await db.execute("UPDATE promo_codes SET uses_left = uses_left - 1 WHERE code = ?", (code,))
            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (reward, user_id))
            await db.commit()
            return reward

db = Database()
