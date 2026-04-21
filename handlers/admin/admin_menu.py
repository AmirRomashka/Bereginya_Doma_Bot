"""
Menu Management Module for Admin Panel
======================================

This module handles the menu management functionality for administrators.
Here the chef creates and updates the menu — what guests will see and order.
"""

from typing import Dict, List, Optional, Any, Tuple

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from icecream import ic
from sqlalchemy.ext.asyncio import AsyncSession

# =============================================================================
# DATABASE IMPORTS
# =============================================================================
from database.orm_query.category_orm import add_category_orm, get_categories_orm, update_category_orm, delete_category_orm
from database.orm_query.dish_orm import (
    add_dish_orm, 
    get_dish_by_category_orm,
    get_dish_by_id_orm,
    delete_dish_orm,
    update_dish_orm
)

# =============================================================================
# PROJECT IMPORTS
# =============================================================================
from States import user_states
from tools import parse_callback, send_clean_message


# =============================================================================
# ROUTER INITIALIZATION
# =============================================================================

MenuRouter = Router()


# =============================================================================
# CONSTANTS
# =============================================================================

# -----------------------------------------------------------------------------
# Message texts — как страницы поваренной книги шефа
# -----------------------------------------------------------------------------

WELCOME_TEXT = """
🍽 <b>Добро пожаловать в управление меню, шеф!</b>

Здесь вы создаёте блюда, которые будут радовать наших гостей.
Всё как на настоящей кухне — выбирайте категории, добавляйте рецепты.
"""

EMPTY_CATEGORIES_TEXT = """
📭 <b>В меню пока нет категорий</b>

Начните с создания первой категории:
• Нажмите "➕ Добавить категорию"
• Придумайте название (например: "Супы", "Горячее", "Десерты")
• Добавляйте блюда в созданные категории

<i>Гости уже ждут ваши новые рецепты 🤍</i>
"""

EMPTY_DISHES_TEXT = """
📭 <b>В этой категории пока нет блюд</b>

✨ Самое время их добавить:
• Нажмите "➕ Добавить блюдо"
• Введите название, описание и цену
• Добавьте аппетитное фото

<i>Блюдо сразу появится в меню у гостей!</i>
"""

CATEGORY_SELECT_TEXT = """
📋 <b>Ваши категории</b>

Нажмите на категорию, чтобы управлять ею или посмотреть блюда.
"""

CATEGORY_MANAGEMENT_TEXT = """
📋 <b>Управление категорией:</b> <i>{name}</i>

Что хотите сделать?
"""

DISH_SELECT_TEXT = """
🍽 <b>Блюда в категории</b>

Выберите блюдо для просмотра или:
✅ Добавьте новое блюдо
✅ Вернитесь к категориям

<i>Кликните по названию блюда — откроется карточка для редактирования</i>
"""

# -----------------------------------------------------------------------------
# Dish detail texts — карточка блюда для шефа
# -----------------------------------------------------------------------------

DISH_DETAIL_TEMPLATE = """
🍽 <b>{name}</b>

━━━━━━━━━━━━━━━━━━━━━
📝 <b>Описание:</b>
{description}

💰 <b>Цена:</b> {price} ₽
📁 <b>Категория:</b> {category_name}
🆔 <b>ID:</b> {dish_id}
━━━━━━━━━━━━━━━━━━━━━

<i>Вы можете отредактировать блюдо или удалить его из меню</i>
"""

DISH_NO_DESCRIPTION = "<i>Описание не добавлено</i>"

# -----------------------------------------------------------------------------
# Success messages
# -----------------------------------------------------------------------------

CATEGORY_ADDED = """
✅ <b>Категория создана!</b>

Теперь вы можете добавлять в неё блюда.
Что делаем дальше?
"""

CATEGORY_UPDATED = """
✏️ <b>Категория обновлена</b>

Новое название: <b>{name}</b>
"""

CATEGORY_DELETED = """
🗑 <b>Категория удалена</b>

Все блюда в этой категории также убраны из меню.
"""

DISH_ADDED = """
✅ <b>Блюдо добавлено в меню!</b>

Оно сразу появится у гостей.
Хотите добавить ещё одно?
"""

DISH_DELETED = """
🗑 <b>Блюдо убрано из меню</b>

Изменения вступят в силу немедленно.
"""

DISH_UPDATED = """
✏️ <b>Блюдо обновлено</b>

Гости уже видят новые данные.
"""

# -----------------------------------------------------------------------------
# Category edit/delete prompts
# -----------------------------------------------------------------------------

CATEGORY_EDIT_PROMPT = """
📝 <b>Изменение названия категории</b>

Текущее название: <i>{name}</i>

Введите новое название:
"""

CATEGORY_DELETE_CONFIRM = """
⚠️ <b>Подтверждение удаления категории</b>

Вы действительно хотите удалить категорию:
<b>«{name}»</b>?

⚠️ <b>Внимание!</b> Вместе с категорией будут удалены <b>все блюда</b> в ней.
Это действие <b>нельзя отменить</b>!
"""

# -----------------------------------------------------------------------------
# Button labels — как инструменты на кухне
# -----------------------------------------------------------------------------
BTN_ADD_CATEGORY = "➕ Добавить категорию"
BTN_ADD_DISH = "➕ Добавить блюдо"
BTN_BACK = "🔙 Назад"
BTN_BACK_TO_CATEGORIES = "📋 К категориям"
BTN_BACK_TO_DISHES = "🍽 К списку блюд"
BTN_EDIT = "✏️ Редактировать"
BTN_DELETE = "🗑 Удалить"
BTN_CONFIRM = "✅ Да, удалить"
BTN_CANCEL = "❌ Отмена"
BTN_VIEW_DISHES = "🍽 Смотреть блюда"
BTN_ADD_MORE = "➕ Добавить ещё"
BTN_ADMIN_PANEL = "🏠 Админ Панель"
BTN_EDIT_CATEGORY = "✏️ Изменить название"
BTN_DELETE_CATEGORY = "🗑 Удалить категорию"

# -----------------------------------------------------------------------------
# Prompt texts — как вопросы шеф-повару
# -----------------------------------------------------------------------------

PROMPT_CATEGORY_NAME = """
📝 <b>Создание новой категории</b>

Введите название категории:
<i>(например: "Супы", "Салаты", "Горячее", "Десерты")</i>
"""

