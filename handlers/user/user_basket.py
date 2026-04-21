"""
User Basket Module
=================

This module handles user's shopping basket and order history functionality.
PURE USER FUNCTIONS - NO ADMIN CAPABILITIES!
"""

from typing import List, Optional, Union, Dict
from datetime import datetime, timedelta

from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, FSInputFile, InputMediaPhoto
from aiogram.enums.parse_mode import ParseMode

from icecream import ic
from sqlalchemy.ext.asyncio import AsyncSession

from States import user_states
from database.enumirate.orders_enum import OrdersStatus
from database.models.orders_model import Order
from database.orm_query.dish_orm import get_dish_by_id_orm, get_user_cart_items
from database.orm_query.order_item_orm import OrderItemRepository
from database.orm_query.orders_orm import OrderRepository
from database.orm_query.address_orm import AddressRepository
from database.orm_query.delivery_status_orm import DeliveryStatusRepository
from database.orm_query.delivery_orm import DeliveryRepository

from keybords.inline import get_callback_btns
from tools import parse_callback, send_clean_message, notify_admins
from config import last_message_dict, ADMIN_IDS, WORK_DIR
from bot_instance import get_bot_instance


# =============================================================================
# CONSTANTS
# =============================================================================

USER_CART_IMAGE = "image/user_images/user_cart.png"

# -----------------------------------------------------------------------------
# Callback prefixes
# -----------------------------------------------------------------------------
CALLBACK_ADD_TO_CART_PREFIX = "add_to_cart_"
CALLBACK_EDIT_DISH_IN_CART = "dish_in_cart_"
CALLBACK_DECREASE_DISH_PREFIX = "decrease_dish_"
CALLBACK_REMOVE_DISH_PREFIX = "remove_dish_"
CALLBACK_PASS = "pass_call"

# -----------------------------------------------------------------------------
# Navigation callbacks
# -----------------------------------------------------------------------------
CALLBACK_CART = "active_orders"
CALLBACK_BACK_TO_MENU = "back_to_user_menu"
CALLBACK_MAIN_MENU = "main_menu"
CALLBACK_CHECKOUT = "checkout"
CALLBACK_SKIP_COMMENT = "skip_comment"

# Callback для дат доставки
CALLBACK_SELECT_DELIVERY_DATE = "select_delivery_date_"
CALLBACK_DELIVERY_DATE_SELECTED = "delivery_date_selected_"
CALLBACK_BACK_TO_ADDRESS = "back_to_address"

# Callback для выбора временного диапазона
CALLBACK_SELECT_HOUR = "select_hour_"
CALLBACK_RESET_HOURS = "reset_hours"
CALLBACK_CONFIRM_TIME_RANGE = "confirm_time_range"
CALLBACK_BACK_TO_DATES = "back_to_dates"

# Callback для адресов
CALLBACK_SELECT_ADDRESS = "select_address_"
CALLBACK_ADD_ADDRESS = "add_address"
CALLBACK_USE_GEOLOCATION = "use_geolocation"
CALLBACK_CONFIRM_ADDRESS = "confirm_address"
CALLBACK_EDIT_ADDRESS = "edit_address"
CALLBACK_DELETE_ADDRESS = "delete_address_"
CALLBACK_ENTER_MANUALLY = "enter_manually"

# -----------------------------------------------------------------------------
# Button text constants
# -----------------------------------------------------------------------------
BUTTON_TEXT = {
    "back_to_menu": "🍽 В меню",
    "main_menu": "🏠 Главная",
    "remove_from_cart": "❌ Убрать из корзины",
    "back_to_cart": "🔙 Назад к корзине",
    "empty_cart_menu": "🍽 В меню",
    "empty_cart_main": "🏠 Главная",
    "checkout": "✅ Оформить заказ",
    "skip_comment": "⏭ Пропустить",
    "add_new_address": "➕ Добавить новый адрес",
    "use_geolocation": "📍 Отправить геопозицию",
    "enter_manually": "✏️ Ввести координаты вручную",
    "confirm": "✅ Подтвердить",
    "edit": "✏️ Редактировать",
    "delete": "🗑 Удалить",
    "select_delivery_date": "📅 Выбрать дату доставки",
    "back_to_checkout": "🔙 Назад к оформлению"
}

# -----------------------------------------------------------------------------
# Delivery date messages
# -----------------------------------------------------------------------------

DELIVERY_DATE_SELECT_PROMPT = """
📅 <b>Выберите дату доставки</b>

Когда вам удобно получить заказ?

{delivery_dates_list}

<i>Минимальное время до доставки — 2 часа</i>
"""

DELIVERY_DATE_CONFIRM_TEXT = """
📅 <b>Вы выбрали дату доставки</b>

<b>📆 Дата:</b> {date}
<b>📊 Статус:</b> {status_icon} {status_text}
<b>📦 Заказов на эту дату:</b> {orders}/{limit}

Всё верно?
"""

NO_DELIVERY_DATES_TEXT = """
📭 <b>Нет доступных дат доставки</b>

К сожалению, на ближайшее время нет свободных дат.
Пожалуйста, попробуйте позже или свяжитесь с администратором.

<i>Мы работаем над тем, чтобы доставить ваш заказ как можно скорее 🤍</i>
"""

# -----------------------------------------------------------------------------
# Time range messages
# -----------------------------------------------------------------------------

TIME_RANGE_SELECT_PROMPT = """
🕐 <b>Выберите удобное время доставки</b>

📅 <b>Дата:</b> {date}

Нажмите на <b>ДВА ЧАСА</b> — начало и конец диапазона.
Часы между ними подсветятся зелёным ✅

<b>Выбранный диапазон:</b> {selected_range}

{hours_buttons}

<i>• Нажмите "Сбросить" чтобы выбрать заново</i>
<i>• После выбора нажмите "Подтвердить"</i>
"""

TIME_RANGE_CONFIRM_TEXT = """
✅ <b>Время доставки выбрано!</b>

📅 <b>Дата:</b> {date}
🕐 <b>Время:</b> {time_range}

Всё верно?
"""

# -----------------------------------------------------------------------------
# Cart messages
# -----------------------------------------------------------------------------

CART_EMPTY_MESSAGE = """
🧺 <b>Ваша корзина пока пуста</b>

Загляните в наше <b>меню</b> — там столько всего вкусного!

<i>Аромат свежей выпечки уже ждёт вас 🥐✨</i>
"""

CART_WELCOME_MESSAGE = """
🧺 <b>Ваша корзина</b>

Вот что вы выбрали сегодня:
"""

CART_ITEM_FORMAT = """
{number}. <b>{name}</b>
   {description}
   🥄 {quantity} × {price}₽ = <b>{subtotal}₽</b>
"""

CART_TOTAL_FORMAT = """
━━━━━━━━━━━━━━━━━━━━━
📦 <b>Итого:</b> {total}₽ <i>({items_count} позиции)</i>
"""

DISH_MANAGEMENT_MESSAGE = """
🍞 <b>{name}</b>

<i>{description}</i>

━━━━━━━━━━━━━━━━━━━━━
💰 Цена: <b>{price}₽</b>
🥄 Количество: <b>{quantity}</b>
💵 Сумма: <b>{subtotal}₽</b>
━━━━━━━━━━━━━━━━━━━━━

<i>Что хотите сделать с этим блюдом?</i>
"""

COMMENT_PROMPT = """
📝 <b>Пожелания к заказу</b>

У вас есть особые пожелания?
Можете написать их здесь, например:
• Без лука
• Побыстрее
• Позвоните перед доставкой

Или нажмите "Пропустить"
"""

ADDRESS_SELECT_PROMPT = """
📍 <b>Выберите адрес доставки</b>

Выберите адрес из сохранённых или добавьте новый:
"""

ADDRESS_ADD_PROMPT = """
📍 <b>Добавление нового адреса</b>

Введите название адреса (например: "Дом", "Работа", "Дача"):
"""

ADDRESS_COORDINATES_PROMPT = """
📍 <b>Координаты адреса</b>

Вы можете:
• 📍 Отправить геопозицию (нажмите кнопку ниже)
• ✏️ Ввести координаты вручную в формате: <i>широта, долгота</i>

Пример: <i>55.751244, 37.618423</i>
"""

ADDRESS_MANUAL_PROMPT = """
📍 <b>Введите координаты вручную</b>

Формат: <i>широта, долгота</i>

Пример: <i>55.751244, 37.618423</i>
"""

ADDRESS_CONFIRM_TEXT = """
📍 <b>Проверьте адрес</b>

<b>Название:</b> {name}
<b>Координаты:</b> {coordinates}

Всё верно?
"""

