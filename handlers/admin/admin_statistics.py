"""
Admin Statistics Module
=======================

This module handles detailed statistics for the chef.
"""

from datetime import datetime, timedelta
from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.enums.parse_mode import ParseMode
from aiogram.types import FSInputFile, InputMediaPhoto

from icecream import ic
from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query.orders_orm import OrderRepository  
from States import user_states
from config import WORK_DIR, last_message_dict

from handlers.admin.admin_panel import send_section_message
from keybords.inline import get_callback_btns


# =============================================================================
# ROUTER INITIALIZATION
# =============================================================================

AdminStatisticsRouter = Router()


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

ADMIN_STATISTICS_IMAGE = "image/admin_images/admin_statistics.png"


def format_number(number: int) -> str:
    """Форматирует число с разделителями тысяч."""
    return f"{number:,}".replace(",", " ")


def format_average(total: int, count: int) -> str:
    """Форматирует среднее значение."""
    if count == 0:
        return "0"
    return f"{total / count:,.0f}".replace(",", " ")


# =============================================================================
# HANDLERS
# =============================================================================

@AdminStatisticsRouter.callback_query(F.data == "detailed_stats", StateFilter(user_states.AdminPanel.admin_panel))
async def show_detailed_statistics(call: types.CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    📊 Детальная статистика — итоги за периоды (неделя, месяц, всё время).
    """
    await call.answer()
    
    order_repo = OrderRepository(session)
    now = datetime.now()
    
    # =========================================================================
    # ЗА ВСЁ ВРЕМЯ
    # =========================================================================
    total_orders = await order_repo.get_total_orders_count()
    completed_total = await order_repo.get_completed_orders_count()
    refused_total = await order_repo.get_refused_orders_count()
    
    # Получаем выручку за всё время
    all_time_revenue = await order_repo.get_total_revenue()
    
    # =========================================================================
    # ЗА ПОСЛЕДНИЕ 30 ДНЕЙ (МЕСЯЦ)
    # =========================================================================
    month_ago = now - timedelta(days=30)
    completed_month = await order_repo.get_completed_orders_count(days=30)
    month_revenue = await order_repo.get_revenue_for_period(month_ago, now)
    
    # =========================================================================
    # ЗА ПОСЛЕДНИЕ 7 ДНЕЙ (НЕДЕЛЯ)
    # =========================================================================
    week_ago = now - timedelta(days=7)
    completed_week = await order_repo.get_completed_orders_count(days=7)
    week_revenue = await order_repo.get_revenue_for_period(week_ago, now)
    
    # =========================================================================
    # ФОРМИРУЕМ ТЕКСТ
    # =========================================================================
    text = f"""
📊 <b>Кухня в цифрах</b>

<b>📅 За всё время</b>
📦 Всего заказов: <b>{format_number(total_orders)}</b>
✅ Выполнено: <b>{format_number(completed_total)}</b>
❌ Отказано: <b>{format_number(refused_total)}</b>
💰 Выручка: <b>{format_number(all_time_revenue)} ₽</b>
📈 Выполняемость: <b>{round(completed_total / total_orders * 100, 1) if total_orders > 0 else 0}%</b>

<b>📅 За последние 30 дней</b>
✅ Выполнено заказов: <b>{format_number(completed_month)}</b>
💰 Выручка: <b>{format_number(month_revenue)} ₽</b>
📊 Средний чек: <b>{format_average(month_revenue, completed_month)} ₽</b>

<b>📅 За последние 7 дней</b>
✅ Выполнено заказов: <b>{format_number(completed_week)}</b>
💰 Выручка: <b>{format_number(week_revenue)} ₽</b>
📊 Средний чек: <b>{format_average(week_revenue, completed_week)} ₽</b>

<i>Доставки выполняются раз в неделю.
Статистика обновляется автоматически.</i>
"""
    
    buttons = {
        "🔙 Назад": "back_to_admin_panel"
    }
    sizes = [1]
    
    # Получаем путь к изображению
    media_path = WORK_DIR / ADMIN_STATISTICS_IMAGE
    
    # Получаем текущее сообщение
    current_msg = call.message
    new_reply_markup = get_callback_btns(btns=buttons, sizes=tuple(sizes))
    
    try:
        # Если текущее сообщение с фото, редактируем его
        if current_msg.photo:
            if media_path.exists():
                media = FSInputFile(media_path)
                media_input = InputMediaPhoto(media=media, caption=text, parse_mode=ParseMode.HTML)
                msg = await current_msg.edit_media(
                    media=media_input,
                    reply_markup=new_reply_markup
                )
            else:
                ic(f"Statistics image not found: {media_path}")
                msg = await current_msg.edit_text(
                    text=text,
                    reply_markup=new_reply_markup,
                    parse_mode=ParseMode.HTML
                )
        else:
            # Если текущее сообщение без фото, пытаемся отправить с фото
            if media_path.exists():
                # Если есть фото, но текущее сообщение без фото — отправляем новое с фото
                media = FSInputFile(media_path)
                msg = await current_msg.answer_photo(
                    photo=media,
                    caption=text,
                    reply_markup=new_reply_markup,
                    parse_mode=ParseMode.HTML
                )
                try:
                    await current_msg.delete()
                except Exception as delete_error:
                    ic(f"Error deleting old message: {delete_error}")
            else:
                # Если фото нет, редактируем текст
                ic(f"Statistics image not found: {media_path}")
                msg = await current_msg.edit_text(
                    text=text,
                    reply_markup=new_reply_markup,
                    parse_mode=ParseMode.HTML
                )
    except Exception as e:
        ic(f"Error editing message: {e}")
        # Fallback: отправляем новое сообщение
        if media_path.exists():
            media = FSInputFile(media_path)
            msg = await current_msg.answer_photo(
                photo=media,
                caption=text,
                reply_markup=new_reply_markup,
                parse_mode=ParseMode.HTML
            )
        else:
            ic(f"Statistics image not found: {media_path}")
            msg = await current_msg.answer(
                text=text,
                reply_markup=new_reply_markup,
                parse_mode=ParseMode.HTML
            )
        try:
            await current_msg.delete()
        except Exception as delete_error:
            ic(f"Error deleting old message: {delete_error}")
    
    # Очистка старых сообщений
    user_id = call.from_user.id
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