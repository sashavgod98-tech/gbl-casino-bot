import asyncio
import aiosqlite

async def check():
    async with aiosqlite.connect("casino_bot.db") as db:
        cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = await cursor.fetchall()
        print("📋 Таблицы в базе данных:")
        for t in tables:
            print(f"  - {t[0]}")

asyncio.run(check())