PAYMENT_PROMPT = """
💳 <b>Оплата заказа</b>

Для подтверждения заказа отправьте фото чека об оплате.

Реквизиты для оплаты:
━━━━━━━━━━━━━━━━━━━━━
🏦 <b>Получатель:</b> ИП Иванова
💳 <b>Счёт:</b> 40802810123456789012
🏛 <b>Банк:</b> Т-Банк
🔢 <b>ИНН:</b> 123456789012
🔢 <b>КПП:</b> 123456789
📱 <b>Сумма:</b> {total} ₽
━━━━━━━━━━━━━━━━━━━━━

После оплаты отправьте фото чека.
<i>Заказ перейдёт в обработку после подтверждения оплаты</i>
"""

ORDER_CONFIRMED_VERIFICATION = """
✅ <b>Заказ №{order_id} оформлен!</b>

Ваш заказ передан на проверку. После подтверждения оплаты менеджером,
заказ будет передан в работу.

<b>Состав заказа:</b>
{items_text}

<b>Адрес доставки:</b>
{address_text}

<b>Дата доставки:</b>
{delivery_date_text}

<b>Время доставки:</b>
{delivery_time_range}

<b>Стоимость доставки:</b> {delivery_price} ₽

<b>Итого к оплате:</b> {total_with_delivery} ₽

<i>Статус заказа можно отслеживать в разделе "🍳 Активные заказы" 🤍</i>
"""

ORDER_CREATED_AWAITING = """
✅ <b>Заказ №{order_id} принят!</b>

Ваш адрес доставки нуждается в проверке.
Наш менеджер скоро определит зону доставки и свяжется с вами.

После подтверждения адреса вы сможете выбрать дату доставки и оплатить заказ
в разделе <b>"✅ Подтвердить заказы"</b>.

<b>Состав заказа:</b>
{items_text}

<b>Адрес доставки:</b>
{address_text}

<b>Итого:</b> {total} ₽

<i>Ожидайте уведомление 🤍</i>
"""

ADD_TO_CART_SUCCESS = "🥐 <b>{name}</b> добавили в корзину! ✨"
INCREASE_QUANTITY_SUCCESS = "🥖 Ещё один <b>{name}</b>! Теперь {quantity} штук"
DECREASE_QUANTITY_SUCCESS = "🥨 Убрали один <b>{name}</b>. Осталось {quantity}"
REMOVE_FROM_CART_SUCCESS = "🗑 <b>{name}</b> убрали из корзины. Приходите ещё! 🥧"


# =============================================================================
# ВРЕМЕННОЕ ХРАНИЛИЩЕ ДЛЯ ВЫБОРА ЧАСОВ
# =============================================================================

# Словарь для хранения временного выбора пользователя
# Ключ: user_id, Значение: {'start': int, 'end': int, 'delivery_id': int}
_temp_hour_selection: Dict[int, Dict] = {}


# =============================================================================
# ROUTER INITIALIZATION
# =============================================================================

UserBasketRouter = Router(name="user_basket")


# =============================================================================
# BUTTONS CREATION FUNCTIONS
# =============================================================================

def get_hour_buttons(selected_start: int = None, selected_end: int = None) -> tuple[dict, list]:
    """
    Создаёт кнопки для часов 9-20 с визуализацией выбранного диапазона.
    Часы внутри диапазона становятся зелёными.
    """
    buttons = {}
    sizes = []
    row = []
    
    for hour in range(9, 21):  # 9,10,11,...,20
        # Определяем, входит ли час в выбранный диапазон
        is_in_range = False
        if selected_start is not None and selected_end is not None:
            if selected_start <= selected_end:
                is_in_range = selected_start <= hour <= selected_end
            else:
                is_in_range = hour >= selected_start or hour <= selected_end
        
        # Эмодзи для визуализации
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
        
        if len(row) == 4:  # по 4 кнопки в ряд
            sizes.append(4)
            row = []
    
    if row:
        sizes.append(len(row))
    
    return buttons, sizes


async def create_cart_dishes_buttons(cart_items: list) -> tuple[dict, list]:
    """Создаёт кнопки для списка блюд в корзине."""
    items = cart_items[:-1] if cart_items and "total" in cart_items[-1] else cart_items
    
    buttons = {}
    sizes = []
    
    for item in items:
        subtotal = item['price'] * item['quantity']
        button_text = f"🍽 {item['name']} ✖️{item['quantity']} = {subtotal}₽"
        callback_data = f"{CALLBACK_EDIT_DISH_IN_CART}{item['dish_id']}_{item['item_id']}"
        buttons[button_text] = callback_data
        sizes.append(1)
    
    buttons[BUTTON_TEXT["checkout"]] = CALLBACK_CHECKOUT
    sizes.append(1)
    
    buttons[BUTTON_TEXT["back_to_menu"]] = CALLBACK_BACK_TO_MENU
    buttons[BUTTON_TEXT["main_menu"]] = CALLBACK_MAIN_MENU
    sizes.append(2)
    
    return buttons, sizes


async def create_compact_dishes_buttons(cart_items: list) -> tuple[dict, list]:
    """Компактная версия кнопок — блюда по 2 в ряд."""
    items = cart_items[:-1] if cart_items and "total" in cart_items[-1] else cart_items
    
    buttons = {}
    sizes = []
    
    row_buttons = []
    for i, item in enumerate(items, 1):
        button_text = f"{i}. {item['name']} ({item['quantity']})"
        callback_data = f"{CALLBACK_EDIT_DISH_IN_CART}{item['dish_id']}_{item['item_id']}"
        
        buttons[button_text] = callback_data
        row_buttons.append(button_text)
        
        if len(row_buttons) == 2:
            sizes.append(2)
            row_buttons = []
    
    if row_buttons:
        sizes.append(len(row_buttons))
    
    buttons[BUTTON_TEXT["back_to_menu"]] = CALLBACK_BACK_TO_MENU
    buttons[BUTTON_TEXT["main_menu"]] = CALLBACK_MAIN_MENU
    sizes.append(2)
    
    return buttons, sizes


async def create_dish_management_buttons(
    dish_id: int,
    item_id: int, 
    current_quantity: int
) -> tuple[dict, list]:
    """Создаёт кнопки управления для отдельного блюда."""
    buttons = {}
    sizes = []
    
    first_row = {}
    
    if current_quantity > 1:
        first_row["➖"] = f"{CALLBACK_DECREASE_DISH_PREFIX}{item_id}_{current_quantity}"
    else:
        first_row["➖"] = CALLBACK_PASS
    
    first_row[f"{current_quantity}"] = CALLBACK_PASS
    first_row["➕"] = f"{CALLBACK_ADD_TO_CART_PREFIX}{dish_id}"
    
    buttons.update(first_row)
    sizes.append(3)
    
    buttons[BUTTON_TEXT["remove_from_cart"]] = f"{CALLBACK_REMOVE_DISH_PREFIX}{item_id}"
    sizes.append(1)
    
    buttons[BUTTON_TEXT["back_to_cart"]] = CALLBACK_CART
    sizes.append(1)
    
    return buttons, sizes


def get_empty_cart_buttons() -> tuple[dict, list]:
    """Кнопки для пустой корзины."""
    buttons = {
        BUTTON_TEXT["empty_cart_menu"]: CALLBACK_BACK_TO_MENU,
        BUTTON_TEXT["empty_cart_main"]: CALLBACK_MAIN_MENU
    }
    sizes = [1, 1]
    return buttons, sizes


# =============================================================================
# FORMATTING FUNCTIONS
# =============================================================================

def format_cart_text(items: List[dict]) -> str:
    """Форматирует содержимое корзины."""
    if not items:
        return CART_EMPTY_MESSAGE
    
    items_copy = items.copy()
    
    if "total" in items_copy[-1]:
        total_info = items_copy.pop()
        total = total_info["total"]
        items_count = total_info["items_count"]
    else:
        total = sum(item["price"] * item["quantity"] for item in items_copy)
        items_count = len(items_copy)
    
    text_lines = [CART_WELCOME_MESSAGE]
    
    for i, item in enumerate(items_copy, 1):
        desc = item.get('description', '')
        if len(desc) > 45:
            desc = desc[:45] + "..."
        
        text_lines.append(
            CART_ITEM_FORMAT.format(
                number=i,
                name=item['name'],
                description=desc,
                quantity=item['quantity'],
                price=item['price'],
                subtotal=item['price'] * item['quantity']
            )
        )
    
    text_lines.append(CART_TOTAL_FORMAT.format(total=total, items_count=items_count))
    
    return "\n".join(text_lines)


