"""
User Main Menu Module
=====================

This module handles the main user menu — the heart of the bot.
This is where users start their journey through our home kitchen.
"""
from icecream import ic
from typing import Union
from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile
from aiogram.enums.parse_mode import ParseMode

from sqlalchemy.ext.asyncio import AsyncSession

from keybords.inline import get_callback_btns
from States import user_states
from config import WORK_DIR, last_message_dict
from tools import message_delete
from database.orm_query.users_orm import get_user_orm
from database.orm_query.orders_orm import OrderRepository
from database.orm_query.address_orm import AddressRepository
from database.enumirate.orders_enum import OrdersStatus

UserPanelRouter = Router()

# Путь к изображению для главного меню
MAIN_MENU_IMAGE = "image/user_images/user_main_menu.jpg"


# =============================================================================
# CONSTANTS
# =============================================================================

# -----------------------------------------------------------------------------
# Main menu text — как встреча гостя в домашней кондитерской
# -----------------------------------------------------------------------------

MENU_TEXT_BASE = """
🤍 <b>Добро пожаловать в «Берегиню Дома»</b>

Здесь всё по-настоящему:
свежий хлеб, натуральные десерты и вкус домашнего уюта.
Выбирайте, что хочется сегодня — мы приготовили для вас лучшее ✨
"""

MENU_TEXT_WITH_BIRTHDAY = """
🎂 <a href="https://t.me/Bereginia_Doma_bot?start=set_birthday">Нажмите здесь, чтобы указать день рождения</a> 🎂

<i>В ваш праздник мы подарим особый сюрприз!</i>
"""

MENU_TEXT_END = """
🍰 <i>Выбирайте, что сегодня к чаю 🤍</i>
"""

# Callback для отзыва
CALLBACK_FEEDBACK = "user_feedback"


# =============================================================================
# HANDLERS
# =============================================================================

