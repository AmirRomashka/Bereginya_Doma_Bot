"""
Mailing Module
==============

This module handles broadcasting messages to all users or selected user groups.
Like sending a warm invitation to all guests at once.
"""

import asyncio
from typing import Union, List, Dict, Any, Optional
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.enums.parse_mode import ParseMode
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from icecream import ic
from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query.users_orm import (
    get_all_users_orm,
    get_users_by_status_orm,
    get_users_count_orm
)
from database.enumirate.users_enum import UserStatus
from database.models.users_model import Users

from keybords.inline import get_callback_btns
from States.user_states import AdminPanel, MailingStates
from config import last_message_dict
from bot_instance import get_bot_instance


# =============================================================================
# ROUTER INITIALIZATION
# =============================================================================

MailingRouter = Router()


# =============================================================================
# CONSTANTS
# =============================================================================

# -----------------------------------------------------------------------------
# Button labels — как инструменты на кухне
# -----------------------------------------------------------------------------
BTN_SELECT_AUDIENCE = "👥 Кому отправим"
BTN_ENTER_TEXT = "📝 Написать сообщение"
BTN_ADD_PHOTO = "🖼 Добавить фото"
BTN_ADD_BUTTONS = "🔘 Добавить кнопки"
BTN_PREVIEW = "👁 Посмотреть"
BTN_SEND = "📨 Отправить"
BTN_CANCEL = "❌ Отмена"
BTN_BACK = "🔙 Назад"
BTN_CONFIRM = "✅ Да, отправляем"
BTN_EDIT = "✏️ Изменить"
BTN_SKIP = "⏭ Пропустить"

# -----------------------------------------------------------------------------
# Audience types — кто наши гости
# -----------------------------------------------------------------------------
AUDIENCE_ALL = "👥 Всем гостям"
AUDIENCE_ACTIVE = "🛒 Кто уже заказывал"
AUDIENCE_NEW = "🆕 Новым гостям"
AUDIENCE_ADMINS = "👑 Команде"
AUDIENCE_COMMON = "👤 Гостям"

# -----------------------------------------------------------------------------
# Callback data
# -----------------------------------------------------------------------------
CALLBACK_MAILING = "mailing"
CALLBACK_MAILING_AUDIENCE = "mailing_audience_"
CALLBACK_MAILING_CONFIRM = "mailing_confirm"
CALLBACK_MAILING_EDIT = "mailing_edit"
CALLBACK_MAILING_SEND = "mailing_send"
CALLBACK_MAILING_CANCEL = "mailing_cancel"
CALLBACK_MAILING_PREVIEW = "mailing_preview"
CALLBACK_MAILING_SKIP_PHOTO = "mailing_skip_photo"
CALLBACK_MAILING_SKIP_BUTTONS = "mailing_skip_buttons"

# -----------------------------------------------------------------------------
# Mailing texts — как личное письмо от шефа
# -----------------------------------------------------------------------------

MAILING_MAIN_TEXT = """
📢 <b>Рассылка</b>

Здесь вы можете написать всем гостям разом — рассказать о новинках, акциях или просто поделиться теплом.

<b>Сейчас у нас:</b>
👥 Всего гостей: <b>{total_users}</b>
👑 Команда: <b>{admin_count}</b>
👤 Гостей: <b>{common_count}</b>

Кому отправим?
"""

AUDIENCE_SELECT_TEXT = """
<b>Кому отправляем:</b> {audience}

👥 Получателей: <b>{count}</b>

Теперь напишите текст сообщения:
"""

PHOTO_PROMPT_TEXT = """
🖼 <b>Добавим фото?</b>

Фото сделает сообщение ярче и вкуснее.
Отправьте фото или нажмите "Пропустить"
"""

BUTTONS_PROMPT_TEXT = """
🔘 <b>Добавим кнопки?</b>

Кнопки помогут гостям сразу перейти по ссылке или сделать заказ.
Формат: Текст кнопки - ссылка

Пример:
Заказать - https://example.com

Или отправьте "-" чтобы пропустить
"""

