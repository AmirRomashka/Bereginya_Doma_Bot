"""
Admin Help Module
=================

This module provides help information for the admin panel.
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

AdminHelpRouter = Router()


# =============================================================================
# HANDLERS
# =============================================================================

@AdminHelpRouter.callback_query(F.data == "admin_help", StateFilter(user_states.AdminPanel.admin_panel))
async def show_admin_help(call: types.CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    ❓ Помощь — подсказки для шеф-повара.
    """
    await call.answer()
    
    text = """
❓ <b>Как управлять кухней</b>

<b>📋 Разделы:</b>
━━━━━━━━━━━━━━━━━━━━━
🆕 <b>Новые заказы</b> — только что поступили, ждут подтверждения
🍳 <b>В работе</b> — заказы, которые уже готовятся
📜 <b>Архив</b> — всё, что уже приготовили
🍽 <b>Моё меню</b> — управляйте категориями и блюдами
📊 <b>Статистика</b> — сколько приготовили и заработали
📢 <b>Сказать гостям</b> — отправьте сообщение всем
🎉 <b>Акции</b> — выделите блюда со скидкой

<b>❓ Частые вопросы:</b>
• Как добавить новое блюдо? → Моё меню → Категория → Добавить блюдо
• Как изменить статус заказа? → Новые заказы или В работе → Выбрать заказ
• Как посмотреть выручку? → Статистика

<b>📞 Нужна помощь?</b>
@tech_support_bot

<i>Готовим с любовью 🤍</i>
    """
    
    buttons = {
        "🔙 Назад": "back_to_admin_panel"
    }
    
    await send_section_message(call, text, buttons)