PROMPT_DISH_NAME = """
🍽 <b>Создание нового блюда</b> [Шаг 1/5]

Введите <b>название блюда</b>:
<i>(например: "Борщ", "Цезарь", "Тирамису")</i>
"""

PROMPT_DISH_DESCRIPTION = """
📝 <b>Создание нового блюда</b> [Шаг 2/5]

Введите <b>описание блюда</b>:
• Ингредиенты
• Особенности подачи
• Вес порции

<i>Или отправьте "-" чтобы пропустить</i>
"""

PROMPT_DISH_PRICE = """
💰 <b>Создание нового блюда</b> [Шаг 3/5]

Введите <b>цену</b> (только цифры):
<i>например: 350</i>
"""

PROMPT_DISH_IMAGE = """
🖼 <b>Создание нового блюда</b> [Шаг 4/5]

Отправьте <b>фотографию блюда</b>:
• Аппетитное фото привлечёт больше гостей
• Поддерживаются форматы JPG, PNG

<i>Или отправьте "-" чтобы пропустить</i>
"""

PROMPT_DISH_CONFIRM = """
🎉 <b>Создание нового блюда</b> [Шаг 5/5]

<b>Проверьте данные:</b>
━━━━━━━━━━━━━━━━━━━━━
🍽 <b>Название:</b> {name}
📝 <b>Описание:</b> {description}
💰 <b>Цена:</b> {price} ₽
🖼 <b>Фото:</b> {photo_status}
━━━━━━━━━━━━━━━━━━━━━

Всё верно? Сохраняем блюдо в меню?
"""

# -----------------------------------------------------------------------------
# Edit prompts
# -----------------------------------------------------------------------------

EDIT_DISH_OPTIONS = """
✏️ <b>Редактирование блюда:</b> <i>{name}</i>

Выберите, что хотите изменить:
• Название
• Описание
• Цену
• Фотографию
• Категорию
"""

EDIT_NAME_PROMPT = """
📝 <b>Изменение названия</b>

Текущее название: <i>{name}</i>

Введите новое название:
"""

EDIT_DESCRIPTION_PROMPT = """
📝 <b>Изменение описания</b>

Текущее описание:
<i>{description}</i>

Введите новое описание:
"""

EDIT_PRICE_PROMPT = """
💰 <b>Изменение цены</b>

Текущая цена: <i>{price} ₽</i>

Введите новую цену (только цифры):
"""

EDIT_IMAGE_PROMPT = """
🖼 <b>Изменение фотографии</b>

Текущее фото: {photo_status}

Отправьте новую фотографию:
"""

# -----------------------------------------------------------------------------
# Confirmation texts
# -----------------------------------------------------------------------------

CONFIRM_DELETE = """
⚠️ <b>Подтверждение удаления</b>

Вы действительно хотите удалить блюдо:
<b>«{name}»</b>?

Это действие <b>нельзя отменить</b>!
"""

# -----------------------------------------------------------------------------
# Error messages
# -----------------------------------------------------------------------------

ERROR_DISH_NOT_FOUND = """
❌ <b>Блюдо не найдено</b>

Возможно, оно уже было удалено.
Попробуйте выбрать другое блюдо.
"""

ERROR_INVALID_PRICE = """
❌ <b>Неверный формат цены</b>

Пожалуйста, введите только цифры.
Например: <i>350</i> или <i>1290</i>
"""

ERROR_GENERIC = """
❌ <b>Что-то пошло не так</b>

Пожалуйста, попробуйте ещё раз.
Если ошибка повторится, обратитесь к разработчику.
"""


# =============================================================================
# CALLBACK CONSTANTS
# =============================================================================

CALLBACK_BACK_TO_PANEL = "panel"
CALLBACK_BACK_TO_MENU = "back_to_menu"
CALLBACK_NEW_CATEGORY = "new_category"
CALLBACK_CATEGORY_PREFIX = "show_category_"
CALLBACK_CATEGORY_VIEW_DISHES = "category_view_dishes_"
CALLBACK_DISH_PREFIX = "admin_dish_"
CALLBACK_NEW_DISH_PREFIX = "new_dish_"
CALLBACK_EDIT_DISH_PREFIX = "edit_dish_"
CALLBACK_DELETE_DISH_PREFIX = "delete_dish_"
CALLBACK_CONFIRM_DELETE_PREFIX = "confirm_delete_"
CALLBACK_EDIT_CATEGORY_PREFIX = "edit_category_"
CALLBACK_DELETE_CATEGORY_PREFIX = "delete_category_"
CALLBACK_CONFIRM_DELETE_CATEGORY_PREFIX = "confirm_delete_category_"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_category_name_by_id(categories: List[Dict[str, Any]], category_id: int) -> str:
    """Возвращает название категории по её ID."""
    for cat in categories:
        if cat['category_id'] == category_id:
            return cat['name']
    return f"Категория {category_id}"


def format_dish_detail(dish: Dict[str, Any], category_name: str = None) -> str:
    """Форматирует карточку блюда для шеф-повара."""
    description = dish.get('description') or DISH_NO_DESCRIPTION
    cat_name = category_name or f"Категория {dish['category_id']}"
    
    return DISH_DETAIL_TEMPLATE.format(
        name=dish['name'],
        description=description,
        price=dish['price'],
        category_name=cat_name,
        dish_id=dish['dish_id']
    )


def calculate_button_sizes(buttons: Dict[str, str]) -> List[int]:
    """
    Рассчитывает расположение кнопок на клавиатуре.
    - Обычные кнопки по 2 в ряд
    - Специальные кнопки по 1 в ряд
    """
    button_count = len(buttons)
    
    if button_count == 0:
        return []
    
    action_buttons = []
    special_buttons = []
    
    special_button_texts = [
        BTN_ADD_CATEGORY, BTN_ADD_DISH, 
        BTN_BACK, BTN_BACK_TO_CATEGORIES, BTN_BACK_TO_DISHES,
        BTN_ADMIN_PANEL, BTN_EDIT_CATEGORY, BTN_DELETE_CATEGORY,
        BTN_VIEW_DISHES
    ]
    
    for text, callback in buttons.items():
        if text in special_button_texts:
            special_buttons.append((text, callback))
        else:
            action_buttons.append((text, callback))
    
    sizes = []
    
    for _ in special_buttons:
        sizes.append(1)
    
    action_count = len(action_buttons)
    full_rows = action_count // 2
    last_row = action_count % 2
    
    sizes.extend([2] * full_rows)
    if last_row:
        sizes.append(last_row)
    
    return sizes if sizes else [1]


