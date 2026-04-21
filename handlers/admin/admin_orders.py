"""
Admin Orders Module
===================

This module handles order management for administrators.
Here the chef reviews and updates order statuses.
"""

from typing import Dict, List, Any, Optional
from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InputMediaPhoto
from aiogram.enums.parse_mode import ParseMode

from icecream import ic
from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query.orders_orm import OrderRepository  
from database.orm_query.address_orm import AddressRepository
from database.orm_query.delivery_orm import DeliveryRepository
from database.orm_query.delivery_status_orm import DeliveryStatusRepository
from database.enumirate.orders_enum import OrdersStatus

from keybords.inline import get_callback_btns
from States import user_states
from config import last_message_dict, ADMIN_IDS
from bot_instance import get_bot_instance
from tools import notify_admins

from handlers.admin.admin_panel import send_section_message


# =============================================================================
# ROUTER INITIALIZATION
# =============================================================================

AdminOrdersRouter = Router()


# =============================================================================
# CONSTANTS
# =============================================================================

# Button labels
BTN_CONFIRM = "✅ Принять"
BTN_PREPARING = "👨‍🍳 Готовлю"
BTN_READY_FOR_DELIVERY = "📦 Готов к выдаче"
BTN_CANCEL = "❌ Отказать"
BTN_BACK = "🔙 Назад"
BTN_REFRESH = "🔄 Обновить"
BTN_ARCHIVE_COMPLETED = "✅ Завершённые"
BTN_ARCHIVE_REFUSED = "❌ Отказанные"
BTN_NEXT = "▶️ Вперёд"
BTN_PREV = "◀️ Назад"

# Callback prefixes
CALLBACK_ACCEPT_ORDER = "admin_accept_"
CALLBACK_READY_ORDER = "admin_mark_ready_"
CALLBACK_COMPLETE_ORDER = "admin_complete_"
CALLBACK_REFUSE_ORDER = "admin_refuse_"
CALLBACK_ORDER_DETAIL = "admin_order_"

# Пагинация
ITEMS_PER_PAGE = 5


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


def format_address_detailed(address) -> str:
    """
    Форматирует адрес доставки с деталями для администратора.
    
    Args:
        address: Объект адреса UserAdress
    
    Returns:
        str: Отформатированный адрес
    """
    if not address:
        return "📍 <i>Адрес не указан</i>"
    
    parts = []
    
    # Основной адрес
    address_line = ""
    if address.street:
        address_line += address.street
    if address.house:
        address_line += f", {address.house}"
    if address_line:
        parts.append(f"📍 {address_line}")
    
    # Корпус/строение
    if address.building:
        parts.append(f"🏢 корп. {address.building}")
    
    # Квартира
    if address.apartment:
        parts.append(f"🔑 кв. {address.apartment}")
    
    # Дополнительная информация
    extra = []
    if address.floor:
        extra.append(f"этаж {address.floor}")
    if address.entrance:
        extra.append(f"подъезд {address.entrance}")
    if address.intercom:
        extra.append(f"домофон {address.intercom}")
    if extra:
        parts.append(f"📌 {', '.join(extra)}")
    
    # Комментарий для курьера
    if address.comment:
        comment = address.comment[:100] + "..." if len(address.comment) > 100 else address.comment
        parts.append(f"📝 <i>{comment}</i>")
    
    # Название адреса (если есть)
    result = f"🏷️ <b>{address.adress_name}</b>\n" if address.adress_name != "Дом" else ""
    result += "\n".join(parts)
    
    return result


async def get_delivery_price_for_order(session: AsyncSession, address_id: int) -> int:
    """
    Получает стоимость доставки для заказа по адресу.
    
    Args:
        session: сессия БД
        address_id: ID адреса
    
    Returns:
        int: стоимость доставки
    """
    try:
        if not address_id:
            return 0
        
        address_repo = AddressRepository(session)
        address = await address_repo.get_by_id(address_id)
        
        if not address or not address.adress_status:
            return 0
        
        status_repo = DeliveryStatusRepository(session)
        status = await status_repo.get_by_id(int(address.adress_status))
        
        return status.price if status else 0
        
    except Exception as e:
        ic(f"Error getting delivery price: {e}")
        return 0


