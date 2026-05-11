"""
User Menu Module
================

This module handles the user menu functionality for regular customers,
including viewing categories and dishes.

NO ADMIN FUNCTIONS HERE - PURE USER EXPERIENCE ONLY!
"""


from typing import Dict, List, Any, Tuple

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from icecream import ic
from sqlalchemy.ext.asyncio import AsyncSession

# =============================================================================
# DATABASE IMPORTS - ONLY READ-ONLY FUNCTIONS!
# =============================================================================
from database.orm_query.category_orm import get_categories_orm
from database.orm_query.dish_orm import (
    get_dish_by_category_orm,
    get_dish_by_id_orm
)

# =============================================================================
# PROJECT IMPORTS
# =============================================================================
from States import user_states
from tools import send_clean_message


# =============================================================================
# ROUTER INITIALIZATION
# =============================================================================

UserMenuRouter = Router(name="user_menu")


# =============================================================================
# CONSTANTS
# =============================================================================

# -----------------------------------------------------------------------------
# Message texts — в стиле «Берегини Дома»
# -----------------------------------------------------------------------------

WELCOME_TEXT = """
🤍 <b>Добро пожаловать в «Берегиню Дома»</b>

Здесь пахнет свежим хлебом, ванилью и заботой.
Мы готовим для вас с теплом, как для своих 🤍
"""

MENU_TEXT = """
📋 <b>Наше меню</b>

Листайте как старую поваренную книгу — выбирайте, что сегодня к чаю:
"""

EMPTY_CATEGORIES_TEXT = """
📭 <b>Меню наполняется</b>

Мы только начинаем — совсем скоро здесь появятся новые домашние рецепты.
Загляните позже! 🤍
"""

EMPTY_DISHES_TEXT = """
📭 <b>В этой категории пока пусто</b>

Но мы уже готовим для вас что-то вкусное.
Скоро здесь появятся новые рецепты ✨
"""

CATEGORY_SELECT_TEXT = """
📋 <b>Что сегодня приготовим?</b>

Выберите раздел, чтобы посмотреть наши блюда:
"""

DISH_SELECT_TEXT = """
🍽 <b>Что у нас в категории:</b> <i>{category_name}</i>

Нажмите на блюдо, чтобы посмотреть и добавить в корзину:
"""

# -----------------------------------------------------------------------------
# Dish detail texts
# -----------------------------------------------------------------------------

DISH_DETAIL_TEMPLATE = """
🍞 <b>{name}</b>

<i>{description}</i>

━━━━━━━━━━━━━━━━━━━━━
💰 <b>Цена:</b> {price} ₽
━━━━━━━━━━━━━━━━━━━━━

<i>Добавляем в корзину? 🤍</i>
"""

DISH_NO_DESCRIPTION = "<i>Это блюдо — наш секрет! Попробуйте — не пожалеете ✨</i>"

# -----------------------------------------------------------------------------
# Button labels — понятные и тёплые
# -----------------------------------------------------------------------------
BTN_BACK = "🔙 Назад"
BTN_BACK_TO_CATEGORIES = "📋 К категориям"
BTN_CART = "🛒 Корзина"
BTN_ORDERS = "📋 Мои заказы"
BTN_MAIN_MENU = "🏠 Главная"
BTN_ADD_TO_CART = "🛒 Добавить в корзину"

# -----------------------------------------------------------------------------
# Callback constants
# -----------------------------------------------------------------------------
CALLBACK_MAIN_MENU = "main_menu"
CALLBACK_BACK_TO_MENU = "back_to_user_menu"
CALLBACK_CATEGORY_PREFIX = "user_category_"
CALLBACK_DISH_PREFIX = "user_dish_"
CALLBACK_ADD_TO_CART_PREFIX = "add_to_cart_"
CALLBACK_CART = "active_orders"
CALLBACK_ORDERS = "user_orders"

# -----------------------------------------------------------------------------
# Layout constants
# -----------------------------------------------------------------------------
LONG_TITLE_THRESHOLD = 16  # если название категории >= 16 символов -> отдельный ряд


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_category_name_by_id(categories: List[Dict[str, Any]], category_id: int) -> str:
    """Возвращает название категории по её ID."""
    for cat in categories:
        if cat['category_id'] == category_id:
            return cat['name']
    return "Домашняя категория"


