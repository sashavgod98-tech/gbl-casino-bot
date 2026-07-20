import asyncio
from database import db

async def add_promos():
    await db.add_promo_code('ADMIN5000', 5000, 1)
    await db.add_promo_code('WELCOME', 1000, 100)
    await db.add_promo_code('GIFT500', 500, 50)
    await db.add_promo_code('TEST100', 100, 10)
    print("✅ Промокоды добавлены!")

asyncio.run(add_promos())