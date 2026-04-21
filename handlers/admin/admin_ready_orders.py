"""
Admin Ready Orders Module
=========================

This module handles displaying orders that are ready for delivery.
Here the chef can see which orders are waiting for customer confirmation.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.enums.parse_mode import ParseMode

from icecream import ic
from sqlalchemy.ext.asyncio import AsyncSession

from database.enumirate.orders_enum import OrdersStatus
from database.orm_query.orders_orm import OrderRepository
from database.orm_query.delivery_orm import DeliveryRepository
from database.orm_query.address_orm import AddressRepository
from keybords.inline import get_callback_btns
from tools import send_clean_message
from bot_instance import get_bot_instance


# =============================================================================
# ROUTER INITIALIZATION
# =============================================================================

AdminReadyOrdersRouter = Router(name="admin_ready_orders")


# =============================================================================
# CONSTANTS
# =============================================================================

# Callback prefixes
CALLBACK_READY_ORDERS_MAIN = "admin_ready_orders"
CALLBACK_READY_ORDERS_BY_DATE = "ready_orders_date_"
CALLBACK_READY_ORDERS_ORDER_DETAIL = "ready_order_detail_"
CALLBACK_READY_ORDERS_CLOSE = "ready_close_delivery_"

# -----------------------------------------------------------------------------
# Button labels
# -----------------------------------------------------------------------------
BTN_BACK = "🔙 Назад"
BTN_CLOSE_DELIVERY = "✅ Закрыть доставку"
BTN_VIEW_ORDERS = "👁 Посмотреть заказы"

# -----------------------------------------------------------------------------
# Messages
# -----------------------------------------------------------------------------

READY_ORDERS_MAIN_TEXT = """
📦 <b>Готовые заказы</b>

Заказы в статусе <b>READY_FOR_DELIVERY</b> ожидают подтверждения получения от пользователей.

<b>Доступные даты доставки:</b>
{delivery_dates}

<i>Заказы остаются здесь, пока пользователи не подтвердят получение,
или вы не закроете доставку вручную (доступно через 5 часов после времени доставки).</i>
"""

READY_ORDERS_EMPTY_TEXT = """
📦 <b>Готовые заказы</b>

Нет заказов в статусе <b>READY_FOR_DELIVERY</b>.

Все заказы подтверждены или ещё не готовы к выдаче.
"""

READY_ORDERS_BY_DATE_TEXT = """
📦 <b>Заказы на {date}</b>

<b>Статус доставки:</b> {status_icon} {status_text}
<b>Заказов:</b> {total}

<b>Список заказов:</b>
{orders_list}

<i>Заказы ждут подтверждения получения от пользователей.</i>
"""

ORDER_DETAIL_TEXT = """
📦 <b>ЗАКАЗ #{order_id}</b>
{'━' * 35}

👤 <b>Клиент:</b> ID {user_id}
📅 <b>Дата оформления:</b> {date}
📊 <b>Статус:</b> {status}
💬 <b>Пожелания:</b> {comment}

{'━' * 35}
🍽 <b>СОСТАВ ЗАКАЗА</b>
{items}

{'━' * 35}
💰 <b>ИТОГО:</b> {total} ₽

<i>Заказ готов и ждёт подтверждения получения.</i>
"""

CLOSE_DELIVERY_CONFIRM_TEXT = """
⚠️ <b>Подтверждение закрытия доставки</b>

Вы действительно хотите закрыть доставку на <b>{date}</b>?

Будет выполнено:
• <b>{count}</b> заказов в статусе READY_FOR_DELIVERY будут переведены в COMPLETED

⚠️ Это действие нельзя отменить!
"""

CLOSE_DELIVERY_SUCCESS_TEXT = """
✅ <b>Доставка закрыта!</b>

Успешно завершено <b>{success}</b> заказов.

Оставшиеся заказы в статусе READY_FOR_DELIVERY: <b>{remaining}</b>
"""


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def format_delivery_time(hour_from: Optional[int], hour_to: Optional[int]) -> str:
    """
    Форматирует время доставки для отображения.
    
    Args:
        hour_from: Час начала (0-23)
        hour_to: Час окончания (0-23)
    
    Returns:
        str: Отформатированное время
    """
    if hour_from is None:
        return "🕐 <i>Не указано</i>"
    
    if hour_to and hour_to != hour_from:
        return f"🕐 {hour_from:02d}:00 — {hour_to:02d}:00"
    return f"🕐 {hour_from:02d}:00"


def format_comment(comment: Optional[str]) -> str:
    """
    Форматирует комментарий/пожелания для отображения с красивым оформлением.
    
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


