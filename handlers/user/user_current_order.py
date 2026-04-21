"""
User Current Orders Module
==========================

This module handles displaying active orders for users.
Here guests can track their orders that are being processed.
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
from bot_instance import get_bot_instance


# =============================================================================
# ROUTER INITIALIZATION
# =============================================================================

UserCurrentOrdersRouter = Router(name="user_current_orders")


# =============================================================================
# CONSTANTS
# =============================================================================

# -----------------------------------------------------------------------------
# Navigation callbacks
# -----------------------------------------------------------------------------
CALLBACK_CURRENT_ORDERS = "user_current_orders"
CALLBACK_ORDER_DETAIL = "current_order_detail_"
CALLBACK_BACK_TO_MENU = "back_to_user_menu"
CALLBACK_MAIN_MENU = "main_menu"
CALLBACK_CANCEL_ORDER = "cancel_order_"
CALLBACK_CONFIRM_CANCEL = "confirm_cancel_"
CALLBACK_CONFIRM_RECEIVED_START = "confirm_received_start_"
CALLBACK_CONFIRM_RECEIVED_EXECUTE = "confirm_received_execute_"

# -----------------------------------------------------------------------------
# Button text constants
# -----------------------------------------------------------------------------
BUTTON_TEXT = {
    "back_to_menu": "🍽 В меню",
    "main_menu": "🏠 Главная",
    "back_to_orders": "📋 К активным заказам",
    "cancel_order": "❌ Отменить заказ",
    "confirm_cancel": "✅ Да, отменить",
    "cancel": "❌ Нет, оставить",
    "confirm_received": "✅ Получил заказ"
}

# -----------------------------------------------------------------------------
# Messages
# -----------------------------------------------------------------------------

ACTIVE_ORDERS_EMPTY = """
🍳 <b>Активные заказы</b>

У вас пока нет активных заказов.
Заказы появляются здесь после того, как вы оформили корзину и отправили фото чека.

<i>Сделайте заказ — и он появится здесь 🤍</i>
"""

ACTIVE_ORDERS_TEXT = """
🍳 <b>Активные заказы</b>

Вот что мы готовим для вас:
"""

ORDER_ITEM_FORMAT = """
{number}. Заказ №{order_id}
   📅 {date}
   💰 {total} ₽
   📊 Статус: {status}
"""

ORDER_DETAIL_TEMPLATE = """
🍳 <b>ЗАКАЗ №{order_id}</b>
{'━' * 35}

📅 <b>Дата оформления:</b> {date}
📊 <b>Статус:</b> {status}
💬 <b>Ваши пожелания:</b> {comment}

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

CANCEL_CONFIRM_TEXT = """
⚠️ <b>Подтверждение отмены заказа #{order_id}</b>

Вы действительно хотите отменить этот заказ?

<b>Состав заказа:</b>
{items_text}

<b>Итого:</b> {total} ₽

⚠️ <b>Внимание!</b> Это действие нельзя отменить.
"""

ORDER_CANCELED_TEXT = """
🗑 <b>Заказ №{order_id} отменён</b>

Вы отменили этот заказ.
Если вы передумали, вы можете оформить новый заказ в корзине.

<i>Ждём вас снова 🤍</i>
"""

CANCEL_ERROR_TEXT = """
❌ <b>Не удалось отменить заказ</b>

Заказ уже находится в статусе <b>{status}</b> и не может быть отменён.
"""

RECEIVED_CONFIRM_TEXT = """
⚠️ <b>Подтверждение получения заказа #{order_id}</b>

Вы действительно хотите подтвердить получение этого заказа?

<b>Состав заказа:</b>
{items_text}

<b>Итого:</b> {total} ₽

⚠️ <b>Внимание!</b> После подтверждения заказ перейдёт в историю.
"""

ORDER_COMPLETED_TEXT = """
✅ <b>Заказ №{order_id} завершён!</b>

Спасибо, что выбрали нас! Будем рады видеть вас снова 🤍

<b>Состав заказа:</b>
{items_text}

<b>Итого:</b> {total} ₽

<i>Заказ передан в историю.</i>
"""

