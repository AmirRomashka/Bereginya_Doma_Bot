"""
Admin Delivery Module
=====================

This module handles delivery date and delivery status management for administrators.
"""

from datetime import datetime, timedelta
from typing import Union, Optional, List, Dict, Any

from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.enums.parse_mode import ParseMode

from icecream import ic
from sqlalchemy.ext.asyncio import AsyncSession

from database.enumirate.orders_enum import OrdersStatus
from database.orm_query.delivery_orm import DeliveryRepository
from database.orm_query.delivery_status_orm import DeliveryStatusRepository
from database.orm_query.address_orm import AddressRepository
from database.orm_query.orders_orm import OrderRepository
from keybords.inline import get_callback_btns
from tools import send_clean_message, message_delete, notify_admins
from config import last_message_dict, ADMIN_IDS
from States import user_states
from handlers.admin.admin_panel import send_section_message
from bot_instance import get_bot_instance


# =============================================================================
# ROUTER INITIALIZATION
# =============================================================================

AdminDeliveryRouter = Router()


# =============================================================================
# CONSTANTS
# =============================================================================

# Callback prefixes
CALLBACK_DELIVERY_MAIN = "delivery_main"
CALLBACK_DELIVERY_ADD_DATE = "delivery_add_date"
CALLBACK_DELIVERY_EDIT_DATE = "delivery_edit_date_"
CALLBACK_DELIVERY_DELETE_DATE = "delivery_delete_date_"
CALLBACK_DELIVERY_VIEW_DATES = "delivery_view_dates"
CALLBACK_DELIVERY_GENERATE = "delivery_generate"
CALLBACK_DELIVERY_STATUSES = "delivery_statuses"
CALLBACK_DELIVERY_STATUS_ADD = "delivery_status_add"
CALLBACK_DELIVERY_STATUS_EDIT = "delivery_status_edit_"
CALLBACK_DELIVERY_STATUS_DELETE = "delivery_status_delete_"
CALLBACK_DELIVERY_STATUS_TOGGLE = "delivery_status_toggle_"
CALLBACK_DELIVERY_ADDRESSES = "delivery_addresses"
CALLBACK_DELIVERY_ADDRESS_STATUS = "delivery_address_status_"
CALLBACK_DELIVERY_ALL_ADDRESSES = "delivery_all_addresses"
CALLBACK_DELIVERY_VIEW_ORDERS = "delivery_view_orders_"
CALLBACK_DELIVERY_BULK_MOVE_TO_READY = "delivery_bulk_move_"
CALLBACK_DELIVERY_CLOSE = "delivery_close_"

# -----------------------------------------------------------------------------
# Button labels
# -----------------------------------------------------------------------------
BTN_ADD_DATE = "➕ Добавить дату"
BTN_VIEW_DATES = "📅 Посмотреть все даты"
BTN_GENERATE = "⚙️ Сгенерировать на 14 дней"
BTN_STATUSES = "🚚 Статусы доставки"
BTN_ADDRESSES = "📍 Адреса пользователей"
BTN_BACK = "🔙 Назад"
BTN_CANCEL = "❌ Отмена"
BTN_DELETE = "🗑 Удалить"
BTN_EDIT = "✏️ Редактировать"
BTN_VIEW_ORDERS = "👁 Просмотреть заказы"
BTN_MOVE_TO_READY = "✅ Перенести все в READY_FOR_DELIVERY"
BTN_CLOSE_DELIVERY = "✅ Закрыть доставку"

# -----------------------------------------------------------------------------
# Messages
# -----------------------------------------------------------------------------

DELIVERY_MAIN_TEXT = """
🚚 <b>Управление доставкой</b>

Здесь вы можете управлять датами доставки, статусами и адресами.

<b>Ближайшие даты доставки:</b>
{dates_text}

<b>📊 Статистика:</b>
📦 Всего дат: {total_dates}
✅ Доступно: {available_dates}
📍 Адресов: {addresses_count}
🏷️ Статусов: {statuses_count}
"""

DELIVERY_ALL_DATES_TEXT = """
📅 <b>Все даты доставки</b>

Выберите дату для просмотра или редактирования:

{dates_list}
"""

DELIVERY_DATE_DETAIL_TEXT = """
📅 <b>Дата доставки</b>

<b>📆 Дата:</b> {date}
<b>📊 Статус:</b> {status_icon} {status_text}
<b>📦 Заказов:</b> {orders}/{limit}
<b>📝 Примечание:</b> {note}

Что хотите сделать?
"""

DELIVERY_ORDERS_LIST_TEXT = """
📅 <b>Заказы на {date}</b>

<b>Статистика:</b>
📦 Всего заказов: {total}
✅ В статусе ACCEPTED: {accepted_count}
🚚 В статусе READY_FOR_DELIVERY: {ready_count}

<b>Заказы в статусе ACCEPTED:</b>
{accepted_list}

<b>Заказы в статусе READY_FOR_DELIVERY:</b>
{ready_list}

<i>Выберите действие:</i>
"""

BULK_MOVE_CONFIRM_TEXT = """
✅ <b>Подтверждение переноса</b>

Вы действительно хотите перенести <b>{count}</b> заказов
в статус <b>READY_FOR_DELIVERY</b> на дату <b>{date}</b>?

Заказы:
{orders_list}

После переноса пользователи смогут подтвердить получение.
"""

BULK_MOVE_SUCCESS_TEXT = """
✅ <b>Готово!</b>

Успешно перенесено <b>{success}</b> заказов в статус READY_FOR_DELIVERY.

Не перенесено: <b>{failed}</b> (не в статусе ACCEPTED)
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

DELIVERY_ADD_DATE_TEXT = """
📅 <b>Добавление даты доставки</b>

Введите дату в формате:
<i>25.03.2026</i>

Время доставки всегда будет установлено на <b>23:59:59</b>.

Минимальное время до доставки — 2 часа (но так как время 23:59, 
фактически доставка будет на следующий день после указанной даты).
"""

DELIVERY_ADD_LIMIT_TEXT = """
📊 <b>Лимит заказов</b>

Введите максимальное количество заказов на эту дату
(0 — без лимита, 1-999 — ограничение):
"""

DELIVERY_EDIT_LIMIT_TEXT = """
✏️ <b>Редактирование лимита</b>

Текущий лимит: {current_limit}
Введите новый лимит (0 — без лимита, 1-999 — ограничение):
"""

DELIVERY_EDIT_NOTE_TEXT = """
✏️ <b>Редактирование примечания</b>

Текущее примечание: {current_note}
Введите новое примечание (или отправьте "-" чтобы удалить):
"""

DELIVERY_CONFIRM_DELETE_TEXT = """
⚠️ <b>Подтверждение удаления</b>

