"""
User Seasonal Dishes Module
===========================

This module handles displaying seasonal dishes to users in a TikTok-style carousel.
Users can swipe through seasonal dishes and add them to cart.
"""

from typing import List, Dict, Any, Optional

from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.enums.parse_mode import ParseMode

from icecream import ic
from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query.dish_orm import get_all_promotion_dishes_orm, get_dish_by_id_orm

from keybords.inline import get_callback_btns
from tools import send_clean_message

from handlers.user.user_menu import CALLBACK_ADD_TO_CART_PREFIX


# =============================================================================
# ROUTER INITIALIZATION
# =============================================================================

UserPromotionsRouter = Router(name="user_promotions")


# =============================================================================
# CONSTANTS
# =============================================================================

# -----------------------------------------------------------------------------
# Navigation callbacks
# -----------------------------------------------------------------------------
CALLBACK_USER_PROMOTIONS = "user_promotions"
CALLBACK_PROMO_DISH = "promo_dish_"
CALLBACK_PROMO_NEXT = "promo_next_"
CALLBACK_PROMO_PREV = "promo_prev_"
CALLBACK_BACK_TO_MENU = "back_to_user_menu"
CALLBACK_MAIN_MENU = "main_menu"

# -----------------------------------------------------------------------------
# Button text constants — понятные и тёплые
# -----------------------------------------------------------------------------
BUTTON_TEXT = {
    "back_to_menu": "🍰 В меню",
    "main_menu": "🏠 Главная",
    "add_to_cart": "🛒 В корзину",
    "next": "▶️ Следующее",
    "prev": "◀️ Предыдущее"
}

# -----------------------------------------------------------------------------
# Dish detail template for carousel
# -----------------------------------------------------------------------------

DISH_DETAIL_TEMPLATE = """
🍽 <b>{name}</b>

<i>{description}</i>

━━━━━━━━━━━━━━━━━━━━━
💰 <b>Цена:</b> {price} ₽
🍂 <i>Только в этом сезоне! 🍂</i>
━━━━━━━━━━━━━━━━━━━━━

<b>{current} из {total}</b> сезонных новинок
"""

DISH_NO_DESCRIPTION = "Попробуйте — это наш сезонный секрет ✨"

SEASONAL_EMPTY = """
🌿 <b>Сезонные блюда</b>

Пока мы готовим для вас что-то особенное.
Загляните позже — скоро здесь появятся новинки! 🤍

<i>Следите за обновлениями ✨</i>
"""


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

async def get_seasonal_dishes(session: AsyncSession) -> List[Dict[str, Any]]:
    """Получает список сезонных блюд."""
    return await get_all_promotion_dishes_orm(session)


def format_dish_detail(dish: Dict[str, Any], current: int, total: int) -> str:
    """Форматирует детальное описание блюда для карусели."""
    description = dish.get('description') or DISH_NO_DESCRIPTION
    
    return DISH_DETAIL_TEMPLATE.format(
        name=dish['name'],
        description=description,
        price=dish['price'],
        current=current,
        total=total
    )


def get_dish_navigation_buttons(
    current_index: int,
    total: int,
    dish_id: int
) -> tuple[Dict[str, str], List[int]]:
    """Создаёт кнопки навигации для карусели блюд."""
    buttons = {}
    sizes = []
    
    buttons[BUTTON_TEXT["add_to_cart"]] = f"{CALLBACK_ADD_TO_CART_PREFIX}{dish_id}"
    sizes.append(1)
    
    nav_buttons = {}
    
    if current_index > 0:
        nav_buttons["◀️"] = f"{CALLBACK_PROMO_PREV}{current_index - 1}"
    
    nav_buttons[f"{current_index + 1}/{total}"] = "pass"
    
    if current_index < total - 1:
        nav_buttons["▶️"] = f"{CALLBACK_PROMO_NEXT}{current_index + 1}"
    
    buttons.update(nav_buttons)
    sizes.append(len(nav_buttons) if nav_buttons else 1)
    
    buttons[BUTTON_TEXT["back_to_menu"]] = CALLBACK_BACK_TO_MENU
    buttons[BUTTON_TEXT["main_menu"]] = CALLBACK_MAIN_MENU
    sizes.append(2)
    
    return buttons, sizes


# =============================================================================
# HANDLERS
# =============================================================================

@UserPromotionsRouter.callback_query(F.data == CALLBACK_USER_PROMOTIONS)
async def show_seasonal_dishes(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Показывает сезонные блюда в формате карусели."""
    seasonal_dishes = await get_seasonal_dishes(session)
    
    if not seasonal_dishes:
        await send_clean_message(
            target=call,
            text=SEASONAL_EMPTY,
            buttons={
                BUTTON_TEXT["back_to_menu"]: CALLBACK_BACK_TO_MENU,
                BUTTON_TEXT["main_menu"]: CALLBACK_MAIN_MENU
            },
            sizes=[1, 1],
            parse_mode="HTML"
        )
        return
    
    await state.update_data(
        seasonal_dishes=seasonal_dishes,
        current_index=0,
        total=len(seasonal_dishes)
    )
    
    await show_dish_at_index(call, state, session, 0)


async def show_dish_at_index(
    target: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    index: int
) -> None:
    """Показывает блюдо по указанному индексу в карусели."""
    data = await state.get_data()
    seasonal_dishes = data.get('seasonal_dishes', [])
    total = data.get('total', 0)
    
    if not seasonal_dishes or index < 0 or index >= len(seasonal_dishes):
        await target.answer("❌ Блюдо не найдено", show_alert=True)
        return
    
    dish_id = seasonal_dishes[index]['dish_id']
    dish = await get_dish_by_id_orm(session, dish_id)
    
    if not dish:
        await target.answer("❌ Блюдо не найдено", show_alert=True)
        return
    
    await state.update_data(current_index=index)
    
    text = format_dish_detail(dish, index + 1, total)
    buttons, sizes = get_dish_navigation_buttons(index, total, dish_id)
    
    if dish.get('image'):
        await send_clean_message(
            target=target,
            text=text,
            buttons=buttons,
            sizes=sizes,
            photo=dish['image'],
            parse_mode="HTML"
        )
    else:
        await send_clean_message(
            target=target,
            text=text,
            buttons=buttons,
            sizes=sizes,
            parse_mode="HTML"
        )


@UserPromotionsRouter.callback_query(F.data.startswith(CALLBACK_PROMO_NEXT))
async def promo_next_dish(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Переход к следующему блюду в карусели."""
    try:
        next_index = int(call.data.split("_")[2])
    except (IndexError, ValueError):
        await call.answer("❌ Ошибка", show_alert=True)
        return
    
    await show_dish_at_index(call, state, session, next_index)


@UserPromotionsRouter.callback_query(F.data.startswith(CALLBACK_PROMO_PREV))
async def promo_prev_dish(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Переход к предыдущему блюду в карусели."""
    try:
        prev_index = int(call.data.split("_")[2])
    except (IndexError, ValueError):
        await call.answer("❌ Ошибка", show_alert=True)
        return
    
    await show_dish_at_index(call, state, session, prev_index)


# =============================================================================
# PASS HANDLER
# =============================================================================

@UserPromotionsRouter.callback_query(F.data == "pass")
async def pass_callback(call: CallbackQuery) -> None:
    """Пустой callback для неактивных кнопок (счётчик блюд)."""
    await call.answer()