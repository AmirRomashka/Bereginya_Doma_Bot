"""
User About Module
=================

This module handles information about the cafe.
Here guests can learn about the place, contacts, and working hours.
"""

from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.enums.parse_mode import ParseMode

from icecream import ic
from sqlalchemy.ext.asyncio import AsyncSession

from keybords.inline import get_callback_btns
from tools import send_clean_message


# =============================================================================
# ROUTER INITIALIZATION
# =============================================================================

UserAboutRouter = Router(name="user_about")


# =============================================================================
# CONSTANTS
# =============================================================================

# -----------------------------------------------------------------------------
# Navigation callbacks
# -----------------------------------------------------------------------------
CALLBACK_ABOUT_US = "about_us"
CALLBACK_ABOUT_US_FROM_START = "about_us_from_start"
CALLBACK_BACK_TO_MENU = "back_to_user_menu"
CALLBACK_MAIN_MENU = "main_menu"
CALLBACK_BACK_TO_START = "start"

# -----------------------------------------------------------------------------
# Button text constants
# -----------------------------------------------------------------------------
BUTTON_TEXT = {
    "back_to_menu": "🍽 В меню",
    "main_menu": "🏠 Главная",
    "back_to_start": "🔙 Назад"
}

# -----------------------------------------------------------------------------
# Messages
# -----------------------------------------------------------------------------

ABOUT_US_TEXT = """
🤍 <b>О нас</b>

Наша пекарня — про простые и настоящие вещи. Про муку, воду и время. Про чистые продукты с местных ферм. Про вкус, который напоминает о доме.

<b>Здесь мы готовим:</b>
🍞 Хлеб и выпечку на закваске
🍫 Полезные сладости собственного производства: шоколад, зефир, торты, печенье и пироги
🌾 По-настоящему вкусную безглютеновую продукцию
🎉 Кейтеринг для ваших тёплых событий

🚚 Еженедельно доставляем домашнюю еду в Калугу, Москву и Подмосковье — чтобы уют был рядом, даже на расстоянии.

<b>📍 Адрес:</b>
Дзержинский район, д. Миленки, ул. Рассветная, 13

<b>🕰 Часы работы:</b>
С 10:00 до 19:00

<b>📞 Контакты:</b>
Телефон: 8 (925) 858-27-75
Telegram: @bereginya_doma1

<i>Заглядывайте — у нас всегда тепло и по-домашнему 🤍</i>
"""


# =============================================================================
# HANDLERS
# =============================================================================

@UserAboutRouter.callback_query(F.data == CALLBACK_ABOUT_US)
@UserAboutRouter.callback_query(F.data == CALLBACK_ABOUT_US_FROM_START)
async def show_about_us(call: CallbackQuery, session: AsyncSession) -> None:
    """
    Показывает информацию о кафе.
    
    В зависимости от callback выбирает подходящие кнопки:
    - about_us — из главного меню → кнопки "🍽 В меню" и "🏠 Главная"
    - about_us_from_start — из стартового экрана → кнопка "🔙 Назад"
    """
    # Определяем источник по callback
    if call.data == CALLBACK_ABOUT_US_FROM_START:
        # Пришли из стартового экрана
        buttons = {
            BUTTON_TEXT["back_to_start"]: CALLBACK_BACK_TO_START
        }
        sizes = [1]
    else:
        # Пришли из главного меню
        buttons = {
            BUTTON_TEXT["back_to_menu"]: CALLBACK_BACK_TO_MENU,
            BUTTON_TEXT["main_menu"]: CALLBACK_MAIN_MENU
        }
        sizes = [1, 1]
    
    await send_clean_message(
        target=call,
        text=ABOUT_US_TEXT,
        buttons=buttons,
        sizes=sizes,
        parse_mode="HTML"
    )