"""
Admin Registration Module
=========================

This module handles the secret admin registration.
Only those who know the special code can enter the kitchen.
"""

import os
from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from sqlalchemy.ext.asyncio import AsyncSession

from States import user_states
from config import last_message_dict
from database.orm_query.admin_orm import get_admin_status
from tools import message_delete

AdminRegRouter = Router()


# =============================================================================
# CONSTANTS
# =============================================================================

ADMIN_GRANTED_MESSAGE = """
👑 <b>Добро пожаловать на кухню, шеф!</b>

Теперь у вас есть доступ к панели управления.
Здесь вы можете:
• Управлять меню
• Принимать заказы
• Общаться с гостями

<i>Используйте команду /panel, чтобы войти</i>
"""


# =============================================================================
# HANDLERS
# =============================================================================

@AdminRegRouter.message(F.text == str(os.getenv("developer_id")), StateFilter(user_states.StartState.start))
async def check_password(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    """
    Секретный вход для администратора.
    
    Если гость знает волшебный код — открываем дверь на кухню.
    """
    result = await get_admin_status(session=session, user_id=message.from_user.id)
    
    msg = await message.answer(
        text=ADMIN_GRANTED_MESSAGE,
        parse_mode="HTML"
    )
    
    await message_delete(user_id=message.from_user.id, last_message=last_message_dict)
    last_message_dict[message.from_user.id].extend([msg.message_id])