def create_navigation_buttons(
    items: List[Dict[str, Any]],
    item_type: str,
    add_new_text: str = None,
    add_new_callback: str = None,
    category_id: Optional[int] = None,
    include_back: bool = True
) -> tuple[Dict[str, str], List[int]]:
    """
    Создаёт кнопки навигации для категорий или блюд.
    """
    buttons: Dict[str, str] = {}
    
    if add_new_text is None:
        add_new_text = BTN_ADD_CATEGORY if item_type == "category" else BTN_ADD_DISH
    
    if add_new_callback:
        buttons[add_new_text] = add_new_callback
    elif item_type == "category":
        buttons[add_new_text] = CALLBACK_NEW_CATEGORY
    else:
        callback = f"{CALLBACK_NEW_DISH_PREFIX}{category_id}" if category_id else CALLBACK_NEW_DISH_PREFIX
        buttons[add_new_text] = callback
    
    if items:
        for item in items:
            if item_type == "category":
                buttons[item["name"]] = f"{CALLBACK_CATEGORY_PREFIX}{item['category_id']}"
            else:
                buttons[item["name"]] = f"{CALLBACK_DISH_PREFIX}{item['dish_id']}"
    
    if include_back:
        back_text = BTN_BACK_TO_CATEGORIES if item_type == "dish" else BTN_BACK
        # ✅ Исправлено: возвращаем к управлению категорией, а не в главное меню
        if item_type == "dish" and category_id:
            buttons[back_text] = f"{CALLBACK_CATEGORY_PREFIX}{category_id}"
        else:
            buttons[back_text] = CALLBACK_BACK_TO_MENU
    
    sizes = calculate_button_sizes(buttons)
    
    return buttons, sizes


def create_category_management_buttons(
    category_id: int,
    category_name: str
) -> Tuple[Dict[str, str], List[int]]:
    """
    Создаёт кнопки для управления категорией.
    """
    buttons = {
        BTN_VIEW_DISHES: f"{CALLBACK_CATEGORY_VIEW_DISHES}{category_id}",
        BTN_EDIT_CATEGORY: f"{CALLBACK_EDIT_CATEGORY_PREFIX}{category_id}",
        BTN_DELETE_CATEGORY: f"{CALLBACK_DELETE_CATEGORY_PREFIX}{category_id}",
        BTN_BACK: CALLBACK_BACK_TO_MENU
    }
    
    return buttons, [1, 1, 1, 1]


def create_dish_detail_buttons(
    dish_id: int,
    category_id: int
) -> Tuple[Dict[str, str], List[int]]:
    """
    Кнопки для карточки блюда: редактировать, удалить, вернуться.
    """
    buttons = {
        BTN_EDIT: f"{CALLBACK_EDIT_DISH_PREFIX}{dish_id}",
        BTN_DELETE: f"{CALLBACK_DELETE_DISH_PREFIX}{dish_id}",
        BTN_BACK_TO_DISHES: f"{CALLBACK_CATEGORY_VIEW_DISHES}{category_id}"  # ✅ уже правильно
    }
    
    return buttons, [2, 1]


# =============================================================================
# MAIN MENU HANDLERS
# =============================================================================

@MenuRouter.callback_query(F.data == "my_menu")
@MenuRouter.callback_query(F.data == CALLBACK_BACK_TO_MENU)
async def show_main_menu(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Главное меню управления меню — как открыть поваренную книгу.
    """
    await state.clear()
    await state.set_state(user_states.AdminPanel.my_menu)

    categories = await get_categories_orm(session=session)
    ic("Categories fetched:", categories)
    
    buttons, sizes = create_navigation_buttons(
        items=categories,
        item_type="category",
        include_back=False
    )

    buttons[BTN_ADMIN_PANEL] = CALLBACK_BACK_TO_PANEL
    sizes.append(1)
    
    if not categories:
        text = EMPTY_CATEGORIES_TEXT
    else:
        text = f"{WELCOME_TEXT}\n\n{CATEGORY_SELECT_TEXT}"
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=sizes
    )


# =============================================================================
# CATEGORY MANAGEMENT HANDLERS
# =============================================================================

@MenuRouter.callback_query(F.data.startswith(CALLBACK_CATEGORY_PREFIX))
async def show_category_management(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Показывает меню управления категорией.
    """
    category_id, error = parse_callback(call, expected_prefix=CALLBACK_CATEGORY_PREFIX)
    
    if error:
        await call.answer(error, show_alert=True)
        ic(f"Parse error in show_category_management: {error}, data: {call.data}")
        return
    
    await state.set_state(user_states.AdminPanel.category)
    await state.update_data(current_category_id=category_id)
    
    categories = await get_categories_orm(session=session)
    category_name = get_category_name_by_id(categories, category_id)
    
    text = CATEGORY_MANAGEMENT_TEXT.format(name=category_name)
    buttons, sizes = create_category_management_buttons(category_id, category_name)
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=sizes
    )