def format_dish_details_text(item: dict) -> str:
    """Карточка блюда в корзине."""
    return DISH_MANAGEMENT_MESSAGE.format(
        name=item['name'],
        description=item.get('description', 'Нет описания'),
        price=item['price'],
        quantity=item['quantity'],
        subtotal=item['price'] * item['quantity']
    )


def format_address_text(address) -> str:
    """Форматирует адрес для отображения с деталями."""
    if not address:
        return "📍 Адрес не указан"
    
    # Формируем полный адрес
    address_parts = []
    if address.street:
        address_parts.append(address.street)
    if address.house:
        address_parts.append(address.house)
    
    address_line = ", ".join(address_parts)
    
    details = []
    if address.building:
        details.append(f"корп. {address.building}")
    if address.apartment:
        details.append(f"кв. {address.apartment}")
    if address.floor:
        details.append(f"этаж {address.floor}")
    if address.entrance:
        details.append(f"подъезд {address.entrance}")
    if address.intercom:
        details.append(f"домофон {address.intercom}")
    
    text = f"📍 <b>{address.adress_name}</b>\n"
    if address_line:
        text += f"📍 {address_line}\n"
    if details:
        text += f"📍 {', '.join(details)}\n"
    if address.comment:
        text += f"📝 {address.comment}\n"
    text += f"📍 Координаты: {address.coordinates}"
    
    return text


def format_delivery_date(date) -> str:
    """Форматирует дату доставки для отображения (только дата)."""
    return date.delivery_date.strftime("%d.%m.%Y")


def format_delivery_time_range(hour_from: int, hour_to: int = None) -> str:
    """Форматирует временной диапазон для отображения."""
    if hour_to and hour_to != hour_from:
        return f"{hour_from}:00 - {hour_to}:00"
    return f"{hour_from}:00"


def get_delivery_status_icon(date) -> tuple[str, str]:
    """Возвращает иконку и текст статуса даты доставки."""
    if not date.is_available:
        return "❌", "Недоступна"
    if date.order_limit and date.current_orders >= date.order_limit:
        return "🔴", "Лимит заполнен"
    return "✅", "Доступна"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def clear_temp_selection(user_id: int) -> None:
    """Очищает временные данные выбора часов для пользователя."""
    if user_id in _temp_hour_selection:
        del _temp_hour_selection[user_id]


async def get_selected_cart_item(
    session: AsyncSession,
    user_id: int,
    dish_id: int
) -> Optional[dict]:
    """Находит блюдо в корзине по его ID."""
    cart_items = await get_user_cart_items(session, user_id)
    
    for item in cart_items:
        if item.get("dish_id") == dish_id:
            return item
    
    return None


async def show_dish_management(
    call: CallbackQuery,
    session: AsyncSession,
    dish_id: int,
    item_id: int
) -> None:
    """Показывает карточку управления блюдом."""
    user_id = call.from_user.id
    selected_item = await get_selected_cart_item(session, user_id, dish_id)
    
    if not selected_item:
        await call.answer("❌ Блюдо не найдено в корзине", show_alert=True)
        return
    
    buttons, sizes = await create_dish_management_buttons(
        dish_id=dish_id,
        item_id=item_id,
        current_quantity=selected_item['quantity']
    )
    
    text = format_dish_details_text(selected_item)
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=sizes,
        parse_mode="HTML"
    )


async def get_cart_total_text(session: AsyncSession, user_id: int, cart: Order) -> tuple[str, int]:
    """Получает текст состава заказа и общую сумму."""
    order_repo = OrderRepository(session=session, user_id=user_id)
    items = await order_repo.get_order_items(cart.order_id)
    
    items_text = ""
    total = 0
    
    for item in items:
        items_text += f"\n• {item['name']} — {item['quantity']} × {item['price']}₽ = {item['subtotal']}₽"
        total += item['subtotal']
    
    return items_text, total


async def get_delivery_price_for_order(
    session: AsyncSession,
    address_id: int,
    delivery_id: int = None
) -> int:
    """
    Получает стоимость доставки для заказа.
    
    Args:
        session: сессия БД
        address_id: ID адреса
        delivery_id: ID даты доставки (опционально, для получения зоны)
    
    Returns:
        int: стоимость доставки
    """
    try:
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


async def send_admin_notification(
    order_id: int,
    session: AsyncSession,
    has_zone: bool
) -> None:
    """
    Отправляет уведомление администраторам о новом заказе.
    """
    order_repo = OrderRepository(session)
    
    # Получаем статистику
    new_orders_count = await order_repo.get_orders_by_status_count(OrdersStatus.VERIFICATION)
    without_status_orders = await order_repo.get_orders_by_status(OrdersStatus.AWAITING_ADDRESS_STATUS)
    without_status_count = len(without_status_orders)
    ready_count = await order_repo.get_orders_by_status_count(OrdersStatus.READY_FOR_DELIVERY)
    
    bot = get_bot_instance()
    
    if has_zone:
        # Заказ с зоной
        text = f"""
🆕 <b>Новый заказ #{order_id}!</b>

<b>📊 Статистика:</b>
🆕 Новых заказов: <b>{new_orders_count}</b>
📍 Без зоны: <b>{without_status_count}</b>
📦 Готовых: <b>{ready_count}</b>

👉 Перейдите в админ-панель для обработки.
"""
        await notify_admins(
            bot=bot,
            text=text,
            admin_ids=ADMIN_IDS,
            buttons={"🔍 Перейти": "new_orders"},
            sizes=[1]
        )
    else:
        # Заказ без зоны
        text = f"""
📍 <b>Новый заказ #{order_id} без зоны доставки!</b>

<b>📊 Статистика:</b>
🆕 Новых заказов: <b>{new_orders_count}</b>
📍 Без зоны: <b>{without_status_count}</b>
📦 Готовых: <b>{ready_count}</b>

👉 Перейдите в раздел <b>"📍 Заказы без статуса"</b>.
"""
        await notify_admins(
            bot=bot,
            text=text,
            admin_ids=ADMIN_IDS,
            buttons={"🔍 Перейти": "orders_without_status"},
            sizes=[1]
        )


async def finalize_order_with_zone(
    target: Union[Message, CallbackQuery],
    state: FSMContext,
    session: AsyncSession,
    order_id: int,
    comment: Optional[str],
    address_id: int,
    delivery_id: int,
    photo_id: str,
    hour_from: Optional[int] = None,
    hour_to: Optional[int] = None
) -> None:
    """
    Финальное оформление заказа с зоной доставки:
    - Сохраняет комментарий и фото
    - Привязывает дату доставки
    - Сохраняет часы доставки
    - Переводит заказ в VERIFICATION
    - Отображает сумму с доставкой
    """
    order_repo = OrderRepository(session=session)
    delivery_repo = DeliveryRepository(session)
    address_repo = AddressRepository(session)
    
    # 1. Сохраняем комментарий и фото
    await order_repo.update_order_comment(order_id, comment)
    await order_repo.update_order_photo(order_id, photo_id)
    
    # 2. Сохраняем часы доставки
    if hour_from is not None:
        await order_repo.update_delivery_hours(order_id, hour_from, hour_to)
    
    # 3. Привязываем дату доставки
    if delivery_id:
        await delivery_repo.assign_to_order(order_id, delivery_id)
    
    # 4. Переводим заказ в VERIFICATION
    updated_order = await order_repo.update_order_status(order_id, OrdersStatus.VERIFICATION)
    
    if not updated_order:
        await target.answer("❌ Не удалось оформить заказ. Попробуйте позже.")
        await state.clear()
        return
    
    await session.commit()
    
    # 5. Получаем детали для сообщения
    order_details = await order_repo.get_order_with_details(order_id)
    
    if not order_details:
        await target.answer("❌ Не удалось получить детали заказа")
        await state.clear()
        return
    
    items_text = ""
    for item in order_details['items']:
        items_text += f"\n• {item['name']} — {item['quantity']} × {item['price']}₽ = {item['subtotal']}₽"
    
    address = await address_repo.get_by_id(address_id) if address_id else None
    address_text = format_address_text(address) if address else "📍 Адрес не указан"
    
    delivery_date = await delivery_repo.get_order_delivery(order_id)
    delivery_date_text = format_delivery_date(delivery_date) if delivery_date else "📅 Не указана"
    
    # Форматируем время доставки
    delivery_time_range = format_delivery_time_range(hour_from, hour_to) if hour_from else "Не указано"
    
    # Получаем стоимость доставки
    delivery_price = await get_delivery_price_for_order(session, address_id, delivery_id)
    order_total = order_details['total']
    total_with_delivery = order_total + delivery_price
    
    text = ORDER_CONFIRMED_VERIFICATION.format(
        order_id=order_id,
        items_text=items_text,
        address_text=address_text,
        delivery_date_text=delivery_date_text,
        delivery_time_range=delivery_time_range,
        delivery_price=delivery_price,
        total_with_delivery=total_with_delivery
    )
    
    buttons = {
        "🍽 В меню": CALLBACK_BACK_TO_MENU,
        "🏠 Главная": CALLBACK_MAIN_MENU
    }
    
    await send_clean_message(
        target=target,
        text=text,
        buttons=buttons,
        sizes=[1, 1],
        parse_mode="HTML"
    )
    
    # Отправляем уведомление администраторам
    await send_admin_notification(order_id, session, has_zone=True)
    
    # Очищаем временные данные
    clear_temp_selection(target.from_user.id)
    await state.clear()