def format_delivery_status(date) -> tuple[str, str]:
    """Форматирует статус даты доставки."""
    if not date.is_available:
        return "❌", "Недоступна (лимит исчерпан)"
    if date.order_limit and date.current_orders >= date.order_limit:
        return "🔴", "Лимит заполнен"
    return "✅", "Доступна"


def format_order_date(date: datetime) -> str:
    """Форматирует дату заказа (только дата)."""
    return date.strftime("%d.%m.%Y")


def can_close_delivery(delivery_date: datetime) -> bool:
    """
    Проверяет, можно ли закрыть доставку (прошло 5 часов после времени доставки).
    """
    now = datetime.now()
    close_time = delivery_date + timedelta(hours=5)
    return now >= close_time


async def get_ready_orders_by_delivery_date(
    session: AsyncSession
) -> Dict[str, Any]:
    """
    Получает заказы в статусе READY_FOR_DELIVERY, сгруппированные по датам доставки.
    """
    order_repo = OrderRepository(session)
    delivery_repo = DeliveryRepository(session)
    
    # Получаем все заказы в статусе READY_FOR_DELIVERY
    ready_orders = await order_repo.get_orders_by_status(OrdersStatus.READY_FOR_DELIVERY)
    
    result = {}
    
    for order in ready_orders:
        # Получаем дату доставки для заказа
        delivery_date = await delivery_repo.get_order_delivery(order.order_id)
        
        if delivery_date:
            date_key = delivery_date.delivery_id
            date_str = delivery_date.delivery_date.strftime("%d.%m.%Y")  # ✅ Только дата
            
            if date_key not in result:
                result[date_key] = {
                    "delivery_id": delivery_date.delivery_id,
                    "date_obj": delivery_date,
                    "date_str": date_str,
                    "orders": [],
                    "count": 0
                }
            
            # Получаем детали заказа
            order_details = await order_repo.get_order_with_details(order.order_id)
            
            result[date_key]["orders"].append({
                "order_id": order.order_id,
                "user_id": order.user_id,
                "total": order_details['total'] if order_details else 0,
                "status": order.order_status,
                "comment": order.comment,
                "items": order_details['items'] if order_details else [],
                "delivery_hour_from": getattr(order, 'delivery_hour_from', None),
                "delivery_hour_to": getattr(order, 'delivery_hour_to', None)
            })
            result[date_key]["count"] += 1
    
    return result


async def get_order_with_details(session: AsyncSession, order_id: int) -> Optional[Dict[str, Any]]:
    """
    Получает полную информацию о заказе с временем доставки.
    """
    order_repo = OrderRepository(session)
    order_details = await order_repo.get_order_with_details(order_id)
    
    if not order_details:
        return None
    
    # Добавляем время доставки
    order = await order_repo.get_order_by_id(order_id)
    if order:
        order_details['delivery_hour_from'] = getattr(order, 'delivery_hour_from', None)
        order_details['delivery_hour_to'] = getattr(order, 'delivery_hour_to', None)
    
    return order_details


# =============================================================================
# HANDLERS
# =============================================================================