@MenuRouter.callback_query(F.data.startswith(CALLBACK_CATEGORY_VIEW_DISHES))
async def show_category_dishes(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Показывает все блюда в выбранной категории.
    """
    category_id, error = parse_callback(call, expected_prefix=CALLBACK_CATEGORY_VIEW_DISHES)
    
    if error:
        await call.answer(error, show_alert=True)
        ic(f"Parse error in show_category_dishes: {error}, data: {call.data}")
        return
    
    await state.set_state(user_states.AdminPanel.category)
    await state.update_data(current_category_id=category_id)

    dish_list = await get_dish_by_category_orm(session=session, category_id=category_id)
    ic(f"Dishes in category {category_id}:", dish_list)

    buttons, sizes = create_navigation_buttons(
        items=dish_list,
        item_type="dish",
        category_id=category_id,
        include_back=True
    )
    
    if not dish_list:
        text = EMPTY_DISHES_TEXT
    else:
        text = f"{WELCOME_TEXT}\n\n{DISH_SELECT_TEXT}"
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=sizes
    )


@MenuRouter.callback_query(F.data.startswith(CALLBACK_EDIT_CATEGORY_PREFIX))
async def edit_category_start(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Начало редактирования названия категории.
    """
    category_id, error = parse_callback(call, expected_prefix=CALLBACK_EDIT_CATEGORY_PREFIX)
    
    if error:
        await call.answer(error, show_alert=True)
        ic(f"Parse error in edit_category_start: {error}, data: {call.data}")
        return
    
    categories = await get_categories_orm(session=session)
    category_name = get_category_name_by_id(categories, category_id)
    
    await state.set_state(user_states.AdminPanel.edit_category_name_fsm)
    await state.update_data(edit_category_id=category_id)
    
    text = CATEGORY_EDIT_PROMPT.format(name=category_name)
    
    await send_clean_message(
        target=call,
        text=text,
        buttons={BTN_CANCEL: CALLBACK_BACK_TO_MENU}
    )


@MenuRouter.message(F.text, StateFilter(user_states.AdminPanel.edit_category_name_fsm))
async def edit_category_save(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """
    Сохранение нового названия категории.
    """
    if message.text.strip() == BTN_CANCEL:
        await send_clean_message(
            target=message,
            text="❌ Редактирование категории отменено",
            buttons={BTN_BACK: CALLBACK_BACK_TO_MENU}
        )
        await state.clear()
        return
    
    data = await state.get_data()
    category_id = data.get('edit_category_id')
    new_name = message.text.strip()
    
    if not new_name:
        await send_clean_message(
            target=message,
            text="❌ Название не может быть пустым. Попробуйте ещё раз:",
            buttons={BTN_CANCEL: CALLBACK_BACK_TO_MENU}
        )
        return
    
    success = await update_category_orm(session, category_id, new_name)
    
    if success:
        await send_clean_message(
            target=message,
            text=CATEGORY_UPDATED.format(name=new_name),
            buttons={BTN_BACK: CALLBACK_BACK_TO_MENU}
        )
    else:
        await send_clean_message(
            target=message,
            text=ERROR_GENERIC,
            buttons={BTN_BACK: CALLBACK_BACK_TO_MENU}
        )
    
    await state.clear()


@MenuRouter.callback_query(F.data.startswith(CALLBACK_DELETE_CATEGORY_PREFIX))
async def delete_category_confirm(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Подтверждение удаления категории.
    """
    category_id, error = parse_callback(call, expected_prefix=CALLBACK_DELETE_CATEGORY_PREFIX)
    
    if error:
        await call.answer(error, show_alert=True)
        ic(f"Parse error in delete_category_confirm: {error}, data: {call.data}")
        return
    
    categories = await get_categories_orm(session=session)
    category_name = get_category_name_by_id(categories, category_id)
    
    text = CATEGORY_DELETE_CONFIRM.format(name=category_name)
    
    await send_clean_message(
        target=call,
        text=text,
        buttons={
            "✅ Да, удалить": f"{CALLBACK_CONFIRM_DELETE_CATEGORY_PREFIX}{category_id}",
            "❌ Нет, отмена": CALLBACK_BACK_TO_MENU
        },
        sizes=[1, 1]
    )


@MenuRouter.callback_query(F.data.startswith(CALLBACK_CONFIRM_DELETE_CATEGORY_PREFIX))
async def delete_category_execute(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Выполнение удаления категории.
    """
    category_id, error = parse_callback(call, expected_prefix=CALLBACK_CONFIRM_DELETE_CATEGORY_PREFIX)
    
    if error:
        await call.answer(error, show_alert=True)
        ic(f"Parse error in delete_category_execute: {error}, data: {call.data}")
        return
    
    success = await delete_category_orm(session, category_id)
    
    if success:
        await send_clean_message(
            target=call,
            text=CATEGORY_DELETED,
            buttons={BTN_BACK: CALLBACK_BACK_TO_MENU}
        )
    else:
        await send_clean_message(
            target=call,
            text=ERROR_GENERIC,
            buttons={BTN_BACK: CALLBACK_BACK_TO_MENU}
        )


# =============================================================================
# DISH DETAIL HANDLER
# =============================================================================

@MenuRouter.callback_query(F.data.startswith(CALLBACK_DISH_PREFIX))
async def show_dish_detail(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Карточка блюда для шефа — здесь можно отредактировать или удалить.
    """
    dish_id, error = parse_callback(call, expected_prefix=CALLBACK_DISH_PREFIX)
    
    if error:
        await call.answer(error, show_alert=True)
        ic(f"Parse error in show_dish_detail: {error}, data: {call.data}")
        return
    
    dish = await get_dish_by_id_orm(session=session, dish_id=dish_id)
    
    if not dish:
        await send_clean_message(
            target=call,
            text=ERROR_DISH_NOT_FOUND,
            buttons={BTN_BACK_TO_CATEGORIES: CALLBACK_BACK_TO_MENU}
        )
        return
    
    categories = await get_categories_orm(session=session)
    category_name = get_category_name_by_id(categories, dish['category_id'])
    
    text = format_dish_detail(dish, category_name)
    buttons, sizes = create_dish_detail_buttons(
        dish_id=dish_id,
        category_id=dish['category_id']
    )
    
    if dish.get('image'):
        await send_clean_message(
            target=call,
            text=text,
            buttons=buttons,
            sizes=sizes,
            photo=dish['image']
        )
    else:
        await send_clean_message(
            target=call,
            text=text,
            buttons=buttons,
            sizes=sizes
        )


# =============================================================================
# CATEGORY CREATION FLOW
# =============================================================================

@MenuRouter.callback_query(F.data == CALLBACK_NEW_CATEGORY)
async def request_category_name(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Шаг 1: запрос названия новой категории."""
    await state.set_state(user_states.AdminPanel.new_category_name_fsm)
    
    await send_clean_message(
        target=call,
        text=PROMPT_CATEGORY_NAME,
        buttons={BTN_BACK: CALLBACK_BACK_TO_MENU}
    )


@MenuRouter.message(F.text, StateFilter(user_states.AdminPanel.new_category_name_fsm))
async def save_new_category(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Шаг 2: сохранение новой категории."""
    if message.text.strip() == BTN_CANCEL:
        await send_clean_message(
            target=message,
            text="❌ Создание категории отменено",
            buttons={BTN_BACK: CALLBACK_BACK_TO_MENU}
        )
        await state.clear()
        return

    category_name = message.text.strip()
    category_data = {"category_name": category_name}
    
    # ✅ Получаем созданный объект с ID
    new_category = await add_category_orm(session=session, data=category_data)
    
    if not new_category:
        await send_clean_message(
            target=message,
            text="❌ Ошибка при создании категории",
            buttons={BTN_BACK: CALLBACK_BACK_TO_MENU}
        )
        await state.clear()
        return
    
    await send_clean_message(
        target=message,
        text=f"{CATEGORY_ADDED}\n\n<b>Название:</b> {category_name}",
        buttons={
            BTN_ADD_DISH: f"{CALLBACK_NEW_DISH_PREFIX}{new_category.category_id}",  # ← Используем ID из объекта
            BTN_BACK_TO_CATEGORIES: CALLBACK_BACK_TO_MENU
        },
        sizes=[1, 1]
    )
    
    await state.clear()


# =============================================================================
# DISH CREATION FLOW
# =============================================================================

@MenuRouter.callback_query(F.data.startswith(CALLBACK_NEW_DISH_PREFIX))
async def request_dish_name(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Шаг 1: запрос названия блюда."""
    category_id, error = parse_callback(call, expected_prefix=CALLBACK_NEW_DISH_PREFIX)
    
    if error:
        await call.answer(error, show_alert=True)
        ic(f"Parse error in request_dish_name: {error}, data: {call.data}")
        return
    
    await state.set_state(user_states.AdminPanel.new_dish_name_fsm)
    await state.update_data(category_id=category_id)

    await send_clean_message(
        target=call,
        text=PROMPT_DISH_NAME,
        buttons={BTN_BACK: f"{CALLBACK_CATEGORY_VIEW_DISHES}{category_id}"}
    )


@MenuRouter.message(F.text, StateFilter(user_states.AdminPanel.new_dish_name_fsm))
async def request_dish_description(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Шаг 2: запрос описания блюда."""
    if message.text.strip() == BTN_CANCEL:
        data = await state.get_data()
        category_id = data.get('category_id')
        await send_clean_message(
            target=message,
            text="❌ Создание блюда отменено",
            buttons={BTN_BACK: f"{CALLBACK_CATEGORY_VIEW_DISHES}{category_id}" if category_id else CALLBACK_BACK_TO_MENU}
        )
        await state.clear()
        return
    
    await state.set_state(user_states.AdminPanel.new_dish_description_fsm)
    
    dish_name = message.text.strip()
    await state.update_data(name=dish_name)

    await send_clean_message(
        target=message,
        text=PROMPT_DISH_DESCRIPTION,
        buttons={BTN_BACK: CALLBACK_BACK_TO_MENU}
    )


@MenuRouter.message(F.text, StateFilter(user_states.AdminPanel.new_dish_description_fsm))
async def request_dish_price(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Шаг 3: запрос цены блюда."""
    if message.text.strip() == BTN_CANCEL:
        await send_clean_message(
            target=message,
            text="❌ Создание блюда отменено",
            buttons={BTN_BACK: CALLBACK_BACK_TO_MENU}
        )
        await state.clear()
        return
    
    await state.set_state(user_states.AdminPanel.new_dish_price_fsm)

    description = None if message.text.strip() == "-" else message.text.strip()
    
    await state.update_data(
        description=description,
        entities=message.entities if description else None
    )

    await send_clean_message(
        target=message,
        text=PROMPT_DISH_PRICE,
        buttons={BTN_BACK: CALLBACK_BACK_TO_MENU}
    )


@MenuRouter.message(F.text, StateFilter(user_states.AdminPanel.new_dish_price_fsm))
async def request_dish_image(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Шаг 4: запрос фото блюда."""
    if message.text.strip() == BTN_CANCEL:
        await send_clean_message(
            target=message,
            text="❌ Создание блюда отменено",
            buttons={BTN_BACK: CALLBACK_BACK_TO_MENU}
        )
        await state.clear()
        return
    
    await state.set_state(user_states.AdminPanel.new_dish_image_fsm)

    try:
        price = int(message.text.strip())
        if price <= 0:
            raise ValueError("Price must be positive")
        await state.update_data(price=price)
    except ValueError:
        await send_clean_message(
            target=message,
            text=ERROR_INVALID_PRICE,
            buttons={BTN_BACK: CALLBACK_BACK_TO_MENU}
        )
        return

    await send_clean_message(
        target=message,
        text=PROMPT_DISH_IMAGE,
        buttons={BTN_BACK: CALLBACK_BACK_TO_MENU}
    )


@MenuRouter.message(F.photo, StateFilter(user_states.AdminPanel.new_dish_image_fsm))
@MenuRouter.message(F.text == "-", StateFilter(user_states.AdminPanel.new_dish_image_fsm))
async def save_new_dish(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Шаг 5: сохранение блюда."""
    if message.text and message.text.strip() == BTN_CANCEL:
        await send_clean_message(
            target=message,
            text="❌ Создание блюда отменено",
            buttons={BTN_BACK: CALLBACK_BACK_TO_MENU}
        )
        await state.clear()
        return
    
    await state.set_state(user_states.AdminPanel.save_dish_fsm)

    dish_data = await state.get_data()
    
    has_photo = bool(message.photo)
    if has_photo:
        dish_data["image"] = message.photo[-1].file_id
        photo_status = "✅ Будет добавлено"
    else:
        dish_data["image"] = None
        photo_status = "❌ Без фото"

    confirm_text = PROMPT_DISH_CONFIRM.format(
        name=dish_data['name'],
        description=dish_data.get('description', 'Нет описания'),
        price=dish_data['price'],
        photo_status=photo_status
    )
    
    await state.update_data(
        final_dish_data=dish_data,
        has_photo=has_photo
    )
    
    await send_clean_message(
        target=message,
        text=confirm_text,
        buttons={
            "✅ Да, сохранить": "confirm_save_dish",
            "🔄 Заполнить заново": f"{CALLBACK_NEW_DISH_PREFIX}{dish_data['category_id']}",
            BTN_CANCEL: f"{CALLBACK_CATEGORY_VIEW_DISHES}{dish_data['category_id']}"
        },
        sizes=[1, 1, 1]
    )


@MenuRouter.callback_query(F.data == "confirm_save_dish", StateFilter(user_states.AdminPanel.save_dish_fsm))
async def confirm_save_dish(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Финальное подтверждение и сохранение блюда."""
    data = await state.get_data()
    dish_data = data.get('final_dish_data')
    
    if not dish_data:
        await send_clean_message(
            target=call,
            text=ERROR_GENERIC,
            buttons={BTN_BACK_TO_CATEGORIES: CALLBACK_BACK_TO_MENU}
        )
        return
    
    result = await add_dish_orm(session=session, data=dish_data)
    
    if result:
        await send_clean_message(
            target=call,
            text=DISH_ADDED,
            buttons={
                BTN_ADD_MORE: f"{CALLBACK_NEW_DISH_PREFIX}{dish_data['category_id']}",
                BTN_VIEW_DISHES: f"{CALLBACK_CATEGORY_VIEW_DISHES}{dish_data['category_id']}"
            },
            sizes=[1, 1]
        )
    else:
        await send_clean_message(
            target=call,
            text=ERROR_GENERIC,
            buttons={BTN_BACK: f"{CALLBACK_CATEGORY_VIEW_DISHES}{dish_data['category_id']}"}
        )
    
    await state.clear()


# =============================================================================
# DISH EDIT FLOW
# =============================================================================

@MenuRouter.callback_query(F.data.startswith(CALLBACK_EDIT_DISH_PREFIX))
async def edit_dish_start(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Начало редактирования блюда — выбор поля для изменения."""
    dish_id, error = parse_callback(call, expected_prefix=CALLBACK_EDIT_DISH_PREFIX)
    
    if error:
        await call.answer(error, show_alert=True)
        ic(f"Parse error in edit_dish_start: {error}, data: {call.data}")
        return
    
    dish = await get_dish_by_id_orm(session=session, dish_id=dish_id)
    
    if not dish:
        await send_clean_message(
            target=call,
            text=ERROR_DISH_NOT_FOUND,
            buttons={BTN_BACK: f"{CALLBACK_CATEGORY_VIEW_DISHES}{dish['category_id']}"}
        )
        return
    
    await state.update_data(
        edit_dish_id=dish_id,
        current_name=dish['name'],
        current_description=dish.get('description', ''),
        current_price=dish['price'],
        current_category_id=dish['category_id'],
        current_image=dish.get('image')
    )
    
    text = EDIT_DISH_OPTIONS.format(name=dish['name'])
    
    categories = await get_categories_orm(session=session)
    category_name = get_category_name_by_id(categories, dish['category_id'])
    text += f"\n\n📁 <b>Текущая категория:</b> {category_name}"
    
    buttons = {
        "📝 Название": f"edit_name_{dish_id}",
        "📄 Описание": f"edit_desc_{dish_id}",
        "💰 Цену": f"edit_price_{dish_id}",
        "🖼 Фото": f"edit_image_{dish_id}",
        "📁 Категорию": f"edit_cat_{dish_id}",
        BTN_BACK: f"{CALLBACK_DISH_PREFIX}{dish_id}"
    }
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=[2, 2, 1, 1]
    )


# =============================================================================
# EDIT NAME
# =============================================================================

@MenuRouter.callback_query(F.data.startswith("edit_name_"))
async def edit_name_start(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Начало редактирования названия."""
    dish_id, error = parse_callback(call, expected_prefix="edit_name_")
    
    if error:
        await call.answer(error, show_alert=True)
        ic(f"Parse error in edit_name_start: {error}, data: {call.data}")
        return
    
    data = await state.get_data()
    current_name = data.get('current_name', '')
    
    await state.set_state(user_states.AdminPanel.edit_dish_name)
    await state.update_data(editing_field='name', edit_dish_id=dish_id)
    
    await send_clean_message(
        target=call,
        text=EDIT_NAME_PROMPT.format(name=current_name),
        buttons={BTN_CANCEL: f"{CALLBACK_EDIT_DISH_PREFIX}{dish_id}"}
    )


@MenuRouter.message(F.text, StateFilter(user_states.AdminPanel.edit_dish_name))
async def edit_name_save(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Сохранение нового названия."""
    if message.text.strip() == BTN_CANCEL:
        data = await state.get_data()
        dish_id = data.get('edit_dish_id')
        await send_clean_message(
            target=message,
            text="❌ Редактирование отменено",
            buttons={BTN_BACK: f"{CALLBACK_EDIT_DISH_PREFIX}{dish_id}"}
        )
        await state.set_state(user_states.AdminPanel.admin_panel)
        return
    
    data = await state.get_data()
    dish_id = data.get('edit_dish_id')
    new_name = message.text.strip()
    
    if not new_name:
        await send_clean_message(
            target=message,
            text="❌ Название не может быть пустым. Попробуйте ещё раз:",
            buttons={BTN_CANCEL: f"{CALLBACK_EDIT_DISH_PREFIX}{dish_id}"}
        )
        return
    
    success = await update_dish_orm(session=session, dish_id=dish_id, update_data={'name': new_name})
    
    if success:
        await state.update_data(current_name=new_name)
        await send_clean_message(
            target=message,
            text="✅ Название успешно обновлено!",
            buttons={BTN_BACK: f"{CALLBACK_EDIT_DISH_PREFIX}{dish_id}"}
        )
        await state.set_state(user_states.AdminPanel.admin_panel)
    else:
        await send_clean_message(
            target=message,
            text=ERROR_GENERIC,
            buttons={BTN_BACK: f"{CALLBACK_EDIT_DISH_PREFIX}{dish_id}"}
        )


# =============================================================================
# EDIT DESCRIPTION
# =============================================================================

@MenuRouter.callback_query(F.data.startswith("edit_desc_"))
async def edit_description_start(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Начало редактирования описания."""
    dish_id, error = parse_callback(call, expected_prefix="edit_desc_")
    
    if error:
        await call.answer(error, show_alert=True)
        ic(f"Parse error in edit_description_start: {error}, data: {call.data}")
        return
    
    data = await state.get_data()
    current_description = data.get('current_description', '')
    
    await state.set_state(user_states.AdminPanel.edit_dish_description)
    await state.update_data(editing_field='description', edit_dish_id=dish_id)
    
    await send_clean_message(
        target=call,
        text=EDIT_DESCRIPTION_PROMPT.format(
            description=current_description if current_description else 'Нет описания'
        ),
        buttons={BTN_CANCEL: f"{CALLBACK_EDIT_DISH_PREFIX}{dish_id}"}
    )


@MenuRouter.message(F.text, StateFilter(user_states.AdminPanel.edit_dish_description))
async def edit_description_save(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Сохранение нового описания."""
    if message.text.strip() == BTN_CANCEL:
        data = await state.get_data()
        dish_id = data.get('edit_dish_id')
        await send_clean_message(
            target=message,
            text="❌ Редактирование отменено",
            buttons={BTN_BACK: f"{CALLBACK_EDIT_DISH_PREFIX}{dish_id}"}
        )
        await state.set_state(user_states.AdminPanel.admin_panel)
        return
    
    data = await state.get_data()
    dish_id = data.get('edit_dish_id')
    new_description = None if message.text.strip() == "-" else message.text.strip()
    
    update_data = {
        'description': new_description,
        'entities': message.entities if new_description else None
    }
    
    success = await update_dish_orm(session=session, dish_id=dish_id, update_data=update_data)
    
    if success:
        await state.update_data(current_description=new_description)
        status = "обновлено" if new_description else "удалено"
        await send_clean_message(
            target=message,
            text=f"✅ Описание успешно {status}!",
            buttons={BTN_BACK: f"{CALLBACK_EDIT_DISH_PREFIX}{dish_id}"}
        )
        await state.set_state(user_states.AdminPanel.admin_panel)
    else:
        await send_clean_message(
            target=message,
            text=ERROR_GENERIC,
            buttons={BTN_BACK: f"{CALLBACK_EDIT_DISH_PREFIX}{dish_id}"}
        )


# =============================================================================
# EDIT PRICE
# =============================================================================

@MenuRouter.callback_query(F.data.startswith("edit_price_"))
async def edit_price_start(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Начало редактирования цены."""
    dish_id, error = parse_callback(call, expected_prefix="edit_price_")
    
    if error:
        await call.answer(error, show_alert=True)
        ic(f"Parse error in edit_price_start: {error}, data: {call.data}")
        return
    
    data = await state.get_data()
    current_price = data.get('current_price', 0)
    
    await state.set_state(user_states.AdminPanel.edit_dish_price)
    await state.update_data(editing_field='price', edit_dish_id=dish_id)
    
    await send_clean_message(
        target=call,
        text=EDIT_PRICE_PROMPT.format(price=current_price),
        buttons={BTN_CANCEL: f"{CALLBACK_EDIT_DISH_PREFIX}{dish_id}"}
    )


@MenuRouter.message(F.text, StateFilter(user_states.AdminPanel.edit_dish_price))
async def edit_price_save(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Сохранение новой цены."""
    if message.text.strip() == BTN_CANCEL:
        data = await state.get_data()
        dish_id = data.get('edit_dish_id')
        await send_clean_message(
            target=message,
            text="❌ Редактирование отменено",
            buttons={BTN_BACK: f"{CALLBACK_EDIT_DISH_PREFIX}{dish_id}"}
        )
        await state.set_state(user_states.AdminPanel.admin_panel)
        return
    
    data = await state.get_data()
    dish_id = data.get('edit_dish_id')
    
    try:
        new_price = int(message.text.strip())
        if new_price <= 0:
            raise ValueError("Price must be positive")
    except ValueError:
        await send_clean_message(
            target=message,
            text=ERROR_INVALID_PRICE,
            buttons={BTN_CANCEL: f"{CALLBACK_EDIT_DISH_PREFIX}{dish_id}"}
        )
        return
    
    success = await update_dish_orm(session=session, dish_id=dish_id, update_data={'price': new_price})
    
    if success:
        await state.update_data(current_price=new_price)
        await send_clean_message(
            target=message,
            text=f"✅ Цена обновлена! Новая цена: {new_price} ₽",
            buttons={BTN_BACK: f"{CALLBACK_EDIT_DISH_PREFIX}{dish_id}"}
        )
        await state.set_state(user_states.AdminPanel.admin_panel)
    else:
        await send_clean_message(
            target=message,
            text=ERROR_GENERIC,
            buttons={BTN_BACK: f"{CALLBACK_EDIT_DISH_PREFIX}{dish_id}"}
        )


# =============================================================================
# EDIT IMAGE
# =============================================================================

@MenuRouter.callback_query(F.data.startswith("edit_image_"))
async def edit_image_start(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Начало редактирования фото."""
    dish_id, error = parse_callback(call, expected_prefix="edit_image_")
    
    if error:
        await call.answer(error, show_alert=True)
        ic(f"Parse error in edit_image_start: {error}, data: {call.data}")
        return
    
    data = await state.get_data()
    has_current_image = data.get('current_image') is not None
    
    await state.set_state(user_states.AdminPanel.edit_dish_image)
    await state.update_data(editing_field='image', edit_dish_id=dish_id)
    
    photo_status = "✅ Есть фото" if has_current_image else "❌ Нет фото"
    
    await send_clean_message(
        target=call,
        text=EDIT_IMAGE_PROMPT.format(photo_status=photo_status),
        buttons={
            "🗑 Удалить фото": f"delete_image_{dish_id}",
            BTN_CANCEL: f"{CALLBACK_EDIT_DISH_PREFIX}{dish_id}"
        },
        sizes=[1, 1]
    )


@MenuRouter.message(F.photo, StateFilter(user_states.AdminPanel.edit_dish_image))
async def edit_image_save(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Сохранение нового фото."""
    data = await state.get_data()
    dish_id = data.get('edit_dish_id')
    
    new_image = message.photo[-1].file_id
    success = await update_dish_orm(session=session, dish_id=dish_id, update_data={'image': new_image})
    
    if success:
        await state.update_data(current_image=new_image)
        await send_clean_message(
            target=message,
            text="✅ Фото успешно обновлено!",
            buttons={BTN_BACK: f"{CALLBACK_EDIT_DISH_PREFIX}{dish_id}"}
        )
        await state.set_state(user_states.AdminPanel.admin_panel)
    else:
        await send_clean_message(
            target=message,
            text=ERROR_GENERIC,
            buttons={BTN_BACK: f"{CALLBACK_EDIT_DISH_PREFIX}{dish_id}"}
        )


@MenuRouter.callback_query(F.data.startswith("delete_image_"))
async def delete_image(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Удаление фото."""
    dish_id, error = parse_callback(call, expected_prefix="delete_image_")
    
    if error:
        await call.answer(error, show_alert=True)
        ic(f"Parse error in delete_image: {error}, data: {call.data}")
        return
    
    success = await update_dish_orm(session=session, dish_id=dish_id, update_data={'image': None})
    
    if success:
        await state.update_data(current_image=None)
        await send_clean_message(
            target=call,
            text="✅ Фото успешно удалено!",
            buttons={BTN_BACK: f"{CALLBACK_EDIT_DISH_PREFIX}{dish_id}"}
        )
    else:
        await send_clean_message(
            target=call,
            text=ERROR_GENERIC,
            buttons={BTN_BACK: f"{CALLBACK_EDIT_DISH_PREFIX}{dish_id}"}
        )


# =============================================================================
# EDIT CATEGORY
# =============================================================================

@MenuRouter.callback_query(F.data.startswith("edit_cat_"))
async def edit_category_start(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Начало редактирования категории — выбор новой категории."""
    dish_id, error = parse_callback(call, expected_prefix="edit_cat_")
    
    if error:
        await call.answer(error, show_alert=True)
        ic(f"Parse error in edit_category_start: {error}, data: {call.data}")
        return
    
    categories = await get_categories_orm(session=session)
    
    if not categories:
        await send_clean_message(
            target=call,
            text="❌ Нет доступных категорий для перемещения.",
            buttons={BTN_BACK: f"{CALLBACK_EDIT_DISH_PREFIX}{dish_id}"}
        )
        return
    
    await state.set_state(user_states.AdminPanel.edit_dish_category)
    await state.update_data(editing_field='category', edit_dish_id=dish_id)
    
    buttons = {}
    for cat in categories:
        buttons[cat['name']] = f"move_to_cat_{dish_id}_{cat['category_id']}"
    
    buttons[BTN_CANCEL] = f"{CALLBACK_EDIT_DISH_PREFIX}{dish_id}"
    
    cat_count = len(categories)
    sizes = [2] * (cat_count // 2)
    if cat_count % 2 == 1:
        sizes.append(1)
    sizes.append(1)
    
    await send_clean_message(
        target=call,
        text="📁 <b>Выберите новую категорию для блюда:</b>",
        buttons=buttons,
        sizes=tuple(sizes)
    )


@MenuRouter.callback_query(F.data.startswith("move_to_cat_"))
async def edit_category_save(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Сохранение новой категории для блюда."""
    ids, error = parse_callback(call, expected_prefix="move_to_cat_", expected_count=2)
    
    if error:
        await call.answer(error, show_alert=True)
        ic(f"Parse error in edit_category_save: {error}, data: {call.data}")
        return
    
    dish_id, new_category_id = ids[0], ids[1]
    
    success = await update_dish_orm(session=session, dish_id=dish_id, update_data={'category_id': new_category_id})
    
    if success:
        await state.update_data(current_category_id=new_category_id)
        
        categories = await get_categories_orm(session=session)
        category_name = get_category_name_by_id(categories, new_category_id)
        
        await send_clean_message(
            target=call,
            text=f"✅ Блюдо перемещено в категорию: <b>{category_name}</b>",
            buttons={BTN_BACK: f"{CALLBACK_DISH_PREFIX}{dish_id}"}
        )
    else:
        await send_clean_message(
            target=call,
            text=ERROR_GENERIC,
            buttons={BTN_BACK: f"{CALLBACK_EDIT_DISH_PREFIX}{dish_id}"}
        )
    
    await state.set_state(user_states.AdminPanel.admin_panel)


# =============================================================================
# DISH DELETE FLOW
# =============================================================================

@MenuRouter.callback_query(F.data.startswith(CALLBACK_DELETE_DISH_PREFIX))
async def delete_dish_confirm(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Подтверждение удаления блюда."""
    dish_id, error = parse_callback(call, expected_prefix=CALLBACK_DELETE_DISH_PREFIX)
    
    if error:
        await call.answer(error, show_alert=True)
        ic(f"Parse error in delete_dish_confirm: {error}, data: {call.data}")
        return
    
    dish = await get_dish_by_id_orm(session=session, dish_id=dish_id)
    
    if not dish:
        await send_clean_message(
            target=call,
            text=ERROR_DISH_NOT_FOUND,
            buttons={BTN_BACK: CALLBACK_BACK_TO_MENU}
        )
        return
    
    await send_clean_message(
        target=call,
        text=CONFIRM_DELETE.format(name=dish['name']),
        buttons={
            BTN_CONFIRM: f"{CALLBACK_CONFIRM_DELETE_PREFIX}{dish_id}",
            BTN_CANCEL: f"{CALLBACK_DISH_PREFIX}{dish_id}"
        },
        sizes=[1, 1]
    )


@MenuRouter.callback_query(F.data.startswith(CALLBACK_CONFIRM_DELETE_PREFIX))
async def delete_dish_execute(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Выполнение удаления блюда."""
    dish_id, error = parse_callback(call, expected_prefix=CALLBACK_CONFIRM_DELETE_PREFIX)
    
    if error:
        await call.answer(error, show_alert=True)
        ic(f"Parse error in delete_dish_execute: {error}, data: {call.data}")
        return
    
    dish = await get_dish_by_id_orm(session=session, dish_id=dish_id)
    category_id = dish['category_id'] if dish else None
    
    success = await delete_dish_orm(session=session, dish_id=dish_id)
    
    if success:
        await send_clean_message(
            target=call,
            text=DISH_DELETED,
            buttons={BTN_BACK_TO_DISHES: f"{CALLBACK_CATEGORY_VIEW_DISHES}{category_id}" if category_id else CALLBACK_BACK_TO_MENU}
        )
    else:
        await send_clean_message(
            target=call,
            text=ERROR_GENERIC,
            buttons={BTN_BACK: f"{CALLBACK_CATEGORY_VIEW_DISHES}{category_id}" if category_id else CALLBACK_BACK_TO_MENU}
        )


# =============================================================================
# ERROR HANDLERS
# =============================================================================

@MenuRouter.message(StateFilter(user_states.AdminPanel.new_dish_price_fsm))
async def invalid_price_input(message: Message, state: FSMContext) -> None:
    """Обработка неверного ввода цены."""
    await send_clean_message(
        target=message,
        text=ERROR_INVALID_PRICE,
        buttons={BTN_BACK: CALLBACK_BACK_TO_MENU}
    )


@MenuRouter.message(StateFilter(user_states.AdminPanel.new_dish_image_fsm))
async def invalid_image_input(message: Message, state: FSMContext) -> None:
    """Обработка неверного ввода фото."""
    if message.text and message.text.strip() != "-":
        await send_clean_message(
            target=message,
            text="❌ Пожалуйста, отправьте фотографию блюда или '-' чтобы пропустить:",
            buttons={BTN_BACK: CALLBACK_BACK_TO_MENU}
        )