async def get_order_full_details(
    session: AsyncSession, 
    order_id: int
) -> Optional[Dict[str, Any]]:
    """
    Получает полную информацию о заказе с адресом, датой доставки и стоимостью доставки.
    
    Args:
        session: Сессия БД
        order_id: ID заказа
    
    Returns:
        Dict с полной информацией о заказе
    """
    order_repo = OrderRepository(session)
    address_repo = AddressRepository(session)
    delivery_repo = DeliveryRepository(session)
    
    # Получаем базовые детали заказа
    order_details = await order_repo.get_order_with_details(order_id)
    
    if not order_details:
        return None
    
    # Получаем адрес доставки
    address = None
    delivery_price = 0
    if order_details.get('address_id'):
        address = await address_repo.get_by_id(order_details['address_id'])
        delivery_price = await get_delivery_price_for_order(session, order_details['address_id'])
    
    # Получаем дату доставки
    delivery_date = await delivery_repo.get_order_delivery(order_id)
    delivery_date_str = delivery_date.delivery_date.strftime("%d.%m.%Y") if delivery_date else None
    
    # Рассчитываем итоговую сумму с доставкой
    order_total = order_details.get('total', 0)
    final_total = order_total + delivery_price
    
    # Формируем полную информацию
    return {
        **order_details,
        'address': address,
        'delivery_date': delivery_date_str,
        'delivery_hour_from': order_details.get('delivery_hour_from', None),
        'delivery_hour_to': order_details.get('delivery_hour_to', None),
        'delivery_price': delivery_price,
        'order_total': order_total,
        'final_total': final_total
    }


async def send_admin_notification(
    order_id: int,
    session: AsyncSession,
    action: str,
    status_name: str = None
) -> None:
    """
    Отправляет уведомление администраторам о действии с заказом.
    
    Args:
        order_id: ID заказа
        session: сессия БД
        action: действие (accepted, ready, completed, refused)
        status_name: название статуса (для отображения)
    """
    order_repo = OrderRepository(session)
    
    # Получаем статистику
    new_orders_count = await order_repo.get_orders_by_status_count(OrdersStatus.VERIFICATION)
    active_orders_count = await order_repo.get_orders_by_status_count(OrdersStatus.ACCEPTED)
    ready_count = await order_repo.get_orders_by_status_count(OrdersStatus.READY_FOR_DELIVERY)
    
    bot = get_bot_instance()
    
    if action == "accepted":
        text = f"""
👨‍🍳 <b>Заказ #{order_id} принят в работу!</b>

<b>📊 Статистика:</b>
🆕 Новых заказов: <b>{new_orders_count}</b>
🍳 В работе: <b>{active_orders_count}</b>
📦 Готовых: <b>{ready_count}</b>

👉 Перейдите в раздел <b>"🍳 В работе"</b>.
"""
        callback = "active_orders"
        
    elif action == "ready":
        text = f"""
📦 <b>Заказ #{order_id} готов к выдаче!</b>

<b>📊 Статистика:</b>
🆕 Новых заказов: <b>{new_orders_count}</b>
🍳 В работе: <b>{active_orders_count}</b>
📦 Готовых: <b>{ready_count}</b>

👉 Перейдите в раздел <b>"📦 Готовые заказы"</b>.
"""
        callback = "admin_ready_orders"
        
    elif action == "completed":
        text = f"""
✅ <b>Заказ #{order_id} завершён!</b>

<b>📊 Статистика:</b>
🆕 Новых заказов: <b>{new_orders_count}</b>
🍳 В работе: <b>{active_orders_count}</b>
📦 Готовых: <b>{ready_count}</b>
"""
        callback = None
        
    elif action == "refused":
        text = f"""
❌ <b>Заказ #{order_id} отклонён!</b>

<b>📊 Статистика:</b>
🆕 Новых заказов: <b>{new_orders_count}</b>
🍳 В работе: <b>{active_orders_count}</b>
📦 Готовых: <b>{ready_count}</b>
"""
        callback = None
    
    buttons = {"🔍 Перейти": callback} if callback else None
    sizes = [1] if callback else None
    
    await notify_admins(
        bot=bot,
        text=text,
        admin_ids=ADMIN_IDS,
        buttons=buttons,
        sizes=sizes
    )


