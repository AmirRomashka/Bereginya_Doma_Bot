"""
Admin Feedback Module
=====================

This module handles viewing user feedback in a TikTok-style carousel.
Admin can browse through reviews one by one, from newest to oldest.
"""

from typing import List, Dict, Any, Optional
from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.enums.parse_mode import ParseMode

from icecream import ic
from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query.feedback_orm import FeedbackRepository
from keybords.inline import get_callback_btns
from tools import send_clean_message
from handlers.admin.admin_panel import send_section_message


# =============================================================================
# ROUTER INITIALIZATION
# =============================================================================

AdminFeedbackRouter = Router(name="admin_feedback")


# =============================================================================
# CONSTANTS
# =============================================================================

# Callback prefixes
CALLBACK_FEEDBACK_LIST = "admin_feedback_list"
CALLBACK_FEEDBACK_NEXT = "admin_feedback_next_"
CALLBACK_FEEDBACK_PREV = "admin_feedback_prev_"
CALLBACK_FEEDBACK_BACK = "admin_feedback_back"

# -----------------------------------------------------------------------------
# Button labels
# -----------------------------------------------------------------------------
BTN_PREV = "◀️ Предыдущий"
BTN_NEXT = "Следующий ▶️"
BTN_BACK = "🔙 Назад"

# -----------------------------------------------------------------------------
# Messages
# -----------------------------------------------------------------------------

FEEDBACK_EMPTY_TEXT = """
📭 <b>Отзывы пользователей</b>

Пока нет ни одного отзыва.
Когда появятся — они будут здесь.
"""

FEEDBACK_CAROUSEL_TEMPLATE = """
📝 <b>ОТЗЫВ #{feedback_id}</b>
{'─' * 35}

👤 <b>Пользователь:</b> {user_name}
🆔 <b>ID:</b> {user_id}
📅 <b>Дата:</b> {date}
📌 <b>Статус:</b> {status_icon} {status_text}

{'─' * 35}
💬 <b>Текст отзыва:</b>

<i>{text}</i>
"""

FEEDBACK_WITH_RESPONSE = """

{'─' * 35}
✨ <b>Ответ кондитерской:</b>
<i>{response}</i>
"""

FEEDBACK_FOOTER = """
{'─' * 35}
<b>📊 {current} из {total}</b>
"""


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_feedback_status_icon(is_published: bool) -> tuple[str, str]:
    """Возвращает иконку и текст статуса отзыва."""
    if is_published:
        return "✅", "Опубликован"
    return "🙈", "Скрыт"


# =============================================================================
# HANDLERS
# =============================================================================

@AdminFeedbackRouter.callback_query(F.data == "admin_feedback")
async def show_feedback_list(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Показывает первый отзыв (самый новый) в режиме карусели.
    """
    await call.answer()
    
    feedback_repo = FeedbackRepository(session)
    all_feedback = await feedback_repo.get_all(limit=200, include_hidden=True)
    
    if not all_feedback:
        await send_section_message(
            call,
            FEEDBACK_EMPTY_TEXT,
            {"🔙 Назад": "back_to_admin_panel"}
        )
        return
    
    # Сохраняем список отзывов в состояние
    feedback_list = [
        {
            "id": fb.feedback_id,
            "user_id": fb.user_id,
            "text": fb.text,
            "is_published": fb.is_published,
            "admin_response": fb.admin_response,
            "created": fb.created
        }
        for fb in all_feedback
    ]
    
    # Сортируем от новых к старым
    feedback_list.sort(key=lambda x: x["created"], reverse=True)
    
    await state.update_data(
        feedback_list=feedback_list,
        current_index=0,
        total=len(feedback_list)
    )
    
    await show_feedback_at_index(call, state, session, 0)


async def show_feedback_at_index(
    target: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    index: int
) -> None:
    """
    Показывает отзыв по указанному индексу.
    """
    data = await state.get_data()
    feedback_list = data.get("feedback_list", [])
    total = data.get("total", 0)
    
    if not feedback_list or index < 0 or index >= len(feedback_list):
        await target.answer("❌ Отзыв не найден", show_alert=True)
        return
    
    feedback = feedback_list[index]
    
    # Получаем информацию о пользователе
    from database.orm_query.users_orm import get_user_orm
    user = await get_user_orm(session, feedback["user_id"])
    user_name = user.full_name if user else f"ID {feedback['user_id']}"
    
    status_icon, status_text = get_feedback_status_icon(feedback["is_published"])
    date_str = feedback["created"].strftime("%d.%m.%Y %H:%M")
    
    # Формируем текст отзыва
    text = FEEDBACK_CAROUSEL_TEMPLATE.format(
        feedback_id=feedback["id"],
        user_name=user_name,
        user_id=feedback["user_id"],
        date=date_str,
        status_icon=status_icon,
        status_text=status_text,
        text=feedback["text"]
    )
    
    # Добавляем ответ администратора если есть
    if feedback.get("admin_response"):
        text += FEEDBACK_WITH_RESPONSE.format(response=feedback["admin_response"])
    
    # Добавляем футер с номером
    text += FEEDBACK_FOOTER.format(current=index + 1, total=total)
    
    # Формируем кнопки — только навигация и назад
    buttons = {}
    sizes = []
    
    # Предыдущий
    if index > 0:
        buttons[BTN_PREV] = f"{CALLBACK_FEEDBACK_PREV}{index - 1}"
        sizes.append(1)
    
    # Следующий
    if index < total - 1:
        buttons[BTN_NEXT] = f"{CALLBACK_FEEDBACK_NEXT}{index + 1}"
        sizes.append(1)
    
    # Назад
    buttons[BTN_BACK] = CALLBACK_FEEDBACK_BACK
    sizes.append(1)
    
    # Сохраняем текущий индекс
    await state.update_data(current_index=index)
    
    await send_clean_message(
        target=target,
        text=text,
        buttons=buttons,
        sizes=sizes,
        parse_mode="HTML"
    )


@AdminFeedbackRouter.callback_query(F.data.startswith(CALLBACK_FEEDBACK_NEXT))
async def feedback_next(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Переход к следующему отзыву."""
    next_index = int(call.data.split("_")[3])
    await show_feedback_at_index(call, state, session, next_index)


@AdminFeedbackRouter.callback_query(F.data.startswith(CALLBACK_FEEDBACK_PREV))
async def feedback_prev(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Переход к предыдущему отзыву."""
    prev_index = int(call.data.split("_")[3])
    await show_feedback_at_index(call, state, session, prev_index)


@AdminFeedbackRouter.callback_query(F.data == CALLBACK_FEEDBACK_BACK)
async def feedback_back(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Возврат в админ-панель."""
    await state.clear()
    from handlers.admin.admin_panel import back_to_admin_panel
    await back_to_admin_panel(call, state, session)


@AdminFeedbackRouter.callback_query(F.data == CALLBACK_FEEDBACK_LIST)
async def feedback_list_refresh(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Обновление списка отзывов и возврат к первому."""
    await show_feedback_list(call, state, session)