@AdminReadyOrdersRouter.callback_query(F.data == CALLBACK_READY_ORDERS_MAIN)
async def show_ready_orders_main(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Показывает главное меню готовых заказов — список дат доставки.
    """
    await call.answer()
    
    ready_by_date = await get_ready_orders_by_delivery_date(session)
    
    if not ready_by_date:
        text = READY_ORDERS_EMPTY_TEXT
        
        buttons = {
            BTN_BACK: "back_to_admin_panel"
        }
        
        await send_clean_message(
            target=call,
            text=text,
            buttons=buttons,
            sizes=[1],
            parse_mode="HTML"
        )
        return
    
    # Формируем список дат
    dates_list = ""
    buttons = {}
    sizes = []
    
    for date_key, data in ready_by_date.items():
        date_str = data["date_str"]
        orders_count = data["count"]
        
        dates_list += f"\n• 📅 {date_str} — {orders_count} заказов"
        buttons[f"📅 {date_str} ({orders_count})"] = f"{CALLBACK_READY_ORDERS_BY_DATE}{date_key}"
        sizes.append(1)
    
    text = READY_ORDERS_MAIN_TEXT.format(delivery_dates=dates_list)
    
    buttons[BTN_BACK] = "back_to_admin_panel"
    sizes.append(1)
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=sizes,
        parse_mode="HTML"
    )


@AdminReadyOrdersRouter.callback_query(F.data.startswith(CALLBACK_READY_ORDERS_BY_DATE))
async def show_ready_orders_by_date(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Показывает список заказов на конкретную дату.
    """
    delivery_id = int(call.data.split("_")[3])
    
    delivery_repo = DeliveryRepository(session)
    delivery_date = await delivery_repo.get_by_id(delivery_id)
    
    if not delivery_date:
        await call.answer("❌ Дата не найдена", show_alert=True)
        await show_ready_orders_main(call, state, session)
        return
    
    # Получаем заказы на эту дату
    ready_by_date = await get_ready_orders_by_delivery_date(session)
    date_data = ready_by_date.get(delivery_id)
    
    if not date_data or not date_data["orders"]:
        await call.answer("❌ Нет заказов на эту дату", show_alert=True)
        await show_ready_orders_main(call, state, session)
        return
    
    status_icon, status_text = format_delivery_status(delivery_date)
    
    # Формируем список заказов
    orders_list = ""
    buttons = {}
    sizes = []
    
    for order in date_data["orders"]:
        order_id = order["order_id"]
        total = order["total"]
        
        # Формируем строку с временем если есть
        time_str = ""
        if order.get("delivery_hour_from"):
            time_str = f" 🕐 {order['delivery_hour_from']:02d}:00"
            if order.get("delivery_hour_to") and order["delivery_hour_to"] != order["delivery_hour_from"]:
                time_str += f"-{order['delivery_hour_to']:02d}:00"
        
        orders_list += f"\n• 📦 Заказ #{order_id}{time_str} — {total} ₽"
        buttons[f"📦 Заказ #{order_id}"] = f"{CALLBACK_READY_ORDERS_ORDER_DETAIL}{order_id}"
        sizes.append(1)
    
    text = READY_ORDERS_BY_DATE_TEXT.format(
        date=date_data["date_str"],
        status_icon=status_icon,
        status_text=status_text,
        total=date_data["count"],
        orders_list=orders_list
    )
    
    # Кнопка закрытия доставки (если прошло 5 часов)
    if can_close_delivery(delivery_date.delivery_date):
        buttons[BTN_CLOSE_DELIVERY] = f"{CALLBACK_READY_ORDERS_CLOSE}{delivery_id}"
        sizes.append(1)
    
    buttons[BTN_BACK] = CALLBACK_READY_ORDERS_MAIN
    sizes.append(1)
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=sizes,
        parse_mode="HTML"
    )


@AdminReadyOrdersRouter.callback_query(F.data.startswith(CALLBACK_READY_ORDERS_ORDER_DETAIL))
async def show_ready_order_detail(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Показывает детальную информацию о заказе в статусе READY_FOR_DELIVERY.
    """
    order_id = int(call.data.split("_")[3])
    
    order_details = await get_order_with_details(session, order_id)
    
    if not order_details:
        await call.answer("❌ Заказ не найден", show_alert=True)
        return
    
    if order_details['status'] != OrdersStatus.READY_FOR_DELIVERY.value:
        await call.answer("❌ Заказ не в статусе READY_FOR_DELIVERY", show_alert=True)
        return
    
    # Статус с эмодзи
    status_emoji = "📦"
    status_name = "Готов к выдаче"
    
    # Формируем текст заказа
    items_text = ""
    for i, item in enumerate(order_details['items'], 1):
        items_text += f"\n{i}. <b>{item['name']}</b>\n   🥄 {item['quantity']} × {item['price']}₽ = <b>{item['subtotal']}₽</b>"
    
    # Формируем полный текст
    text = f"""
{status_emoji} <b>ЗАКАЗ #{order_details['order_id']}</b>
{'━' * 35}

👤 <b>Клиент:</b> ID {order_details['user_id']}
📅 <b>Дата оформления:</b> {format_order_date(order_details['created'])}
📊 <b>Статус:</b> {status_emoji} {status_name}

{format_comment(order_details.get('comment'))}

{'━' * 35}
🍽 <b>СОСТАВ ЗАКАЗА</b>
{items_text}

{'━' * 35}
💰 <b>ИТОГО:</b> {order_details['total']} ₽
"""
    
    # Добавляем время доставки если есть
    if order_details.get('delivery_hour_from'):
        time_text = format_delivery_time(
            order_details['delivery_hour_from'],
            order_details['delivery_hour_to']
        )
        # Вставляем время после даты оформления
        lines = text.split('\n')
        insert_pos = 0
        for i, line in enumerate(lines):
            if 'Дата оформления' in line:
                insert_pos = i + 1
                break
        lines.insert(insert_pos, f"\n{time_text}")
        text = '\n'.join(lines)
    
    text += "\n\n<i>Заказ готов и ждёт подтверждения получения.</i>"
    
    buttons = {
        BTN_BACK: f"{CALLBACK_READY_ORDERS_BY_DATE}{order_details.get('delivery_id')}" if order_details.get('delivery_id') else CALLBACK_READY_ORDERS_MAIN
    }
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=[1],
        parse_mode="HTML"
    )


@AdminReadyOrdersRouter.callback_query(F.data.startswith(CALLBACK_READY_ORDERS_CLOSE))
async def close_delivery_confirm(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Подтверждение закрытия доставки (перевод READY_FOR_DELIVERY → COMPLETED).
    """
    delivery_id = int(call.data.split("_")[3])
    
    delivery_repo = DeliveryRepository(session)
    delivery_date = await delivery_repo.get_by_id(delivery_id)
    
    if not delivery_date:
        await call.answer("❌ Дата не найдена", show_alert=True)
        return
    
    # Проверяем, прошло ли 5 часов
    if not can_close_delivery(delivery_date.delivery_date):
        await call.answer("❌ Доставку можно закрыть только через 5 часов после времени доставки", show_alert=True)
        return
    
    ready_by_date = await get_ready_orders_by_delivery_date(session)
    date_data = ready_by_date.get(delivery_id)
    
    if not date_data or not date_data["orders"]:
        await call.answer("❌ Нет заказов на эту дату", show_alert=True)
        await show_ready_orders_main(call, state, session)
        return
    
    text = CLOSE_DELIVERY_CONFIRM_TEXT.format(
        date=date_data["date_str"],
        count=date_data["count"]
    )
    
    await state.update_data(close_delivery_id=delivery_id)
    
    buttons = {
        "✅ Да, закрыть": f"confirm_close_ready_{delivery_id}",
        "❌ Отмена": f"{CALLBACK_READY_ORDERS_BY_DATE}{delivery_id}"
    }
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=[1, 1],
        parse_mode="HTML"
    )


