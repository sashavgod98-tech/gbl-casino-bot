import asyncio
import aiosqlite
import uuid

async def migrate():
    async with aiosqlite.connect("casino_bot.db") as db:
        # РџСЂРѕРІРµСЂСЏРµРј СЃСѓС‰РµСЃС‚РІСѓСЋС‰РёРµ РєРѕР»РѕРЅРєРё
        cursor = await db.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in await cursor.fetchall()]
        
        # Р”РѕР±Р°РІР»СЏРµРј ref_code, РµСЃР»Рё РЅРµС‚
        if 'ref_code' not in columns:
            await db.execute("ALTER TABLE users ADD COLUMN ref_code TEXT DEFAULT NULL")
            print("вњ… Р”РѕР±Р°РІР»РµРЅР° РєРѕР»РѕРЅРєР° ref_code")
            
        # Р”РѕР±Р°РІР»СЏРµРј referrer_id, РµСЃР»Рё РЅРµС‚
        if 'referrer_id' not in columns:
            await db.execute("ALTER TABLE users ADD COLUMN referrer_id INTEGER DEFAULT NULL")
            print("вњ… Р”РѕР±Р°РІР»РµРЅР° РєРѕР»РѕРЅРєР° referrer_id")
            
        await db.commit()
        
        # Р“РµРЅРµСЂРёСЂСѓРµРј СЂРµС„РµСЂР°Р»СЊРЅС‹Рµ РєРѕРґС‹ РґР»СЏ СЃС‚Р°СЂС‹С… РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№
        cursor = await db.execute("SELECT tg_id FROM users WHERE ref_code IS NULL")
        old_users = await cursor.fetchall()
        
        for user in old_users:
            tg_id = user[0]
            new_code = str(uuid.uuid4())[:8].upper()
            await db.execute("UPDATE users SET ref_code = ? WHERE tg_id = ?", (new_code, tg_id))
            
        await db.commit()
        print(f"вњ… РЎРіРµРЅРµСЂРёСЂРѕРІР°РЅС‹ СЂРµС„РµСЂР°Р»СЊРЅС‹Рµ РєРѕРґС‹ РґР»СЏ {len(old_users)} СЃС‚Р°СЂС‹С… РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№")
        print("рџЋ‰ РњРёРіСЂР°С†РёСЏ Р·Р°РІРµСЂС€РµРЅР°! РўРµРїРµСЂСЊ РјРѕР¶РЅРѕ Р·Р°РїСѓСЃРєР°С‚СЊ Р±РѕС‚Р°.")

asyncio.run(migrate())