@UserPanelRouter.callback_query(F.data == "main_menu")
@UserPanelRouter.message(Command("menu"))
async def show_user_panel(
    event: Union[types.Message, types.CallbackQuery], 
    state: FSMContext, 
    session: AsyncSession
):
    """
    Главное меню — сердце нашего бота.
    
    Сюда попадает пользователь после регистрации или по команде /menu.
    Здесь начинается знакомство с нашей домашней кондитерской.
    """
    # Сбрасываем состояние — как начать с чистого листа
    await state.clear()
    await state.set_state(user_states.StartState.start)
    
    user_id = event.from_user.id
    
    # Проверяем, зарегистрирован ли пользователь
    user = await get_user_orm(session, user_id)
    
    if isinstance(event, types.Message):
        message = event
        await event.delete()
    else:
        message = event.message
        await event.answer()
    
    # Подготовка списков заказов
    active_orders = []
    confirm_orders = []
    has_completed_orders = False  # Флаг для отображения кнопки отзыва
    
    if user and user.phone_number:
        order_repo = OrderRepository(session, user_id=user_id)
        address_repo = AddressRepository(session)
        
        # 1️⃣ Заказы, готовые к подтверждению:
        #    AWAITING_ADDRESS_STATUS + у адреса есть зона доставки
        awaiting_orders = await order_repo.get_orders_by_user_and_status(OrdersStatus.AWAITING_ADDRESS_STATUS)
        
        for order in awaiting_orders:
            if order.address_id:
                address = await address_repo.get_by_id(order.address_id)
                if address and address.adress_status:
                    confirm_orders.append(order)
        
        # 2️⃣ Активные заказы:
        #    VERIFICATION, ACCEPTED, READY_FOR_DELIVERY
        verification_orders = await order_repo.get_orders_by_user_and_status(OrdersStatus.VERIFICATION)
        accepted_orders = await order_repo.get_orders_by_user_and_status(OrdersStatus.ACCEPTED)
        ready_orders = await order_repo.get_orders_by_user_and_status(OrdersStatus.READY_FOR_DELIVERY)
        
        active_orders = verification_orders + accepted_orders + ready_orders
        active_orders.sort(key=lambda x: x.created, reverse=True)
        
        # 3️⃣ Проверяем, есть ли завершённые заказы (для отзыва)
        completed_orders = await order_repo.get_orders_by_user_and_status(OrdersStatus.COMPLETED)
        has_completed_orders = len(completed_orders) > 0
    
    active_orders_count = len(active_orders)
    confirm_orders_count = len(confirm_orders)
    
    # Формируем текст меню в зависимости от наличия даты рождения
    menu_text = MENU_TEXT_BASE
    
    # Если пользователь зарегистрирован и у него нет даты рождения
    if user and not user.birth_date:
        menu_text += MENU_TEXT_WITH_BIRTHDAY
    
    menu_text += MENU_TEXT_END
    
    # ✅ Кнопки главного меню — формируем последовательно
    menu_buttons = {}
    sizes = []
    
    # ========================================================================
    # 1️⃣ СРОЧНЫЕ ЗАКАЗЫ — отдельные строки
    # ========================================================================
    
    # Заказы, готовые к подтверждению
    if confirm_orders_count > 0:
        menu_buttons[f"✅ Подтвердить заказы 🔥 {confirm_orders_count}"] = "confirm_orders"
        sizes.append(1)
    
    # Активные заказы
    if active_orders_count > 0:
        menu_buttons["🍳 Активные заказы 🔥"] = "user_current_orders"
        sizes.append(1)
    
    # ========================================================================
    # 2️⃣ ОСНОВНЫЕ КНОПКИ
    # ========================================================================
    
    # Меню — отдельная строка
    menu_buttons["🍰 Меню"] = "user_catalog"
    sizes.append(1)
    
    # Сезонные блюда — отдельная строка
    menu_buttons["🧁 Сезонные десерты"] = "user_promotions"
    sizes.append(1)
    
    # История | Корзина — 2 кнопки в ряд
    menu_buttons["📖 История"] = "order_history"
    menu_buttons["🛒 Корзина"] = "active_orders"
    sizes.append(2)
    
    # ========================================================================
    # 3️⃣ ИНФОРМАЦИОННЫЕ КНОПКИ — 2 кнопки в ряд
    # ========================================================================
    
    menu_buttons["ℹ️ О нас"] = "about_us"
    
    # Отзыв показываем только если есть завершённые заказы
    if has_completed_orders:
        menu_buttons["💬 Оставить отзыв"] = CALLBACK_FEEDBACK
    else:
        menu_buttons["💬 Оставить отзыв"] = CALLBACK_FEEDBACK
        # Можно добавить условие, но пока кнопка есть всегда
        # Если хочешь показывать только после заказов, раскомментируй условие выше
    
    sizes.append(2)
    
    # ========================================================================
    # 4️⃣ РЕГИСТРАЦИЯ (если не зарегистрирован)
    # ========================================================================
    
    if not user:
        menu_buttons["📝 Регистрация"] = "registration"
        sizes.append(1)
    
    media_path = WORK_DIR / MAIN_MENU_IMAGE
    
    if media_path.exists():
        media = FSInputFile(media_path)
        msg = await message.answer_photo(
            photo=media,
            caption=menu_text,
            reply_markup=get_callback_btns(btns=menu_buttons, sizes=tuple(sizes)),
            parse_mode=ParseMode.HTML
        )
    else:
        ic(f"Main menu image not found: {media_path}")
        msg = await message.answer(
            text=menu_text,
            reply_markup=get_callback_btns(btns=menu_buttons, sizes=tuple(sizes)),
            parse_mode=ParseMode.HTML
        )
    
    # Очищаем старые сообщения, чтобы не было беспорядка
    await message_delete(user_id, last_message_dict)
    last_message_dict[user_id].extend([msg.message_id])