def format_dish_detail(dish: Dict[str, Any]) -> str:
    """Форматирует детальное описание блюда."""
    description = dish.get('description') or DISH_NO_DESCRIPTION
    
    return DISH_DETAIL_TEMPLATE.format(
        name=dish['name'],
        description=description,
        price=dish['price']
    )


def create_categories_buttons(
    categories: List[Dict[str, Any]]
) -> Tuple[Dict[str, str], List[int]]:
    """
    Создаёт кнопки для выбора категории.
    
    Правила:
    1. Если название категории >= 16 символов -> кнопка занимает отдельный ряд (width=1)
    2. Остальные кнопки группируются в пары (по 2 в ряд)
    3. Если после группировки остаётся одна короткая кнопка -> она занимает отдельный ряд
    """
    buttons: Dict[str, str] = {}
    sizes: List[int] = []
    
    if not categories:
        # Если категорий нет, добавляем только служебные кнопки
        buttons[BTN_CART] = CALLBACK_CART
        buttons[BTN_ORDERS] = CALLBACK_ORDERS
        buttons[BTN_MAIN_MENU] = CALLBACK_MAIN_MENU
        return buttons, [2, 1]
    
    # Разделяем категории на длинные и короткие
    long_buttons: List[Tuple[str, str]] = []      # (label, callback)
    short_buttons: List[Tuple[str, str]] = []     # (label, callback)
    
    for cat in categories:
        label = cat["name"].title()
        callback = f"{CALLBACK_CATEGORY_PREFIX}{cat['category_id']}"
        
        if len(label) >= LONG_TITLE_THRESHOLD:
            long_buttons.append((label, callback))
        else:
            short_buttons.append((label, callback))
    
    # 1. Сначала добавляем длинные кнопки — каждая в отдельный ряд
    for label, callback in long_buttons:
        buttons[label] = callback
        sizes.append(1)  # одна кнопка в ряду
    
    # 2. Группируем короткие кнопки в пары
    i = 0
    while i < len(short_buttons):
        label1, callback1 = short_buttons[i]
        buttons[label1] = callback1
        
        if i + 1 < len(short_buttons):
            # Есть пара — добавляем вторую кнопку в тот же ряд
            label2, callback2 = short_buttons[i + 1]
            buttons[label2] = callback2
            sizes.append(2)  # ряд из двух кнопок
            i += 2
        else:
            # Нечётное количество коротких кнопок — последняя занимает отдельный ряд
            sizes.append(1)
            i += 1
    
    # 3. Добавляем служебные кнопки
    cart_label = BTN_CART
    orders_label = BTN_ORDERS
    
    buttons[cart_label] = CALLBACK_CART
    buttons[orders_label] = CALLBACK_ORDERS
    
    # Проверяем, нужно ли разносить их по разным рядам из-за длины
    if len(cart_label) >= LONG_TITLE_THRESHOLD or len(orders_label) >= LONG_TITLE_THRESHOLD:
        # Если одна из служебных кнопок длинная — обе в отдельные ряды
        sizes.append(1)
        sizes.append(1)
    else:
        # Обе короткие — в один ряд парой
        sizes.append(2)
    
    # 4. Главная кнопка — всегда отдельный ряд
    buttons[BTN_MAIN_MENU] = CALLBACK_MAIN_MENU
    sizes.append(1)
    
    return buttons, sizes


def create_dishes_buttons(
    dishes: List[Dict[str, Any]],
    category_id: int
) -> Tuple[Dict[str, str], List[int]]:
    """Создаёт кнопки для списка блюд в категории (все блюда короткие по определению)."""
    buttons: Dict[str, str] = {}
    sizes: List[int] = []
    
    if dishes:
        for dish in dishes:
            buttons[dish["name"]] = f"{CALLBACK_DISH_PREFIX}{dish['dish_id']}"
    
    # Группируем блюда в пары
    dish_count = len(dishes)
    for i in range(0, dish_count, 2):
        if i + 1 < dish_count:
            sizes.append(2)  # пара
        else:
            sizes.append(1)  # последнее непарное
    
    # Кнопка "Назад" — всегда отдельный ряд
    buttons[BTN_BACK] = CALLBACK_BACK_TO_MENU
    sizes.append(1)
    
    return buttons, sizes