RECEIVED_ERROR_TEXT = """
❌ <b>Не удалось подтвердить получение</b>

Заказ уже находится в статусе <b>{status}</b>.
"""


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def format_delivery_time(hour_from: Optional[int], hour_to: Optional[int]) -> str:
    """
    Форматирует время доставки для отображения пользователю.
    
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
        return "💬 <i>Нет пожеланий</i>"
    
    # Если комментарий длинный, обрезаем с многоточием
    if len(comment) > 150:
        comment = comment[:147] + "..."
    
    # Экранируем HTML-спецсимволы
    comment = comment.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    
    return f"💬 <b>Пожелания:</b>\n📝 {comment}"


def format_order_status(status: str) -> str:
    """Форматирует статус заказа для отображения."""
    if not isinstance(status, str):
        ic(f"Unexpected status type: {type(status)}, value: {status}")
        return "❓ Неизвестный статус"
    
    status_map = {
        OrdersStatus.VERIFICATION.value: "🔄 Ожидает подтверждения",
        OrdersStatus.ACCEPTED.value: "👨‍🍳 Готовится",
        OrdersStatus.READY_FOR_DELIVERY.value: "🚚 Готов к получению",
        OrdersStatus.COMPLETED.value: "✅ Завершён",
        OrdersStatus.REFUSED.value: "❌ Отменён"
    }
    return status_map.get(status, status)


def format_order_date(date: datetime) -> str:
    """
    Форматирует дату заказа для пользователя.
    Показывает только дату, без времени.
    """
    if not hasattr(date, 'strftime'):
        ic(f"Unexpected date type: {type(date)}, value: {date}")
        return "дата неизвестна"
    return date.strftime("%d.%m.%Y")  # ✅ Только дата, без времени


async def get_user_active_orders(session: AsyncSession, user_id: int) -> List:
    """
    Получает активные заказы пользователя:
    - VERIFICATION (ждёт подтверждения)
    - ACCEPTED (готовится)
    - READY_FOR_DELIVERY (готов к получению)
    """
    order_repo = OrderRepository(session=session, user_id=user_id)
    
    verification_orders = await order_repo.get_orders_by_user_and_status(OrdersStatus.VERIFICATION)
    accepted_orders = await order_repo.get_orders_by_user_and_status(OrdersStatus.ACCEPTED)
    ready_orders = await order_repo.get_orders_by_user_and_status(OrdersStatus.READY_FOR_DELIVERY)
    
    all_orders = verification_orders + accepted_orders + ready_orders
    all_orders.sort(key=lambda x: x.created, reverse=True)
    
    return all_orders


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


async def format_orders_list(orders: List, session: AsyncSession) -> str:
    """Форматирует список активных заказов для вывода."""
    if not orders:
        return ACTIVE_ORDERS_EMPTY
    
    text = ACTIVE_ORDERS_TEXT + "\n\n"
    
    for i, order in enumerate(orders, 1):
        status = format_order_status(order.order_status)
        date = format_order_date(order.created)
        
        order_repo = OrderRepository(session=session)
        total = await order_repo.get_order_total(order.order_id)
        
        text += ORDER_ITEM_FORMAT.format(
            number=i,
            order_id=order.order_id,
            date=date,
            total=total,
            status=status
        )
    
    return text


def can_cancel_order(status: str) -> bool:
    """
    Проверяет, можно ли отменить заказ в данном статусе.
    Отменить можно только заказы в статусе VERIFICATION (ещё не приняты в работу).
    """
    return status == OrdersStatus.VERIFICATION.value


def can_confirm_received(status: str) -> bool:
    """
    Проверяет, можно ли подтвердить получение заказа.
    Подтвердить можно только заказы в статусе READY_FOR_DELIVERY.
    """
    return status == OrdersStatus.READY_FOR_DELIVERY.value


# =============================================================================
# HANDLERS
# =============================================================================

@UserCurrentOrdersRouter.callback_query(F.data == CALLBACK_CURRENT_ORDERS)
async def show_active_orders(call: CallbackQuery, session: AsyncSession) -> None:
    """
    Показывает активные заказы пользователя.
    """
    user_id = call.from_user.id
    orders = await get_user_active_orders(session, user_id)
    
    if not orders:
        await send_clean_message(
            target=call,
            text=ACTIVE_ORDERS_EMPTY,
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
    
    for i, order in enumerate(orders, 1):
        order_repo = OrderRepository(session=session, user_id=user_id)
        total = await order_repo.get_order_total(order.order_id)
        date_str = format_order_date(order.created)
        button_text = f"{i}. Заказ №{order.order_id} — {date_str}"
        buttons[button_text] = f"{CALLBACK_ORDER_DETAIL}{order.order_id}"
        sizes.append(1)
    
    buttons["🔙 Назад"] = CALLBACK_BACK_TO_MENU
    sizes.append(1)
    
    text = await format_orders_list(orders, session)
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=sizes,
        parse_mode="HTML"
    )


@UserCurrentOrdersRouter.callback_query(F.data.startswith(CALLBACK_ORDER_DETAIL))
async def show_order_detail(call: CallbackQuery, session: AsyncSession) -> None:
    """
    Показывает детальную информацию об активном заказе.
    """
    order_id = int(call.data.split("_")[3])
    
    order_details = await get_order_details(session, order_id)
    
    if not order_details:
        await call.answer("❌ Заказ не найден", show_alert=True)
        return
    
    # Проверяем, что заказ активен
    active_statuses = [
        OrdersStatus.VERIFICATION.value,
        OrdersStatus.ACCEPTED.value,
        OrdersStatus.READY_FOR_DELIVERY.value
    ]
    if order_details['status'] not in active_statuses:
        await call.answer("❌ Этот заказ уже завершён", show_alert=True)
        await show_active_orders(call, session)
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
    
    # Формируем кнопки в зависимости от статуса
    buttons = {}
    sizes = []
    
    # Кнопка отмены — только для VERIFICATION
    if can_cancel_order(order_details['status']):
        buttons[BUTTON_TEXT["cancel_order"]] = f"{CALLBACK_CANCEL_ORDER}{order_id}"
        sizes.append(1)
    
    # Кнопка подтверждения получения — только для READY_FOR_DELIVERY
    if can_confirm_received(order_details['status']):
        buttons[BUTTON_TEXT["confirm_received"]] = f"{CALLBACK_CONFIRM_RECEIVED_START}{order_id}"
        sizes.append(1)
    
    buttons["📋 К активным заказам"] = CALLBACK_CURRENT_ORDERS
    buttons["🔙 Назад"] = CALLBACK_BACK_TO_MENU
    sizes.append(1)
    sizes.append(1)
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=sizes,
        parse_mode="HTML"
    )


# =============================================================================
# CANCEL ORDER HANDLERS
# =============================================================================

@UserCurrentOrdersRouter.callback_query(F.data.startswith(CALLBACK_CANCEL_ORDER))
async def cancel_order_confirm(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Подтверждение отмены заказа.
    """
    order_id = int(call.data.split("_")[2])
    
    order_details = await get_order_details(session, order_id)
    
    if not order_details:
        await call.answer("❌ Заказ не найден", show_alert=True)
        return
    
    # Проверяем, можно ли отменить
    if not can_cancel_order(order_details['status']):
        await call.answer(f"❌ Заказ в статусе '{format_order_status(order_details['status'])}' нельзя отменить", show_alert=True)
        return
    
    # Формируем текст для подтверждения
    items_text = ""
    for item in order_details['items']:
        items_text += f"\n• {item['name']} — {item['quantity']} × {item['price']}₽ = {item['subtotal']}₽"
    
    text = CANCEL_CONFIRM_TEXT.format(
        order_id=order_id,
        items_text=items_text,
        total=order_details['total']
    )
    
    buttons = {
        BUTTON_TEXT["confirm_cancel"]: f"{CALLBACK_CONFIRM_CANCEL}{order_id}",
        BUTTON_TEXT["cancel"]: f"{CALLBACK_ORDER_DETAIL}{order_id}"
    }
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=[1, 1],
        parse_mode="HTML"
    )