Вы действительно хотите удалить дату доставки:
<b>{date}</b>?

⚠️ <b>Внимание!</b> Если на эту дату есть заказы, они останутся без даты доставки.
Это действие <b>нельзя отменить</b>!
"""

DELIVERY_STATUSES_MAIN_TEXT = """
🚚 <b>Статусы доставки</b>

Статусы нужны для определения стоимости доставки в зависимости от зоны.
Каждый адрес можно прикрепить к определённому статусу (зоне).

<b>Доступные статусы:</b>
{statuses_text}

<i>Статус определяет цену доставки для адреса.</i>
"""

DELIVERY_STATUS_ADD_TEXT = """
➕ <b>Добавление статуса доставки</b>

Введите название статуса (например: "Зона 1", "Центр", "Пригород"):
"""

DELIVERY_STATUS_PRICE_TEXT = """
💰 <b>Цена доставки</b>

Введите стоимость доставки для статуса <b>{name}</b> в рублях:
"""

DELIVERY_STATUS_EDIT_TEXT = """
✏️ <b>Редактирование статуса</b>

<b>Название:</b> {name}
<b>Цена:</b> {price} ₽
<b>Активен:</b> {active}

Выберите действие:
"""

ADDRESSES_MAIN_TEXT = """
📍 <b>Адреса пользователей</b>

Здесь вы можете управлять адресами и присваивать им статусы доставки.
Каждый адрес должен быть привязан к зоне (статусу) для расчёта стоимости.

<b>Статистика:</b>
📍 Всего адресов: {total}
✅ С привязанным статусом: {confirmed}
❌ Без статуса: {unconfirmed}

<b>Список адресов:</b>
{addresses_text}
"""


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def format_date_status(date) -> tuple[str, str]:
    """Форматирует статус даты доставки."""
    if not date.is_available:
        return "❌", "Недоступна (лимит исчерпан)"
    if date.order_limit and date.current_orders >= date.order_limit:
        return "🔴", "Лимит заполнен"
    return "✅", "Доступна"


def format_limit(limit: Optional[int], current: int) -> str:
    """Форматирует лимит заказов."""
    if limit is None:
        return f"{current}/∞"
    return f"{current}/{limit}"


def format_orders_list(orders: List[Dict[str, Any]]) -> str:
    """Форматирует список заказов для вывода."""
    if not orders:
        return "   Нет заказов\n"
    
    text = ""
    for order in orders:
        total = order.get("total", 0)
        text += f"   📦 Заказ #{order['order_id']} — {total} ₽\n"
    return text


def format_address_detailed(address) -> str:
    """
    Форматирует адрес с деталями для отображения в админ-панели.
    """
    if not address:
        return "📍 Адрес не указан"
    
    text = f"📍 <b>{address.get('adress_name', 'Без названия')}</b>\n"
    
    # Формируем основной адрес
    address_parts = []
    if address.get('street'):
        address_parts.append(address['street'])
    if address.get('house'):
        address_parts.append(address['house'])
    
    if address_parts:
        text += f"   📍 {', '.join(address_parts)}\n"
    
    # Добавляем детали
    details = []
    if address.get('building'):
        details.append(f"корп. {address['building']}")
    if address.get('apartment'):
        details.append(f"кв. {address['apartment']}")
    if details:
        text += f"   📍 {', '.join(details)}\n"
    
    # Добавляем дополнительные детали
    extra = []
    if address.get('floor'):
        extra.append(f"этаж {address['floor']}")
    if address.get('entrance'):
        extra.append(f"подъезд {address['entrance']}")
    if address.get('intercom'):
        extra.append(f"домофон {address['intercom']}")
    if extra:
        text += f"   📍 {', '.join(extra)}\n"
    
    # Добавляем комментарий
    if address.get('comment'):
        text += f"   📝 {address['comment']}\n"
    
    # Добавляем координаты
    if address.get('coordinates'):
        text += f"   📍 Координаты: {address['coordinates']}\n"
    
    return text


def can_close_delivery(delivery_date: datetime) -> bool:
    """
    Проверяет, можно ли закрыть доставку (прошло 24 часа после времени доставки).
    """
    now = datetime.now()
    # Время доставки всегда 23:59:59, поэтому проверяем, прошли ли сутки
    close_time = delivery_date + timedelta(days=1)
    return now >= close_time


async def send_admin_notification(
    action: str,
    delivery_date: datetime = None,
    success_count: int = 0,
    failed_count: int = 0,
    remaining: int = 0
) -> None:
    """
    Отправляет уведомление администраторам о массовых операциях с доставкой.
    
    Args:
        action: действие (bulk_move, close_delivery)
        delivery_date: дата доставки
        success_count: количество успешных операций
        failed_count: количество ошибок
        remaining: количество оставшихся заказов
    """
    bot = get_bot_instance()
    date_str = delivery_date.strftime("%d.%m.%Y %H:%M") if delivery_date else ""
    
    if action == "bulk_move":
        text = f"""
📦 <b>Массовый перенос заказов выполнен!</b>

Дата: <b>{date_str}</b>
Перенесено в READY_FOR_DELIVERY: <b>{success_count}</b>
Не перенесено: <b>{failed_count}</b>

👉 Перейдите в раздел <b>"📦 Готовые заказы"</b>.
"""
        callback = "admin_ready_orders"
        
    elif action == "close_delivery":
        text = f"""
✅ <b>Доставка закрыта!</b>

Дата: <b>{date_str}</b>
Завершено заказов: <b>{success_count}</b>
Осталось в READY_FOR_DELIVERY: <b>{remaining}</b>

👉 Перейдите в раздел <b>"📦 Готовые заказы"</b>.
"""
        callback = "admin_ready_orders"
    else:
        return
    
    await notify_admins(
        bot=bot,
        text=text,
        admin_ids=ADMIN_IDS,
        buttons={"🔍 Перейти": callback},
        sizes=[1]
    )


# =============================================================================
# MAIN DELIVERY MENU HANDLER
# =============================================================================

@AdminDeliveryRouter.callback_query(F.data == "delivery_management")
@AdminDeliveryRouter.callback_query(F.data == CALLBACK_DELIVERY_MAIN)
async def show_delivery_main_callback(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Главное меню управления доставкой (из callback).
    """
    await call.answer()
    await send_delivery_main(call, state, session, edit=True)


# =============================================================================
# DELIVERY DATES HANDLERS
# =============================================================================

