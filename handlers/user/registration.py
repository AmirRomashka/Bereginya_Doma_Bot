"""
Registration Module
===================

This module handles user registration process.
New users register by sharing their phone number.
"""

import asyncio
from datetime import datetime, date
from typing import Optional
from icecream import ic
from aiogram import F, Router, types
from aiogram.filters import StateFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import KeyboardButton, FSInputFile, ReplyKeyboardRemove
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.enums.parse_mode import ParseMode

from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query.users_orm import (
    update_user_phone_number_orm, 
    update_user_birth_date_orm,
    get_user_orm
)
from keybords.inline import get_callback_btns
from States import user_states
from config import WORK_DIR, last_message_dict
from tools import message_delete, send_clean_message

RegistrationRouter = Router()


# =============================================================================
# CONSTANTS
# =============================================================================

# -----------------------------------------------------------------------------
# Registration messages — в стиле домашней пекарни «Берегиня Дома»
# -----------------------------------------------------------------------------

REGISTRATION_TEXT = {
    'phone_request': """
🤍 <b>Давайте знакомиться!</b>

Мы — «Берегиня Дома», пекарня, где всё по-настоящему.
Здесь пахнет свежим хлебом, ванилью и заботой.

Поделитесь номером телефона — так мы сможем готовить для вас самое любимое.
Нажмите на кнопку ниже, это займёт всего секунду ✨
""",
    'loading_start': "🍞 <b>Готовим для вас</b>",
    'loading_checking': "🔍 Проверяем номер телефона",
    'loading_creating': "📝 Создаём ваш профиль",
    'loading_almost': "✨ Уже почти готово",
    'success_frame1': "🎉 Всё готово!",
    'success_frame2': "✨ Добро пожаловать в «Берегиню Дома»!",
    'success_final': """
🤍 <b>Добро пожаловать в нашу домашнюю пекарню!</b>

🌟 <b>Что дальше?</b>
• Открывайте меню — как заглянуть в бабушкину тетрадь с рецептами
• Выбирайте то, что сегодня хочется к чаю
• Заказывайте с доставкой — будем рады привезти тепло в ваш дом

<i>Приятного аппетита! Пусть будет вкусно, как дома 🥧</i>
""",
    'error_generic': """
❌ <b>Что-то пошло не так</b>

На кухне небольшая заминка. Попробуйте ещё раз чуть позже.
Если ошибка повторится — напишите нам, и мы всё поправим 🤍
""",
    'invalid_phone': """
❍ Пожалуйста, нажмите кнопку <b>📱 Отправить контакт</b>

Так мы точно будем знать, что это вы, и сможем радовать вас свежей выпечкой!
"""
}

# -----------------------------------------------------------------------------
# Birthday messages — про подарки и внимание
# -----------------------------------------------------------------------------

BIRTHDAY_TEXT = {
    'prompt': """
🎂 <b>День рождения — праздник со вкусом!</b>

Расскажите, когда у вас день рождения?
Мы будем рады поздравить вас и приготовить что-то особенное 🎉

Введите дату в формате: <i>15.05.1990</i>

""",
    'invalid_format': """
❌ <b>Неразборчиво</b>

Пожалуйста, напишите дату понятнее.
Вот так: <i>15.05.1990</i> или <i>15/05/1990</i>
""",
    'too_young': "❌ Для такого возраста у нас пока нет меню. Попробуйте через пару лет 😊",
    'too_old': "❌ Уверены? Давайте проверим дату — 120 лет многовато даже для нашей бабушкиной тетради",
    'future_date': "❌ Вы из будущего? Напишите дату, которая уже была",
    'canceled': "❌ Хорошо, в другой раз расскажете ✨",
    'saved': """
🎂 <b>Спасибо, {name}!</b>

Мы запомнили ваш день рождения — <b>{date}</b> 🎉

В этот день мы обязательно поздравим вас и подарим особый подарок!
А уже сейчас — <b>скидка 20%</b> на первый заказ 🥧

<i>С любовью, «Берегиня Дома» 🤍</i>
""",
    'error': "❌ Не удалось сохранить дату. Попробуйте позже — мы уже ищем, в чём дело",
    'already_exists': """
🎂 <b>Мы уже знаем!</b>

Вы уже рассказывали о своём дне рождения — <b>{date}</b> 🎉

Ждём праздника, чтобы поздравить вас как следует!
"""
}

# Путь к изображению для приветствия
TEST_IMAGE_PATH = "image/test_screen.jpg"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def escape_html(text: str) -> str:
    """Экранирует HTML-спецсимволы для безопасного отображения"""
    import html
    return html.escape(text)


def parse_birth_date(text: str) -> Optional[date]:
    """Парсит дату рождения из текста."""
    for fmt in ["%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d"]:
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    return None


