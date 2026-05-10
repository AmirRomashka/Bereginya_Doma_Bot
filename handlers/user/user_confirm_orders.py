"""
User Confirm Orders Module
==========================

This module handles orders that are waiting for user confirmation and payment.
After address status is assigned by admin, user can select delivery date and time range, then pay.
"""

from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta

from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.enums.parse_mode import ParseMode

from icecream import ic
from sqlalchemy.ext.asyncio import AsyncSession

from States import user_states
from database.enumirate.orders_enum import OrdersStatus
from database.orm_query.orders_orm import OrderRepository
from database.orm_query.address_orm import AddressRepository
from database.orm_query.delivery_orm import DeliveryRepository
from database.orm_query.delivery_status_orm import DeliveryStatusRepository
from keybords.inline import get_callback_btns
from tools import send_clean_message


# =============================================================================
# ROUTER INITIALIZATION
# =============================================================================

UserConfirmOrdersRouter = Router(name="user_confirm_orders")


# =============================================================================
# CONSTANTS
# =============================================================================

# -----------------------------------------------------------------------------
# Navigation callbacks
# -----------------------------------------------------------------------------
CALLBACK_CONFIRM_ORDERS = "confirm_orders"
CALLBACK_SELECT_ORDER = "select_order_"
CALLBACK_SELECT_DELIVERY_DATE = "confirm_select_delivery_date_"
CALLBACK_BACK_TO_CONFIRM_ORDERS = "back_to_confirm_orders"
CALLBACK_SKIP_COMMENT = "skip_comment"
CALLBACK_BACK_TO_MENU = "back_to_user_menu"
CALLBACK_MAIN_MENU = "main_menu"

# Callback для выбора временного диапазона
CALLBACK_SELECT_HOUR = "confirm_select_hour_"
CALLBACK_RESET_HOURS = "confirm_reset_hours"
CALLBACK_CONFIRM_TIME_RANGE = "confirm_time_range"
CALLBACK_BACK_TO_DATES = "confirm_back_to_dates"

# -----------------------------------------------------------------------------
# Button text constants — понятные и тёплые
# -----------------------------------------------------------------------------
BUTTON_TEXT = {
    "skip_comment": "⏭ Без пожеланий",
    "back_to_menu": "🍰 В меню",
    "main_menu": "🏠 Главная",
    "select_time": "🕐 Выбрать время"
}

# -----------------------------------------------------------------------------
# Messages
# -----------------------------------------------------------------------------

CONFIRM_ORDERS_EMPTY = """
📭 <b>Нет заказов на оплату</b>

Когда администратор проверит адрес доставки, заказы появятся здесь.
Мы пришлём уведомление 🤍

<i>А пока можно посмотреть меню 🥐</i>
"""

CONFIRM_ORDERS_TEXT = """
✅ <b>Заказы, готовые к оплате</b>

Выберите, какой заказ оплачиваем:
"""

ORDER_SELECT_TEXT = """
📦 <b>Заказ №{order_id}</b> от {date}

📍 <b>Адрес:</b> {address}
💰 <b>Сумма заказа:</b> {order_total} ₽
🚚 <b>Зона доставки:</b> {delivery_zone}
💵 <b>Доставка:</b> {delivery_price} ₽

<b>Итого к оплате:</b> {final_total} ₽

<i>Выберите дату и время доставки 🤍</i>
"""

DELIVERY_DATE_SELECT_TEXT = """
📅 <b>Когда привезти?</b>

Для заказа №{order_id} выберите удобный день:

{delivery_dates}
"""

DELIVERY_DATE_CONFIRM_TEXT = """
✅ <b>Вы выбрали:</b> {date}

В этот день у нас уже заказов: {orders}/{limit}

Продолжим?
"""

# -----------------------------------------------------------------------------
# Time range messages
# -----------------------------------------------------------------------------