@AdminReadyOrdersRouter.callback_query(F.data.startswith("confirm_close_ready_"))
async def close_delivery_execute(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Выполнение закрытия доставки (READY_FOR_DELIVERY → COMPLETED).
    """
    delivery_id = int(call.data.split("_")[3])
    
    delivery_repo = DeliveryRepository(session)
    order_repo = OrderRepository(session)
    delivery_date = await delivery_repo.get_by_id(delivery_id)
    
    if not delivery_date:
        await call.answer("❌ Дата не найдена", show_alert=True)
        return
    
    # Проверяем, прошло ли 5 часов
    if not can_close_delivery(delivery_date.delivery_date):
        await call.answer("❌ Доставку можно закрыть только через 5 часов после времени доставки", show_alert=True)
        return
    
    ready_by_date = await get_ready_orders_by_delivery_date(session)
    date_data = ready_by_date.get(delivery_id)
    
    if not date_data or not date_data["orders"]:
        await call.answer("❌ Нет заказов на эту дату", show_alert=True)
        await show_ready_orders_main(call, state, session)
        return
    
    success_count = 0
    bot = get_bot_instance()
    
    for order in date_data["orders"]:
        updated = await order_repo.update_order_status(order["order_id"], OrdersStatus.COMPLETED)
        
        if updated:
            success_count += 1
            
            # Формируем сообщение с временем доставки если есть
            time_text = ""
            if order.get("delivery_hour_from"):
                time_text = f"\n🕐 <b>Время:</b> {order['delivery_hour_from']:02d}:00"
                if order.get("delivery_hour_to") and order["delivery_hour_to"] != order["delivery_hour_from"]:
                    time_text += f" - {order['delivery_hour_to']:02d}:00"
            
            # Уведомляем пользователя
            try:
                await bot.send_message(
                    chat_id=order["user_id"],
                    text=f"""
✅ <b>Заказ №{order['order_id']} завершён!</b>
📅 <b>Дата доставки:</b> {date_data['date_str']}{time_text}

Спасибо, что выбрали нас! Будем рады видеть вас снова 🤍

<i>Заказ передан в историю.</i>
""",
                    parse_mode="HTML"
                )
            except Exception as e:
                ic(f"Error notifying user {order['user_id']}: {e}")
    
    await session.commit()
    
    remaining = date_data["count"] - success_count
    
    text = CLOSE_DELIVERY_SUCCESS_TEXT.format(
        success=success_count,
        remaining=remaining
    )
    
    buttons = {
        "📦 К готовым заказам": CALLBACK_READY_ORDERS_MAIN
    }
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=[1],
        parse_mode="HTML"
    )