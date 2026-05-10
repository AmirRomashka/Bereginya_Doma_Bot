# main.py
import os
import asyncio

# Load environment variables
from dotenv import find_dotenv, load_dotenv
load_dotenv(find_dotenv())
# Импортируйте с другим именем
from database.engine import create_db, drop_db, session_maker
from handlers.user_private.user_router import UserRouter
from handlers.admin_router.admin_router import AdminRouter 
from handlers.channel_router.channel_router import ChannelRouter
from middlewares.db import DataBaseSession

from aiogram import Dispatcher, Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums.parse_mode import ParseMode

import bot_instance  # Импортируем модуль с синглтоном

# Создаем бота
bot = Bot(token=os.getenv("TOKEN"), default=DefaultBotProperties(parse_mode=ParseMode.HTML))

# Сохраняем бота в синглтоне
bot_instance.set_bot_instance(bot)
all_user_id = []

# Initialize dispatcher
dp = Dispatcher()

# Include routers
dp.include_router(UserRouter)
dp.include_router(AdminRouter)
dp.include_router(ChannelRouter)

async def on_startup(bot: Bot):
    """Initialize database on bot startup"""
    run_param = False  # Set to True to reset database
    if run_param:
        await drop_db()
    await create_db()
    print("✅ Bot started successfully")

async def on_shutdown(bot: Bot):
    """Cleanup on bot shutdown"""
    print("❌ Bot stopped")

async def polling_bot():
    """Main function to start the bot"""
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    dp.update.middleware(DataBaseSession(session_pool=session_maker))
    
    # Используйте переименованную переменную telegram_bot
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(
        bot,  # ← ИЗМЕНИТЕ ЗДЕСЬ
        allowed_updates=dp.resolve_used_update_types()
    )

if __name__ == "__main__":
    asyncio.run(polling_bot())