TIME_RANGE_SELECT_PROMPT = """
🕐 <b>Удобное время доставки</b>

📅 <b>Дата:</b> {date}
📦 <b>Заказ №{order_id}</b>

Нажмите на <b>два часа</b> — начало и конец.
Мы приедем в этот промежуток.

<b>Вы выбрали:</b> {selected_range}

{hours_buttons}

<i>• «Сбросить» — начать заново</i>
<i>• «Подтвердить» — запомнить время</i>
"""

TIME_RANGE_CONFIRM_TEXT = """
✅ <b>Время запомнили!</b>

📅 {date}, с {time_range}

Теперь перейдём к оплате 🤍
"""

PAYMENT_TEXT = """
💳 <b>Оплата заказа №{order_id}</b>

<b>Сумма:</b> {total} ₽

<b>Реквизиты:</b>
━━━━━━━━━━━━━━━━━━━━━
💳 <b>Счёт:</b> 2200700115185265
🏛 <b>Банк:</b> Т-Банк
📱 <b>Сумма:</b> {total} ₽
━━━━━━━━━━━━━━━━━━━━━

После оплаты отправьте фото чека — и мы начнём готовить 🤍
"""

COMMENT_PROMPT = """
📝 <b>Пожелания к заказу</b>

Хотите что-то добавить?
• Без лука
• Позвонить перед доставкой
• Побыстрее, если получится

Или просто нажмите «Без пожеланий» 🤍
"""

ORDER_CONFIRMED = """
✅ <b>Заказ №{order_id} принят в работу!</b>

Скоро с вами свяжется наш менеджер.

<b>Состав:</b>
{items_text}

<b>Адрес доставки:</b>
{address_text}

<b>Дата:</b> {delivery_date_text}
<b>Время:</b> {delivery_time_range}
<b>Итого:</b> {total} ₽

<i>Спасибо! Готовим с любовью 🤍</i>
"""


# =============================================================================
# ВРЕМЕННОЕ ХРАНИЛИЩЕ ДЛЯ ВЫБОРА ЧАСОВ
# =============================================================================

_temp_hour_selection: Dict[int, Dict] = {}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def clear_temp_selection(user_id: int) -> None:
    """Очищает временные данные выбора часов для пользователя."""
    if user_id in _temp_hour_selection:
        del _temp_hour_selection[user_id]


def get_hour_buttons(selected_start: int = None, selected_end: int = None) -> tuple[dict, list]:
    """Создаёт кнопки для часов 9-20 с визуализацией выбранного диапазона."""
    buttons = {}
    sizes = []
    row = []
    
    for hour in range(9, 21):
        is_in_range = False
        if selected_start is not None and selected_end is not None:
            if selected_start <= selected_end:
                is_in_range = selected_start <= hour <= selected_end
            else:
                is_in_range = hour >= selected_start or hour <= selected_end
        
        if is_in_range:
            emoji = "✅"
        elif hour == selected_start:
            emoji = "🔵"
        elif hour == selected_end:
            emoji = "🔵"
        else:
            emoji = "⚪"
        
        button_text = f"{emoji} {hour}:00"
        buttons[button_text] = f"{CALLBACK_SELECT_HOUR}{hour}"
        row.append(button_text)
        
        if len(row) == 4:
            sizes.append(4)
            row = []
    
    if row:
        sizes.append(len(row))
    
    return buttons, sizes


def format_order_date(date: datetime) -> str:
    """Форматирует дату заказа."""
    return date.strftime("%d.%m.%Y")


def format_delivery_date(date) -> str:
    """Форматирует дату доставки."""
    return date.delivery_date.strftime("%d.%m.%Y")


def format_delivery_time_range(hour_from: int, hour_to: int = None) -> str:
    """Форматирует временной диапазон."""
    if hour_to and hour_to != hour_from:
        return f"{hour_from}:00 - {hour_to}:00"
    return f"{hour_from}:00"


def get_delivery_status_icon(date) -> tuple[str, str]:
    """Возвращает иконку и текст статуса даты доставки."""
    if not date.is_available:
        return "❌", "Недоступна"
    if date.order_limit and date.current_orders >= date.order_limit:
        return "🔴", "Лимит"
    return "✅", "Свободно"