def validate_birth_date(birth_date: date) -> tuple[bool, str]:
    """Проверяет корректность даты рождения."""
    today = date.today()
    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    
    if birth_date > today:
        return False, BIRTHDAY_TEXT['future_date']
    if age < 5:
        return False, BIRTHDAY_TEXT['too_young']
    if age > 120:
        return False, BIRTHDAY_TEXT['too_old']
    
    return True, ""


def format_birth_date(birth_date: date) -> str:
    """Красиво форматирует дату рождения в тёплом стиле."""
    months = {
        1: "января", 2: "февраля", 3: "марта", 4: "апреля",
        5: "мая", 6: "июня", 7: "июля", 8: "августа",
        9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
    }
    return f"{birth_date.day} {months[birth_date.month]} {birth_date.year}"


# =============================================================================
# HANDLERS
# =============================================================================

@RegistrationRouter.callback_query(F.data == "registration", StateFilter(user_states.StartState.start))
async def phone_number_query(call: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    """
    Запрос номера телефона — как приглашение заглянуть на огонёк.
    """
    await state.set_state(user_states.RegistrationState.phone_number)
    await call.answer()

    user_id = call.from_user.id

    # Создаём клавиатуру с кнопкой для отправки контакта
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(
        text="📱 Отправить контакт", 
        request_contact=True
    ))
    builder.adjust(1)

    media_path = WORK_DIR / TEST_IMAGE_PATH
    
    if media_path.exists():
        media = FSInputFile(media_path)
        msg = await call.message.answer_photo(
            photo=media,
            caption=REGISTRATION_TEXT['phone_request'],
            reply_markup=builder.as_markup(resize_keyboard=True),
            parse_mode=ParseMode.HTML
        )
    else:
        ic(f"Image not found: {media_path}")
        msg = await call.message.answer(
            text=REGISTRATION_TEXT['phone_request'],
            reply_markup=builder.as_markup(resize_keyboard=True),
            parse_mode=ParseMode.HTML
        )

    await message_delete(user_id, last_message_dict)
    last_message_dict[user_id].extend([msg.message_id])


@RegistrationRouter.message(
    lambda message: message.contact is not None, 
    StateFilter(user_states.RegistrationState.phone_number)
)
async def user_registration(message: types.Message, state: FSMContext, session: AsyncSession):
    """
    Обработка полученного контакта — как встреча дорогого гостя.
    """
    user_id = message.from_user.id
    
    # Проверяем, что присланный контакт принадлежит пользователю
    if message.contact.user_id != user_id:
        await message.answer(
            REGISTRATION_TEXT['invalid_phone'],
            reply_markup=ReplyKeyboardRemove(),
            parse_mode=ParseMode.HTML
        )
        return
    
    try:
        loading_messages = [
            REGISTRATION_TEXT['loading_checking'],
            REGISTRATION_TEXT['loading_creating'],
            REGISTRATION_TEXT['loading_almost']
        ]
        
        msg = await message.answer(
            text=REGISTRATION_TEXT['loading_start'],
            parse_mode=ParseMode.HTML
        )
        
        # Анимация процесса регистрации — как хлеб подходит в печи
        for i, status_text in enumerate(loading_messages):
            await asyncio.sleep(1.2)
            
            progress = "█" * (i + 1) + "░" * (2 - i)
            progress_percent = ((i + 1) * 33)
            
            await msg.edit_text(
                text=f"""🤍 <b>Регистрация</b>

{progress} {progress_percent}%

{status_text}...""",
                parse_mode=ParseMode.HTML
            )
        
        # Сохраняем номер телефона
        result = await update_user_phone_number_orm(
            session=session, 
            user_id=user_id, 
            phone_number=message.contact.phone_number
        )
        
        await message.delete()
        await message_delete(user_id, last_message_dict)
        
        if result is True:
            # Финальная анимация — выпечка готова!
            success_frames = [
                REGISTRATION_TEXT['success_frame1'],
                REGISTRATION_TEXT['success_frame2']
            ]
            
            for frame in success_frames:
                await msg.edit_text(
                    text=f"""🤍 <b>Успешно!</b>

{frame}""",
                    parse_mode=ParseMode.HTML
                )
                await asyncio.sleep(0.8)
            
            # Финальное сообщение с приглашением в меню
            await msg.edit_text(
                text=REGISTRATION_TEXT['success_final'],
                reply_markup=get_callback_btns(
                    btns={"🍰 Перейти в меню": "main_menu"},
                    sizes=(1,)
                ),
                parse_mode=ParseMode.HTML
            )
            
            if user_id not in last_message_dict:
                last_message_dict[user_id] = []
            last_message_dict[user_id].append(msg.message_id)
            
            await state.clear()
            
        else:
            # Ошибка при регистрации
            if isinstance(result, str):
                clean_result = escape_html(result)
                error_text = f"❌ <b>Ошибка</b>\n\n{clean_result}\n\n<i>Давайте попробуем ещё раз 🤍</i>"
            else:
                error_text = REGISTRATION_TEXT['error_generic']
            
            await msg.edit_text(
                text=error_text,
                reply_markup=get_callback_btns(
                    btns={"🔄 Попробовать снова": "registration", "🏠 Главное меню": "main_menu"},
                    sizes=(1, 1)
                ),
                parse_mode=ParseMode.HTML
            )
            
    except Exception as e:
        ic(f"Registration error: {e}")
        error_msg = await message.answer(
            text=REGISTRATION_TEXT['error_generic'],
            reply_markup=get_callback_btns(
                btns={"🔄 Попробовать снова": "registration", "🏠 Главное меню": "main_menu"},
                sizes=(1, 1)
            ),
            parse_mode=ParseMode.HTML
        )
        
        if user_id not in last_message_dict:
            last_message_dict[user_id] = []
        last_message_dict[user_id].append(error_msg.message_id)