@AdminDeliveryRouter.callback_query(F.data == CALLBACK_DELIVERY_VIEW_DATES)
async def view_all_dates(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Показывает все даты доставки."""
    await call.answer()
    await show_all_dates(call, state, session, edit=True)


@AdminDeliveryRouter.callback_query(F.data.startswith(CALLBACK_DELIVERY_EDIT_DATE))
async def view_date_detail(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Показывает детали конкретной даты."""
    delivery_id = int(call.data.split("_")[3])
    await show_date_detail(call, state, session, delivery_id)


@AdminDeliveryRouter.callback_query(F.data.startswith(CALLBACK_DELIVERY_VIEW_ORDERS))
async def view_delivery_orders(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Показывает заказы, привязанные к дате доставки.
    Использует новый метод DeliveryRepository.get_delivery_with_orders_count()
    """
    delivery_id = int(call.data.split("_")[3])
    
    delivery_repo = DeliveryRepository(session)
    delivery_info = await delivery_repo.get_delivery_with_orders_count(delivery_id)
    
    if not delivery_info:
        await call.answer("❌ Дата не найдена", show_alert=True)
        return
    
    delivery_date = delivery_info["delivery_date"]
    status_counts = delivery_info["status_counts"]
    
    # Получаем заказы для отображения
    orders = delivery_info["orders"]
    
    accepted_orders = [o for o in orders if o.get("order_status") == OrdersStatus.ACCEPTED.value]
    ready_orders = [o for o in orders if o.get("order_status") == OrdersStatus.READY_FOR_DELIVERY.value]
    
    accepted_list = format_orders_list(accepted_orders)
    ready_list = format_orders_list(ready_orders)
    
    text = DELIVERY_ORDERS_LIST_TEXT.format(
        date=delivery_date.strftime("%d.%m.%Y %H:%M"),
        total=len(orders),
        accepted_count=status_counts.get("accepted", 0),
        ready_count=status_counts.get("ready", 0),
        accepted_list=accepted_list,
        ready_list=ready_list
    )
    
    buttons = {}
    sizes = []
    
    # Кнопка переноса всех ACCEPTED заказов в READY_FOR_DELIVERY
    if accepted_orders:
        buttons[BTN_MOVE_TO_READY] = f"{CALLBACK_DELIVERY_BULK_MOVE_TO_READY}{delivery_id}"
        sizes.append(1)
    
    # Кнопка закрытия доставки (если прошло 5 часов и есть заказы в READY)
    if can_close_delivery(delivery_date) and ready_orders:
        buttons[BTN_CLOSE_DELIVERY] = f"{CALLBACK_DELIVERY_CLOSE}{delivery_id}"
        sizes.append(1)
    
    buttons[BTN_BACK] = CALLBACK_DELIVERY_VIEW_DATES
    sizes.append(1)
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=sizes,
        parse_mode="HTML"
    )


@AdminDeliveryRouter.callback_query(F.data.startswith(CALLBACK_DELIVERY_BULK_MOVE_TO_READY))
async def bulk_move_to_ready_confirm(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Подтверждение массового переноса заказов в READY_FOR_DELIVERY.
    Использует новый метод DeliveryRepository.get_orders_by_delivery_date()
    """
    delivery_id = int(call.data.split("_")[3])
    
    delivery_repo = DeliveryRepository(session)
    delivery_date = await delivery_repo.get_by_id(delivery_id)
    
    if not delivery_date:
        await call.answer("❌ Дата не найдена", show_alert=True)
        return
    
    # Получаем заказы на эту дату
    orders = await delivery_repo.get_orders_by_delivery_date(delivery_id, include_details=True)
    accepted_orders = [o for o in orders if o.get("order_status") == OrdersStatus.ACCEPTED.value]
    
    if not accepted_orders:
        await call.answer("❌ Нет заказов в статусе ACCEPTED", show_alert=True)
        await view_delivery_orders(call, state, session)
        return
    
    orders_list = ""
    for order in accepted_orders:
        total = order.get("total", 0)
        orders_list += f"\n• Заказ #{order['order_id']} — {total} ₽"
    
    text = BULK_MOVE_CONFIRM_TEXT.format(
        count=len(accepted_orders),
        date=delivery_date.delivery_date.strftime("%d.%m.%Y %H:%M"),
        orders_list=orders_list
    )
    
    await state.update_data(bulk_move_delivery_id=delivery_id)
    
    buttons = {
        "✅ Да, перенести": f"confirm_bulk_move_{delivery_id}",
        "❌ Отмена": f"{CALLBACK_DELIVERY_VIEW_ORDERS}{delivery_id}"
    }
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=[1, 1],
        parse_mode="HTML"
    )


@AdminDeliveryRouter.callback_query(F.data.startswith("confirm_bulk_move_"))
async def bulk_move_to_ready_execute(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Выполнение массового переноса заказов в READY_FOR_DELIVERY.
    """
    # Правильный парсинг: confirm_bulk_move_{delivery_id}
    parts = call.data.split("_")
    delivery_id = int(parts[3])  # индекс 3, потому что: confirm, bulk, move, {id}
    
    delivery_repo = DeliveryRepository(session)
    order_repo = OrderRepository(session)
    delivery_date = await delivery_repo.get_by_id(delivery_id)
    
    if not delivery_date:
        await call.answer("❌ Дата не найдена", show_alert=True)
        return
    
    # Получаем заказы на эту дату
    orders = await delivery_repo.get_orders_by_delivery_date(delivery_id, include_details=True)
    accepted_orders = [o for o in orders if o.get("order_status") == OrdersStatus.ACCEPTED.value]
    
    success_count = 0
    failed_count = 0
    
    bot = get_bot_instance()
    
    for order in accepted_orders:
        updated = await order_repo.update_order_status(order["order_id"], OrdersStatus.READY_FOR_DELIVERY)
        
        if updated:
            success_count += 1
            
            # Уведомляем пользователя
            try:
                await bot.send_message(
                    chat_id=order["user_id"],
                    text=f"""
📦 <b>Заказ №{order['order_id']} готов к получению!</b>

Ваш заказ готов. Пожалуйста, подтвердите получение в разделе <b>"🍳 Активные заказы"</b>.

<i>Спасибо, что выбрали нас 🤍</i>
""",
                    parse_mode="HTML"
                )
            except Exception as e:
                ic(f"Error notifying user {order['user_id']}: {e}")
        else:
            failed_count += 1
    
    await session.commit()
    
    # Отправляем уведомление администраторам
    await send_admin_notification(
        action="bulk_move",
        delivery_date=delivery_date.delivery_date,
        success_count=success_count,
        failed_count=failed_count
    )
    
    text = BULK_MOVE_SUCCESS_TEXT.format(
        success=success_count,
        failed=failed_count
    )
    
    buttons = {
        "🔙 Назад": f"{CALLBACK_DELIVERY_VIEW_ORDERS}{delivery_id}"
    }
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=[1],
        parse_mode="HTML"
    )


@AdminDeliveryRouter.callback_query(F.data.startswith("confirm_close_"))
async def close_delivery_execute(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Выполнение закрытия доставки (READY_FOR_DELIVERY → COMPLETED).
    """
    # Правильный парсинг: confirm_close_{delivery_id}
    parts = call.data.split("_")
    delivery_id = int(parts[2])  # индекс 2, потому что: confirm, close, {id}
    
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
    
    # Получаем заказы на эту дату
    orders = await delivery_repo.get_orders_by_delivery_date(delivery_id, include_details=False)
    ready_orders = [o for o in orders if o.get("order_status") == OrdersStatus.READY_FOR_DELIVERY.value]
    
    success_count = 0
    bot = get_bot_instance()
    
    for order in ready_orders:
        updated = await order_repo.update_order_status(order["order_id"], OrdersStatus.COMPLETED)
        
        if updated:
            success_count += 1
            
            # Уведомляем пользователя
            try:
                await bot.send_message(
                    chat_id=order["user_id"],
                    text=f"""
✅ <b>Заказ №{order['order_id']} завершён!</b>

Спасибо, что выбрали нас! Будем рады видеть вас снова 🤍

<i>Заказ передан в историю.</i>
""",
                    parse_mode="HTML"
                )
            except Exception as e:
                ic(f"Error notifying user {order['user_id']}: {e}")
    
    await session.commit()
    
    remaining = len(ready_orders) - success_count
    
    # Отправляем уведомление администраторам
    await send_admin_notification(
        action="close_delivery",
        delivery_date=delivery_date.delivery_date,
        success_count=success_count,
        remaining=remaining
    )
    
    text = CLOSE_DELIVERY_SUCCESS_TEXT.format(
        success=success_count,
        remaining=remaining
    )
    
    buttons = {
        "🔙 К датам доставки": CALLBACK_DELIVERY_VIEW_DATES
    }
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=[1],
        parse_mode="HTML"
    )


# =============================================================================
# ADDRESSES HANDLERS
# =============================================================================

@AdminDeliveryRouter.callback_query(F.data == CALLBACK_DELIVERY_ADDRESSES)
async def show_addresses(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Показывает список адресов пользователей."""
    await call.answer()
    
    address_repo = AddressRepository(session)
    addresses = await address_repo.get_all_with_users()
    
    total = len(addresses)
    confirmed = len([a for a in addresses if a.get("adress_status") is not None])
    unconfirmed = total - confirmed
    
    if addresses:
        addresses_text = ""
        for addr in addresses[:10]:
            status_icon = "✅" if addr.get("adress_status") else "⏳"
            user_name = addr.get("user_name", "Неизвестно")
            
            # Форматируем адрес с деталями
            addresses_text += f"\n{status_icon} <b>{addr['adress_name']}</b>"
            
            # Основной адрес
            address_parts = []
            if addr.get('street'):
                address_parts.append(addr['street'])
            if addr.get('house'):
                address_parts.append(addr['house'])
            if address_parts:
                addresses_text += f"\n   📍 {', '.join(address_parts)}"
            
            # Детали (корпус, квартира)
            details = []
            if addr.get('building'):
                details.append(f"корп. {addr['building']}")
            if addr.get('apartment'):
                details.append(f"кв. {addr['apartment']}")
            if details:
                addresses_text += f"\n   📍 {', '.join(details)}"
            
            # Дополнительные детали (этаж, подъезд, домофон)
            extra = []
            if addr.get('floor'):
                extra.append(f"этаж {addr['floor']}")
            if addr.get('entrance'):
                extra.append(f"подъезд {addr['entrance']}")
            if addr.get('intercom'):
                extra.append(f"домофон {addr['intercom']}")
            if extra:
                addresses_text += f"\n   📍 {', '.join(extra)}"
            
            # Комментарий
            if addr.get('comment'):
                addresses_text += f"\n   📝 {addr['comment']}"
            
            # Пользователь и координаты
            addresses_text += f"\n   👤 {user_name}"
            addresses_text += f"\n   📍 {addr['coordinates']}\n"
            
    else:
        addresses_text = "\n📭 Нет добавленных адресов"
    
    text = ADDRESSES_MAIN_TEXT.format(
        total=total,
        confirmed=confirmed,
        unconfirmed=unconfirmed,
        addresses_text=addresses_text
    )
    
    buttons = {}
    sizes = []
    
    for addr in addresses[:10]:
        status_icon = "✅" if addr.get("adress_status") else "⏳"
        buttons[f"{status_icon} {addr['adress_name']}"] = f"{CALLBACK_DELIVERY_ADDRESS_STATUS}{addr['adress_id']}"
        sizes.append(1)
    
    if len(addresses) > 10:
        buttons["📋 Все адреса"] = CALLBACK_DELIVERY_ALL_ADDRESSES
        sizes.append(1)
    
    buttons[BTN_BACK] = CALLBACK_DELIVERY_MAIN
    sizes.append(1)
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=sizes,
        parse_mode="HTML"
    )


@AdminDeliveryRouter.callback_query(F.data == CALLBACK_DELIVERY_ALL_ADDRESSES)
async def show_all_addresses(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Показывает все адреса (без ограничения 10)."""
    await call.answer()
    
    address_repo = AddressRepository(session)
    addresses = await address_repo.get_all_with_users()
    
    if not addresses:
        await call.answer("📭 Нет адресов", show_alert=True)
        await show_addresses(call, state, session)
        return
    
    text = "📍 <b>Все адреса пользователей</b>\n\n"
    
    for addr in addresses:
        status_icon = "✅" if addr.get("adress_status") else "⏳"
        user_name = addr.get("user_name", "Неизвестно")
        
        text += f"{status_icon} <b>{addr['adress_name']}</b>\n"
        
        # Основной адрес
        address_parts = []
        if addr.get('street'):
            address_parts.append(addr['street'])
        if addr.get('house'):
            address_parts.append(addr['house'])
        if address_parts:
            text += f"   📍 {', '.join(address_parts)}\n"
        
        # Детали (корпус, квартира)
        details = []
        if addr.get('building'):
            details.append(f"корп. {addr['building']}")
        if addr.get('apartment'):
            details.append(f"кв. {addr['apartment']}")
        if details:
            text += f"   📍 {', '.join(details)}\n"
        
        # Дополнительные детали (этаж, подъезд, домофон)
        extra = []
        if addr.get('floor'):
            extra.append(f"этаж {addr['floor']}")
        if addr.get('entrance'):
            extra.append(f"подъезд {addr['entrance']}")
        if addr.get('intercom'):
            extra.append(f"домофон {addr['intercom']}")
        if extra:
            text += f"   📍 {', '.join(extra)}\n"
        
        # Комментарий
        if addr.get('comment'):
            text += f"   📝 {addr['comment']}\n"
        
        text += f"   👤 {user_name}\n"
        text += f"   📍 {addr['coordinates']}\n\n"
    
    buttons = {
        "🔙 Назад": CALLBACK_DELIVERY_ADDRESSES
    }
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=[1],
        parse_mode="HTML"
    )


@AdminDeliveryRouter.callback_query(F.data.startswith(CALLBACK_DELIVERY_ADDRESS_STATUS))
async def edit_address_status(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Редактирование статуса адреса и привязка к зоне доставки."""
    address_id = int(call.data.split("_")[3])
    
    address_repo = AddressRepository(session)
    status_repo = DeliveryStatusRepository(session)
    
    address = await address_repo.get_by_id(address_id)
    statuses = await status_repo.get_all(only_active=True)
    
    if not address:
        await call.answer("❌ Адрес не найден", show_alert=True)
        return
    
    await state.update_data(edit_address_id=address_id)
    
    # Форматируем адрес с деталями для отображения
    address_text = format_address_detailed({
        'adress_name': address.adress_name,
        'street': address.street,
        'house': address.house,
        'building': address.building,
        'apartment': address.apartment,
        'floor': address.floor,
        'entrance': address.entrance,
        'intercom': address.intercom,
        'comment': address.comment,
        'coordinates': address.coordinates
    })
    
    text = f"""
📍 <b>Редактирование адреса</b>

{address_text}

<b>Текущий статус:</b> {address.adress_status or 'Не указан'}

Выберите зону доставки (статус) для этого адреса:
"""
    
    buttons = {}
    sizes = []
    
    for status in statuses:
        buttons[f"🚚 {status.name} — {status.price} ₽"] = f"assign_status_{address_id}_{status.status_id}"
        sizes.append(1)
    
    buttons["❌ Снять статус"] = f"remove_status_{address_id}"
    buttons[BTN_BACK] = CALLBACK_DELIVERY_ADDRESSES
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
# ОСТАЛЬНЫЕ ОБРАБОТЧИКИ (без изменений)
# =============================================================================

async def show_all_dates(
    target: Union[Message, CallbackQuery],
    state: FSMContext,
    session: AsyncSession,
    edit: bool = True
) -> None:
    """
    Показывает все даты доставки для выбора.
    """
    delivery_repo = DeliveryRepository(session)
    all_dates = await delivery_repo.get_all(include_unavailable=True, limit=50)
    
    if not all_dates:
        text = "📭 Нет запланированных дат доставки."
        buttons = {BTN_BACK: CALLBACK_DELIVERY_MAIN}
        sizes = [1]
    else:
        text = DELIVERY_ALL_DATES_TEXT.format(
            dates_list="\n".join([
                f"• {date.delivery_date.strftime('%d.%m.%Y %H:%M')} "
                f"— {format_limit(date.order_limit, date.current_orders)}"
                for date in all_dates[:20]
            ])
        )
        if len(all_dates) > 20:
            text += f"\n\n... и ещё {len(all_dates) - 20} дат"
        
        buttons = {}
        sizes = []
        
        # Кнопки для просмотра деталей и заказов
        for date in all_dates[:15]:
            date_str = date.delivery_date.strftime("%d.%m.%Y %H:%M")
            status_icon, _ = format_date_status(date)
            buttons[f"{status_icon} {date_str}"] = f"{CALLBACK_DELIVERY_EDIT_DATE}{date.delivery_id}"
            sizes.append(1)
            buttons[f"👁 {date_str}"] = f"{CALLBACK_DELIVERY_VIEW_ORDERS}{date.delivery_id}"
            sizes.append(1)
        
        buttons[BTN_BACK] = CALLBACK_DELIVERY_MAIN
        sizes.append(1)
    
    if isinstance(target, CallbackQuery):
        if edit:
            try:
                await target.message.edit_text(
                    text=text,
                    reply_markup=get_callback_btns(btns=buttons, sizes=tuple(sizes)),
                    parse_mode=ParseMode.HTML
                )
            except Exception:
                msg = await target.message.answer(
                    text=text,
                    reply_markup=get_callback_btns(btns=buttons, sizes=tuple(sizes)),
                    parse_mode=ParseMode.HTML
                )
                await target.message.delete()
        else:
            msg = await target.message.answer(
                text=text,
                reply_markup=get_callback_btns(btns=buttons, sizes=tuple(sizes)),
                parse_mode=ParseMode.HTML
            )
        await target.answer()
    else:
        msg = await target.answer(
            text=text,
            reply_markup=get_callback_btns(btns=buttons, sizes=tuple(sizes)),
            parse_mode=ParseMode.HTML
        )
        await target.delete()


async def show_date_detail(
    call: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    delivery_id: int
) -> None:
    """
    Показывает детальную информацию о дате доставки.
    """
    delivery_repo = DeliveryRepository(session)
    date = await delivery_repo.get_by_id(delivery_id)
    
    if not date:
        await call.answer("❌ Дата не найдена", show_alert=True)
        await show_all_dates(call, state, session, edit=True)
        return
    
    status_icon, status_text = format_date_status(date)
    
    text = DELIVERY_DATE_DETAIL_TEXT.format(
        date=date.delivery_date.strftime("%d.%m.%Y %H:%M"),
        status_icon=status_icon,
        status_text=status_text,
        orders=date.current_orders,
        limit=date.order_limit or "∞",
        note=date.note or "Нет"
    )
    
    buttons = {
        "👁 Просмотреть заказы": f"{CALLBACK_DELIVERY_VIEW_ORDERS}{delivery_id}",
        "📊 Изменить лимит": f"edit_date_limit_{delivery_id}",
        "📝 Изменить примечание": f"edit_date_note_{delivery_id}",
        "🔄 Вкл/Выкл": f"toggle_date_{delivery_id}",
        "🗑 Удалить": f"confirm_delete_date_{delivery_id}",
        BTN_BACK: CALLBACK_DELIVERY_VIEW_DATES
    }
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=[1, 1, 1, 1, 1, 1],
        parse_mode="HTML"
    )


# =============================================================================
# ОСТАЛЬНЫЕ ОБРАБОТЧИКИ (без изменений)
# =============================================================================

@AdminDeliveryRouter.callback_query(F.data.startswith("toggle_date_"))
async def toggle_delivery_date(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Включает/выключает доступность даты."""
    delivery_id = int(call.data.split("_")[2])
    
    delivery_repo = DeliveryRepository(session)
    date = await delivery_repo.get_by_id(delivery_id)
    
    if not date:
        await call.answer("❌ Дата не найдена", show_alert=True)
        return
    
    success = await delivery_repo.set_available(delivery_id, not date.is_available)
    
    if success:
        status_text = "доступна" if not date.is_available else "недоступна"
        await call.answer(f"✅ Дата теперь {status_text}", show_alert=False)
    else:
        await call.answer("❌ Ошибка", show_alert=True)
    
    await show_date_detail(call, state, session, delivery_id)


@AdminDeliveryRouter.callback_query(F.data.startswith("edit_date_limit_"))
async def edit_date_limit_start(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Начало редактирования лимита даты."""
    delivery_id = int(call.data.split("_")[3])
    
    delivery_repo = DeliveryRepository(session)
    date = await delivery_repo.get_by_id(delivery_id)
    
    if not date:
        await call.answer("❌ Дата не найдена", show_alert=True)
        return
    
    await state.update_data(edit_delivery_id=delivery_id)
    await state.set_state(user_states.AdminPanel.edit_delivery_limit)
    
    current_limit = date.order_limit if date.order_limit is not None else 0
    
    await send_clean_message(
        target=call,
        text=DELIVERY_EDIT_LIMIT_TEXT.format(current_limit=current_limit),
        buttons={BTN_CANCEL: f"{CALLBACK_DELIVERY_EDIT_DATE}{delivery_id}"},
        sizes=[1],
        parse_mode="HTML"
    )


@AdminDeliveryRouter.message(StateFilter(user_states.AdminPanel.edit_delivery_limit))
async def edit_date_limit_save(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Сохранение нового лимита."""
    data = await state.get_data()
    delivery_id = data.get("edit_delivery_id")
    
    try:
        limit = int(message.text.strip())
        if limit < 0:
            raise ValueError
        order_limit = limit if limit > 0 else None
    except ValueError:
        await send_clean_message(
            target=message,
            text="❌ Введите число (0 — без лимита, 1-999 — ограничение)",
            buttons={BTN_CANCEL: f"{CALLBACK_DELIVERY_EDIT_DATE}{delivery_id}"},
            sizes=[1],
            parse_mode="HTML"
        )
        return
    
    delivery_repo = DeliveryRepository(session)
    success = await delivery_repo.update(delivery_id, order_limit=order_limit)
    
    if success:
        await send_clean_message(
            target=message,
            text="✅ Лимит обновлён!",
            buttons={BTN_BACK: f"{CALLBACK_DELIVERY_EDIT_DATE}{delivery_id}"},
            sizes=[1],
            parse_mode="HTML"
        )
    else:
        await send_clean_message(
            target=message,
            text="❌ Ошибка при обновлении",
            buttons={BTN_BACK: f"{CALLBACK_DELIVERY_EDIT_DATE}{delivery_id}"},
            sizes=[1],
            parse_mode="HTML"
        )
    
    await state.clear()


@AdminDeliveryRouter.callback_query(F.data.startswith("edit_date_note_"))
async def edit_date_note_start(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Начало редактирования примечания даты."""
    delivery_id = int(call.data.split("_")[3])
    
    delivery_repo = DeliveryRepository(session)
    date = await delivery_repo.get_by_id(delivery_id)
    
    if not date:
        await call.answer("❌ Дата не найдена", show_alert=True)
        return
    
    await state.update_data(edit_delivery_id=delivery_id)
    await state.set_state(user_states.AdminPanel.edit_delivery_note)
    
    await send_clean_message(
        target=call,
        text=DELIVERY_EDIT_NOTE_TEXT.format(current_note=date.note or "Нет"),
        buttons={BTN_CANCEL: f"{CALLBACK_DELIVERY_EDIT_DATE}{delivery_id}"},
        sizes=[1],
        parse_mode="HTML"
    )


@AdminDeliveryRouter.message(StateFilter(user_states.AdminPanel.edit_delivery_note))
async def edit_date_note_save(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Сохранение нового примечания."""
    data = await state.get_data()
    delivery_id = data.get("edit_delivery_id")
    
    note = None if message.text.strip() == "-" else message.text.strip()
    
    delivery_repo = DeliveryRepository(session)
    success = await delivery_repo.update(delivery_id, note=note)
    
    if success:
        await send_clean_message(
            target=message,
            text="✅ Примечание обновлено!",
            buttons={BTN_BACK: f"{CALLBACK_DELIVERY_EDIT_DATE}{delivery_id}"},
            sizes=[1],
            parse_mode="HTML"
        )
    else:
        await send_clean_message(
            target=message,
            text="❌ Ошибка при обновлении",
            buttons={BTN_BACK: f"{CALLBACK_DELIVERY_EDIT_DATE}{delivery_id}"},
            sizes=[1],
            parse_mode="HTML"
        )
    
    await state.clear()


@AdminDeliveryRouter.callback_query(F.data.startswith("confirm_delete_date_"))
async def confirm_delete_date(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Подтверждение удаления даты."""
    delivery_id = int(call.data.split("_")[3])
    
    delivery_repo = DeliveryRepository(session)
    date = await delivery_repo.get_by_id(delivery_id)
    
    if not date:
        await call.answer("❌ Дата не найдена", show_alert=True)
        return
    
    await state.update_data(delete_delivery_id=delivery_id)
    
    text = DELIVERY_CONFIRM_DELETE_TEXT.format(
        date=date.delivery_date.strftime("%d.%m.%Y %H:%M")
    )
    
    buttons = {
        "✅ Да, удалить": f"delete_date_{delivery_id}",
        "❌ Нет, отмена": f"{CALLBACK_DELIVERY_EDIT_DATE}{delivery_id}"
    }
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=[1, 1],
        parse_mode="HTML"
    )


@AdminDeliveryRouter.callback_query(F.data.startswith("delete_date_"))
async def delete_delivery_date(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Удаление даты доставки."""
    delivery_id = int(call.data.split("_")[2])
    
    delivery_repo = DeliveryRepository(session)
    success = await delivery_repo.delete(delivery_id, force=True)
    
    if success:
        await call.answer("✅ Дата удалена", show_alert=False)
        await show_all_dates(call, state, session, edit=True)
    else:
        await call.answer("❌ Не удалось удалить (есть заказы?)", show_alert=True)
        await show_date_detail(call, state, session, delivery_id)


@AdminDeliveryRouter.callback_query(F.data == CALLBACK_DELIVERY_ADD_DATE)
async def add_delivery_date_start(call: CallbackQuery, state: FSMContext) -> None:
    """Начало добавления даты доставки."""
    await state.set_state(user_states.AdminPanel.add_delivery_date)
    
    await send_clean_message(
        target=call,
        text=DELIVERY_ADD_DATE_TEXT,
        buttons={BTN_CANCEL: CALLBACK_DELIVERY_MAIN},
        sizes=[1],
        parse_mode="HTML"
    )


@AdminDeliveryRouter.message(StateFilter(user_states.AdminPanel.add_delivery_date))
async def add_delivery_date_limit(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Запрос лимита для даты доставки."""
    if message.text.strip() == BTN_CANCEL:
        await state.clear()
        await send_delivery_main(message, state, session, edit=False)
        return
    
    try:
        # Парсим дату (без времени или с временем)
        if " " in message.text.strip():
            delivery_date = datetime.strptime(message.text.strip(), "%d.%m.%Y %H:%M")
        else:
            delivery_date = datetime.strptime(message.text.strip(), "%d.%m.%Y")
        
        # ✅ Устанавливаем время на 23:59:59
        delivery_date = delivery_date.replace(hour=23, minute=59, second=59, microsecond=0)
        
    except ValueError:
        await send_clean_message(
            target=message,
            text="❌ Неверный формат. Используйте: <i>25.03.2026</i> или <i>25.03.2026</i>",
            buttons={BTN_CANCEL: CALLBACK_DELIVERY_MAIN},
            sizes=[1],
            parse_mode="HTML"
        )
        return
    
    # Проверяем, что дата не в прошлом
    if delivery_date < datetime.now():
        await send_clean_message(
            target=message,
            text="❌ Дата не может быть в прошлом",
            buttons={BTN_CANCEL: CALLBACK_DELIVERY_MAIN},
            sizes=[1],
            parse_mode="HTML"
        )
        return
    
    await state.update_data(delivery_date=delivery_date.isoformat())
    await state.set_state(user_states.AdminPanel.add_delivery_limit)
    
    await send_clean_message(
        target=message,
        text=DELIVERY_ADD_LIMIT_TEXT,
        buttons={BTN_CANCEL: CALLBACK_DELIVERY_MAIN},
        sizes=[1],
        parse_mode="HTML"
    )


@AdminDeliveryRouter.message(StateFilter(user_states.AdminPanel.add_delivery_limit))
async def save_delivery_date(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Сохранение даты доставки."""
    data = await state.get_data()
    delivery_date = datetime.fromisoformat(data.get('delivery_date'))
    
    try:
        limit = int(message.text.strip())
        if limit < 0:
            raise ValueError
        order_limit = limit if limit > 0 else None
    except ValueError:
        await send_clean_message(
            target=message,
            text="❌ Введите число (0 — без лимита, 1-999 — ограничение)",
            buttons={BTN_CANCEL: CALLBACK_DELIVERY_MAIN},
            sizes=[1],
            parse_mode="HTML"
        )
        return
    
    delivery_repo = DeliveryRepository(session)
    result = await delivery_repo.create(delivery_date, order_limit)
    
    if result:
        await send_clean_message(
            target=message,
            text=f"✅ Дата <b>{delivery_date.strftime('%d.%m.%Y %H:%M')}</b> добавлена!",
            buttons={"🔙 К доставке": CALLBACK_DELIVERY_MAIN},
            sizes=[1],
            parse_mode="HTML"
        )
    else:
        await send_clean_message(
            target=message,
            text="❌ Ошибка при добавлении даты",
            buttons={"🔙 К доставке": CALLBACK_DELIVERY_MAIN},
            sizes=[1],
            parse_mode="HTML"
        )
    
    await state.clear()


@AdminDeliveryRouter.callback_query(F.data == CALLBACK_DELIVERY_GENERATE)
async def generate_delivery_dates(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Автоматическая генерация дат на 14 дней."""
    await call.answer("⏳ Генерируем даты...")
    
    delivery_repo = DeliveryRepository(session)
    created = await delivery_repo.auto_generate(days_ahead=14, default_limit=20)
    
    await call.answer(f"✅ Добавлено {created} дат", show_alert=True)
    await send_delivery_main(call, state, session, edit=True)


# =============================================================================
# DELIVERY STATUSES HANDLERS
# =============================================================================

@AdminDeliveryRouter.callback_query(F.data == CALLBACK_DELIVERY_STATUSES)
async def show_delivery_statuses_callback(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Показывает список статусов доставки (из callback)."""
    await call.answer()
    await send_delivery_statuses(call, state, session, edit=True)


@AdminDeliveryRouter.callback_query(F.data == CALLBACK_DELIVERY_STATUS_ADD)
async def add_delivery_status_start(call: CallbackQuery, state: FSMContext) -> None:
    """Начало добавления статуса доставки."""
    await state.set_state(user_states.AdminPanel.add_delivery_status_name)
    
    await send_clean_message(
        target=call,
        text=DELIVERY_STATUS_ADD_TEXT,
        buttons={BTN_CANCEL: CALLBACK_DELIVERY_STATUSES},
        sizes=[1],
        parse_mode="HTML"
    )


@AdminDeliveryRouter.message(StateFilter(user_states.AdminPanel.add_delivery_status_name))
async def add_delivery_status_price(
    message: Message, 
    state: FSMContext, 
    session: AsyncSession
) -> None:
    """Запрос цены статуса."""
    name = message.text.strip()
    
    if name == BTN_CANCEL:
        await state.clear()
        await send_delivery_statuses(message, state, session, edit=False)
        return
    
    await state.update_data(status_name=name)
    await state.set_state(user_states.AdminPanel.add_delivery_status_price)
    
    await send_clean_message(
        target=message,
        text=DELIVERY_STATUS_PRICE_TEXT.format(name=name),
        buttons={BTN_CANCEL: CALLBACK_DELIVERY_STATUSES},
        sizes=[1],
        parse_mode="HTML"
    )


@AdminDeliveryRouter.message(StateFilter(user_states.AdminPanel.add_delivery_status_price))
async def save_delivery_status(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Сохранение статуса доставки."""
    data = await state.get_data()
    name = data.get("status_name")
    
    try:
        price = int(message.text.strip())
        if price < 0:
            raise ValueError
    except ValueError:
        await send_clean_message(
            target=message,
            text="❌ Введите корректную цену (только цифры, неотрицательное число)",
            buttons={BTN_CANCEL: CALLBACK_DELIVERY_STATUSES},
            sizes=[1],
            parse_mode="HTML"
        )
        return
    
    status_repo = DeliveryStatusRepository(session)
    result = await status_repo.create(name=name, price=price)
    
    if result:
        await send_clean_message(
            target=message,
            text=f"✅ Статус <b>{name}</b> добавлен! Цена: {price} ₽",
            buttons={"🔙 К статусам": CALLBACK_DELIVERY_STATUSES},
            sizes=[1],
            parse_mode="HTML"
        )
    else:
        await send_clean_message(
            target=message,
            text="❌ Ошибка при добавлении статуса",
            buttons={"🔙 К статусам": CALLBACK_DELIVERY_STATUSES},
            sizes=[1],
            parse_mode="HTML"
        )
    
    await state.clear()


@AdminDeliveryRouter.callback_query(F.data.startswith(CALLBACK_DELIVERY_STATUS_EDIT))
async def edit_delivery_status_start(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Начало редактирования статуса доставки."""
    status_id = int(call.data.split("_")[3])
    
    status_repo = DeliveryStatusRepository(session)
    status = await status_repo.get_by_id(status_id)
    
    if not status:
        await call.answer("❌ Статус не найден", show_alert=True)
        return
    
    await state.update_data(edit_status_id=status_id)
    await state.set_state(user_states.AdminPanel.edit_delivery_status)
    
    active_text = "✅ Да" if status.is_active else "❌ Нет"
    
    text = DELIVERY_STATUS_EDIT_TEXT.format(
        name=status.name,
        price=status.price,
        active=active_text
    )
    
    buttons = {
        "📝 Изменить название": f"edit_status_name_{status_id}",
        "💰 Изменить цену": f"edit_status_price_{status_id}",
        "🔄 Вкл/Выкл": f"toggle_status_{status_id}",
        "🗑 Удалить": f"delete_status_{status_id}",
        BTN_BACK: CALLBACK_DELIVERY_STATUSES
    }
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=[1, 1, 1, 1, 1],
        parse_mode="HTML"
    )


@AdminDeliveryRouter.callback_query(F.data.startswith("toggle_status_"))
async def toggle_delivery_status(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Включает/выключает статус доставки."""
    status_id = int(call.data.split("_")[2])
    
    status_repo = DeliveryStatusRepository(session)
    success = await status_repo.toggle_active(status_id)
    
    if success:
        await call.answer("✅ Статус обновлён", show_alert=False)
    else:
        await call.answer("❌ Ошибка", show_alert=True)
    
    await send_delivery_statuses(call, state, session, edit=True)


async def send_delivery_main(
    target: Union[Message, CallbackQuery],
    state: FSMContext,
    session: AsyncSession,
    edit: bool = True
) -> None:
    """
    Отправляет или редактирует главное меню доставки.
    """
    delivery_repo = DeliveryRepository(session)
    status_repo = DeliveryStatusRepository(session)
    address_repo = AddressRepository(session)
    
    upcoming_dates = await delivery_repo.get_upcoming(days=7)
    
    if upcoming_dates:
        dates_text = ""
        for date in upcoming_dates[:5]:
            date_str = date.delivery_date.strftime("%d.%m.%Y %H:%M")
            status_icon, _ = format_date_status(date)
            orders_info = format_limit(date.order_limit, date.current_orders)
            dates_text += f"\n{status_icon} {date_str} — заказов: {orders_info}"
        
        if len(upcoming_dates) > 5:
            dates_text += f"\n... и ещё {len(upcoming_dates) - 5}"
    else:
        dates_text = "\n📭 Нет запланированных дат"
    
    stats = await delivery_repo.get_stats()
    addresses = await address_repo.get_all()
    statuses = await status_repo.get_all()
    
    text = DELIVERY_MAIN_TEXT.format(
        dates_text=dates_text,
        total_dates=stats["total"],
        available_dates=stats["available"],
        addresses_count=len(addresses),
        statuses_count=len(statuses)
    )
    
    buttons = {
        BTN_ADD_DATE: CALLBACK_DELIVERY_ADD_DATE,
        BTN_VIEW_DATES: CALLBACK_DELIVERY_VIEW_DATES,
        BTN_GENERATE: CALLBACK_DELIVERY_GENERATE,
        BTN_STATUSES: CALLBACK_DELIVERY_STATUSES,
        BTN_ADDRESSES: CALLBACK_DELIVERY_ADDRESSES,
        BTN_BACK: "back_to_admin_panel"
    }
    sizes = [1, 1, 1, 1, 1, 1]
    
    if isinstance(target, CallbackQuery):
        if edit:
            try:
                await target.message.edit_text(
                    text=text,
                    reply_markup=get_callback_btns(btns=buttons, sizes=tuple(sizes)),
                    parse_mode=ParseMode.HTML
                )
            except Exception:
                msg = await target.message.answer(
                    text=text,
                    reply_markup=get_callback_btns(btns=buttons, sizes=tuple(sizes)),
                    parse_mode=ParseMode.HTML
                )
                await target.message.delete()
        else:
            msg = await target.message.answer(
                text=text,
                reply_markup=get_callback_btns(btns=buttons, sizes=tuple(sizes)),
                parse_mode=ParseMode.HTML
            )
        await target.answer()
    else:
        msg = await target.answer(
            text=text,
            reply_markup=get_callback_btns(btns=buttons, sizes=tuple(sizes)),
            parse_mode=ParseMode.HTML
        )
        await target.delete()
        
        user_id = target.from_user.id
        await message_delete(user_id, last_message_dict)
        if user_id not in last_message_dict:
            last_message_dict[user_id] = []
        last_message_dict[user_id].append(msg.message_id)


async def send_delivery_statuses(
    target: Union[Message, CallbackQuery],
    state: FSMContext,
    session: AsyncSession,
    edit: bool = True
) -> None:
    """Универсальная функция для отправки списка статусов доставки."""
    status_repo = DeliveryStatusRepository(session)
    statuses = await status_repo.get_all()
    
    if statuses:
        statuses_text = ""
        for status in statuses:
            status_icon = "✅" if status.is_active else "❌"
            statuses_text += f"\n{status_icon} <b>{status.name}</b> — {status.price} ₽"
    else:
        statuses_text = "\n📭 Нет добавленных статусов"
    
    text = DELIVERY_STATUSES_MAIN_TEXT.format(statuses_text=statuses_text)
    
    buttons = {
        "➕ Добавить статус": CALLBACK_DELIVERY_STATUS_ADD,
        BTN_BACK: CALLBACK_DELIVERY_MAIN
    }
    sizes = [1, 1]
    
    if isinstance(target, CallbackQuery):
        if edit:
            try:
                await target.message.edit_text(
                    text=text,
                    reply_markup=get_callback_btns(btns=buttons, sizes=tuple(sizes)),
                    parse_mode=ParseMode.HTML
                )
            except Exception:
                msg = await target.message.answer(
                    text=text,
                    reply_markup=get_callback_btns(btns=buttons, sizes=tuple(sizes)),
                    parse_mode=ParseMode.HTML
                )
                await target.message.delete()
        else:
            msg = await target.message.answer(
                text=text,
                reply_markup=get_callback_btns(btns=buttons, sizes=tuple(sizes)),
                parse_mode=ParseMode.HTML
            )
        await target.answer()
    else:
        msg = await target.answer(
            text=text,
            reply_markup=get_callback_btns(btns=buttons, sizes=tuple(sizes)),
            parse_mode=ParseMode.HTML
        )
        await target.delete()