def format_address_text(address) -> str:
    """Форматирует адрес для отображения."""
    if not address:
        return "📍 Адрес не указан"
    return f"📍 <b>{address.adress_name}</b>"


async def get_user_confirm_orders(session: AsyncSession, user_id: int) -> List:
    """Получает заказы пользователя, готовые к подтверждению."""
    order_repo = OrderRepository(session=session, user_id=user_id)
    address_repo = AddressRepository(session)
    
    awaiting_orders = await order_repo.get_orders_by_user_and_status(OrdersStatus.AWAITING_ADDRESS_STATUS)
    
    ready_orders = []
    for order in awaiting_orders:
        if order.address_id:
            address = await address_repo.get_by_id(order.address_id)
            if address and address.adress_status:
                ready_orders.append(order)
    
    ready_orders.sort(key=lambda x: x.created, reverse=True)
    return ready_orders


async def get_order_with_details(session: AsyncSession, order_id: int) -> Dict[str, Any]:
    """Получает детальную информацию о заказе с расчётом стоимости доставки."""
    order_repo = OrderRepository(session=session)
    order_details = await order_repo.get_order_with_details(order_id)
    
    if not order_details:
        return None
    
    address_repo = AddressRepository(session)
    address = None
    delivery_zone = "Не определена"
    delivery_price = 0
    
    if order_details.get('address_id'):
        address = await address_repo.get_by_id(order_details['address_id'])
        if address and address.adress_status:
            status_repo = DeliveryStatusRepository(session)
            status = await status_repo.get_by_id(int(address.adress_status))
            if status:
                delivery_zone = status.name
                delivery_price = status.price
    
    order_total = order_details['total']
    final_total = order_total + delivery_price
    
    return {
        **order_details,
        'address': address,
        'delivery_zone': delivery_zone,
        'delivery_price': delivery_price,
        'order_total': order_total,
        'final_total': final_total
    }


# =============================================================================
# HANDLERS
# =============================================================================

@UserConfirmOrdersRouter.callback_query(F.data == CALLBACK_CONFIRM_ORDERS)
async def show_confirm_orders(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Показывает заказы, готовые к подтверждению и оплате."""
    user_id = call.from_user.id
    
    clear_temp_selection(user_id)
    await state.set_state(user_states.UserMenu.confirm_orders)
    
    orders = await get_user_confirm_orders(session, user_id)
    
    if not orders:
        await send_clean_message(
            target=call,
            text=CONFIRM_ORDERS_EMPTY,
            buttons={
                "🍰 В меню": CALLBACK_BACK_TO_MENU,
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
        button_text = f"{i}. Заказ №{order.order_id} — {format_order_date(order.created)} — {total} ₽"
        buttons[button_text] = f"{CALLBACK_SELECT_ORDER}{order.order_id}"
        sizes.append(1)
    
    buttons["🔙 Назад"] = CALLBACK_BACK_TO_MENU
    sizes.append(1)
    
    await send_clean_message(
        target=call,
        text=CONFIRM_ORDERS_TEXT,
        buttons=buttons,
        sizes=sizes,
        parse_mode="HTML"
    )


@UserConfirmOrdersRouter.callback_query(F.data.startswith(CALLBACK_SELECT_ORDER))
async def select_order(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Выбор заказа для оплаты."""
    parts = call.data.split("_")
    
    if len(parts) < 3 or not parts[2]:
        await call.answer("❌ Ошибка", show_alert=True)
        return
    
    try:
        order_id = int(parts[2])
    except ValueError:
        await call.answer("❌ Неверный ID заказа", show_alert=True)
        return
    
    order_details = await get_order_with_details(session, order_id)
    
    if not order_details:
        await call.answer("❌ Заказ не найден", show_alert=True)
        return
    
    await state.set_state(user_states.UserMenu.confirm_order_detail)
    await state.update_data(
        confirm_order_id=order_id,
        confirm_address_id=order_details.get('address_id')
    )
    
    address_text = format_address_text(order_details['address'])
    
    text = ORDER_SELECT_TEXT.format(
        order_id=order_details['order_id'],
        date=format_order_date(order_details['created']),
        address=address_text,
        order_total=order_details['order_total'],
        delivery_zone=order_details['delivery_zone'],
        delivery_price=order_details['delivery_price'],
        final_total=order_details['final_total']
    )
    
    buttons = {
        "📅 Выбрать дату": f"{CALLBACK_SELECT_DELIVERY_DATE}{order_id}",
        "🔙 К списку заказов": CALLBACK_CONFIRM_ORDERS
    }
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=[1, 1],
        parse_mode="HTML"
    )


