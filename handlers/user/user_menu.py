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
# Message texts — в стиле домашней кухни
# -----------------------------------------------------------------------------

WELCOME_TEXT = """
🍞 <b>Добро пожаловать в нашу домашнюю пекарню!</b>

Здесь пахнет свежим хлебом, ванилью и заботой.
Мы готовим для вас с теплом, как для своих.
"""

MENU_TEXT = """
📋 <b>Наше меню</b>

Листайте как старую поваренную книгу — выбирайте то, что сегодня хочется:
"""

EMPTY_CATEGORIES_TEXT = """
📭 <b>В меню пока нет категорий</b>

Мы только начинаем наполнять нашу кухню вкусами.
Загляните позже — будет ещё больше домашних рецептов!
"""

EMPTY_DISHES_TEXT = """
📭 <b>В этой категории пока нет блюд</b>

Скоро здесь появятся новые рецепты — те самые, что передаются из поколения в поколение.
"""

CATEGORY_SELECT_TEXT = """
📋 <b>Что сегодня приготовим?</b>

Выберите раздел, чтобы увидеть наши домашние блюда:
"""

DISH_SELECT_TEXT = """
🍽 <b>Что у нас сегодня в категории:</b> <i>{category_name}</i>

Нажмите на блюдо, чтобы увидеть, как оно выглядит, и добавить в корзину:
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

<i>Хотите попробовать? Добавим в корзину!</i>
"""

DISH_NO_DESCRIPTION = "<i>Нет описания — но мы уверены, что это будет вкусно!</i>"

# -----------------------------------------------------------------------------
# Button labels
# -----------------------------------------------------------------------------
BTN_BACK = "🔙 Назад"
BTN_BACK_TO_CATEGORIES = "📋 К категориям"
BTN_CART = "🛒 Корзина"
BTN_ORDERS = "📋 Мои заказы"
BTN_MAIN_MENU = "🏠 В главную"
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
    """Форматирует детальное описание блюда — как из старой кулинарной книги."""
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
    """
    buttons: Dict[str, str] = {}
    
    if categories:
        for cat in categories:
            buttons[cat["name"].title()] = f"{CALLBACK_CATEGORY_PREFIX}{cat['category_id']}"
    
    buttons[BTN_CART] = CALLBACK_CART
    buttons[BTN_ORDERS] = CALLBACK_ORDERS
    buttons[BTN_MAIN_MENU] = CALLBACK_MAIN_MENU
    
    sizes = []
    
    cat_count = len(categories)
    if cat_count > 0:
        sizes.extend([2] * (cat_count // 2))
        if cat_count % 2 == 1:
            sizes.append(1)
    
    # Корзина + Мои заказы в одной строке, Главная отдельно
    sizes.append(2)  # 🛒 Корзина + 📋 Заказы
    sizes.append(1)  # 🏠 Главная
    
    return buttons, sizes


def create_dishes_buttons(
    dishes: List[Dict[str, Any]],
    category_id: int
) -> Tuple[Dict[str, str], List[int]]:
    """
    Создаёт кнопки для списка блюд в категории.
    """
    buttons: Dict[str, str] = {}
    
    if dishes:
        for dish in dishes:
            buttons[dish["name"]] = f"{CALLBACK_DISH_PREFIX}{dish['dish_id']}"
    
    # Кнопка "Назад" возвращает к списку категорий
    buttons[BTN_BACK] = CALLBACK_BACK_TO_MENU
    
    dish_count = len(dishes)
    sizes = [2] * (dish_count // 2)
    if dish_count % 2 == 1:
        sizes.append(1)
    sizes.append(1)  # Кнопка "Назад"
    
    return buttons, sizes


def create_dish_detail_buttons(
    dish_id: int,
    category_id: int
) -> Tuple[Dict[str, str], List[int]]:
    """
    Кнопки для карточки блюда: добавить в корзину или вернуться в главное меню.
    """
    buttons = {
        BTN_ADD_TO_CART: f"{CALLBACK_ADD_TO_CART_PREFIX}{dish_id}",
        BTN_BACK: CALLBACK_BACK_TO_MENU  # ✅ Возврат в главное меню (категории)
    }
    
    return buttons, [1, 1]


# =============================================================================
# HANDLERS
# =============================================================================
# Разделение по логике:
#   - NAVIGATION: переходы по меню
#   - CATALOG: просмотр категорий и блюд
#   - ORDERS: история заказов
# =============================================================================


# -----------------------------------------------------------------------------
# NAVIGATION HANDLERS
# -----------------------------------------------------------------------------

@UserMenuRouter.callback_query(F.data == "user_catalog")
@UserMenuRouter.callback_query(F.data == CALLBACK_BACK_TO_MENU)
async def show_categories(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Главное меню — как вход на кухню, где всё готовится с любовью.
    """
    await state.clear()
    await state.set_state(user_states.UserMenu.catalog)

    categories = await get_categories_orm(session=session)
    ic("Categories fetched:", categories)
    
    buttons, sizes = create_categories_buttons(categories)
    
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


# -----------------------------------------------------------------------------
# CATALOG HANDLERS
# -----------------------------------------------------------------------------

@UserMenuRouter.callback_query(F.data.startswith(CALLBACK_CATEGORY_PREFIX))
async def show_category_dishes(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Показывает блюда в выбранной категории.
    Как открыть старую тетрадь с рецептами и выбрать, что приготовить сегодня.
    """
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
    """
    Детальная карточка блюда.
    Как перелистнуть страницу кулинарной книги и увидеть, как выглядит это блюдо.
    """
    dish_id = int(call.data.split("_")[2])
    
    dish = await get_dish_by_id_orm(session=session, dish_id=dish_id)
    
    if not dish:
        await send_clean_message(
            target=call,
            text="❌ Блюдо не найдено",
            buttons={BTN_BACK_TO_CATEGORIES: CALLBACK_BACK_TO_MENU}
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
    """
    История заказов.
    Здесь будут храниться ваши любимые блюда, которые вы уже пробовали.
    """
    await send_clean_message(
        target=call,
        text="""
📋 <b>Ваши заказы</b>

Здесь будет храниться история ваших заказов — как заметки на кухне,
чтобы не забыть, что особенно понравилось.

<i>Скоро эта страница наполнится любимыми блюдами!</i>
        """,
        buttons={
            BTN_CART: CALLBACK_CART,
            BTN_MAIN_MENU: CALLBACK_MAIN_MENU
        },
        sizes=[1, 1]
    )