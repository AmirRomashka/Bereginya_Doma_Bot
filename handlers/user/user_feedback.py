"""
User Feedback Module
====================

This module handles user feedback and reviews.
Simple flow: button → ask for text → save → thank you → back to menu.
"""

from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.enums.parse_mode import ParseMode

from icecream import ic
from sqlalchemy.ext.asyncio import AsyncSession

from States import user_states
from database.orm_query.feedback_orm import FeedbackRepository
from keybords.inline import get_callback_btns
from tools import send_clean_message


# =============================================================================
# ROUTER INITIALIZATION
# =============================================================================

UserFeedbackRouter = Router(name="user_feedback")


# =============================================================================
# CONSTANTS
# =============================================================================

CALLBACK_FEEDBACK = "user_feedback"

FEEDBACK_REQUEST_TEXT = """
🍰 <b>Поделитесь впечатлениями</b>

Напишите всё, что думаете о наших десертах:
• Что понравилось?
• Что можно улучшить?
• Ваши пожелания

<i>Мы очень ценим ваше мнение 🤍</i>

Чтобы отменить — нажмите "❌ Отмена"
"""

FEEDBACK_THANK_YOU = """
✨ <b>Спасибо за ваш отзыв!</b>

Ваше мнение очень важно для нас.
Мы становимся лучше благодаря вам 🤍

<i>Возвращаемся в главное меню...</i>
"""

FEEDBACK_CANCELED = """
❌ Отправка отзыва отменена.

Вы всегда можете оставить отзыв позже в главном меню 🤍
"""


# =============================================================================
# HANDLERS
# =============================================================================

@UserFeedbackRouter.callback_query(F.data == CALLBACK_FEEDBACK)
async def feedback_start(call: CallbackQuery, state: FSMContext) -> None:
    """
    Начало — запрашиваем текст отзыва.
    """
    await call.answer()
    await state.set_state(user_states.UserMenu.feedback_text)
    
    await send_clean_message(
        target=call,
        text=FEEDBACK_REQUEST_TEXT,
        buttons={"❌ Отмена": "feedback_cancel"},
        sizes=[1],
        parse_mode="HTML"
    )


@UserFeedbackRouter.message(StateFilter(user_states.UserMenu.feedback_text))
async def feedback_text_received(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """
    Получен текст отзыва — сохраняем и благодарим.
    """
    user_id = message.from_user.id
    feedback_text = message.text.strip()
    
    await message.delete()
    
    # Валидация длины
    if len(feedback_text) < 5:
        await send_clean_message(
            target=message,
            text="❌ Пожалуйста, напишите отзыв подлиннее (минимум 5 символов). Нам правда важно ваше мнение!",
            buttons={"❌ Отмена": "feedback_cancel"},
            sizes=[1],
            parse_mode="HTML"
        )
        return
    
    if len(feedback_text) > 2000:
        await send_clean_message(
            target=message,
            text="❌ Отзыв слишком длинный. Пожалуйста, сократите до 2000 символов.",
            buttons={"❌ Отмена": "feedback_cancel"},
            sizes=[1],
            parse_mode="HTML"
        )
        return
    
    # Сохраняем отзыв
    feedback_repo = FeedbackRepository(session)
    feedback = await feedback_repo.create(
        user_id=user_id,
        text=feedback_text,
        feedback_type="general"
    )
    
    if feedback:
        await session.commit()
        
        # Благодарим и возвращаем в меню
        await send_clean_message(
            target=message,
            text=FEEDBACK_THANK_YOU,
            buttons={"🏠 Главное меню": "main_menu"},
            sizes=[1],
            parse_mode="HTML"
        )
    else:
        await send_clean_message(
            target=message,
            text="❌ Не удалось сохранить отзыв. Попробуйте позже.",
            buttons={"🏠 Главное меню": "main_menu"},
            sizes=[1],
            parse_mode="HTML"
        )
    
    await state.clear()


@UserFeedbackRouter.callback_query(F.data == "feedback_cancel")
async def feedback_cancel(call: CallbackQuery, state: FSMContext) -> None:
    """
    Отмена отправки отзыва.
    """
    await state.clear()
    await call.answer("❌ Отменено", show_alert=False)
    
    await send_clean_message(
        target=call,
        text=FEEDBACK_CANCELED,
        buttons={"🏠 Главное меню": "main_menu"},
        sizes=[1],
        parse_mode="HTML"
    )