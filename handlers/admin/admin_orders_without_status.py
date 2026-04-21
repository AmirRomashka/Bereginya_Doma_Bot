"""
Admin Orders Without Status Module
==================================

This module handles orders that are waiting for address status assignment.
"""

from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.enums.parse_mode import ParseMode

from icecream import ic
from sqlalchemy.ext.asyncio import AsyncSession

from database.enumirate.orders_enum import OrdersStatus
from database.orm_query.orders_orm import OrderRepository
from database.orm_query.address_orm import AddressRepository
from database.orm_query.delivery_status_orm import DeliveryStatusRepository
from keybords.inline import get_callback_btns
from tools import send_clean_message, notify_admins
from config import ADMIN_IDS
from bot_instance import get_bot_instance
from handlers.admin.admin_panel import send_section_message


# =============================================================================
# ROUTER INITIALIZATION
# =============================================================================

AdminOrdersWithoutStatusRouter = Router(name="admin_orders_without_status")


# =============================================================================
# CONSTANTS
# =============================================================================

CALLBACK_ORDERS_WITHOUT_STATUS = "orders_without_status"
CALLBACK_ASSIGN_ADDRESS_STATUS = "assign_address_status_"
CALLBACK_CONFIRM_ASSIGN_STATUS = "confirm_assign_status_"
CALLBACK_CREATE_STATUS = "create_delivery_status"
CALLBACK_BACK_TO_ORDERS_WITHOUT_STATUS = "back_to_orders_without_status"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

async def get_orders_without_zone(session: AsyncSession):
    """
    Возвращает заказы в статусе AWAITING_ADDRESS_STATUS,
    у которых адрес не имеет зоны (adress_status is None).
    """
    order_repo = OrderRepository(session)
    address_repo = AddressRepository(session)

    awaiting_orders = await order_repo.get_orders_by_status(OrdersStatus.AWAITING_ADDRESS_STATUS)
    result = []

    for order in awaiting_orders:
        if not order.address_id:
            # Если у заказа нет адреса — считаем, что зоны нет
            result.append(order)
            continue

        address = await address_repo.get_by_id(order.address_id)
        if address and address.adress_status is None:
            result.append(order)

    return result


async def send_admin_notification(
    order_id: int,
    session: AsyncSession,
    status_name: str = None,
    status_price: int = None
) -> None:
    """
    Отправляет уведомление администраторам о назначении зоны доставки.
    """
    order_repo = OrderRepository(session)
    
    # Получаем статистику
    without_status_orders = await get_orders_without_zone(session)
    without_status_count = len(without_status_orders)
    new_orders_count = await order_repo.get_orders_by_status_count(OrdersStatus.VERIFICATION)
    ready_count = await order_repo.get_orders_by_status_count(OrdersStatus.READY_FOR_DELIVERY)
    
    bot = get_bot_instance()
    
    zone_info = f" — {status_name} ({status_price} ₽)" if status_name else ""
    
    text = f"""
📍 <b>Заказу #{order_id} присвоена зона доставки{zone_info}!</b>

<b>📊 Статистика:</b>
📍 Заказов без зоны: <b>{without_status_count}</b>
🆕 Новых заказов: <b>{new_orders_count}</b>
📦 Готовых: <b>{ready_count}</b>

👉 Перейдите в раздел <b>"📍 Заказы без статуса"</b> для обработки остальных.
"""
    
    await notify_admins(
        bot=bot,
        text=text,
        admin_ids=ADMIN_IDS,
        buttons={"🔍 Перейти": "orders_without_status"},
        sizes=[1]
    )


# =============================================================================
# HANDLERS
# =============================================================================