async def send_notification_to_user(
    order_id: int,
    user_id: int,
    action: str,
    order_details: Dict[str, Any] = None
) -> None:
    """
    Отправляет уведомление пользователю о смене статуса заказа.
    
    Args:
        order_id: ID заказа
        user_id: ID пользователя
        action: действие (accepted, ready, completed, refused)
        order_details: детали заказа (опционально)
    """
    bot = get_bot_instance()
    
    if action == "accepted":
        text = f"""
👨‍🍳 <b>Заказ №{order_id} принят!</b>

Ваш заказ принят в работу. Наша команда уже приступила к приготовлению.

<i>Статус заказа можно отслеживать в разделе "🍳 Активные заказы" 🤍</i>
"""
    elif action == "ready":
        text = f"""
📦 <b>Заказ №{order_id} готов к получению!</b>

Ваш заказ готов. Пожалуйста, подтвердите получение в разделе <b>"🍳 Активные заказы"</b>.

<i>Спасибо, что выбрали нас 🤍</i>
"""
    elif action == "completed":
        # Получаем детали заказа для отображения в уведомлении
        if order_details:
            items_text = ""
            for item in order_details.get('items', []):
                items_text += f"\n• {item['name']} — {item['quantity']} × {item['price']}₽ = {item['subtotal']}₽"
            
            text = f"""
✅ <b>Заказ №{order_id} завершён!</b>

<b>Состав заказа:</b>
{items_text}

<b>Итого:</b> {order_details.get('final_total', order_details.get('total', 0))} ₽

Спасибо, что выбрали нас! Будем рады видеть вас снова 🤍

<i>Заказ передан в историю.</i>
"""
        else:
            text = f"""
✅ <b>Заказ №{order_id} завершён!</b>

Спасибо, что выбрали нас! Будем рады видеть вас снова 🤍

<i>Заказ передан в историю.</i>
"""
    elif action == "refused":
        text = f"""
❌ <b>Заказ №{order_id} отклонён</b>

К сожалению, ваш заказ не может быть выполнен.
Если у вас есть вопросы, свяжитесь с нашим менеджером.

<i>Приносим извинения за неудобства 🤍</i>
"""
    else:
        return
    
    try:
        await bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode="HTML"
        )
    except Exception as e:
        ic(f"Error notifying user {user_id}: {e}")


async def send_section_message_with_photo(
    call: types.CallbackQuery,
    text: str,
    photo: str,
    buttons: dict,
    sizes: tuple = (1,)
) -> None:
    """
    Отправляет сообщение с фото в разделе админки.
    """
    user_id = call.from_user.id
    
    new_reply_markup = get_callback_btns(btns=buttons, sizes=sizes)
    
    try:
        # Пытаемся отредактировать существующее сообщение, если оно с фото
        if call.message.photo:
            media = InputMediaPhoto(media=photo, caption=text, parse_mode=ParseMode.HTML)
            msg = await call.message.edit_media(
                media=media,
                reply_markup=new_reply_markup
            )
        else:
            # Если текущее сообщение без фото — отправляем новое
            msg = await call.message.answer_photo(
                photo=photo,
                caption=text,
                reply_markup=new_reply_markup,
                parse_mode=ParseMode.HTML
            )
            await call.message.delete()
    except Exception as e:
        ic(f"Error editing message with photo: {e}")
        # Fallback: отправляем новое сообщение
        msg = await call.message.answer_photo(
            photo=photo,
            caption=text,
            reply_markup=new_reply_markup,
            parse_mode=ParseMode.HTML
        )
        try:
            await call.message.delete()
        except Exception as delete_error:
            ic(f"Error deleting old message: {delete_error}")
    
    # Очистка старых сообщений
    if user_id in last_message_dict and last_message_dict[user_id]:
        current_msg_id = msg.message_id
        
        for msg_id in last_message_dict[user_id][:]:
            if msg_id != current_msg_id:
                try:
                    await call.message.bot.delete_message(chat_id=user_id, message_id=msg_id)
                except Exception as e:
                    ic("Error: ", e)
        
        last_message_dict[user_id] = [current_msg_id]
    else:
        if user_id not in last_message_dict:
            last_message_dict[user_id] = []
        last_message_dict[user_id].append(msg.message_id)


