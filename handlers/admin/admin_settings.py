"""
Admin Settings Module
=====================

This module handles admin settings.
"""

from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.enums.parse_mode import ParseMode

from sqlalchemy.ext.asyncio import AsyncSession

from States import user_states

from handlers.admin.admin_panel import send_section_message


# =============================================================================
# ROUTER INITIALIZATION
# =============================================================================

AdminSettingsRouter = Router()


# =============================================================================
# HANDLERS
# =============================================================================

@AdminSettingsRouter.callback_query(F.data == "admin_settings", StateFilter(user_states.AdminPanel.admin_panel))
async def show_admin_settings(call: types.CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    ⚙️ Настройки — скоро здесь можно будет настроить всё под себя.
    """
    await call.answer()
    
    text = """
⚙️ <b>Настройки</b>

Скоро здесь появится возможность настроить:
• Уведомления о заказах
• Часы работы
• Способы доставки

<i>Готовим обновление 🤍</i>
    """
    
    buttons = {
        "🔙 Назад": "back_to_admin_panel"
    }
    
    await send_section_message(call, text, buttons)