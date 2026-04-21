from typing import Union
from aiogram import F, Router, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile

from sqlalchemy.ext.asyncio import AsyncSession

from database.models.users_model import Users
from database.orm_query.users_orm import add_user_orm, get_user_orm
from handlers.user.user_panel import show_user_panel
from keybords.inline import get_callback_btns
from States import user_states
from config import WORK_DIR, last_message_dict
from tools import message_delete

StartRouter = Router()

CALLBACK_ABOUT_US_FROM_START = "about_us_from_start"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def format_birth_date(birth_date) -> str:
    """Красиво форматирует дату рождения."""
    if not birth_date:
        return ""
    months = {
        1: "января", 2: "февраля", 3: "марта", 4: "апреля",
        5: "мая", 6: "июня", 7: "июля", 8: "августа",
        9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
    }
    return f"{birth_date.day} {months[birth_date.month]} {birth_date.year}"


# =============================================================================
# HANDLERS
# =============================================================================

@StartRouter.message(CommandStart(deep_link=True, magic=F.args == "set_birthday"))
async def start_with_birthday(message: types.Message, state: FSMContext, session: AsyncSession):
    """
    Обработка глубокой ссылки с параметром set_birthday.
    Пользователь нажал на ссылку с приглашением указать день рождения.
    """
    user_id = message.from_user.id
    
    # Получаем пользователя из БД
    user = await get_user_orm(session, user_id)
    
    # Проверяем, зарегистрирован ли пользователь
    is_registered = user and user.phone_number is not None
    
    if not is_registered:
        # Если не зарегистрирован — показываем стартовый экран
        await start(message, state, session)
        return
    
    # Если дата рождения уже есть
    if user.birth_date:
        formatted_date = format_birth_date(user.birth_date)
        await message.answer(
            f"🎂 Ваш день рождения уже указан — <b>{formatted_date}</b>! 🎉",
            reply_markup=get_callback_btns(
                btns={"🍽 В меню": "main_menu"},
                sizes=(1,)
            ),
            parse_mode="HTML"
        )
        return
    
    # Запрашиваем дату рождения
    from handlers.user.registration import request_birth_date
    await request_birth_date(message, state, session)


@StartRouter.message(Command("start"))
@StartRouter.callback_query(F.data == "start")
async def start(event: Union[types.Message, types.CallbackQuery], 
                state: FSMContext, 
                session: AsyncSession):
    """
    Стартовый экран — приветствие и предложение зарегистрироваться.
    """
    user_id = event.from_user.id

    # Проверяем, есть ли пользователь в БД
    user: Users = await get_user_orm(session, user_id)
    
    # Проверяем, зарегистрирован ли пользователь
    is_registered = user and user.phone_number is not None
    
    if is_registered:
        # Если пользователь уже зарегистрирован — показываем главное меню
        await show_user_panel(event, state, session)
        return
    
    # Если пользователя нет в БД — создаём
    if not user:
        user_data = {
            "user_id": user_id,
            "full_name": event.from_user.full_name,
            "username": event.from_user.username
        }
        await add_user_orm(session=session, data=user_data)
        await session.commit()
    
    if isinstance(event, types.Message):
        message = event
    else:
        message = event.message
        await event.answer()

    await state.clear()
    await state.set_state(user_states.StartState.start)
    
    start_text = """
🍞 <b>Добро пожаловать в «Берегиню Дома»</b>

Здесь пахнет хлебом, заботой и чем-то очень родным.

Мы печём для вас живой хлеб на фруктовой закваске, создаём полезные сладости без лишнего, готовим домашнюю еду, которая ждёт вас в морозилке и спасает в самые занятые дни.

🌾 <b>Что мы для вас готовим:</b>
🍞 Хлеб на закваске — с хрустящей корочкой и душой
🍫 Полезные сладости — шоколад, зефир, торты без компромиссов
🌱 Безглютеновую линейку — для тех, кто бережёт себя
🎉 Кейтеринг и доставку на мероприятия

🚚 Еженедельно доставляем в Калугу, Москву и Подмосковье.

<i>Зарегистрируйтесь, чтобы сделать заказ, и получите скидку на день рождения 🎂</i>
"""

    start_buttons = {
        "📝 Регистрация": "registration",
        "ℹ️ О нас": CALLBACK_ABOUT_US_FROM_START
    }
        
    relative_path = "image/test_screen.jpg"
    media_path = WORK_DIR / relative_path
    media = FSInputFile(media_path)
    msg = await message.answer_photo(
        photo=media,
        caption=start_text,
        reply_markup=get_callback_btns(btns=start_buttons, sizes=(1, 1)),
        parse_mode="HTML"
    )
        
    await message_delete(user_id, last_message_dict)
    last_message_dict[user_id].extend([msg.message_id])
        
    if isinstance(event, types.Message):
        await event.delete()