async def finalize_order_without_zone(
    target: Union[Message, CallbackQuery],
    state: FSMContext,
    session: AsyncSession,
    order_id: int,
    address_id: int
) -> None:
    """
    Финальное оформление заказа без зоны:
    - Переводит заказ в AWAITING_ADDRESS_STATUS
    """
    order_repo = OrderRepository(session=session)
    address_repo = AddressRepository(session)
    
    # 1. Переводим заказ в AWAITING_ADDRESS_STATUS
    updated_order = await order_repo.update_order_status(order_id, OrdersStatus.AWAITING_ADDRESS_STATUS)
    
    if not updated_order:
        await target.answer("❌ Не удалось оформить заказ. Попробуйте позже.")
        await state.clear()
        return
    
    await session.commit()
    
    # 2. Получаем детали для сообщения
    order_details = await order_repo.get_order_with_details(order_id)
    
    if not order_details:
        await target.answer("❌ Не удалось получить детали заказа")
        await state.clear()
        return
    
    items_text = ""
    for item in order_details['items']:
        items_text += f"\n• {item['name']} — {item['quantity']} × {item['price']}₽ = {item['subtotal']}₽"
    
    address = await address_repo.get_by_id(address_id) if address_id else None
    address_text = format_address_text(address) if address else "📍 Адрес не указан"
    
    total = order_details['total']
    
    text = ORDER_CREATED_AWAITING.format(
        order_id=order_id,
        items_text=items_text,
        address_text=address_text,
        total=total
    )
    
    buttons = {
        "🍽 В меню": CALLBACK_BACK_TO_MENU,
        "🏠 Главная": CALLBACK_MAIN_MENU
    }
    
    await send_clean_message(
        target=target,
        text=text,
        buttons=buttons,
        sizes=[1, 1],
        parse_mode="HTML"
    )
    
    # Отправляем уведомление администраторам
    await send_admin_notification(order_id, session, has_zone=False)
    
    await state.clear()


# =============================================================================
# TIME RANGE SELECTION HANDLERS
# =============================================================================

