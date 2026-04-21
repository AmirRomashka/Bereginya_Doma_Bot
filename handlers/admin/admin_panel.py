"""
Admin Panel Module
==================

This module handles the main admin panel functionality.
Here the chef sees statistics and navigates to different sections.
"""

from typing import Union

from aiogram import F, Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile
from aiogram.enums.parse_mode import ParseMode

from icecream import ic
from sqlalchemy.ext.asyncio import AsyncSession

from database.enumirate.users_enum import UserStatus
from database.enumirate.orders_enum import OrdersStatus
from database.models.users_model import Users
from database.orm_query.users_orm import get_user_orm 
from database.orm_query.orders_orm import OrderRepository
from database.orm_query.address_orm import AddressRepository
from database.orm_query.dish_orm import get_promotion_dishes_count_orm
from database.orm_query.feedback_orm import FeedbackRepository

from keybords.inline import get_callback_btns
from States import user_states
from config import WORK_DIR, last_message_dict


# =============================================================================
# ROUTER INITIALIZATION
# =============================================================================

AdminPanelRouter = Router()


# =============================================================================
# CONSTANTS
# =============================================================================

# Путь к изображению для главного меню админа
ADMIN_MAIN_MENU_IMAGE = "image/admin_images/admin_main_menu_1.jpg"

ADMIN_WELCOME = """
👋 <b>Здравствуйте, шеф!</b>

Добро пожаловать на вашу кухню.
Здесь всё под контролем: заказы, меню, акции, доставка.
"""

ADMIN_UNAUTHORIZED = """
⚠️ <b>Доступ запрещён</b>

Эта кухня только для своих. 
Если вы считаете, что это ошибка, напишите разработчику.
"""


# =============================================================================
# MAIN ADMIN PANEL HANDLER
# =============================================================================

