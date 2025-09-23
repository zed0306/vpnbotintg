import asyncio
from os import getenv

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.registration import router as reg_router
from app.database.models import Base, engine
from app.database import requests as rq
from app.handlers import router

# ======= Токен бота =======
BOT_TOKEN = "8431106484:AAHL8-PJHItqUINV1R0s5vtYMemPwvI8l3A"

async def main():
    try:
        # 1️⃣ Создаём таблицы базы данных (если их нет)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # 2️⃣ Инициализация пакетов подписки
        await rq.init_subscription_plans()

        # 3️⃣ Инициализация бота и диспетчера
        bot = Bot(
            token=BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        
        dp = Dispatcher()

        # 4️⃣ Подключаем роутеры
        dp.include_router(router)
        dp.include_router(reg_router)

        # 5️⃣ Запуск polling
        print("✅ Бот запущен с поддержкой Telegram Stars...")
        print(f"🤖 Токен бота: {BOT_TOKEN[:10]}...")
        
        await dp.start_polling(bot)

    except Exception as e:
        print(f"❌ Ошибка при запуске: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("⏹️ Бот выключен")