def format_orders_list(orders: List, order_type: str = "new") -> tuple[str, dict, list]:
    """
    Форматирует список заказов для вывода.
    
    Args:
        orders: список заказов
        order_type: тип заказа (new, active, completed, refused)
    
    Returns:
        tuple: (текст, кнопки, размеры)
    """
    if not orders:
        if order_type == "new":
            text = "🆕 <b>Новые заказы</b>\n\n🍽 Пока всё спокойно. Новых заказов нет."
        elif order_type == "active":
            text = "🍳 <b>В работе</b>\n\n😴 Сейчас всё готово. Активных заказов нет."
        elif order_type == "completed":
            text = "✅ <b>Завершённые заказы</b>\n\n📭 Архив пока пуст."
        else:
            text = "❌ <b>Отказанные заказы</b>\n\n📭 Архив пока пуст."
        
        buttons = {
            "🔙 Назад": "back_to_admin_panel"
        }
        return text, buttons, [1]
    
    text = ""
    if order_type == "new":
        text = "🆕 <b>Новые заказы</b>\n\n<i>Требуют подтверждения:</i>\n"
    elif order_type == "active":
        text = "🍳 <b>В работе</b>\n\n<i>Сейчас готовятся:</i>\n"
    elif order_type == "completed":
        text = "✅ <b>Завершённые заказы</b>\n\n<i>Уже доставлены гостям:</i>\n"
    else:
        text = "❌ <b>Отказанные заказы</b>\n\n<i>По разным причинам не состоялись:</i>\n"
    
    for i, order in enumerate(orders, 1):
        created_time = order.created.strftime("%H:%M") if hasattr(order, 'created') else "неизвестно"
        text += f"\n{i}. Заказ #{order.order_id} ({created_time})"
    
    buttons = {}
    sizes = []
    
    for order in orders:
        buttons[f"📦 Заказ #{order.order_id}"] = f"{CALLBACK_ORDER_DETAIL}{order.order_id}"
        sizes.append(1)
    
    return text, buttons, sizes


async def show_paginated_orders(
    call: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    order_type: str,
    page: int = 0
) -> None:
    """
    Показывает заказы с пагинацией.
    
    Args:
        call: CallbackQuery
        state: FSMContext
        session: AsyncSession
        order_type: completed или refused
        page: номер страницы (0-index)
    """
    order_repo = OrderRepository(session)
    
    if order_type == "completed":
        all_orders = await order_repo.get_orders_by_status(OrdersStatus.COMPLETED)
    else:
        all_orders = await order_repo.get_orders_by_status(OrdersStatus.REFUSED)
    
    # Сортируем по дате (сначала новые)
    all_orders.sort(key=lambda x: x.created, reverse=True)
    
    total = len(all_orders)
    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    orders_page = all_orders[start:end]
    
    # Сохраняем данные пагинации в состояние
    await state.update_data(
        current_order_type=order_type,
        current_page=page,
        total_orders=total
    )
    
    text, buttons, sizes = format_orders_list(orders_page, order_type)
    
    # Добавляем кнопки пагинации
    nav_buttons = {}
    nav_sizes = []
    
    if page > 0:
        nav_buttons["◀️ Назад"] = f"archive_page_{order_type}_{page - 1}"
        nav_sizes.append(1)
    
    if end < total:
        nav_buttons["Вперёд ▶️"] = f"archive_page_{order_type}_{page + 1}"
        nav_sizes.append(1)
    
    nav_buttons["🔙 В админку"] = "back_to_admin_panel"
    nav_sizes.append(1)
    
    # Добавляем кнопку для переключения между архивами
    if order_type == "completed":
        nav_buttons["❌ Посмотреть отказанные"] = "archive_refused"
        nav_sizes.append(1)
    else:
        nav_buttons["✅ Посмотреть завершённые"] = "archive_completed"
        nav_sizes.append(1)
    
    # Объединяем кнопки
    all_buttons = {**buttons, **nav_buttons}
    all_sizes = sizes + nav_sizes
    
    await send_section_message(call, text, all_buttons, tuple(all_sizes))