@AdminPanelRouter.message(Command("panel"))
@AdminPanelRouter.callback_query(F.data == "panel")
async def admin_panel(
    event: Union[types.Message, types.CallbackQuery], 
    state: FSMContext, 
    session: AsyncSession
) -> None:
    """
    Главная панель шеф-повара.
    """
    await state.set_state(user_states.AdminPanel.admin_panel)
    
    if isinstance(event, types.Message):
        user_id = event.from_user.id
        message = event
        is_callback = False
    else:
        user_id = event.from_user.id
        message = event.message
        is_callback = True
        await event.answer()

    user = await get_user_orm(session=session, user_id=user_id)
    
    if not user or user.status == UserStatus.COMMON.value:
        await message.answer(
            text=ADMIN_UNAUTHORIZED,
            parse_mode=ParseMode.HTML
        )
        if isinstance(event, types.Message):
            await event.delete()
        return
    
    order_repo = OrderRepository(session)
    address_repo = AddressRepository(session)
    feedback_repo = FeedbackRepository(session)
    
    # Получаем количество заказов в разных статусах для кнопок
    new_orders_count = await order_repo.get_orders_by_status_count(OrdersStatus.VERIFICATION)
    active_orders_count = await order_repo.get_orders_by_status_count(OrdersStatus.ACCEPTED)
    
    # Получаем количество блюд в акции
    promo_count = await get_promotion_dishes_count_orm(session)
    
    # Получаем количество отзывов
    feedback_stats = await feedback_repo.get_stats()
    feedback_count = feedback_stats.get("total", 0)
    
    # Получаем заказы в статусе AWAITING_ADDRESS_STATUS
    awaiting_orders = await order_repo.get_orders_by_status(OrdersStatus.AWAITING_ADDRESS_STATUS)
    
    # Фильтруем: только те, у которых адрес НЕ имеет зоны (adress_status is None)
    orders_without_status_count = 0
    for order in awaiting_orders:
        if order.address_id:
            address = await address_repo.get_by_id(order.address_id)
            if address and address.adress_status is None:
                orders_without_status_count += 1
        else:
            # Если у заказа нет адреса — тоже считаем как "без статуса"
            orders_without_status_count += 1
    
    # Получаем количество заказов в статусе READY_FOR_DELIVERY
    ready_orders_count = await order_repo.get_orders_by_status_count(OrdersStatus.READY_FOR_DELIVERY)
    
    admin_panel_text = ADMIN_WELCOME + "\n<b>Что будем делать?</b>"
    
    # Формируем кнопки
    admin_panel_buttons = {}
    sizes = []
    
    # 1️⃣ Заказы без статуса (на самом верху, если есть)
    if orders_without_status_count > 0:
        admin_panel_buttons[f"📍 Заказы без статуса 🔥 {orders_without_status_count}"] = "orders_without_status"
        sizes.append(1)
    
    # 2️⃣ Готовые заказы (READY_FOR_DELIVERY)
    if ready_orders_count > 0:
        admin_panel_buttons[f"📦 Готовые заказы 🔥 {ready_orders_count}"] = "admin_ready_orders"
        sizes.append(1)
    
    # 3️⃣ Новые заказы
    if new_orders_count > 0:
        admin_panel_buttons[f"🆕 Новые заказы 🔥 {new_orders_count}"] = "new_orders"
    else:
        admin_panel_buttons[f"🆕 Новые заказы"] = "new_orders"
    sizes.append(1)
    
    # 4️⃣ В работе
    if active_orders_count > 0:
        admin_panel_buttons[f"🍳 В работе 🔥 {active_orders_count}"] = "active_orders"
    else:
        admin_panel_buttons[f"🍳 В работе"] = "active_orders"
    sizes.append(1)
    
    # 5️⃣ Сезонные блюда
    if promo_count > 0:
        admin_panel_buttons[f"🌿 Сезонные блюда 🔥 {promo_count}"] = "promotions"
    else:
        admin_panel_buttons[f"🌿 Сезонные блюда"] = "promotions"
    sizes.append(1)
    
    # 6️⃣ Моё меню
    admin_panel_buttons["🍽 Моё меню"] = "my_menu"
    sizes.append(1)
    
    # 7️⃣ Доставка
    admin_panel_buttons["🚚 Доставка"] = "delivery_management"
    sizes.append(1)
    
    # 8️⃣ Архив заказов + Статистика (2 кнопки)
    admin_panel_buttons["📜 Архив заказов"] = "orders_history"
    admin_panel_buttons["📊 Статистика"] = "detailed_stats"
    sizes.append(2)
    
    # 9️⃣ Сказать гостям + Настройки (2 кнопки)
    admin_panel_buttons["📢 Сказать гостям"] = "mailing"
    admin_panel_buttons["⚙️ Настройки"] = "admin_settings"
    sizes.append(2)
    
    # 🔟 Помощь
    admin_panel_buttons["❓ Помощь"] = "admin_help"
    sizes.append(1)
    
    # 1️⃣1️⃣ Отзывы (в самом конце, с количеством)
    if feedback_count > 0:
        admin_panel_buttons[f"📝 Отзывы ({feedback_count})"] = "admin_feedback"
    else:
        admin_panel_buttons[f"📝 Отзывы"] = "admin_feedback"
    sizes.append(1)
    
    # Получаем путь к изображению
    media_path = WORK_DIR / ADMIN_MAIN_MENU_IMAGE
    
    if is_callback:
        # Для callback-запросов пытаемся отредактировать сообщение
        try:
            # Если текущее сообщение с фото, редактируем его
            if message.photo:
                media = FSInputFile(media_path) if media_path.exists() else None
                if media:
                    from aiogram.types import InputMediaPhoto
                    media_input = InputMediaPhoto(media=media, caption=admin_panel_text, parse_mode=ParseMode.HTML)
                    msg = await message.edit_media(
                        media=media_input,
                        reply_markup=get_callback_btns(btns=admin_panel_buttons, sizes=tuple(sizes))
                    )
                else:
                    # Если фото нет, редактируем текст
                    msg = await message.edit_text(
                        text=admin_panel_text,
                        reply_markup=get_callback_btns(btns=admin_panel_buttons, sizes=tuple(sizes)),
                        parse_mode=ParseMode.HTML
                    )
            else:
                # Если текущее сообщение без фото, редактируем текст
                msg = await message.edit_text(
                    text=admin_panel_text,
                    reply_markup=get_callback_btns(btns=admin_panel_buttons, sizes=tuple(sizes)),
                    parse_mode=ParseMode.HTML
                )
        except Exception as e:
            ic(f"Error editing message: {e}")
            # Если не получилось отредактировать, отправляем новое сообщение
            if media_path.exists():
                media = FSInputFile(media_path)
                msg = await message.answer_photo(
                    photo=media,
                    caption=admin_panel_text,
                    reply_markup=get_callback_btns(btns=admin_panel_buttons, sizes=tuple(sizes)),
                    parse_mode=ParseMode.HTML
                )
            else:
                ic(f"Admin main menu image not found: {media_path}")
                msg = await message.answer(
                    text=admin_panel_text,
                    reply_markup=get_callback_btns(btns=admin_panel_buttons, sizes=tuple(sizes)),
                    parse_mode=ParseMode.HTML
                )
            try:
                await message.delete()
            except Exception as delete_error:
                ic(f"Error deleting old message: {delete_error}")
    else:
        # Для новых сообщений (не callback)
        if media_path.exists():
            media = FSInputFile(media_path)
            msg = await message.answer_photo(
                photo=media,
                caption=admin_panel_text,
                reply_markup=get_callback_btns(btns=admin_panel_buttons, sizes=tuple(sizes)),
                parse_mode=ParseMode.HTML
            )
        else:
            ic(f"Admin main menu image not found: {media_path}")
            msg = await message.answer(
                text=admin_panel_text,
                reply_markup=get_callback_btns(btns=admin_panel_buttons, sizes=tuple(sizes)),
                parse_mode=ParseMode.HTML
            )
        
        await message.delete()
    
    # Очистка старых сообщений
    if user_id in last_message_dict and last_message_dict[user_id]:
        current_msg_id = msg.message_id
        
        for msg_id in last_message_dict[user_id][:]:
            if msg_id != current_msg_id:
                try:
                    await message.bot.delete_message(chat_id=user_id, message_id=msg_id)
                except Exception as e:
                    ic("Error: ", e)
        
        last_message_dict[user_id] = [current_msg_id]
    else:
        if user_id not in last_message_dict:
            last_message_dict[user_id] = []
        last_message_dict[user_id].append(msg.message_id)


