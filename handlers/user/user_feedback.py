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
🤍 <b>Расскажите, как вам у нас?</b>

Для нас важно каждое ваше слово — оно помогает становиться лучше и вкуснее.

Напишите, что думаете:
• Что особенно понравилось?
• Что можно сделать ещё лучше?
• Есть ли пожелания?

<i>Мы читаем каждый отзыв и берём его на кухню 🤍</i>

Чтобы отменить — нажмите "❌ Отмена"
"""

FEEDBACK_THANK_YOU = """
✨ <b>Сердечное спасибо!</b>

Ваш отзыв уже на нашей кухне — мы обязательно его изучим и учтём.
Вы помогаете «Берегине Дома» становиться уютнее и вкуснее 🤍

<i>Возвращаемся в меню...</i>
"""

FEEDBACK_CANCELED = """
❌ Хорошо, в другой раз.

Вы всегда сможете оставить отзыв в главном меню — мы будем ждать 🤍
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
            text="❌ Напишите чуть подробнее — нам правда важно каждое слово (минимум 5 символов) 🤍",
            buttons={"❌ Отмена": "feedback_cancel"},
            sizes=[1],
            parse_mode="HTML"
        )
        return
    
    if len(feedback_text) > 2000:
        await send_clean_message(
            target=message,
            text="❌ Очень душевно, но давайте чуть короче? Попробуйте уложиться в 2000 символов ✨",
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
            buttons={"🍰 Главное меню": "main_menu"},
            sizes=[1],
            parse_mode="HTML"
        )
    else:
        await send_clean_message(
            target=message,
            text="❌ Что-то пошло не так — отзыв не сохранился. Попробуйте ещё раз или напишите нам напрямую 🤍",
            buttons={"🍰 Главное меню": "main_menu"},
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
        buttons={"🍰 Главное меню": "main_menu"},
        sizes=[1],
        parse_mode="HTML"
    )