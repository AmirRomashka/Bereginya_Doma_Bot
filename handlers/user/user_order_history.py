"""
User Orders History Module
==========================

This module handles user's order history.
Here guests can see what they've ordered before.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.enums.parse_mode import ParseMode

from icecream import ic
from sqlalchemy.ext.asyncio import AsyncSession

from database.enumirate.orders_enum import OrdersStatus
from database.orm_query.orders_orm import OrderRepository

from keybords.inline import get_callback_btns
from tools import send_clean_message


# =============================================================================
# ROUTER INITIALIZATION
# =============================================================================

UserOrdersRouter = Router(name="user_orders")


# =============================================================================
# CONSTANTS
# =============================================================================

# -----------------------------------------------------------------------------
# Navigation callbacks
# -----------------------------------------------------------------------------
CALLBACK_ORDERS_HISTORY = "order_history"
CALLBACK_ORDER_DETAIL = "order_detail_"
CALLBACK_BACK_TO_MENU = "back_to_user_menu"
CALLBACK_MAIN_MENU = "main_menu"

# -----------------------------------------------------------------------------
# Button text constants
# -----------------------------------------------------------------------------
BUTTON_TEXT = {
    "back_to_menu": "🍽 В меню",
    "main_menu": "🏠 Главная",
    "back_to_orders": "📋 К заказам"
}

# -----------------------------------------------------------------------------
# Messages
# -----------------------------------------------------------------------------

ORDERS_HISTORY_EMPTY = """
📭 <b>История заказов</b>

Вы ещё ничего не заказывали.
Загляните в наше <b>меню</b> — там столько всего вкусного!

<i>Первый заказ уже ждёт вас 🤍</i>
"""

ORDERS_HISTORY_TEXT = """
📋 <b>Ваши заказы</b>

Вот что вы заказывали у нас:
"""

ORDER_ITEM_FORMAT = """
{number}. Заказ №{order_id}
   📅 {date}
   💰 {total} ₽
   📊 Статус: {status}
"""

ORDER_DETAIL_TEMPLATE = """
📦 <b>ЗАКАЗ №{order_id}</b>
{'━' * 35}

📅 <b>Дата оформления:</b> {date}
📊 <b>Статус:</b> {status}
💬 <b>Комментарий:</b> {comment}

{time_section}
{'━' * 35}
🍽 <b>СОСТАВ ЗАКАЗА</b>
{items}

{'━' * 35}
💰 <b>ИТОГО:</b> {total} ₽
"""

ORDER_ITEM_DETAIL = """
{number}. <b>{name}</b>
   🥄 {quantity} × {price}₽ = <b>{subtotal}₽</b>