# =============================================================================
# BACK TO ADMIN PANEL HANDLER
# =============================================================================

@AdminPanelRouter.callback_query(F.data == "back_to_admin_panel")
async def back_to_admin_panel(call: types.CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Возврат на главную панель — как вернуться на кухню.
    """
    await admin_panel(call, state, session)


# =============================================================================
# ERROR HANDLER
# =============================================================================

@AdminPanelRouter.message(StateFilter(user_states.AdminPanel.admin_panel))
async def invalid_admin_input(message: types.Message, state: FSMContext) -> None:
    """
    Если кто-то пытается писать текст в админке — мягко напоминаем про кнопки.
    """
    msg = await message.answer(
        text="❓ Шеф, управлять кухней удобнее кнопками внизу 😊",
        parse_mode=ParseMode.HTML
    )
    
    user_id = message.from_user.id
    await message.delete()
    
    if user_id in last_message_dict and last_message_dict[user_id]:
        current_msg_id = msg.message_id
        
        for msg_id in last_message_dict[user_id][:]:
            if msg_id != current_msg_id:
                try:
                    await message.bot.delete_message(chat_id=user_id, message_id=msg_id)
                except Exception as e:
                    ic("Error: ", e)
        
        last_message_dict[user_id] = [current_msg_id]
    else:
        if user_id not in last_message_dict:
            last_message_dict[user_id] = []
        last_message_dict[user_id].append(msg.message_id)


# =============================================================================
# HELPER FUNCTION (для других модулей)
# =============================================================================

async def send_section_message(
    call: types.CallbackQuery,
    text: str,
    buttons: dict,
    sizes: tuple = (1,)
) -> None:
    """
    Отправляет сообщение в разделе админки.
    Используется другими модулями.
    """
    user_id = call.from_user.id
    
    # Получаем текущее сообщение
    current_msg = call.message
    current_text = current_msg.text or current_msg.caption
    current_reply_markup = current_msg.reply_markup
    
    # Создаём новую клавиатуру
    new_reply_markup = get_callback_btns(btns=buttons, sizes=sizes)
    
    # Проверяем, изменилось ли сообщение
    if current_text == text and current_reply_markup == new_reply_markup:
        # Сообщение не изменилось — просто показываем уведомление
        await call.answer("🔄 Всё актуально, обновлений нет", show_alert=False)
        return
    
    try:
        msg = await current_msg.edit_text(
            text=text,
            reply_markup=new_reply_markup,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        # Если не получилось отредактировать — отправляем новое
        ic(f"Error editing message: {e}")
        msg = await current_msg.answer(
            text=text,
            reply_markup=new_reply_markup,
            parse_mode=ParseMode.HTML
        )
        # Удаляем старое сообщение
        try:
            await current_msg.delete()
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