@AdminOrdersWithoutStatusRouter.callback_query(F.data == CALLBACK_ORDERS_WITHOUT_STATUS)
async def show_orders_without_status(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Показывает заказы, ожидающие присвоения статуса адресу.
    """
    await call.answer()

    orders = await get_orders_without_zone(session)

    if not orders:
        # Если нет таких заказов, возвращаемся в админку
        from handlers.admin.admin_panel import back_to_admin_panel
        await back_to_admin_panel(call, state, session)  # ✅ передаём state
        return

    text = """
📍 <b>Заказы, ожидающие статуса адреса</b>

Выберите заказ, чтобы присвоить адресу зону доставки:
"""

    buttons = {}
    sizes = []
    order_repo = OrderRepository(session)
    address_repo = AddressRepository(session)

    for order in orders:
        order_details = await order_repo.get_order_with_details(order.order_id)
        address_name = "Адрес не указан"
        if order_details and order_details.get('address_id'):
            address = await address_repo.get_by_id(order_details['address_id'])
            if address:
                address_name = address.adress_name[:30]

        button_text = f"📦 Заказ №{order.order_id} — {address_name}"
        buttons[button_text] = f"{CALLBACK_ASSIGN_ADDRESS_STATUS}{order.order_id}"
        sizes.append(1)

    buttons["🔙 Назад"] = "back_to_admin_panel"
    sizes.append(1)

    await send_section_message(call, text, buttons, tuple(sizes))


@AdminOrdersWithoutStatusRouter.callback_query(F.data.startswith(CALLBACK_ASSIGN_ADDRESS_STATUS))
async def assign_address_status_start(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Начало присвоения статуса доставки адресу из заказа.
    """
    order_id = int(call.data.split("_")[3])

    order_repo = OrderRepository(session)
    address_repo = AddressRepository(session)
    status_repo = DeliveryStatusRepository(session)

    order_details = await order_repo.get_order_with_details(order_id)
    if not order_details:
        await call.answer("❌ Заказ не найден", show_alert=True)
        return

    # Получаем адрес из заказа
    address_id = order_details.get('address_id')
    if not address_id:
        await call.answer("❌ У заказа нет адреса", show_alert=True)
        return

    address = await address_repo.get_by_id(address_id)
    if not address:
        await call.answer("❌ Адрес не найден", show_alert=True)
        return

    # Сохраняем в состояние
    await state.update_data(
        assign_order_id=order_id,
        assign_address_id=address_id,
        assign_user_id=order_details['user_id']
    )

    # Получаем список доступных статусов (зон доставки)
    statuses = await status_repo.get_all(only_active=True)

    # Если нет статусов — показываем кнопку для создания
    if not statuses:
        text = f"""
📍 <b>Присвоение зоны доставки</b>

<b>Заказ №{order_id}</b>
<b>Адрес:</b> {address.adress_name}
<b>Координаты:</b> {address.coordinates}

⚠️ <b>Нет доступных статусов доставки!</b>

Сначала создайте зоны доставки в разделе "🚚 Доставка" → "🚚 Статусы доставки".

После создания статусов вернитесь сюда и продолжите.
"""

        buttons = {
            "➕ Создать статус": CALLBACK_CREATE_STATUS,
            "🔙 К списку заказов": CALLBACK_ORDERS_WITHOUT_STATUS,
            "🏠 В админ-панель": "back_to_admin_panel"
        }
        sizes = [1, 1, 1]

        await send_clean_message(
            target=call,
            text=text,
            buttons=buttons,
            sizes=sizes,
            parse_mode="HTML"
        )
        return

    text = f"""
📍 <b>Присвоение зоны доставки</b>

<b>Заказ №{order_id}</b>
<b>Адрес:</b> {address.adress_name}
<b>Координаты:</b> {address.coordinates}

Выберите зону доставки для этого адреса:
"""

    buttons = {}
    sizes = []

    for status in statuses:
        status_icon = "✅" if status.is_active else "❌"
        buttons[f"{status_icon} {status.name} — {status.price} ₽"] = f"{CALLBACK_CONFIRM_ASSIGN_STATUS}{order_id}_{address_id}_{status.status_id}"
        sizes.append(1)

    buttons["➕ Создать новый статус"] = CALLBACK_CREATE_STATUS
    buttons["🔙 К списку заказов"] = CALLBACK_ORDERS_WITHOUT_STATUS
    sizes.append(1)
    sizes.append(1)

    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=sizes,
        parse_mode="HTML"
    )


@AdminOrdersWithoutStatusRouter.callback_query(F.data == CALLBACK_CREATE_STATUS)
async def redirect_to_delivery_statuses(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Перенаправляет в раздел создания статусов доставки.
    """
    await call.answer("🔄 Перенаправляем в раздел статусов доставки...")

    # Сохраняем в состояние, откуда пришли, чтобы вернуться
    data = await state.get_data()
    return_to = data.get('assign_order_id')

    await state.update_data(return_to_order_id=return_to)

    # Вызываем хендлер из admin_delivery.py для показа статусов
    from handlers.admin.admin_delivery import send_delivery_statuses
    await send_delivery_statuses(call, state=state, session=session, edit=False)


@AdminOrdersWithoutStatusRouter.callback_query(F.data.startswith(CALLBACK_CONFIRM_ASSIGN_STATUS))
async def confirm_assign_status(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Подтверждение присвоения статуса адресу.
    """
    parts = call.data.split("_")
    order_id = int(parts[3])
    address_id = int(parts[4])
    status_id = int(parts[5])

    order_repo = OrderRepository(session)
    address_repo = AddressRepository(session)
    status_repo = DeliveryStatusRepository(session)

    # Присваиваем статус адресу
    success = await address_repo.update_status(address_id, status_id)

    if not success:
        await call.answer("❌ Ошибка при сохранении статуса адреса", show_alert=True)
        return

    # ✅ Статус заказа НЕ МЕНЯЕМ — остаётся AWAITING_ADDRESS_STATUS
    # (заказ исчезнет из этого списка при следующем вызове из-за фильтрации)

    await session.commit()

    # Получаем данные для уведомления
    order_details = await order_repo.get_order_with_details(order_id)
    status = await status_repo.get_by_id(status_id)

    # Отправляем уведомление пользователю
    if order_details:
        bot = get_bot_instance()
        await bot.send_message(
            chat_id=order_details['user_id'],
            text=f"""
✅ <b>Ваш заказ №{order_id} готов к оформлению!</b>

Адрес доставки подтверждён.
Зона доставки: <b>{status.name if status else 'определена'}</b>
Стоимость доставки: <b>{status.price if status else '0'} ₽</b>

Теперь вы можете подтвердить заказ в разделе <b>"✅ Подтвердить заказы"</b> в главном меню.
""",
            parse_mode="HTML"
        )

    # Отправляем уведомление администраторам
    await send_admin_notification(
        order_id=order_id,
        session=session,
        status_name=status.name if status else None,
        status_price=status.price if status else None
    )

    await call.answer("✅ Статус адреса присвоен, заказ доступен пользователю для подтверждения")
    await show_orders_without_status(call, state, session)  # ✅ передаём state

    await state.clear()


@AdminOrdersWithoutStatusRouter.callback_query(F.data == CALLBACK_BACK_TO_ORDERS_WITHOUT_STATUS)
async def back_to_orders_without_status(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Возврат к списку заказов без статуса.
    """
    await show_orders_without_status(call, state, session)  # ✅ передаём state