@RegistrationRouter.message(StateFilter(user_states.RegistrationState.phone_number))
async def invalid_phone_input(message: types.Message, state: FSMContext):
    """
    Обработка, когда пользователь вводит текст вместо кнопки.
    """
    msg = await message.answer(
        REGISTRATION_TEXT['invalid_phone'],
        reply_markup=ReplyKeyboardRemove(),
        parse_mode=ParseMode.HTML
    )
    
    user_id = message.from_user.id
    if user_id not in last_message_dict:
        last_message_dict[user_id] = []
    last_message_dict[user_id].append(msg.message_id)


# =============================================================================
# BIRTHDAY HANDLERS
# =============================================================================

@RegistrationRouter.message(Command("set_birthday"))
async def request_birth_date(message: types.Message, state: FSMContext, session: AsyncSession):
    """
    Запрос даты рождения — как секретный ингредиент для особого подарка.
    """
    await message.delete()
    
    # Проверяем, зарегистрирован ли пользователь
    user = await get_user_orm(session, message.from_user.id)
    
    # Если пользователь не зарегистрирован — показываем стартовый экран
    if not user or not user.phone_number:
        return
    
    # Если дата рождения уже указана
    if user.birth_date:
        return
    
    await state.set_state(user_states.RegistrationState.birth_date)
    
    await send_clean_message(
        target=message,
        text=BIRTHDAY_TEXT['prompt'],
        buttons={"❌ Отмена": "cancel_birth_date"},
        sizes=[1],
        parse_mode="HTML"
    )


@RegistrationRouter.message(StateFilter(user_states.RegistrationState.birth_date))
async def save_birth_date(message: types.Message, state: FSMContext, session: AsyncSession):
    """
    Сохранение даты рождения — записываем в семейную книгу рецептов.
    """
    # Проверяем, зарегистрирован ли пользователь (на случай, если состояние осталось)
    user = await get_user_orm(session, message.from_user.id)
    if not user or not user.phone_number:
        from handlers.start import start
        await start(message, state, session)
        return
    
    birth_date = parse_birth_date(message.text)
    
    if not birth_date:
        await send_clean_message(
            target=message,
            text=BIRTHDAY_TEXT['invalid_format'],
            buttons={"❌ Отмена": "cancel_birth_date"},
            sizes=[1],
            parse_mode="HTML"
        )
        return
    
    # Валидация
    is_valid, error_msg = validate_birth_date(birth_date)
    if not is_valid:
        await send_clean_message(
            target=message,
            text=error_msg,
            buttons={"❌ Отмена": "cancel_birth_date"},
            sizes=[1],
            parse_mode="HTML"
        )
        return
    
    # Сохраняем в БД
    success = await update_user_birth_date_orm(session, message.from_user.id, birth_date)
    
    if success:
        formatted_date = format_birth_date(birth_date)
        
        await send_clean_message(
            target=message,
            text=BIRTHDAY_TEXT['saved'].format(
                name=message.from_user.full_name,
                date=formatted_date
            ),
            buttons={"🍰 Перейти в меню": "user_catalog"},
            sizes=[1],
            parse_mode="HTML"
        )
        await state.clear()
    else:
        await send_clean_message(
            target=message,
            text=BIRTHDAY_TEXT['error'],
            buttons={"❌ Отмена": "cancel_birth_date"},
            sizes=[1],
            parse_mode="HTML"
        )


@RegistrationRouter.callback_query(F.data == "cancel_birth_date")
async def cancel_birth_date(call: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    """
    Отмена ввода даты рождения — ничего страшного, расскажете в следующий раз.
    """
    await state.clear()
    await send_clean_message(
        target=call,
        text=BIRTHDAY_TEXT['canceled'],
        buttons={"🏠 Главное меню": "main_menu"},
        sizes=[1],
        parse_mode="HTML"
    )