# =============================================================================
# ORDER MANAGEMENT HANDLERS
# =============================================================================

@AdminOrdersRouter.callback_query(F.data == "new_orders", StateFilter(user_states.AdminPanel.admin_panel))
async def show_new_orders(call: types.CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    🆕 Новые заказы — заказы в статусе VERIFICATION (ожидают подтверждения).
    """
    await call.answer()
    
    order_repo = OrderRepository(session)
    new_orders = await order_repo.get_orders_by_status(OrdersStatus.VERIFICATION)
    
    text, buttons, sizes = format_orders_list(new_orders, "new")
    
    # Добавляем кнопку обновления и возврата
    buttons["🔄 Обновить"] = "refresh_new_orders"
    buttons["🔙 Назад"] = "back_to_admin_panel"
    sizes.extend([1, 1])
    
    await send_section_message(call, text, buttons, tuple(sizes))


@AdminOrdersRouter.callback_query(F.data == "active_orders", StateFilter(user_states.AdminPanel.admin_panel))
async def show_active_orders(call: types.CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    🍳 Активные заказы — заказы в статусе ACCEPTED (в процессе приготовления).
    """
    await call.answer()
    
    order_repo = OrderRepository(session)
    active_orders = await order_repo.get_orders_by_status(OrdersStatus.ACCEPTED)
    
    text, buttons, sizes = format_orders_list(active_orders, "active")
    
    # Добавляем кнопку обновления и возврата
    buttons["🔄 Обновить"] = "refresh_active_orders"
    buttons["🔙 Назад"] = "back_to_admin_panel"
    sizes.extend([1, 1])
    
    await send_section_message(call, text, buttons, tuple(sizes))


@AdminOrdersRouter.callback_query(F.data == "orders_history", StateFilter(user_states.AdminPanel.admin_panel))
async def show_orders_history(call: types.CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    📜 История заказов — выбор между завершёнными и отказанными.
    """
    await call.answer()
    
    order_repo = OrderRepository(session)
    completed_count = len(await order_repo.get_orders_by_status(OrdersStatus.COMPLETED))
    refused_count = len(await order_repo.get_orders_by_status(OrdersStatus.REFUSED))
    
    text = f"""
📜 <b>Архив заказов</b>

📊 <b>Статистика:</b>
✅ Завершённых заказов: <b>{completed_count}</b>
❌ Отказанных заказов: <b>{refused_count}</b>

Выберите, какой архив посмотреть:
"""
    
    buttons = {
        "✅ Завершённые": "archive_completed",
        "❌ Отказанные": "archive_refused",
        "🔙 Назад": "back_to_admin_panel"
    }
    sizes = [1, 1, 1]
    
    await send_section_message(call, text, buttons, tuple(sizes))


# =============================================================================
# ARCHIVE HANDLERS (с пагинацией)
# =============================================================================

@AdminOrdersRouter.callback_query(F.data == "archive_completed", StateFilter(user_states.AdminPanel.admin_panel))
async def archive_completed(call: types.CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    ✅ Показать завершённые заказы (COMPLETED) с пагинацией.
    """
    await call.answer()
    await show_paginated_orders(call, state, session, "completed", page=0)


@AdminOrdersRouter.callback_query(F.data == "archive_refused", StateFilter(user_states.AdminPanel.admin_panel))
async def archive_refused(call: types.CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    ❌ Показать отказанные заказы (REFUSED) с пагинацией.
    """
    await call.answer()
    await show_paginated_orders(call, state, session, "refused", page=0)


@AdminOrdersRouter.callback_query(F.data.startswith("archive_page_"))
async def archive_page_navigation(call: types.CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Навигация по страницам архива.
    Формат: archive_page_{order_type}_{page}
    """
    parts = call.data.split("_")
    order_type = parts[2]  # completed или refused
    page = int(parts[3])
    
    await call.answer()
    await show_paginated_orders(call, state, session, order_type, page)


# =============================================================================
# ORDER DETAIL HANDLERS
# =============================================================================

@AdminOrdersRouter.callback_query(F.data.startswith(CALLBACK_ORDER_DETAIL))
async def show_order_details(call: types.CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    📦 Детали заказа — как рецепт, который нужно приготовить.
    Улучшенная версия с полной информацией о доставке и пожеланиями.
    """
    order_id = int(call.data.split("_")[2])
    await call.answer()
    
    # Получаем полную информацию о заказе
    order_details = await get_order_full_details(session, order_id)
    
    if not order_details:
        await send_section_message(
            call,
            "❌ Заказ не найден",
            {"🔙 Назад": "back_to_admin_panel"}
        )
        return
    
    # Эмодзи статуса
    status_emoji = {
        OrdersStatus.VERIFICATION.value: "🆕",
        OrdersStatus.ACCEPTED.value: "🍳",
        OrdersStatus.READY_FOR_DELIVERY.value: "📦",
        OrdersStatus.COMPLETED.value: "✅",
        OrdersStatus.REFUSED.value: "❌"
    }.get(order_details['status'], "📦")
    
    # Название статуса по-русски
    status_name = {
        OrdersStatus.VERIFICATION.value: "Ожидает подтверждения",
        OrdersStatus.ACCEPTED.value: "Готовится",
        OrdersStatus.READY_FOR_DELIVERY.value: "Готов к выдаче",
        OrdersStatus.COMPLETED.value: "Завершён",
        OrdersStatus.REFUSED.value: "Отклонён"
    }.get(order_details['status'], order_details['status'])
    
    # =========================================================================
    # ФОРМИРУЕМ ТЕКСТ ЗАКАЗА
    # =========================================================================
    
    # Шапка заказа
    text = f"""
{status_emoji} <b>ЗАКАЗ #{order_details['order_id']}</b> {status_emoji}
{'─' * 45}

👤 <b>Клиент:</b>     ID {order_details['user_id']}
📊 <b>Статус:</b>     {status_emoji} {status_name}
📅 <b>Дата заказа:</b> {order_details['created'].strftime('%d.%m.%Y')} в {order_details['created'].strftime('%H:%M')}

{'─' * 45}
"""

    # Адрес доставки (если есть)
    if order_details.get('address'):
        address = order_details['address']
        text += f"\n📍 <b>АДРЕС ДОСТАВКИ</b>\n"
        text += f"   🏠 {address.adress_name}\n"
        text += f"   📭 {address.street}, {address.house}"
        
        if address.building:
            text += f", корп. {address.building}"
        if address.apartment:
            text += f", кв. {address.apartment}"
        text += "\n"
        
        # Детали (этаж, подъезд, домофон)
        details = []
        if address.floor:
            details.append(f"этаж {address.floor}")
        if address.entrance:
            details.append(f"подъезд {address.entrance}")
        if address.intercom:
            details.append(f"домофон {address.intercom}")
        if details:
            text += f"   📌 {', '.join(details)}\n"
        
        if address.comment:
            text += f"   💬 {address.comment[:80]}\n"
        
        text += f"\n{'─' * 45}"

    # Дата и время доставки
    if order_details.get('delivery_date') or order_details.get('delivery_hour_from'):
        text += f"\n📦 <b>ДОСТАВКА</b>\n"
        
        if order_details.get('delivery_date'):
            text += f"   📆 <b>Дата:</b> {order_details['delivery_date']}\n"
        
        if order_details.get('delivery_hour_from'):
            time_text = format_delivery_time(
                order_details['delivery_hour_from'],
                order_details['delivery_hour_to']
            )
            text += f"   {time_text}\n"
        
        text += f"\n{'─' * 45}"

    # Пожелания к заказу
    text += f"\n💬 <b>ПОЖЕЛАНИЯ</b>\n"
    if order_details.get('comment'):
        text += f"   📝 {order_details['comment']}\n"
    else:
        text += f"   💭 Нет пожеланий\n"

    text += f"\n{'─' * 45}"

    # Состав заказа
    text += f"\n🍽 <b>СОСТАВ ЗАКАЗА</b>\n"

    for i, item in enumerate(order_details['items'], 1):
        text += f"\n   {i}. <b>{item['name']}</b>\n"
        text += f"      🥄 {item['quantity']} × {item['price']}₽ = {item['subtotal']}₽"

    text += f"\n\n{'─' * 45}"

    # Стоимость доставки и итого
    if order_details.get('delivery_price', 0) > 0:
        text += f"\n   🚚 Доставка:               +{order_details['delivery_price']} ₽"

    text += f"\n   💰 <b>ИТОГО К ОПЛАТЕ:</b>      {order_details['final_total']} ₽"

    text += f"\n{'─' * 45}"

    # Фото чека
    if order_details.get('photo'):
        text += f"\n🖼 <b>Фото чека приложено выше</b>"
    
    # =========================================================================
    # КНОПКИ УПРАВЛЕНИЯ
    # =========================================================================
    
    buttons = {}
    sizes = []
    
    # Кнопки управления в зависимости от статуса
    if order_details['status'] == OrdersStatus.VERIFICATION.value:
        # Новый заказ — можно принять или отказать
        buttons[BTN_CONFIRM] = f"{CALLBACK_ACCEPT_ORDER}{order_id}"
        buttons[BTN_CANCEL] = f"{CALLBACK_REFUSE_ORDER}{order_id}"
        sizes.extend([1, 1])
        
    elif order_details['status'] == OrdersStatus.ACCEPTED.value:
        # Заказ в работе — можно отметить готовым к выдаче или отказать
        buttons[BTN_READY_FOR_DELIVERY] = f"{CALLBACK_READY_ORDER}{order_id}"
        buttons[BTN_CANCEL] = f"{CALLBACK_REFUSE_ORDER}{order_id}"
        sizes.extend([1, 1])
    
    elif order_details['status'] == OrdersStatus.READY_FOR_DELIVERY.value:
        # Заказ уже готов к выдаче — дополнительных действий нет
        buttons["📋 К списку"] = "active_orders"
        sizes.append(1)
    
    buttons[BTN_BACK] = "back_to_admin_panel"
    sizes.append(1)
    
    # Отправляем сообщение с фото (если есть)
    if order_details.get('photo'):
        await send_section_message_with_photo(
            call=call,
            text=text,
            photo=order_details['photo'],
            buttons=buttons,
            sizes=tuple(sizes)
        )
    else:
        await send_section_message(call, text, buttons, tuple(sizes))
# =============================================================================
# ORDER STATUS UPDATE HANDLERS
# =============================================================================

@AdminOrdersRouter.callback_query(F.data.startswith(CALLBACK_ACCEPT_ORDER))
async def accept_order(call: types.CallbackQuery, session: AsyncSession) -> None:
    """
    ✅ Принять заказ — переводим из VERIFICATION в ACCEPTED.
    """
    order_id = int(call.data.split("_")[2])
    
    order_repo = OrderRepository(session)
    updated = await order_repo.update_order_status(order_id, OrdersStatus.ACCEPTED)
    
    if updated:
        await session.commit()
        await call.answer("✅ Заказ принят! Приступаем к готовке!")
        
        # Получаем детали заказа для уведомления пользователя
        order_details = await get_order_full_details(session, order_id)
        if order_details:
            await send_notification_to_user(
                order_id=order_id,
                user_id=order_details['user_id'],
                action="accepted"
            )
        
        # Отправляем уведомление администраторам
        await send_admin_notification(order_id, session, "accepted")
        
    else:
        await call.answer("❌ Не получилось принять", show_alert=True)
    
    # Возвращаемся к списку новых заказов
    await show_new_orders(call, None, session)


@AdminOrdersRouter.callback_query(F.data.startswith(CALLBACK_READY_ORDER))
async def ready_for_delivery(call: types.CallbackQuery, session: AsyncSession) -> None:
    """
    📦 Заказ готов к выдаче — переводим из ACCEPTED в READY_FOR_DELIVERY.
    """
    # Формат: admin_mark_ready_{order_id}
    order_id = int(call.data.split("_")[3])
    
    order_repo = OrderRepository(session)
    updated = await order_repo.update_order_status(order_id, OrdersStatus.READY_FOR_DELIVERY)
    
    if updated:
        await session.commit()
        await call.answer("✅ Заказ готов к выдаче!")
        
        # Получаем детали заказа для уведомления пользователя
        order_details = await get_order_full_details(session, order_id)
        if order_details:
            await send_notification_to_user(
                order_id=order_id,
                user_id=order_details['user_id'],
                action="ready"
            )
        
        # Отправляем уведомление администраторам
        await send_admin_notification(order_id, session, "ready")
        
    else:
        await call.answer("❌ Ошибка", show_alert=True)
    
    # Возвращаемся к списку активных заказов
    await show_active_orders(call, None, session)


@AdminOrdersRouter.callback_query(F.data.startswith(CALLBACK_COMPLETE_ORDER))
async def complete_order(call: types.CallbackQuery, session: AsyncSession) -> None:
    """
    ✅ Завершить заказ — переводим из READY_FOR_DELIVERY в COMPLETED.
    Используется для ручного завершения (если пользователь не подтвердил).
    """
    order_id = int(call.data.split("_")[2])
    
    order_repo = OrderRepository(session)
    updated = await order_repo.update_order_status(order_id, OrdersStatus.COMPLETED)
    
    if updated:
        await session.commit()
        await call.answer("✅ Заказ завершён!")
        
        # Получаем детали заказа для уведомления пользователя
        order_details = await get_order_full_details(session, order_id)
        if order_details:
            await send_notification_to_user(
                order_id=order_id,
                user_id=order_details['user_id'],
                action="completed",
                order_details=order_details
            )
        
        # Отправляем уведомление администраторам
        await send_admin_notification(order_id, session, "completed")
        
    else:
        await call.answer("❌ Ошибка", show_alert=True)
    
    # Возвращаемся к списку активных заказов
    await show_active_orders(call, None, session)


@AdminOrdersRouter.callback_query(F.data.startswith(CALLBACK_REFUSE_ORDER))
async def refuse_order(call: types.CallbackQuery, session: AsyncSession) -> None:
    """
    ❌ Отказ от заказа — переводим в REFUSED.
    """
    order_id = int(call.data.split("_")[2])
    
    order_repo = OrderRepository(session)
    updated = await order_repo.update_order_status(order_id, OrdersStatus.REFUSED)
    
    if updated:
        await session.commit()
        await call.answer("❌ Заказ отклонён")
        
        # Получаем детали заказа для уведомления пользователя
        order_details = await get_order_full_details(session, order_id)
        if order_details:
            await send_notification_to_user(
                order_id=order_id,
                user_id=order_details['user_id'],
                action="refused"
            )
        
        # Отправляем уведомление администраторам
        await send_admin_notification(order_id, session, "refused")
        
        # Определяем, откуда пришли (из новых или из активных)
        order = await order_repo.get_order_by_id(order_id)
        if order and order.order_status == OrdersStatus.VERIFICATION.value:
            await show_new_orders(call, None, session)
        else:
            await show_active_orders(call, None, session)
    else:
        await call.answer("❌ Ошибка", show_alert=True)


# =============================================================================
# REFRESH HANDLERS
# =============================================================================

@AdminOrdersRouter.callback_query(F.data == "refresh_new_orders")
async def refresh_new_orders(call: types.CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Обновить список новых заказов"""
    await show_new_orders(call, state, session)


@AdminOrdersRouter.callback_query(F.data == "refresh_active_orders")
async def refresh_active_orders(call: types.CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Обновить список активных заказов"""
    await show_active_orders(call, state, session)