"""


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def format_delivery_time(hour_from: Optional[int], hour_to: Optional[int]) -> str:
    """
    Форматирует время доставки для отображения в истории заказов.
    
    Args:
        hour_from: Час начала (0-23)
        hour_to: Час окончания (0-23)
    
    Returns:
        str: Отформатированное время или пустая строка
    """
    if hour_from is None:
        return ""
    
    if hour_to and hour_to != hour_from:
        return f"🕐 <b>Время доставки:</b> {hour_from:02d}:00 — {hour_to:02d}:00"
    return f"🕐 <b>Время доставки:</b> {hour_from:02d}:00"


def format_comment(comment: Optional[str]) -> str:
    """
    Форматирует комментарий/пожелания для отображения.
    
    Args:
        comment: Текст комментария
    
    Returns:
        str: Отформатированный комментарий
    """
    if not comment:
        return "💬 <i>Нет комментария</i>"
    
    # Если комментарий длинный, обрезаем с многоточием
    if len(comment) > 150:
        comment = comment[:147] + "..."
    
    # Экранируем HTML-спецсимволы
    comment = comment.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    
    return f"💬 {comment}"


def format_order_status(status: str) -> str:
    """Форматирует статус заказа для отображения в истории."""
    status_map = {
        OrdersStatus.ASSEMBLY.value: "🛒 В корзине",
        OrdersStatus.VERIFICATION.value: "🔄 Ожидает подтверждения",
        OrdersStatus.ACCEPTED.value: "👨‍🍳 Готовится",
        OrdersStatus.READY_FOR_DELIVERY.value: "🚚 Готов к получению",
        OrdersStatus.COMPLETED.value: "✅ Выполнен",
        OrdersStatus.REFUSED.value: "❌ Отменён"
    }
    return status_map.get(status, status)


def format_order_date(date: datetime) -> str:
    """
    Форматирует дату заказа для истории.
    Показывает только дату, без времени.
    """
    return date.strftime("%d.%m.%Y")


async def get_user_completed_orders(session: AsyncSession, user_id: int):
    """Получает завершённые заказы пользователя."""
    order_repo = OrderRepository(session=session, user_id=user_id)
    orders = await order_repo.get_orders_by_user_and_status(OrdersStatus.COMPLETED)
    return sorted(orders, key=lambda x: x.created, reverse=True)


async def get_order_details(session: AsyncSession, order_id: int) -> Dict[str, Any]:
    """Получает детальную информацию о заказе с временем доставки."""
    order_repo = OrderRepository(session=session)
    order_details = await order_repo.get_order_with_details(order_id)
    
    if not order_details:
        return None
    
    # Добавляем время доставки из модели Order
    order = await order_repo.get_order_by_id(order_id)
    if order:
        order_details['delivery_hour_from'] = getattr(order, 'delivery_hour_from', None)
        order_details['delivery_hour_to'] = getattr(order, 'delivery_hour_to', None)
    
    return order_details


# =============================================================================
# HANDLERS
# =============================================================================

@UserOrdersRouter.callback_query(F.data == CALLBACK_ORDERS_HISTORY)
async def show_orders_history(call: CallbackQuery, session: AsyncSession) -> None:
    """
    Показывает историю заказов пользователя.
    """
    user_id = call.from_user.id
    orders = await get_user_completed_orders(session, user_id)
    order_repo = OrderRepository(session=session, user_id=user_id)
    
    if not orders:
        await send_clean_message(
            target=call,
            text=ORDERS_HISTORY_EMPTY,
            buttons={
                "🍽 В меню": CALLBACK_BACK_TO_MENU,
                "🏠 Главная": CALLBACK_MAIN_MENU
            },
            sizes=[1, 1],
            parse_mode="HTML"
        )
        return
    
    buttons = {}
    sizes = []
    
    for i, order in enumerate(orders[:10], 1):  # Показываем последние 10
        total = await order_repo.get_order_total(order.order_id)
        date = format_order_date(order.created)
        status = format_order_status(order.order_status)
        
        button_text = f"{i}. Заказ №{order.order_id} — {date} ({status})"
        buttons[button_text] = f"{CALLBACK_ORDER_DETAIL}{order.order_id}"
        sizes.append(1)
    
    buttons["🔙 Назад"] = CALLBACK_BACK_TO_MENU
    sizes.append(1)
    
    await send_clean_message(
        target=call,
        text=ORDERS_HISTORY_TEXT,
        buttons=buttons,
        sizes=sizes,
        parse_mode="HTML"
    )


@UserOrdersRouter.callback_query(F.data.startswith(CALLBACK_ORDER_DETAIL))
async def show_order_detail(call: CallbackQuery, session: AsyncSession) -> None:
    """
    Показывает детальную информацию о заказе из истории.
    """
    order_id = int(call.data.split("_")[2])
    
    order_details = await get_order_details(session, order_id)
    
    if not order_details:
        await call.answer("❌ Заказ не найден", show_alert=True)
        return
    
    # Формируем список блюд с нумерацией
    items_text = ""
    for i, item in enumerate(order_details['items'], 1):
        items_text += ORDER_ITEM_DETAIL.format(
            number=i,
            name=item['name'],
            quantity=item['quantity'],
            price=item['price'],
            subtotal=item['subtotal']
        )
    
    # Формируем секцию времени (если есть)
    time_section = ""
    if order_details.get('delivery_hour_from'):
        time_section = format_delivery_time(
            order_details['delivery_hour_from'],
            order_details['delivery_hour_to']
        )
    
    # Формируем полный текст
    text = ORDER_DETAIL_TEMPLATE.format(
        order_id=order_details['order_id'],
        date=format_order_date(order_details['created']),
        status=format_order_status(order_details['status']),
        comment=format_comment(order_details.get('comment')),
        time_section=time_section + "\n" if time_section else "",
        items=items_text,
        total=order_details['total']
    )
    
    buttons = {
        "📋 К заказам": CALLBACK_ORDERS_HISTORY,
        "🔙 Назад": CALLBACK_BACK_TO_MENU
    }
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=[1, 1],
        parse_mode="HTML"
    )