def create_dish_detail_buttons(
    dish_id: int,
    category_id: int
) -> Tuple[Dict[str, str], List[int]]:
    """Кнопки для карточки блюда."""
    buttons = {
        BTN_ADD_TO_CART: f"{CALLBACK_ADD_TO_CART_PREFIX}{dish_id}",
        BTN_BACK: CALLBACK_BACK_TO_MENU
    }
    
    # Обе кнопки короткие, поэтому можно в один ряд
    return buttons, [2]


# =============================================================================
# HANDLERS
# =============================================================================

# -----------------------------------------------------------------------------
# NAVIGATION HANDLERS
# -----------------------------------------------------------------------------

@UserMenuRouter.callback_query(F.data == "user_catalog")
@UserMenuRouter.callback_query(F.data == CALLBACK_BACK_TO_MENU)
async def show_categories(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Главное меню — как вход на домашнюю кухню."""
    await state.clear()
    await state.set_state(user_states.UserMenu.catalog)

    categories = await get_categories_orm(session=session)
    ic("Categories fetched:", categories)
    
    buttons, sizes = create_categories_buttons(categories)
    
    if not categories:
        text = EMPTY_CATEGORIES_TEXT
    else:
        text = f"{WELCOME_TEXT}\n\n{CATEGORY_SELECT_TEXT}"
    
    ic("Button layout sizes:", sizes)
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=sizes
    )


# -----------------------------------------------------------------------------
# CATALOG HANDLERS
# -----------------------------------------------------------------------------

@UserMenuRouter.callback_query(F.data.startswith(CALLBACK_CATEGORY_PREFIX))
async def show_category_dishes(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Показывает блюда в выбранной категории."""
    await state.set_state(user_states.UserMenu.category)

    ic("Category selected:", call.data)
    category_id = int(call.data.split("_")[2])

    categories = await get_categories_orm(session=session)
    category_name = get_category_name_by_id(categories, category_id)

    dish_list = await get_dish_by_category_orm(
        session=session, 
        category_id=category_id
    )
    ic(f"Dishes in category {category_id}:", dish_list)

    buttons, sizes = create_dishes_buttons(dish_list, category_id)
    
    if not dish_list:
        text = EMPTY_DISHES_TEXT
    else:
        text = DISH_SELECT_TEXT.format(category_name=category_name)
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=sizes
    )


@UserMenuRouter.callback_query(F.data.startswith(CALLBACK_DISH_PREFIX))
async def show_dish_detail(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Детальная карточка блюда."""
    dish_id = int(call.data.split("_")[2])
    
    dish = await get_dish_by_id_orm(session=session, dish_id=dish_id)
    
    if not dish:
        await send_clean_message(
            target=call,
            text="❌ Блюдо не найдено",
            buttons={BTN_BACK_TO_CATEGORIES: CALLBACK_BACK_TO_MENU},
            sizes=[1]
        )
        return
    
    ic(f"Displaying dish for user: {dish['name']}")
    
    text = format_dish_detail(dish)
    
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


# -----------------------------------------------------------------------------
# ORDERS HANDLER
# -----------------------------------------------------------------------------

@UserMenuRouter.callback_query(F.data == CALLBACK_ORDERS)
async def show_orders(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """История заказов — как заметки на кухне."""
    await send_clean_message(
        target=call,
        text="""
📋 <b>Ваши заказы</b>

Здесь будет храниться история ваших заказов — как заметки на кухне,
чтобы не забыть, что особенно понравилось.

<i>Скоро эта страница наполнится любимыми блюдами 🤍</i>
        """,
        buttons={
            BTN_CART: CALLBACK_CART,
            BTN_MAIN_MENU: CALLBACK_MAIN_MENU
        },
        sizes=[2]
    )