@UserCurrentOrdersRouter.callback_query(F.data.startswith(CALLBACK_CONFIRM_CANCEL))
async def cancel_order_execute(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Выполнение отмены заказа.
    """
    order_id = int(call.data.split("_")[2])
    
    order_details = await get_order_details(session, order_id)
    
    if not order_details:
        await call.answer("❌ Заказ не найден", show_alert=True)
        return
    
    # Проверяем, можно ли отменить (повторная проверка)
    if not can_cancel_order(order_details['status']):
        await call.answer(f"❌ Заказ уже в статусе '{format_order_status(order_details['status'])}' и не может быть отменён", show_alert=True)
        await show_order_detail(call, session)
        return
    
    # Отменяем заказ
    order_repo = OrderRepository(session=session)
    updated_order = await order_repo.update_order_status(order_id, OrdersStatus.REFUSED)
    
    if updated_order:
        await session.commit()
        
        # Формируем сообщение об успешной отмене
        items_text = ""
        for item in order_details['items']:
            items_text += f"\n• {item['name']} — {item['quantity']} × {item['price']}₽ = {item['subtotal']}₽"
        
        text = ORDER_CANCELED_TEXT.format(
            order_id=order_id,
            items_text=items_text,
            total=order_details['total']
        )
        
        buttons = {
            "🍽 В меню": CALLBACK_BACK_TO_MENU,
            "🏠 Главная": CALLBACK_MAIN_MENU
        }
        
        await send_clean_message(
            target=call,
            text=text,
            buttons=buttons,
            sizes=[1, 1],
            parse_mode="HTML"
        )
        
    else:
        await call.answer("❌ Не удалось отменить заказ", show_alert=True)


# =============================================================================
# CONFIRM RECEIVED HANDLERS
# =============================================================================

@UserCurrentOrdersRouter.callback_query(F.data.startswith(CALLBACK_CONFIRM_RECEIVED_START))
async def confirm_received_confirm(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Подтверждение получения заказа.
    """
    # Формат: confirm_received_start_{order_id}
    parts = call.data.split("_")
    order_id = int(parts[3])
    
    order_details = await get_order_details(session, order_id)
    
    if not order_details:
        await call.answer("❌ Заказ не найден", show_alert=True)
        return
    
    # Проверяем, можно ли подтвердить получение
    if not can_confirm_received(order_details['status']):
        await call.answer(f"❌ Заказ в статусе '{format_order_status(order_details['status'])}' нельзя подтвердить", show_alert=True)
        return
    
    # Формируем текст для подтверждения
    items_text = ""
    for item in order_details['items']:
        items_text += f"\n• {item['name']} — {item['quantity']} × {item['price']}₽ = {item['subtotal']}₽"
    
    text = RECEIVED_CONFIRM_TEXT.format(
        order_id=order_id,
        items_text=items_text,
        total=order_details['total']
    )
    
    buttons = {
        "✅ Да, подтвердить": f"{CALLBACK_CONFIRM_RECEIVED_EXECUTE}{order_id}",
        "❌ Отмена": f"{CALLBACK_ORDER_DETAIL}{order_id}"
    }
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=[1, 1],
        parse_mode="HTML"
    )


