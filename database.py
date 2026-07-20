import aiosqlite
from datetime import datetime, timedelta
import uuid

DB_PATH = "casino_bot.db"

class Database:
    def __init__(self):
        self.path = DB_PATH

    async def init_db(self):
        async with aiosqlite.connect(self.path) as db:
            await db.execute('''
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
                    referrer_id INTEGER DEFAULT NULL
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS inventory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    item_name TEXT,
                    item_rarity TEXT,
                    item_price INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users(tg_id)
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS duels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    creator_id INTEGER,
                    challenger_id INTEGER,
                    bet INTEGER,
                    creator_choice TEXT,
                    status TEXT DEFAULT 'waiting',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS promo_codes (
                    code TEXT PRIMARY KEY,
                    reward INTEGER,
                    max_uses INTEGER DEFAULT 1,
                    current_uses INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS used_promos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    promo_code TEXT,
                    used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(tg_id),
                    FOREIGN KEY (promo_code) REFERENCES promo_codes(code)
                )
            ''')
            await db.commit()
            print("✅ База данных инициализирована")

    async def get_user(self, tg_id: int):
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('SELECT * FROM users WHERE tg_id = ?', (tg_id,))
            return await cursor.fetchone()

    async def create_user(self, tg_id: int, username: str):
        ref_code = str(uuid.uuid4())[:8].upper()
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                'INSERT INTO users (tg_id, username, balance, ref_code) VALUES (?, ?, 1000, ?)',
                (tg_id, username, ref_code)
            )
            await db.commit()

    async def update_balance(self, tg_id: int, amount: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                'UPDATE users SET balance = balance + ? WHERE tg_id = ?',
                (amount, tg_id)
            )
            if amount > 0:
                await db.execute(
                    'UPDATE users SET total_won = total_won + ? WHERE tg_id = ?',
                    (amount, tg_id)
                )
            else:
                await db.execute(
                    'UPDATE users SET total_spent = total_spent + ? WHERE tg_id = ?',
                    (abs(amount), tg_id)
                )
            await db.commit()

    async def can_claim_daily(self, tg_id: int) -> bool:
        user = await self.get_user(tg_id)
        if not user or not user['last_daily']:
            return True
        last = datetime.fromisoformat(user['last_daily'])
        return datetime.now() - last > timedelta(hours=24)

    async def claim_daily(self, tg_id: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE users SET last_daily = ?, balance = balance + 500 WHERE tg_id = ?",
                (datetime.now().isoformat(), tg_id)
            )
            await db.commit()

    async def add_item(self, tg_id: int, name: str, rarity: str, price: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                'INSERT INTO inventory (user_id, item_name, item_rarity, item_price) VALUES (?, ?, ?, ?)',
                (tg_id, name, rarity, price)
            )
            await db.execute(
                'UPDATE users SET inventory_value = inventory_value + ? WHERE tg_id = ?',
                (price, tg_id)
            )
            await db.commit()

    async def get_inventory(self, tg_id: int):
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                'SELECT * FROM inventory WHERE user_id = ? ORDER BY item_price DESC',
                (tg_id,)
            )
            return await cursor.fetchall()

    async def sell_item(self, item_id: int, tg_id: int) -> int:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                'SELECT item_price FROM inventory WHERE id = ? AND user_id = ?',
                (item_id, tg_id)
            )
            item = await cursor.fetchone()
            if not item:
                return 0
            price = item['item_price']
            await db.execute('DELETE FROM inventory WHERE id = ?', (item_id,))
            await db.execute(
                'UPDATE users SET balance = balance + ?, inventory_value = inventory_value - ? WHERE tg_id = ?',
                (price, price, tg_id)
            )
            await db.commit()
            return price

    async def get_top_balance(self, limit: int = 10):
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                'SELECT * FROM users ORDER BY balance DESC LIMIT ?', (limit,)
            )
            return await cursor.fetchall()

    async def get_top_inventory(self, limit: int = 10):
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                'SELECT * FROM users ORDER BY inventory_value DESC LIMIT ?', (limit,)
            )
            return await cursor.fetchall()

    async def add_promo_code(self, code: str, reward: int, max_uses: int = 1):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                'INSERT OR REPLACE INTO promo_codes (code, reward, max_uses) VALUES (?, ?, ?)',
                (code.upper(), reward, max_uses)
            )
            await db.commit()

    async def use_promo_code(self, user_id: int, code: str):
        code = code.upper()
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                'SELECT id FROM used_promos WHERE user_id = ? AND promo_code = ?',
                (user_id, code)
            )
            if await cursor.fetchone():
                return False
            cursor = await db.execute(
                'SELECT * FROM promo_codes WHERE code = ? AND is_active = 1 AND current_uses < max_uses',
                (code,)
            )
            promo = await cursor.fetchone()
            if not promo:
                return False
            await db.execute(
                'UPDATE users SET balance = balance + ? WHERE tg_id = ?',
                (promo['reward'], user_id)
            )
            await db.execute(
                'UPDATE promo_codes SET current_uses = current_uses + 1 WHERE code = ?',
                (code,)
            )
            await db.execute(
                'INSERT INTO used_promos (user_id, promo_code) VALUES (?, ?)',
                (user_id, code)
            )
            await db.commit()
            return promo['reward']

    async def get_user_by_ref_code(self, ref_code: str):
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                'SELECT * FROM users WHERE ref_code = ?',
                (ref_code.upper(),)
            )
            return await cursor.fetchone()

    async def add_referral(self, referrer_id: int, referred_id: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                'UPDATE users SET referrer_id = ? WHERE tg_id = ?',
                (referrer_id, referred_id)
            )
            await db.commit()

    async def get_referral_link(self, tg_id: int):
        user = await self.get_user(tg_id)
        if not user or not user['ref_code']:
            return None
        return f"https://t.me/gbl_games_bot?start={user['ref_code']}"

    async def get_user_rank(self, tg_id: int):
        users = await self.get_top_balance(100)
        for i, user in enumerate(users, 1):
            if user['tg_id'] == tg_id:
                return i
        return None

db = Database()