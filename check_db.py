import asyncio
import aiosqlite

async def check():
    async with aiosqlite.connect("casino_bot.db") as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = await cursor.fetchall()
        print("Таблицы в БД:")
        for table in tables:
            print(f"  - {table[0]}")

asyncio.run(check())