@UserCurrentOrdersRouter.callback_query(F.data.startswith(CALLBACK_CONFIRM_RECEIVED_EXECUTE))
async def confirm_received_execute(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Выполнение подтверждения получения заказа.
    """
    # Формат: confirm_received_execute_{order_id}
    parts = call.data.split("_")
    order_id = int(parts[3])
    
    order_details = await get_order_details(session, order_id)
    
    if not order_details:
        await call.answer("❌ Заказ не найден", show_alert=True)
        return
    
    # Проверяем, можно ли подтвердить получение (повторная проверка)
    if not can_confirm_received(order_details['status']):
        await call.answer(f"❌ Заказ уже в статусе '{format_order_status(order_details['status'])}'", show_alert=True)
        await show_order_detail(call, session)
        return
    
    # Завершаем заказ
    order_repo = OrderRepository(session=session)
    updated_order = await order_repo.update_order_status(order_id, OrdersStatus.COMPLETED)
    
    if updated_order:
        await session.commit()
        
        # Формируем сообщение об успешном завершении
        items_text = ""
        for item in order_details['items']:
            items_text += f"\n• {item['name']} — {item['quantity']} × {item['price']}₽ = {item['subtotal']}₽"
        
        text = ORDER_COMPLETED_TEXT.format(
            order_id=order_id,
            items_text=items_text,
            total=order_details['total']
        )
        
        buttons = {
            "🍽 В меню": CALLBACK_BACK_TO_MENU,
            "🏠 Главная": CALLBACK_MAIN_MENU
        }
        
        await send_clean_message(
            target=call,
            text=text,
            buttons=buttons,
            sizes=[1, 1],
            parse_mode="HTML"
        )
        
    else:
        await call.answer("❌ Не удалось подтвердить получение", show_alert=True)