# =============================================================================
# DELIVERY DATE SELECTION HANDLERS
# =============================================================================

@UserConfirmOrdersRouter.callback_query(
    F.data.startswith(CALLBACK_SELECT_DELIVERY_DATE),
    StateFilter(user_states.UserMenu.confirm_order_detail)
)
async def select_delivery_date(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Выбор даты доставки для заказа."""
    callback_data = call.data
    
    if callback_data.startswith(CALLBACK_SELECT_DELIVERY_DATE):
        order_id_str = callback_data[len(CALLBACK_SELECT_DELIVERY_DATE):]
    else:
        await call.answer("❌ Ошибка", show_alert=True)
        return
    
    if not order_id_str:
        await call.answer("❌ Ошибка", show_alert=True)
        return
    
    try:
        order_id = int(order_id_str)
    except ValueError:
        await call.answer("❌ Неверный ID заказа", show_alert=True)
        return
    
    await state.set_state(user_states.UserMenu.confirm_order_delivery_date)
    await state.update_data(confirm_order_id=order_id)
    
    delivery_repo = DeliveryRepository(session)
    available_dates = await delivery_repo.get_available_dates(min_hours_ahead=2)
    
    if not available_dates:
        await send_clean_message(
            target=call,
            text="📭 К сожалению, нет свободных дат. Попробуйте позже 🤍",
            buttons={
                "🔙 К заказу": f"{CALLBACK_SELECT_ORDER}{order_id}",
                "🏠 Главная": CALLBACK_MAIN_MENU
            },
            sizes=[1, 1],
            parse_mode="HTML"
        )
        return
    
    dates_list = ""
    buttons = {}
    sizes = []
    
    for date in available_dates[:10]:
        date_str = format_delivery_date(date)
        status_icon, status_text = get_delivery_status_icon(date)
        limit_info = f"{date.current_orders}/{date.order_limit or '∞'}"
        
        dates_list += f"\n• {status_icon} {date_str} — заказов: {limit_info}"
        buttons[f"{status_icon} {date_str}"] = f"confirm_delivery_date_{order_id}_{date.delivery_id}"
        sizes.append(1)
    
    if len(available_dates) > 10:
        dates_list += f"\n... и ещё {len(available_dates) - 10} дат"
    
    text = DELIVERY_DATE_SELECT_TEXT.format(
        order_id=order_id,
        delivery_dates=dates_list
    )
    
    buttons["🔙 К заказу"] = f"{CALLBACK_SELECT_ORDER}{order_id}"
    sizes.append(1)
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=sizes,
        parse_mode="HTML"
    )


@UserConfirmOrdersRouter.callback_query(
    F.data.startswith("confirm_delivery_date_"),
    StateFilter(user_states.UserMenu.confirm_order_delivery_date)
)
async def confirm_delivery_date(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Подтверждение выбранной даты доставки и переход к выбору времени."""
    parts = call.data.split("_")
    
    if len(parts) < 5:
        await call.answer("❌ Ошибка формата", show_alert=True)
        return
    
    if not parts[3] or not parts[4]:
        await call.answer("❌ Ошибка данных", show_alert=True)
        return
    
    try:
        order_id = int(parts[3])
        delivery_id = int(parts[4])
    except ValueError:
        await call.answer("❌ Неверный ID", show_alert=True)
        return
    
    order_repo = OrderRepository(session=session)
    order = await order_repo.get_order_by_id(order_id)
    
    if not order:
        await call.answer("❌ Заказ не найден", show_alert=True)
        return
    
    if order.order_status != OrdersStatus.AWAITING_ADDRESS_STATUS.value:
        await call.answer(f"❌ Заказ №{order_id} не готов к оплате", show_alert=True)
        return
    
    user_id = call.from_user.id
    if order.user_id != user_id:
        await call.answer("❌ Это не ваш заказ", show_alert=True)
        return
    
    delivery_repo = DeliveryRepository(session)
    delivery_date = await delivery_repo.get_by_id(delivery_id)
    
    if not delivery_date:
        await call.answer("❌ Дата не найдена", show_alert=True)
        return
    
    if not delivery_date.is_available:
        await call.answer("❌ Эта дата уже недоступна", show_alert=True)
        await select_delivery_date(call, state, session)
        return
    
    if delivery_date.order_limit and delivery_date.current_orders >= delivery_date.order_limit:
        await call.answer(f"❌ На эту дату лимит заказов ({delivery_date.current_orders}/{delivery_date.order_limit})", show_alert=True)
        await select_delivery_date(call, state, session)
        return
    
    now = datetime.now()
    if delivery_date.delivery_date < now:
        await call.answer("❌ Эта дата уже прошла", show_alert=True)
        await select_delivery_date(call, state, session)
        return
    
    min_hours = 2
    if delivery_date.delivery_date < now + timedelta(hours=min_hours):
        await call.answer(f"❌ До доставки не менее {min_hours} часов", show_alert=True)
        await select_delivery_date(call, state, session)
        return
    
    await state.update_data(
        confirm_order_id=order_id,
        selected_delivery_id=delivery_id
    )
    
    await show_time_range_selection(call, state, session, delivery_id, order_id)


# =============================================================================
# TIME RANGE SELECTION HANDLERS
# =============================================================================

async def show_time_range_selection(
    target: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    delivery_id: int,
    order_id: int
) -> None:
    """Показывает интерфейс выбора временного диапазона."""
    delivery_repo = DeliveryRepository(session)
    delivery_date = await delivery_repo.get_by_id(delivery_id)
    
    if not delivery_date:
        await target.answer("❌ Дата не найдена")
        return
    
    user_id = target.from_user.id
    
    _temp_hour_selection[user_id] = {
        'delivery_id': delivery_id,
        'order_id': order_id,
        'start': None,
        'end': None
    }
    
    await state.set_state(user_states.UserMenu.confirm_order_time_range)
    await state.update_data(
        selected_delivery_id=delivery_id,
        confirm_order_id=order_id
    )
    
    buttons, sizes = get_hour_buttons()
    
    buttons["🔄 Сбросить"] = CALLBACK_RESET_HOURS
    buttons["✅ Подтвердить"] = CALLBACK_CONFIRM_TIME_RANGE
    buttons["🔙 К выбору даты"] = CALLBACK_BACK_TO_DATES
    sizes.extend([1, 1, 1])
    
    text = TIME_RANGE_SELECT_PROMPT.format(
        date=format_delivery_date(delivery_date),
        order_id=order_id,
        selected_range="не выбран",
        hours_buttons=""
    )
    
    await send_clean_message(
        target=target,
        text=text,
        buttons=buttons,
        sizes=sizes,
        parse_mode="HTML"
    )


@UserConfirmOrdersRouter.callback_query(
    F.data.startswith(CALLBACK_SELECT_HOUR),
    StateFilter(user_states.UserMenu.confirm_order_time_range)
)
async def select_hour(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Обработка выбора часа."""
    hour = int(call.data.split("_")[3])
    user_id = call.from_user.id
    
    if user_id not in _temp_hour_selection:
        _temp_hour_selection[user_id] = {'start': None, 'end': None}
    
    current = _temp_hour_selection[user_id]
    
    if current['start'] is None:
        current['start'] = hour
        await call.answer(f"🔵 Начало: {hour}:00")
        
    elif current['end'] is None:
        current['end'] = hour
        
        if current['start'] > current['end']:
            current['start'], current['end'] = current['end'], current['start']
        
        await call.answer(f"✅ Диапазон: {current['start']}:00 - {current['end']}:00")
        
    else:
        current['start'] = hour
        current['end'] = None
        await call.answer(f"🔄 Начнём заново: {hour}:00")
    
    data = await state.get_data()
    delivery_id = data.get('selected_delivery_id')
    order_id = data.get('confirm_order_id')
    
    delivery_repo = DeliveryRepository(session)
    delivery_date = await delivery_repo.get_by_id(delivery_id)
    
    if current['start'] is not None and current['end'] is not None:
        range_text = f"{current['start']}:00 - {current['end']}:00"
    elif current['start'] is not None:
        range_text = f"{current['start']}:00 (выберите конец)"
    else:
        range_text = "не выбран"
    
    buttons, sizes = get_hour_buttons(current['start'], current['end'])
    buttons["🔄 Сбросить"] = CALLBACK_RESET_HOURS
    buttons["✅ Подтвердить"] = CALLBACK_CONFIRM_TIME_RANGE
    buttons["🔙 К выбору даты"] = CALLBACK_BACK_TO_DATES
    sizes.extend([1, 1, 1])
    
    text = TIME_RANGE_SELECT_PROMPT.format(
        date=format_delivery_date(delivery_date),
        order_id=order_id,
        selected_range=range_text,
        hours_buttons=""
    )
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=sizes,
        parse_mode="HTML"
    )


@UserConfirmOrdersRouter.callback_query(
    F.data == CALLBACK_RESET_HOURS,
    StateFilter(user_states.UserMenu.confirm_order_time_range)
)
async def reset_hours(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Сброс выбранного диапазона."""
    user_id = call.from_user.id
    
    if user_id in _temp_hour_selection:
        _temp_hour_selection[user_id]['start'] = None
        _temp_hour_selection[user_id]['end'] = None
    
    await call.answer("🔄 Выбор сброшен")
    
    data = await state.get_data()
    delivery_id = data.get('selected_delivery_id')
    order_id = data.get('confirm_order_id')
    
    delivery_repo = DeliveryRepository(session)
    delivery_date = await delivery_repo.get_by_id(delivery_id)
    
    buttons, sizes = get_hour_buttons()
    buttons["🔄 Сбросить"] = CALLBACK_RESET_HOURS
    buttons["✅ Подтвердить"] = CALLBACK_CONFIRM_TIME_RANGE
    buttons["🔙 К выбору даты"] = CALLBACK_BACK_TO_DATES
    sizes.extend([1, 1, 1])
    
    text = TIME_RANGE_SELECT_PROMPT.format(
        date=format_delivery_date(delivery_date),
        order_id=order_id,
        selected_range="не выбран",
        hours_buttons=""
    )
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=sizes,
        parse_mode="HTML"
    )


@UserConfirmOrdersRouter.callback_query(
    F.data == CALLBACK_CONFIRM_TIME_RANGE,
    StateFilter(user_states.UserMenu.confirm_order_time_range)
)
async def confirm_time_range(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Подтверждение выбранного диапазона и переход к оплате."""
    user_id = call.from_user.id
    selection = _temp_hour_selection.get(user_id, {})
    
    start_hour = selection.get('start')
    end_hour = selection.get('end')
    
    if start_hour is None:
        await call.answer("❌ Сначала выберите время!", show_alert=True)
        return
    
    if end_hour is None:
        end_hour = start_hour
    
    data = await state.get_data()
    order_id = data.get('confirm_order_id')
    delivery_id = data.get('selected_delivery_id')
    
    if not order_id:
        await call.answer("❌ Ошибка: заказ не найден", show_alert=True)
        return
    
    order_repo = OrderRepository(session=session)
    updated_order = await order_repo.update_delivery_hours(order_id, start_hour, end_hour)
    
    if updated_order:
        await session.commit()
        
        await state.update_data(
            selected_hour_from=start_hour,
            selected_hour_to=end_hour
        )
        
        clear_temp_selection(user_id)
        
        delivery_repo = DeliveryRepository(session)
        delivery_date = await delivery_repo.get_by_id(delivery_id)
        date_str = format_delivery_date(delivery_date) if delivery_date else "не указана"
        time_range = format_delivery_time_range(start_hour, end_hour)
        
        text = TIME_RANGE_CONFIRM_TEXT.format(
            date=date_str,
            time_range=time_range
        )
        
        await send_clean_message(
            target=call,
            text=text,
            buttons={
                "✅ Далее": "proceed_to_payment"
            },
            sizes=[1],
            parse_mode="HTML"
        )
        
        await state.set_state(user_states.UserMenu.confirm_order_time_confirmed)
        
    else:
        await call.answer("❌ Ошибка при сохранении времени", show_alert=True)


@UserConfirmOrdersRouter.callback_query(
    F.data == "proceed_to_payment",
    StateFilter(user_states.UserMenu.confirm_order_time_confirmed)
)
async def proceed_to_payment(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Переход к оплате после выбора времени."""
    await call.message.delete()
    await show_payment(call, state, session)


@UserConfirmOrdersRouter.callback_query(
    F.data == CALLBACK_BACK_TO_DATES,
    StateFilter(user_states.UserMenu.confirm_order_time_range)
)
async def back_to_dates(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Возврат к выбору даты."""
    clear_temp_selection(call.from_user.id)
    
    data = await state.get_data()
    order_id = data.get('confirm_order_id')
    
    if order_id:
        await select_delivery_date(call, state, session)
    else:
        await show_confirm_orders(call, state, session)


# =============================================================================
# COMMENT HANDLERS
# =============================================================================

@UserConfirmOrdersRouter.callback_query(
    F.data == CALLBACK_SKIP_COMMENT,
    StateFilter(user_states.UserMenu.confirm_order_comment)
)
async def confirm_order_skip_comment(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Пропустить комментарий."""
    data = await state.get_data()
    order_id = data.get('confirm_order_id')
    
    if not order_id:
        await call.answer("❌ Ошибка: заказ не найден", show_alert=True)
        await state.clear()
        return
    
    await state.update_data(confirm_order_comment=None)
    await call.message.delete()
    await show_payment(call, state, session)


@UserConfirmOrdersRouter.message(StateFilter(user_states.UserMenu.confirm_order_comment))
async def confirm_order_comment(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Получен комментарий к заказу."""
    data = await state.get_data()
    order_id = data.get('confirm_order_id')
    
    if not order_id:
        await message.answer("❌ Ошибка: заказ не найден")
        await state.clear()
        return
    
    if message.text and message.text.strip() == BUTTON_TEXT["skip_comment"]:
        comment = None
    else:
        comment = message.text.strip()
    
    await message.delete()
    await state.update_data(confirm_order_comment=comment)
    await show_payment(message, state, session)


# =============================================================================
# PAYMENT HANDLERS
# =============================================================================

async def show_payment(
    target: Union[Message, CallbackQuery],
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Показывает реквизиты для оплаты."""
    data = await state.get_data()
    order_id = data.get('confirm_order_id')
    
    if not order_id:
        await target.answer("❌ Ошибка: заказ не найден")
        await state.clear()
        return
    
    order_details = await get_order_with_details(session, order_id)
    
    if not order_details:
        await target.answer("❌ Заказ не найден")
        await state.clear()
        return
    
    await state.set_state(user_states.UserMenu.confirm_order_payment)
    
    text = PAYMENT_TEXT.format(
        order_id=order_id,
        total=order_details['final_total']
    )
    
    await send_clean_message(
        target=target,
        text=text,
        buttons={
            "🔙 К заказу": f"{CALLBACK_SELECT_ORDER}{order_id}"
        },
        sizes=[1],
        parse_mode="HTML"
    )


@UserConfirmOrdersRouter.message(F.photo, StateFilter(user_states.UserMenu.confirm_order_payment))
async def confirm_order_payment(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Получено фото чека — завершаем оформление заказа."""
    data = await state.get_data()
    order_id = data.get('confirm_order_id')
    comment = data.get('confirm_order_comment')
    delivery_id = data.get('selected_delivery_id')
    address_id = data.get('confirm_address_id')
    hour_from = data.get('selected_hour_from')
    hour_to = data.get('selected_hour_to')
    
    if not order_id:
        await message.answer("❌ Ошибка: заказ не найден")
        await state.clear()
        return
    
    photo_id = message.photo[-1].file_id
    await message.delete()
    
    order_repo = OrderRepository(session=session)
    delivery_repo = DeliveryRepository(session)
    address_repo = AddressRepository(session)
    
    if comment:
        await order_repo.update_order_comment(order_id, comment)
    
    await order_repo.update_order_photo(order_id, photo_id)
    
    if hour_from is not None:
        await order_repo.update_delivery_hours(order_id, hour_from, hour_to)
    
    if delivery_id:
        await delivery_repo.assign_to_order(order_id, delivery_id)
    
    updated_order = await order_repo.update_order_status(order_id, OrdersStatus.VERIFICATION)
    
    if updated_order:
        await session.commit()
        
        order_details = await get_order_with_details(session, order_id)
        
        if not order_details:
            await message.answer("❌ Не удалось получить детали заказа")
            await state.clear()
            return
        
        items_text = ""
        for item in order_details['items']:
            items_text += f"\n• {item['name']} — {item['quantity']} × {item['price']}₽ = {item['subtotal']}₽"
        
        address = await address_repo.get_by_id(address_id) if address_id else None
        address_text = format_address_text(address)
        
        delivery_date = await delivery_repo.get_order_delivery(order_id)
        delivery_date_text = format_delivery_date(delivery_date) if delivery_date else "📅 Не указана"
        delivery_time_range = format_delivery_time_range(hour_from, hour_to) if hour_from else "Не указано"
        
        text = ORDER_CONFIRMED.format(
            order_id=order_id,
            items_text=items_text,
            address_text=address_text,
            delivery_date_text=delivery_date_text,
            delivery_time_range=delivery_time_range,
            total=order_details['final_total']
        )
        
        buttons = {
            "🍰 В меню": CALLBACK_BACK_TO_MENU,
            "🏠 Главная": CALLBACK_MAIN_MENU
        }
        
        await send_clean_message(
            target=message,
            text=text,
            buttons=buttons,
            sizes=[1, 1],
            parse_mode="HTML"
        )
        
    else:
        await message.answer("❌ Не удалось подтвердить заказ. Попробуйте позже.")
    
    clear_temp_selection(message.from_user.id)
    await state.clear()


@UserConfirmOrdersRouter.message(StateFilter(user_states.UserMenu.confirm_order_payment))
async def invalid_payment_input(message: Message, state: FSMContext) -> None:
    """Обработка некорректного ввода при запросе фото чека."""
    await message.answer(
        "❓ Пожалуйста, отправьте фото чека об оплате",
        reply_markup=get_callback_btns(
            btns={"🔙 К списку заказов": CALLBACK_CONFIRM_ORDERS},
            sizes=(1,)
        )
    )


# =============================================================================
# INVALID INPUT HANDLERS
# =============================================================================

@UserConfirmOrdersRouter.message(StateFilter(user_states.UserMenu.confirm_order_comment))
async def invalid_comment_input(message: Message, state: FSMContext) -> None:
    """Обработка некорректного ввода при запросе комментария."""
    await message.answer(
        "❓ Напишите пожелания или нажмите «Без пожеланий»",
        reply_markup=get_callback_btns(
            btns={BUTTON_TEXT["skip_comment"]: CALLBACK_SKIP_COMMENT},
            sizes=(1,)
        )
    )