async def show_time_range_selection(
    target: Union[Message, CallbackQuery],
    state: FSMContext,
    session: AsyncSession,
    delivery_id: int
) -> None:
    """Показывает интерфейс выбора временного диапазона."""
    delivery_repo = DeliveryRepository(session)
    delivery_date = await delivery_repo.get_by_id(delivery_id)
    
    if not delivery_date:
        await target.answer("❌ Дата не найдена")
        return
    
    user_id = target.from_user.id
    
    # Инициализируем временное хранилище
    _temp_hour_selection[user_id] = {
        'delivery_id': delivery_id,
        'start': None,
        'end': None
    }
    
    await state.set_state(user_states.UserMenu.select_time_range)
    await state.update_data(selected_delivery_id=delivery_id)
    
    buttons, sizes = get_hour_buttons()
    
    # Добавляем кнопки управления
    buttons["🔄 Сбросить"] = CALLBACK_RESET_HOURS
    buttons["✅ Подтвердить"] = CALLBACK_CONFIRM_TIME_RANGE
    buttons["🔙 Назад"] = CALLBACK_BACK_TO_DATES
    sizes.extend([1, 1, 1])
    
    text = TIME_RANGE_SELECT_PROMPT.format(
        date=format_delivery_date(delivery_date),
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


@UserBasketRouter.callback_query(F.data.startswith(CALLBACK_SELECT_HOUR), StateFilter(user_states.UserMenu.select_time_range))
async def select_hour(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Обработка выбора часа (первый или второй в диапазоне)."""
    hour = int(call.data.split("_")[2])
    user_id = call.from_user.id
    
    # Получаем текущее состояние выбора
    if user_id not in _temp_hour_selection:
        _temp_hour_selection[user_id] = {'start': None, 'end': None}
    
    current = _temp_hour_selection[user_id]
    
    # Логика выбора
    if current['start'] is None:
        # Первый час — начало диапазона
        current['start'] = hour
        await call.answer(f"🔵 Начало диапазона: {hour}:00")
        
    elif current['end'] is None:
        # Второй час — конец диапазона
        current['end'] = hour
        
        # Сортируем, чтобы начало было меньше конца
        if current['start'] > current['end']:
            current['start'], current['end'] = current['end'], current['start']
        
        await call.answer(f"✅ Диапазон: {current['start']}:00 - {current['end']}:00")
        
    else:
        # Если уже выбран полный диапазон — сбрасываем и начинаем заново
        current['start'] = hour
        current['end'] = None
        await call.answer(f"🔄 Начало заново: {hour}:00")
    
    # Обновляем отображение
    data = await state.get_data()
    delivery_id = data.get('selected_delivery_id')
    
    delivery_repo = DeliveryRepository(session)
    delivery_date = await delivery_repo.get_by_id(delivery_id)
    
    # Формируем текст с выбранным диапазоном
    if current['start'] is not None and current['end'] is not None:
        range_text = f"{current['start']}:00 - {current['end']}:00"
    elif current['start'] is not None:
        range_text = f"{current['start']}:00 (выберите конец)"
    else:
        range_text = "не выбран"
    
    # Генерируем кнопки с подсветкой
    buttons, sizes = get_hour_buttons(current['start'], current['end'])
    buttons["🔄 Сбросить"] = CALLBACK_RESET_HOURS
    buttons["✅ Подтвердить"] = CALLBACK_CONFIRM_TIME_RANGE
    buttons["🔙 Назад"] = CALLBACK_BACK_TO_DATES
    sizes.extend([1, 1, 1])
    
    text = TIME_RANGE_SELECT_PROMPT.format(
        date=format_delivery_date(delivery_date),
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


@UserBasketRouter.callback_query(F.data == CALLBACK_RESET_HOURS, StateFilter(user_states.UserMenu.select_time_range))
async def reset_hours(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Сброс выбранного диапазона."""
    user_id = call.from_user.id
    
    if user_id in _temp_hour_selection:
        _temp_hour_selection[user_id]['start'] = None
        _temp_hour_selection[user_id]['end'] = None
    
    await call.answer("🔄 Выбор сброшен")
    
    # Перерисовываем интерфейс
    data = await state.get_data()
    delivery_id = data.get('selected_delivery_id')
    
    delivery_repo = DeliveryRepository(session)
    delivery_date = await delivery_repo.get_by_id(delivery_id)
    
    buttons, sizes = get_hour_buttons()
    buttons["🔄 Сбросить"] = CALLBACK_RESET_HOURS
    buttons["✅ Подтвердить"] = CALLBACK_CONFIRM_TIME_RANGE
    buttons["🔙 Назад"] = CALLBACK_BACK_TO_DATES
    sizes.extend([1, 1, 1])
    
    text = TIME_RANGE_SELECT_PROMPT.format(
        date=format_delivery_date(delivery_date),
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


@UserBasketRouter.callback_query(F.data == CALLBACK_CONFIRM_TIME_RANGE, StateFilter(user_states.UserMenu.select_time_range))
async def confirm_time_range(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Подтверждение выбранного диапазона и сохранение в заказ."""
    user_id = call.from_user.id
    selection = _temp_hour_selection.get(user_id, {})
    
    start_hour = selection.get('start')
    end_hour = selection.get('end')
    
    if start_hour is None:
        await call.answer("❌ Сначала выберите начало диапазона!", show_alert=True)
        return
    
    # Если выбран только начало, устанавливаем его же как конец (один час)
    if end_hour is None:
        end_hour = start_hour
    
    data = await state.get_data()
    delivery_id = data.get('selected_delivery_id')
    order_id = data.get('checkout_order_id')
    
    if not order_id:
        await call.answer("❌ Ошибка: заказ не найден", show_alert=True)
        return
    
    # Сохраняем часы в заказ
    order_repo = OrderRepository(session=session)
    updated_order = await order_repo.update_delivery_hours(order_id, start_hour, end_hour)
    
    if updated_order:
        await session.commit()
        
        # Сохраняем выбранную дату и время в состояние для оплаты
        await state.update_data(
            selected_delivery_id=delivery_id,
            selected_hour_from=start_hour,
            selected_hour_to=end_hour
        )
        
        # Переходим к оплате
        await checkout_show_payment(call, state, session)
    else:
        await call.answer("❌ Ошибка при сохранении времени доставки", show_alert=True)


@UserBasketRouter.callback_query(F.data == CALLBACK_BACK_TO_DATES, StateFilter(user_states.UserMenu.select_time_range))
async def back_to_dates(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Возврат к выбору даты."""
    # Очищаем временные данные
    clear_temp_selection(call.from_user.id)
    
    # Возвращаемся к выбору даты
    await show_delivery_date_selection(call, state, session)


# =============================================================================
# DELIVERY DATE SELECTION HANDLERS (ОБНОВЛЁННЫЕ)
# =============================================================================

async def show_delivery_date_selection(
    target: Union[Message, CallbackQuery],
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Показывает выбор даты доставки."""
    delivery_repo = DeliveryRepository(session)
    available_dates = await delivery_repo.get_available_dates(min_hours_ahead=2)
    
    if not available_dates:
        await send_clean_message(
            target=target,
            text=NO_DELIVERY_DATES_TEXT,
            buttons={
                "🔙 Назад": CALLBACK_CHECKOUT
            },
            sizes=[1],
            parse_mode="HTML"
        )
        return
    
    dates_list = ""
    buttons = {}
    sizes = []
    
    for date in available_dates[:10]:
        date_str = format_delivery_date(date)  # ✅ Только дата
        status_icon, status_text = get_delivery_status_icon(date)
        limit_info = f"{date.current_orders}/{date.order_limit or '∞'}"
        
        dates_list += f"\n• {status_icon} {date_str} — заказов: {limit_info}"
        buttons[f"{status_icon} {date_str}"] = f"{CALLBACK_SELECT_DELIVERY_DATE}{date.delivery_id}"
        sizes.append(1)
    
    if len(available_dates) > 10:
        dates_list += f"\n... и ещё {len(available_dates) - 10} дат"
    
    text = DELIVERY_DATE_SELECT_PROMPT.format(delivery_dates_list=dates_list)
    
    buttons["🔙 Назад"] = CALLBACK_BACK_TO_ADDRESS
    sizes.append(1)
    
    await send_clean_message(
        target=target,
        text=text,
        buttons=buttons,
        sizes=sizes,
        parse_mode="HTML"
    )


@UserBasketRouter.callback_query(F.data.startswith(CALLBACK_SELECT_DELIVERY_DATE))
async def select_delivery_date(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Выбор конкретной даты доставки — переход к выбору времени."""
    delivery_id = int(call.data.split("_")[3])
    
    delivery_repo = DeliveryRepository(session)
    delivery_date = await delivery_repo.get_by_id(delivery_id)
    
    if not delivery_date:
        await call.answer("❌ Дата не найдена", show_alert=True)
        return
    
    if not delivery_date.is_available:
        await call.answer("❌ Эта дата больше недоступна", show_alert=True)
        await show_delivery_date_selection(call, state, session)
        return
    
    if delivery_date.order_limit and delivery_date.current_orders >= delivery_date.order_limit:
        await call.answer("❌ На эту дату лимит заказов исчерпан", show_alert=True)
        await show_delivery_date_selection(call, state, session)
        return
    
    # Сохраняем выбранную дату и переходим к выбору времени
    await state.update_data(selected_delivery_id=delivery_id)
    await show_time_range_selection(call, state, session, delivery_id)


# =============================================================================
# NAVIGATION HANDLERS
# =============================================================================

@UserBasketRouter.callback_query(F.data == CALLBACK_CART)
async def show_cart(call: CallbackQuery, session: AsyncSession) -> None:
    """Показывает корзину."""
    user_id = call.from_user.id
    cart_items = await get_user_cart_items(session, user_id)
    
    if not cart_items or len(cart_items) <= 1:
        buttons, sizes = get_empty_cart_buttons()
        
        # Пустая корзина с фото
        media_path = WORK_DIR / USER_CART_IMAGE
        
        if media_path.exists():
            media = FSInputFile(media_path)
            msg = await call.message.answer_photo(
                photo=media,
                caption=CART_EMPTY_MESSAGE,
                reply_markup=get_callback_btns(btns=buttons, sizes=tuple(sizes)),
                parse_mode="HTML"
            )
            await call.message.delete()
            
            # Очистка старых сообщений
            if user_id in last_message_dict and last_message_dict[user_id]:
                current_msg_id = msg.message_id
                for msg_id in last_message_dict[user_id][:]:
                    if msg_id != current_msg_id:
                        try:
                            await call.message.bot.delete_message(chat_id=user_id, message_id=msg_id)
                        except Exception:
                            pass
                last_message_dict[user_id] = [current_msg_id]
            else:
                if user_id not in last_message_dict:
                    last_message_dict[user_id] = []
                last_message_dict[user_id].append(msg.message_id)
        else:
            await send_clean_message(
                target=call,
                text=CART_EMPTY_MESSAGE,
                buttons=buttons,
                sizes=sizes
            )
        return
    
    text = format_cart_text(cart_items)
    buttons, sizes = await create_cart_dishes_buttons(cart_items)
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=sizes,
        parse_mode="HTML"
    )


@UserBasketRouter.callback_query(F.data.startswith(CALLBACK_EDIT_DISH_IN_CART))
async def manage_cart_dish(call: CallbackQuery, session: AsyncSession) -> None:
    """Переход к управлению конкретным блюдом."""
    ids, error = parse_callback(call, expected_prefix=CALLBACK_EDIT_DISH_IN_CART, expected_count=2)
    
    if error:
        await call.answer(error, show_alert=True)
        return
    
    dish_id, item_id = ids[0], ids[1]
    await show_dish_management(call, session, dish_id, item_id)


# =============================================================================
# CART OPERATION HANDLERS
# =============================================================================

@UserBasketRouter.callback_query(F.data.startswith(CALLBACK_ADD_TO_CART_PREFIX))
async def add_dish_to_cart(call: types.CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Добавляет блюдо в корзину или увеличивает количество."""
    dish_id, error = parse_callback(call, expected_prefix=CALLBACK_ADD_TO_CART_PREFIX)
    
    if error:
        await call.answer(error, show_alert=True)
        return
    
    dish_info = await get_dish_by_id_orm(session=session, dish_id=dish_id)
    if not dish_info:
        await call.answer("❌ Блюдо не найдено", show_alert=True)
        return
    
    order_repo = OrderRepository(session=session, user_id=call.from_user.id)
    item_repo = OrderItemRepository(db_session=session)
    
    active_order = await order_repo.get_user_active_orders()
    
    if not active_order:
        active_order = await order_repo.create_order()
        await session.commit()
    else:
        available_dish = await item_repo.get_by_order_and_dish(
            order_id=active_order.order_id, 
            dish_id=dish_id
        )
        
        if available_dish:
            new_quantity = available_dish.quantity + 1
            await item_repo.update_quantity(
                item_id=available_dish.item_id, 
                quantity=new_quantity
            )
            await session.commit()
            
            await call.answer(
                text=INCREASE_QUANTITY_SUCCESS.format(
                    name=dish_info['name'],
                    quantity=new_quantity
                ),
                show_alert=False
            )
            
            await show_dish_management(call, session, dish_id, available_dish.item_id)
            return
    
    await item_repo.create(
        order_id=active_order.order_id,
        dish_id=dish_info["dish_id"],
        price=dish_info["price"]
    )
    await session.commit()
    
    await call.answer(
        text=ADD_TO_CART_SUCCESS.format(name=dish_info['name']),
        show_alert=False
    )


@UserBasketRouter.callback_query(F.data.startswith(CALLBACK_DECREASE_DISH_PREFIX))
async def decrease_dish_quantity(call: CallbackQuery, session: AsyncSession) -> None:
    """Уменьшает количество блюда на 1."""
    ids, error = parse_callback(call, expected_prefix=CALLBACK_DECREASE_DISH_PREFIX, expected_count=2)
    
    if error:
        await call.answer(error, show_alert=True)
        return
    
    item_id, current_quantity = ids[0], ids[1]
    
    if current_quantity <= 1:
        await call.answer("❌ Нельзя уменьшить количество меньше 1", show_alert=True)
        return
    
    repo = OrderItemRepository(db_session=session)
    new_quantity = current_quantity - 1
    await repo.update_quantity(item_id=item_id, quantity=new_quantity)
    await session.commit()
    
    order_item = await repo.get_by_id(item_id)
    dish_info = await get_dish_by_id_orm(session=session, dish_id=order_item.dish_id) if order_item else None
    
    if dish_info:
        await call.answer(
            text=DECREASE_QUANTITY_SUCCESS.format(
                name=dish_info['name'],
                quantity=new_quantity
            ),
            show_alert=False
        )
    
    if order_item:
        await show_dish_management(call, session, order_item.dish_id, item_id)


@UserBasketRouter.callback_query(F.data.startswith(CALLBACK_REMOVE_DISH_PREFIX))
async def remove_dish_from_cart(call: CallbackQuery, session: AsyncSession) -> None:
    """Полностью удаляет блюдо из корзины."""
    item_id, error = parse_callback(call, expected_prefix=CALLBACK_REMOVE_DISH_PREFIX)
    
    if error:
        await call.answer(error, show_alert=True)
        return
    
    repo = OrderItemRepository(db_session=session)
    order_item = await repo.get_by_id(item_id)
    
    dish_name = "блюдо"
    if order_item:
        dish_info = await get_dish_by_id_orm(session=session, dish_id=order_item.dish_id)
        dish_name = dish_info['name'] if dish_info else "блюдо"
    
    await repo.delete(item_id=item_id)
    await session.commit()
    
    await call.answer(
        text=REMOVE_FROM_CART_SUCCESS.format(name=dish_name),
        show_alert=False
    )
    
    await show_cart(call, session)


# =============================================================================
# CHECKOUT HANDLERS
# =============================================================================

@UserBasketRouter.callback_query(F.data == CALLBACK_CHECKOUT)
async def checkout_start(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Начало оформления заказа — запрос комментария."""
    user_id = call.from_user.id
    order_repo = OrderRepository(session=session, user_id=user_id)
    
    cart = await order_repo.get_user_active_orders()
    
    if not cart:
        await call.answer("🛒 Корзина пуста", show_alert=True)
        return
    
    items = await order_repo.get_order_items(cart.order_id)
    if not items:
        await call.answer("🛒 Корзина пуста", show_alert=True)
        return
    
    # Очищаем временные данные на случай, если остались от предыдущей попытки
    clear_temp_selection(user_id)
    
    await state.update_data(checkout_order_id=cart.order_id)
    await state.set_state(user_states.UserMenu.checkout_comment)
    
    await send_clean_message(
        target=call,
        text=COMMENT_PROMPT,
        buttons={
            BUTTON_TEXT["skip_comment"]: CALLBACK_SKIP_COMMENT,
            "🔙 Назад": CALLBACK_CART
        },
        sizes=[1, 1],
        parse_mode="HTML"
    )


@UserBasketRouter.callback_query(F.data == CALLBACK_SKIP_COMMENT, StateFilter(user_states.UserMenu.checkout_comment))
async def checkout_skip_comment(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Пропустить комментарий."""
    await state.update_data(comment=None)
    await call.message.delete()
    await checkout_show_address_selection(call, state, session)


@UserBasketRouter.message(F.text, StateFilter(user_states.UserMenu.checkout_comment))
async def checkout_comment_received(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Получен комментарий к заказу."""
    comment = message.text.strip()
    await message.delete()
    
    if comment == BUTTON_TEXT["skip_comment"]:
        comment = None
    
    await state.update_data(comment=comment)
    await checkout_show_address_selection(message, state, session)


@UserBasketRouter.message(StateFilter(user_states.UserMenu.checkout_comment))
async def invalid_checkout_input(message: Message, state: FSMContext) -> None:
    """Обработка некорректного ввода при запросе комментария."""
    await message.answer(
        "❓ Пожалуйста, напишите текст комментария или нажмите 'Пропустить'",
        reply_markup=get_callback_btns(
            btns={BUTTON_TEXT["skip_comment"]: CALLBACK_SKIP_COMMENT},
            sizes=(1,)
        )
    )


# =============================================================================
# ADDRESS SELECTION HANDLERS (БЕЗ ИЗМЕНЕНИЙ)
# =============================================================================

async def checkout_show_address_selection(
    target: Union[Message, CallbackQuery],
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Показывает выбор адреса доставки."""
    user_id = target.from_user.id
    address_repo = AddressRepository(session)
    addresses = await address_repo.get_by_user_id(user_id)
    
    await state.set_state(user_states.UserMenu.checkout_address)
    
    if addresses:
        buttons = {}
        sizes = []
        
        for addr in addresses:
            # Формируем краткое название для кнопки
            btn_text = addr.adress_name
            if addr.street and addr.house:
                btn_text += f" ({addr.street}, {addr.house})"
            elif addr.street:
                btn_text += f" ({addr.street})"
            
            buttons[btn_text] = f"{CALLBACK_SELECT_ADDRESS}{addr.adress_id}"
            sizes.append(1)
        
        buttons[BUTTON_TEXT["add_new_address"]] = CALLBACK_ADD_ADDRESS
        buttons["🔙 Назад"] = CALLBACK_CHECKOUT
        sizes.extend([1, 1])
        
        await send_clean_message(
            target=target,
            text=ADDRESS_SELECT_PROMPT,
            buttons=buttons,
            sizes=sizes,
            parse_mode="HTML"
        )
    else:
        await checkout_add_address_start(target, state, session)


@UserBasketRouter.callback_query(F.data.startswith(CALLBACK_SELECT_ADDRESS), StateFilter(user_states.UserMenu.checkout_address))
async def checkout_select_address(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Выбор адреса из списка."""
    address_id = int(call.data.split("_")[2])
    
    address_repo = AddressRepository(session)
    address = await address_repo.get_by_id(address_id)
    
    if not address:
        await call.answer("❌ Адрес не найден", show_alert=True)
        return
    
    await state.update_data(selected_address_id=address_id)
    await checkout_show_address_confirmation(call, state, session, address)


@UserBasketRouter.callback_query(F.data == CALLBACK_ADD_ADDRESS, StateFilter(user_states.UserMenu.checkout_address))
async def checkout_add_address_start(
    target: Union[Message, CallbackQuery],
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Начало добавления нового адреса."""
    await state.set_state(user_states.UserMenu.add_address_name)
    await state.update_data(adding_address=True)
    
    await send_clean_message(
        target=target,
        text=ADDRESS_ADD_PROMPT,
        buttons={"🔙 Назад": CALLBACK_CHECKOUT},
        sizes=[1],
        parse_mode="HTML"
    )


@UserBasketRouter.message(F.text, StateFilter(user_states.UserMenu.add_address_name))
async def checkout_add_address_name(message: Message, state: FSMContext) -> None:
    """Получение названия адреса."""
    name = message.text.strip()
    await message.delete()
    
    await state.update_data(new_address_name=name)
    await state.set_state(user_states.UserMenu.add_address_coordinates)
    
    await send_clean_message(
        target=message,
        text=ADDRESS_COORDINATES_PROMPT,
        buttons={
            BUTTON_TEXT["use_geolocation"]: CALLBACK_USE_GEOLOCATION,
            BUTTON_TEXT["enter_manually"]: CALLBACK_ENTER_MANUALLY,
            "🔙 Назад": CALLBACK_CHECKOUT
        },
        sizes=[1, 1, 1],
        parse_mode="HTML"
    )


@UserBasketRouter.callback_query(F.data == CALLBACK_USE_GEOLOCATION, StateFilter(user_states.UserMenu.add_address_coordinates))
async def checkout_use_geolocation(call: CallbackQuery, state: FSMContext) -> None:
    """Запрос геопозиции через кнопку."""
    await state.set_state(user_states.UserMenu.add_address_location)
    await call.message.delete()
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📍 Отправить геопозицию", request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    msg = await call.message.answer(
        text="📍 Отправьте вашу геопозицию, нажав на кнопку ниже:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    user_id = call.from_user.id
    if user_id not in last_message_dict:
        last_message_dict[user_id] = []
    last_message_dict[user_id].append(msg.message_id)


@UserBasketRouter.callback_query(F.data == CALLBACK_ENTER_MANUALLY, StateFilter(user_states.UserMenu.add_address_coordinates))
async def checkout_enter_manually(call: CallbackQuery, state: FSMContext) -> None:
    """Переход к ручному вводу координат."""
    await call.message.delete()
    await state.set_state(user_states.UserMenu.add_address_manual)
    
    await send_clean_message(
        target=call,
        text=ADDRESS_MANUAL_PROMPT,
        buttons={"🔙 Назад": CALLBACK_CHECKOUT},
        sizes=[1],
        parse_mode="HTML"
    )


@UserBasketRouter.message(F.location, StateFilter(user_states.UserMenu.add_address_location))
async def checkout_geolocation_received(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Получена геопозиция."""
    coordinates = f"{message.location.latitude}, {message.location.longitude}"
    await message.delete()
    
    data = await state.get_data()
    name = data.get('new_address_name')
    
    await state.update_data(new_address_coordinates=coordinates)
    await state.set_state(user_states.UserMenu.add_address_street)
    
    await send_clean_message(
        target=message,
        text="📍 <b>Введите улицу</b>\n\nНапример: <i>ул. Примерная</i>",
        buttons={"🔙 Назад": CALLBACK_CHECKOUT},
        sizes=[1],
        parse_mode="HTML"
    )


@UserBasketRouter.message(F.text, StateFilter(user_states.UserMenu.add_address_manual))
async def checkout_manual_coordinates(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Получены координаты вручную — переходим к вводу улицы."""
    coordinates = message.text.strip()
    await message.delete()
    
    data = await state.get_data()
    name = data.get('new_address_name')
    
    await state.update_data(new_address_coordinates=coordinates)
    await state.set_state(user_states.UserMenu.add_address_street)
    
    await send_clean_message(
        target=message,
        text="📍 <b>Введите улицу</b>\n\nНапример: <i>ул. Примерная</i>",
        buttons={"🔙 Назад": CALLBACK_CHECKOUT},
        sizes=[1],
        parse_mode="HTML"
    )


@UserBasketRouter.message(F.text, StateFilter(user_states.UserMenu.add_address_street))
async def checkout_add_street(message: Message, state: FSMContext) -> None:
    """Получена улица — переходим к вводу дома."""
    street = message.text.strip()
    await message.delete()
    
    await state.update_data(new_address_street=street)
    await state.set_state(user_states.UserMenu.add_address_house)
    
    await send_clean_message(
        target=message,
        text="🏠 <b>Введите номер дома</b>\n\nНапример: <i>123</i> или <i>123А</i>",
        buttons={"🔙 Назад": CALLBACK_CHECKOUT},
        sizes=[1],
        parse_mode="HTML"
    )


@UserBasketRouter.message(F.text, StateFilter(user_states.UserMenu.add_address_house))
async def checkout_add_house(message: Message, state: FSMContext) -> None:
    """Получен дом — переходим к вводу корпуса (опционально)."""
    house = message.text.strip()
    await message.delete()
    
    await state.update_data(new_address_house=house)
    await state.set_state(user_states.UserMenu.add_address_building)
    
    await send_clean_message(
        target=message,
        text="🏢 <b>Введите корпус/строение</b> (если есть)\n\n<i>Или отправьте \"-\" чтобы пропустить</i>",
        buttons={"🔙 Назад": CALLBACK_CHECKOUT},
        sizes=[1],
        parse_mode="HTML"
    )


@UserBasketRouter.message(F.text, StateFilter(user_states.UserMenu.add_address_building))
async def checkout_add_building(message: Message, state: FSMContext) -> None:
    """Получен корпус — переходим к вводу квартиры."""
    building = None if message.text.strip() == "-" else message.text.strip()
    await message.delete()
    
    await state.update_data(new_address_building=building)
    await state.set_state(user_states.UserMenu.add_address_apartment)
    
    await send_clean_message(
        target=message,
        text="🔑 <b>Введите квартиру/офис</b> (если есть)\n\n<i>Или отправьте \"-\" чтобы пропустить</i>",
        buttons={"🔙 Назад": CALLBACK_CHECKOUT},
        sizes=[1],
        parse_mode="HTML"
    )


@UserBasketRouter.message(F.text, StateFilter(user_states.UserMenu.add_address_apartment))
async def checkout_add_apartment(message: Message, state: FSMContext) -> None:
    """Получена квартира — переходим к вводу этажа."""
    apartment = None if message.text.strip() == "-" else message.text.strip()
    await message.delete()
    
    await state.update_data(new_address_apartment=apartment)
    await state.set_state(user_states.UserMenu.add_address_floor)
    
    await send_clean_message(
        target=message,
        text="📶 <b>Введите этаж</b> (если нужно)\n\n<i>Или отправьте \"-\" чтобы пропустить</i>",
        buttons={"🔙 Назад": CALLBACK_CHECKOUT},
        sizes=[1],
        parse_mode="HTML"
    )


@UserBasketRouter.message(F.text, StateFilter(user_states.UserMenu.add_address_floor))
async def checkout_add_floor(message: Message, state: FSMContext) -> None:
    """Получен этаж — переходим к вводу подъезда."""
    floor = None if message.text.strip() == "-" else message.text.strip()
    await message.delete()
    
    await state.update_data(new_address_floor=floor)
    await state.set_state(user_states.UserMenu.add_address_entrance)
    
    await send_clean_message(
        target=message,
        text="🚪 <b>Введите подъезд</b> (если есть)\n\n<i>Или отправьте \"-\" чтобы пропустить</i>",
        buttons={"🔙 Назад": CALLBACK_CHECKOUT},
        sizes=[1],
        parse_mode="HTML"
    )


@UserBasketRouter.message(F.text, StateFilter(user_states.UserMenu.add_address_entrance))
async def checkout_add_entrance(message: Message, state: FSMContext) -> None:
    """Получен подъезд — переходим к вводу домофона."""
    entrance = None if message.text.strip() == "-" else message.text.strip()
    await message.delete()
    
    await state.update_data(new_address_entrance=entrance)
    await state.set_state(user_states.UserMenu.add_address_intercom)
    
    await send_clean_message(
        target=message,
        text="📞 <b>Введите код домофона</b> (если есть)\n\n<i>Или отправьте \"-\" чтобы пропустить</i>",
        buttons={"🔙 Назад": CALLBACK_CHECKOUT},
        sizes=[1],
        parse_mode="HTML"
    )


@UserBasketRouter.message(F.text, StateFilter(user_states.UserMenu.add_address_intercom))
async def checkout_add_intercom(message: Message, state: FSMContext) -> None:
    """Получен домофон — переходим к вводу комментария."""
    intercom = None if message.text.strip() == "-" else message.text.strip()
    await message.delete()
    
    await state.update_data(new_address_intercom=intercom)
    await state.set_state(user_states.UserMenu.add_address_comment)
    
    await send_clean_message(
        target=message,
        text="📝 <b>Комментарий для курьера</b>\n\nКак пройти, где оставить заказ и т.д.\n\n<i>Или отправьте \"-\" чтобы пропустить</i>",
        buttons={"🔙 Назад": CALLBACK_CHECKOUT},
        sizes=[1],
        parse_mode="HTML"
    )


@UserBasketRouter.message(F.text, StateFilter(user_states.UserMenu.add_address_comment))
async def checkout_add_comment(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Получен комментарий — показываем подтверждение адреса."""
    comment = None if message.text.strip() == "-" else message.text.strip()
    await message.delete()
    
    data = await state.get_data()
    
    await state.update_data(
        new_address_comment=comment,
        new_address_name=data.get('new_address_name'),
        new_address_coordinates=data.get('new_address_coordinates'),
        new_address_street=data.get('new_address_street'),
        new_address_house=data.get('new_address_house'),
        new_address_building=data.get('new_address_building'),
        new_address_apartment=data.get('new_address_apartment'),
        new_address_floor=data.get('new_address_floor'),
        new_address_entrance=data.get('new_address_entrance'),
        new_address_intercom=data.get('new_address_intercom')
    )
    
    await state.set_state(user_states.UserMenu.confirm_address)
    
    # Формируем текст для подтверждения
    text = "📍 <b>Проверьте адрес</b>\n\n"
    text += f"<b>Название:</b> {data.get('new_address_name')}\n"
    text += f"<b>Улица:</b> {data.get('new_address_street')}\n"
    text += f"<b>Дом:</b> {data.get('new_address_house')}"
    if data.get('new_address_building'):
        text += f", корп. {data.get('new_address_building')}"
    if data.get('new_address_apartment'):
        text += f", кв. {data.get('new_address_apartment')}"
    if data.get('new_address_floor'):
        text += f"\n<b>Этаж:</b> {data.get('new_address_floor')}"
    if data.get('new_address_entrance'):
        text += f"\n<b>Подъезд:</b> {data.get('new_address_entrance')}"
    if data.get('new_address_intercom'):
        text += f"\n<b>Домофон:</b> {data.get('new_address_intercom')}"
    if comment:
        text += f"\n<b>Комментарий:</b> {comment}"
    text += f"\n<b>Координаты:</b> {data.get('new_address_coordinates')}"
    text += "\n\n✅ Всё верно?"
    
    buttons = {
        BUTTON_TEXT["confirm"]: CALLBACK_CONFIRM_ADDRESS,
        "✏️ Изменить": CALLBACK_EDIT_ADDRESS,
        "🔙 Назад": CALLBACK_CHECKOUT
    }
    
    await send_clean_message(
        target=message,
        text=text,
        buttons=buttons,
        sizes=[1, 1, 1],
        parse_mode="HTML"
    )


@UserBasketRouter.callback_query(F.data == CALLBACK_CONFIRM_ADDRESS, StateFilter(user_states.UserMenu.confirm_address))
async def checkout_confirm_address(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Подтверждение добавления адреса с сохранением всех деталей."""
    data = await state.get_data()
    user_id = call.from_user.id
    
    # Собираем все данные адреса
    address_data = {
        "adress_name": data.get('new_address_name'),
        "coordinates": data.get('new_address_coordinates'),
        "street": data.get('new_address_street'),
        "house": data.get('new_address_house'),
        "building": data.get('new_address_building'),
        "apartment": data.get('new_address_apartment'),
        "floor": data.get('new_address_floor'),
        "entrance": data.get('new_address_entrance'),
        "intercom": data.get('new_address_intercom'),
        "comment": data.get('new_address_comment')
    }
    
    address_repo = AddressRepository(session)
    new_address = await address_repo.create(
        user_id=user_id,
        **address_data
    )
    
    if new_address:
        await state.update_data(selected_address_id=new_address.adress_id)
        await checkout_show_address_confirmation(call, state, session, new_address)
    else:
        await call.answer("❌ Ошибка при сохранении адреса", show_alert=True)


@UserBasketRouter.callback_query(F.data == CALLBACK_EDIT_ADDRESS, StateFilter(user_states.UserMenu.confirm_address))
async def checkout_edit_address(call: CallbackQuery, state: FSMContext) -> None:
    """Редактирование адреса — возврат к вводу названия."""
    await state.set_state(user_states.UserMenu.add_address_name)
    await call.message.delete()
    
    await send_clean_message(
        target=call,
        text=ADDRESS_ADD_PROMPT,
        buttons={"🔙 Назад": CALLBACK_CHECKOUT},
        sizes=[1],
        parse_mode="HTML"
    )


async def checkout_show_address_confirmation(
    target: Union[Message, CallbackQuery],
    state: FSMContext,
    session: AsyncSession,
    address
) -> None:
    """Показывает подтверждение выбранного адреса."""
    text = format_address_text(address)
    text += "\n\n✅ Этот адрес будет использован для доставки?"

    await state.set_state(user_states.UserMenu.confirm_delivery_address)
    
    await send_clean_message(
        target=target,
        text=text,
        buttons={
            BUTTON_TEXT["confirm"]: "confirm_delivery_address",
            "🔙 Назад": CALLBACK_CHECKOUT
        },
        sizes=[1, 1],
        parse_mode="HTML"
    )


@UserBasketRouter.callback_query(F.data == "confirm_delivery_address", StateFilter(user_states.UserMenu.confirm_delivery_address))
async def checkout_confirm_delivery_address(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Подтверждение адреса доставки.
    Если у адреса есть зона → выбор даты и времени
    Если нет зоны → заказ в AWAITING_ADDRESS_STATUS
    """
    data = await state.get_data()
    address_id = data.get('selected_address_id')
    order_id = data.get('checkout_order_id')
    comment = data.get('comment')
    
    if not address_id or not order_id:
        await call.answer("❌ Ошибка: не найден адрес или заказ", show_alert=True)
        return
    
    address_repo = AddressRepository(session)
    address = await address_repo.get_by_id(address_id)
    
    if not address:
        await call.answer("❌ Адрес не найден", show_alert=True)
        return
    
    # Сохраняем адрес в заказ
    order_repo = OrderRepository(session)
    await order_repo.update_order_address(order_id, address_id)
    await session.commit()
    
    # Проверяем, есть ли у адреса статус доставки
    if address.adress_status:
        # Есть статус — сохраняем комментарий и переходим к выбору даты
        await state.update_data(comment=comment)
        await show_delivery_date_selection(call, state, session)
    else:
        # Нет статуса — заказ в AWAITING_ADDRESS_STATUS
        await finalize_order_without_zone(
            target=call,
            state=state,
            session=session,
            order_id=order_id,
            address_id=address_id
        )


# =============================================================================
# BACK TO ADDRESS HANDLER
# =============================================================================

@UserBasketRouter.callback_query(F.data == CALLBACK_BACK_TO_ADDRESS)
async def back_to_address_selection(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Возврат к выбору адреса."""
    await checkout_show_address_selection(call, state, session)


# =============================================================================
# PAYMENT HANDLERS
# =============================================================================

async def checkout_show_payment(
    target: Union[Message, CallbackQuery],
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Показывает реквизиты для оплаты."""
    data = await state.get_data()
    order_id = data.get('checkout_order_id')
    delivery_id = data.get('selected_delivery_id')
    comment = data.get('comment')
    address_id = data.get('selected_address_id')
    hour_from = data.get('selected_hour_from')
    hour_to = data.get('selected_hour_to')
    
    if not order_id:
        await target.answer("❌ Ошибка: заказ не найден")
        await state.clear()
        return
    
    order_repo = OrderRepository(session=session)
    order = await order_repo.get_order_by_id(order_id)
    
    if not order:
        await target.answer("❌ Заказ не найден")
        await state.clear()
        return
    
    items_text, preliminary_total = await get_cart_total_text(session, target.from_user.id, order)
    
    # Получаем стоимость доставки
    delivery_price = await get_delivery_price_for_order(session, address_id, delivery_id)
    total = preliminary_total + delivery_price
    
    await state.update_data(
        selected_delivery_id=delivery_id,
        comment=comment,
        selected_address_id=address_id,
        selected_hour_from=hour_from,
        selected_hour_to=hour_to
    )
    await state.set_state(user_states.UserMenu.checkout_payment)
    
    text = PAYMENT_PROMPT.format(total=total)
    
    await send_clean_message(
        target=target,
        text=text,
        buttons={
            "🔙 Назад": CALLBACK_SELECT_DELIVERY_DATE
        },
        sizes=[1],
        parse_mode="HTML"
    )


@UserBasketRouter.message(F.photo, StateFilter(user_states.UserMenu.checkout_payment))
async def checkout_photo_received(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Получено фото чека — завершаем оформление заказа."""
    data = await state.get_data()
    order_id = data.get('checkout_order_id')
    comment = data.get('comment')
    address_id = data.get('selected_address_id')
    delivery_id = data.get('selected_delivery_id')
    hour_from = data.get('selected_hour_from')
    hour_to = data.get('selected_hour_to')
    
    if not order_id:
        await message.answer("❌ Ошибка: заказ не найден")
        await state.clear()
        return
    
    photo_id = message.photo[-1].file_id
    await message.delete()
    
    await finalize_order_with_zone(
        target=message,
        state=state,
        session=session,
        order_id=order_id,
        comment=comment,
        address_id=address_id,
        delivery_id=delivery_id,
        photo_id=photo_id,
        hour_from=hour_from,
        hour_to=hour_to
    )


@UserBasketRouter.message(StateFilter(user_states.UserMenu.checkout_payment))
async def invalid_payment_input(message: Message, state: FSMContext) -> None:
    """Обработка некорректного ввода при запросе фото чека."""
    await message.answer(
        "❓ Пожалуйста, отправьте фото чека об оплате.",
        reply_markup=get_callback_btns(
            btns={"🔙 Назад": CALLBACK_SELECT_DELIVERY_DATE},
            sizes=(1,)
        )
    )


# =============================================================================
# UTILITY HANDLERS
# =============================================================================

@UserBasketRouter.callback_query(F.data == CALLBACK_PASS)
async def pass_callback(call: CallbackQuery) -> None:
    """Пустой callback для неактивных кнопок."""
    await call.answer()