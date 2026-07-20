import asyncio
import aiosqlite
import uuid

async def migrate():
    async with aiosqlite.connect("casino_bot.db") as db:
        # Проверяем существующие колонки
        cursor = await db.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in await cursor.fetchall()]
        
        # Добавляем ref_code, если нет
        if 'ref_code' not in columns:
            await db.execute("ALTER TABLE users ADD COLUMN ref_code TEXT DEFAULT NULL")
            print("✅ Добавлена колонка ref_code")
            
        # Добавляем referrer_id, если нет
        if 'referrer_id' not in columns:
            await db.execute("ALTER TABLE users ADD COLUMN referrer_id INTEGER DEFAULT NULL")
            print("✅ Добавлена колонка referrer_id")
            
        await db.commit()
        
        # Генерируем реферальные коды для старых пользователей
        cursor = await db.execute("SELECT tg_id FROM users WHERE ref_code IS NULL")
        old_users = await cursor.fetchall()
        
        for user in old_users:
            tg_id = user[0]
            new_code = str(uuid.uuid4())[:8].upper()
            await db.execute("UPDATE users SET ref_code = ? WHERE tg_id = ?", (new_code, tg_id))
            
        await db.commit()
        print(f"✅ Сгенерированы реферальные коды для {len(old_users)} старых пользователей")
        print("🎉 Миграция завершена! Теперь можно запускать бота.")

asyncio.run(migrate())