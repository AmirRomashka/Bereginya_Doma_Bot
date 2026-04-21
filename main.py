# main.py
import os
import asyncio
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv()) 

from handlers.developer.developer_router import DeveloperRouter  

from aiogram import Dispatcher, Bot 
from aiogram.client.default import DefaultBotProperties  
from aiogram.enums.parse_mode import ParseMode 

from database.engine import create_db, drop_db, session_maker 
from database.orm_query.users_orm import get_users_by_status_orm
from database.enumirate.users_enum import UserStatus

from middlewares.db import DataBaseSession 

from handlers.start import StartRouter 
from handlers.admin.admin_router import AdminRouter
from handlers.user.user_router import UserRouter 
import bot_instance 
from config import ADMIN_IDS



# ======================================================================
# INITIALIZATION
# ======================================================================

# Initialize bot
bot = Bot(
    token=os.getenv("TOKEN"), default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

# Initialize dispatcher
dp = Dispatcher()


# Include routers
dp.include_router(DeveloperRouter)
dp.include_router(StartRouter)
dp.include_router(AdminRouter)
dp.include_router(UserRouter)


# Сохраняем бота в синглтоне
bot_instance.set_bot_instance(bot)
all_user_id = []


# ======================================================================
# HELPER FUNCTIONS
# ======================================================================

async def load_admin_ids() -> None:
    """
    Загружает ID всех администраторов из базы данных в глобальную переменную.
    """
    async with session_maker() as session:
        try:
            admins = await get_users_by_status_orm(session, UserStatus.ADMIN.value)
            ADMIN_IDS.clear()
            ADMIN_IDS.extend([admin.user_id for admin in admins])
            print(f"✅ Загружено {len(ADMIN_IDS)} администраторов: {ADMIN_IDS}")
        except Exception as e:
            print(f"❌ Ошибка загрузки администраторов: {e}")
            ADMIN_IDS.clear()


# ======================================================================
# STARTUP/SHUTDOWN HANDLERS
# ======================================================================

async def on_startup(bot):
    """Initialize database on bot startup"""
    run_param = True   # Set to True to reset database
    if run_param:
        await drop_db()

    await create_db()
    print("✅ Database initialized")
    
    # Загружаем ID администраторов
    await load_admin_ids()
    print("✅ Bot started successfully")


async def on_shutdown(bot: Bot):
    """Cleanup on bot shutdown"""
    print("❌ Bot stopped")


# ======================================================================
# SCHEDULED TASKS SETUP
# ======================================================================


# ======================================================================
# MAIN BOT POLLING FUNCTION
# ======================================================================

async def polling_bot():
    """Main function to start the bot"""

    # Register startup/shutdown handlers
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Add database middleware
    dp.update.middleware(DataBaseSession(session_pool=session_maker))

    # Start polling
    await bot.delete_webhook(
        drop_pending_updates=True,
    )
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


# ======================================================================
# ENTRY POINT
# ======================================================================

if __name__ == "__main__":
    asyncio.run(polling_bot())