PREVIEW_TEXT = """
<b>👁 Как увидят гости</b>

━━━━━━━━━━━━━━━━━━━━━
<b>Кому:</b> {audience}
<b>Получателей:</b> {count}

<b>Текст:</b>
{text}

<b>Фото:</b> {photo_status}
<b>Кнопки:</b> {buttons_status}
━━━━━━━━━━━━━━━━━━━━━

Всё верно? Отправляем?
"""

SENDING_PROGRESS = """
📨 <b>Отправляем...</b>

Прогресс: {sent}/{total}
✅ Доставлено: {success}
❌ Не доставлено: {failed}

Последний: {current}
"""

SENDING_COMPLETE = """
✅ <b>Готово!</b>

━━━━━━━━━━━━━━━━━━━━━
📊 <b>Результат:</b>
Всего: {total}
✅ Доставлено: {success}
❌ Не дошло: {failed}

⏱ За {time} сек
━━━━━━━━━━━━━━━━━━━━━
"""


# =============================================================================
# MAILING HANDLERS
# =============================================================================

@MailingRouter.callback_query(F.data == CALLBACK_MAILING, StateFilter(AdminPanel.admin_panel))
async def mailing_start(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Начало рассылки — выбираем, кому отправим приглашение.
    """
    await call.answer()
    
    total_users = await get_users_count_orm(session)
    admins = await get_users_by_status_orm(session, UserStatus.ADMIN.value)
    common = await get_users_by_status_orm(session, UserStatus.COMMON.value)
    
    text = MAILING_MAIN_TEXT.format(
        total_users=total_users,
        admin_count=len(admins),
        common_count=len(common)
    )
    
    buttons = {
        AUDIENCE_ALL: f"{CALLBACK_MAILING_AUDIENCE}all",
        AUDIENCE_ADMINS: f"{CALLBACK_MAILING_AUDIENCE}admins",
        AUDIENCE_COMMON: f"{CALLBACK_MAILING_AUDIENCE}common",
        AUDIENCE_NEW: f"{CALLBACK_MAILING_AUDIENCE}new",
        AUDIENCE_ACTIVE: f"{CALLBACK_MAILING_AUDIENCE}active",
        BTN_CANCEL: "back_to_admin_panel"
    }
    
    await state.set_state(MailingStates.select_audience)
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=[2, 2, 1, 1],
        is_new=True
    )


@MailingRouter.callback_query(F.data.startswith(CALLBACK_MAILING_AUDIENCE), StateFilter(MailingStates.select_audience))
async def mailing_audience_selected(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Выбрали, кому отправим — теперь напишем текст.
    """
    audience_type = call.data.replace(CALLBACK_MAILING_AUDIENCE, "")
    
    users = await get_users_by_audience(session, audience_type)
    
    if not users:
        await call.answer("❌ В этой группе пока нет гостей", show_alert=True)
        return
    
    await state.update_data(
        audience_type=audience_type,
        audience_name=get_audience_name(audience_type),
        users=users,
        user_count=len(users)
    )
    
    text = AUDIENCE_SELECT_TEXT.format(
        audience=get_audience_name(audience_type),
        count=len(users)
    )
    
    await state.set_state(MailingStates.enter_text)
    
    await send_clean_message(
        target=call,
        text=text,
        buttons={BTN_CANCEL: CALLBACK_MAILING_CANCEL},
        edit=True
    )


@MailingRouter.message(F.text, StateFilter(MailingStates.enter_text))
async def mailing_text_received(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """
    Получили текст — теперь спросим про фото.
    """
    text = message.text.strip()
    
    await state.update_data(
        message_text=text,
        message_entities=message.entities
    )
    
    await state.set_state(MailingStates.add_photo)
    
    await send_clean_message(
        target=message,
        text=PHOTO_PROMPT_TEXT,
        buttons={
            BTN_SKIP: CALLBACK_MAILING_SKIP_PHOTO,
            BTN_CANCEL: CALLBACK_MAILING_CANCEL
        },
        sizes=[1, 1],
        is_new=True
    )


@MailingRouter.callback_query(F.data == CALLBACK_MAILING_SKIP_PHOTO, StateFilter(MailingStates.add_photo))
async def mailing_skip_photo(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Фото не нужно — спросим про кнопки.
    """
    await state.update_data(photo=None)
    await state.set_state(MailingStates.add_buttons)
    
    await send_clean_message(
        target=call,
        text=BUTTONS_PROMPT_TEXT,
        buttons={
            BTN_SKIP: CALLBACK_MAILING_SKIP_BUTTONS,
            BTN_CANCEL: CALLBACK_MAILING_CANCEL
        },
        sizes=[1, 1],
        edit=True
    )


@MailingRouter.message(F.photo, StateFilter(MailingStates.add_photo))
async def mailing_photo_received(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """
    Фото добавили — спросим про кнопки.
    """
    photo_id = message.photo[-1].file_id
    
    await state.update_data(photo=photo_id, photo_caption=message.caption)
    await state.set_state(MailingStates.add_buttons)
    
    await send_clean_message(
        target=message,
        text=BUTTONS_PROMPT_TEXT,
        buttons={
            BTN_SKIP: CALLBACK_MAILING_SKIP_BUTTONS,
            BTN_CANCEL: CALLBACK_MAILING_CANCEL
        },
        sizes=[1, 1],
        is_new=True
    )


@MailingRouter.callback_query(F.data == CALLBACK_MAILING_SKIP_BUTTONS, StateFilter(MailingStates.add_buttons))
async def mailing_skip_buttons(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Кнопки не нужны — покажем предпросмотр.
    """
    await state.update_data(buttons=None)
    await show_mailing_preview(call, state, edit=True)


@MailingRouter.message(F.text, StateFilter(MailingStates.add_buttons))
async def mailing_buttons_received(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """
    Получили кнопки — покажем предпросмотр.
    """
    if message.text.strip() == "-":
        await state.update_data(buttons=None)
    else:
        buttons = parse_buttons_text(message.text)
        if buttons:
            await state.update_data(buttons=buttons)
        else:
            await send_clean_message(
                target=message,
                text="❌ Непонятный формат. Попробуйте ещё раз:\n\n" + BUTTONS_PROMPT_TEXT,
                buttons={
                    BTN_SKIP: CALLBACK_MAILING_SKIP_BUTTONS,
                    BTN_CANCEL: CALLBACK_MAILING_CANCEL
                },
                sizes=[1, 1],
                is_new=False
            )
            return
    
    await show_mailing_preview(message, state, edit=False)


async def show_mailing_preview(
    target: Union[Message, CallbackQuery], 
    state: FSMContext, 
    edit: bool = True
) -> None:
    """
    Показываем, как увидят сообщение гости.
    """
    data = await state.get_data()
    
    audience_name = data.get('audience_name', 'Не выбрана')
    user_count = data.get('user_count', 0)
    message_text = data.get('message_text', '')
    has_photo = data.get('photo') is not None
    has_buttons = data.get('buttons') is not None
    
    photo_status = "✅ Будет" if has_photo else "❌ Нет"
    buttons_status = f"✅ {len(data.get('buttons', []))} кнопок" if has_buttons else "❌ Нет"
    
    text = PREVIEW_TEXT.format(
        audience=audience_name,
        count=user_count,
        text=message_text,
        photo_status=photo_status,
        buttons_status=buttons_status
    )
    
    await state.set_state(MailingStates.preview)
    
    buttons = {
        BTN_CONFIRM: CALLBACK_MAILING_SEND,
        BTN_EDIT: CALLBACK_MAILING_EDIT,
        BTN_CANCEL: CALLBACK_MAILING_CANCEL
    }
    
    if has_photo:
        await send_clean_message(
            target=target,
            text=text,
            buttons=buttons,
            sizes=[1, 1, 1],
            photo=data['photo'],
            edit=edit
        )
    else:
        await send_clean_message(
            target=target,
            text=text,
            buttons=buttons,
            sizes=[1, 1, 1],
            edit=edit
        )


@MailingRouter.callback_query(F.data == CALLBACK_MAILING_SEND, StateFilter(MailingStates.preview))
async def mailing_send(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Отправляем рассылку!
    """
    await call.answer()
    
    data = await state.get_data()
    users = data.get('users', [])
    message_text = data.get('message_text', '')
    photo = data.get('photo')
    buttons = data.get('buttons')
    message_entities = data.get('message_entities')
    
    if not users:
        await send_clean_message(
            target=call,
            text="❌ Нет получателей",
            buttons={BTN_BACK: CALLBACK_MAILING},
            edit=True
        )
        return
    
    await state.set_state(MailingStates.sending)
    
    progress_msg = await call.message.answer(
        text=SENDING_PROGRESS.format(
            sent=0,
            total=len(users),
            success=0,
            failed=0,
            current="Начинаем..."
        ),
        parse_mode=ParseMode.HTML
    )
    
    user_id = call.from_user.id
    if user_id not in last_message_dict:
        last_message_dict[user_id] = []
    last_message_dict[user_id].append(progress_msg.message_id)
    
    bot = get_bot_instance()
    results = await send_bulk_messages(
        bot=bot,
        users=users,
        text=message_text,
        photo=photo,
        buttons=buttons,
        entities=message_entities,
        progress_msg=progress_msg,
        total=len(users)
    )
    
    await progress_msg.edit_text(
        text=SENDING_COMPLETE.format(
            total=len(users),
            success=results['success'],
            failed=results['failed'],
            time=results['time']
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=get_callback_btns(
            btns={"🔙 В админ-панель": "back_to_admin_panel"},
            sizes=[1]
        )
    )
    
    await state.clear()


@MailingRouter.callback_query(F.data == CALLBACK_MAILING_EDIT, StateFilter(MailingStates.preview))
async def mailing_edit(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Вернуться к выбору аудитории.
    """
    await state.set_state(MailingStates.select_audience)
    await mailing_start(call, state, session)


@MailingRouter.callback_query(F.data == CALLBACK_MAILING_CANCEL)
async def mailing_cancel(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Отмена рассылки.
    """
    await state.clear()
    await call.answer("❌ Отменили")
    
    from handlers.admin.admin_panel import back_to_admin_panel
    await back_to_admin_panel(call, state, session)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

async def get_users_by_audience(session: AsyncSession, audience_type: str) -> List[Users]:
    """
    Кого позовём?
    """
    if audience_type == "all":
        return await get_all_users_orm(session)
    
    elif audience_type == "admins":
        return await get_users_by_status_orm(session, UserStatus.ADMIN.value)
    
    elif audience_type == "common":
        return await get_users_by_status_orm(session, UserStatus.COMMON.value)
    
    elif audience_type == "new":
        all_users = await get_all_users_orm(session)
        from datetime import datetime, timedelta
        week_ago = datetime.now() - timedelta(days=7)
        return [u for u in all_users if u.created >= week_ago]
    
    elif audience_type == "active":
        return await get_all_users_orm(session)
    
    return []


def get_audience_name(audience_type: str) -> str:
    """
    Название группы.
    """
    names = {
        "all": "👥 Всем гостям",
        "admins": "👑 Команде",
        "common": "👤 Гостям",
        "new": "🆕 Новым гостям",
        "active": "🛒 Кто уже заказывал"
    }
    return names.get(audience_type, audience_type)


def parse_buttons_text(text: str) -> Optional[List[Dict[str, str]]]:
    """
    Разбираем кнопки из текста.
    Формат: "Текст - ссылка"
    """
    try:
        buttons = []
        lines = text.strip().split('\n')
        
        for line in lines:
            if ' - ' in line:
                btn_text, btn_data = line.split(' - ', 1)
                btn_text = btn_text.strip()
                btn_data = btn_data.strip()
                
                if btn_text and btn_data:
                    buttons.append({
                        'text': btn_text,
                        'data': btn_data
                    })
        
        return buttons if buttons else None
    except Exception as e:
        ic(f"Error parsing buttons: {e}")
        return None


async def send_bulk_messages(
    bot,
    users: List[Users],
    text: str,
    photo: Optional[str] = None,
    buttons: Optional[List[Dict[str, str]]] = None,
    entities=None,
    progress_msg: Message = None,
    total: int = 0
) -> Dict[str, Any]:
    """
    Отправляем сообщения всем.
    """
    start_time = datetime.now()
    success = 0
    failed = 0
    
    reply_markup = None
    if buttons:
        btn_dict = {btn['text']: btn['data'] for btn in buttons}
        reply_markup = get_callback_btns(btns=btn_dict, sizes=[1] * len(buttons))
    
    for i, user in enumerate(users, 1):
        try:
            if photo:
                await bot.send_photo(
                    chat_id=user.user_id,
                    photo=photo,
                    caption=text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
            else:
                await bot.send_message(
                    chat_id=user.user_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML,
                    entities=entities
                )
            success += 1
            
        except TelegramForbiddenError:
            failed += 1
            ic(f"User {user.user_id} blocked the bot")
            
        except TelegramRetryAfter as e:
            ic(f"Rate limited, waiting {e.retry_after} seconds")
            await asyncio.sleep(e.retry_after)
            i -= 1
            continue
            
        except Exception as e:
            failed += 1
            ic(f"Error sending to {user.user_id}: {e}")
        
        if i % 5 == 0 and progress_msg:
            try:
                await progress_msg.edit_text(
                    text=SENDING_PROGRESS.format(
                        sent=i,
                        total=total,
                        success=success,
                        failed=failed,
                        current=f"{user.full_name}"
                    ),
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                ic(f"Error updating progress: {e}")
        
        await asyncio.sleep(0.05)
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    return {
        'success': success,
        'failed': failed,
        'time': round(duration, 2)
    }


async def send_clean_message(
    target: Union[Message, CallbackQuery],
    text: str,
    buttons: Optional[Dict[str, str]] = None,
    sizes: tuple = (1,),
    parse_mode: Optional[str] = ParseMode.HTML,
    photo: Optional[str] = None,
    edit: bool = False,
    is_new: bool = False
) -> Message:
    """
    Отправляет сообщение и следит за порядком.
    """
    user_id = target.from_user.id
    
    reply_markup = get_callback_btns(btns=buttons, sizes=sizes) if buttons else None
    
    if isinstance(target, CallbackQuery):
        if edit:
            if photo:
                media = InputMediaPhoto(media=photo, caption=text, parse_mode=parse_mode)
                msg = await target.message.edit_media(media=media, reply_markup=reply_markup)
            else:
                msg = await target.message.edit_text(text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            if photo:
                msg = await target.message.answer_photo(photo=photo, caption=text, reply_markup=reply_markup, parse_mode=parse_mode)
            else:
                msg = await target.message.answer(text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        await target.answer()
    else:
        if photo:
            msg = await target.answer_photo(photo=photo, caption=text, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            msg = await target.answer(text=text, reply_markup=reply_markup, parse_mode=parse_mode)
    
    if is_new:
        if user_id in last_message_dict:
            for msg_id in last_message_dict[user_id][:]:
                try:
                    await target.bot.delete_message(chat_id=user_id, message_id=msg_id)
                except Exception as e:
                    ic(e)
            last_message_dict[user_id] = [msg.message_id]
        else:
            last_message_dict[user_id] = [msg.message_id]
    elif not edit:
        if user_id not in last_message_dict:
            last_message_dict[user_id] = []
        last_message_dict[user_id].append(msg.message_id)
    
    return msg