"""
Admin Seasonal Dishes Module
============================

This module handles seasonal dishes management for administrators.
Here the chef selects special dishes that are particularly good this season.
"""

from typing import Dict, List, Any

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from sqlalchemy.ext.asyncio import AsyncSession

# =============================================================================
# DATABASE IMPORTS
# =============================================================================
from database.orm_query.category_orm import get_categories_orm
from database.orm_query.dish_orm import (
    get_dish_by_category_orm,
    get_dish_by_id_orm,
    get_status_promotion_by_dish_orm,
    set_dish_promotion_orm,
    get_all_promotion_dishes_orm,
    get_promotion_dishes_count_orm,
    bulk_set_promotion_orm
)
from database.enumirate.dish_enum import DishStatus

# =============================================================================
# PROJECT IMPORTS
# =============================================================================
from States.user_states import PromotionStates
from tools import send_clean_message


# =============================================================================
# ROUTER INITIALIZATION
# =============================================================================

AdminPromotionRouter = Router()


# =============================================================================
# CONSTANTS
# =============================================================================

# -----------------------------------------------------------------------------
# Message texts — как афиша с сезонными предложениями на доске шефа
# -----------------------------------------------------------------------------

PROMOTION_MAIN_TEXT = """
🌿 <b>Сезонные блюда</b>

Здесь вы выбираете блюда, которые особенно хороши в этом сезоне.
Отметьте любимые позиции — пусть гости попробуют самое вкусное!

<b>Сейчас в сезоне:</b>
━━━━━━━━━━━━━━━━━━━━━
🌿 Блюд: <b>{promo_count}</b>
🍽 Всего в меню: <b>{total_dishes}</b>
━━━━━━━━━━━━━━━━━━━━━

Что делаем?
"""

PROMO_LIST_TEXT = """
🌿 <b>Сейчас в сезоне</b>

Вот что особенно вкусное ждёт наших гостей:
"""

NO_PROMO_TEXT = """
📭 <b>Пока нет сезонных блюд</b>

Нажмите "➕ Добавить в сезонные" — выберите, чем порадуем гостей сегодня.
"""

CATEGORY_SELECT_TEXT = """
📋 <b>Выберите категорию</b>

Посмотрим, что вкусного в этом разделе:
"""

DISH_SELECT_TEXT_ADD = """
🍽 <b>Добавляем в сезонные</b>

Нажмите на блюдо — оно попадёт в список сезонных предложений.

✅ — уже в сезоне
"""

DISH_SELECT_TEXT_REMOVE = """
🍽 <b>Убираем из сезонных</b>

Нажмите на блюдо, чтобы убрать его из сезонных предложений.

✅ — сейчас в сезоне
"""

BULK_SELECT_TEXT = """
📦 <b>Быстрое редактирование</b>

Выберите несколько блюд сразу, потом нажмите "Готово".

✅ — выбрано для сезонных
⬜ — обычное меню
"""

CONFIRM_BULK_TEXT = """
📦 <b>Подтверждение</b>

━━━━━━━━━━━━━━━━━━━━━
<b>Что делаем:</b> {action}
<b>Сколько блюд:</b> {count}

Обновим:
{dishes_list}
━━━━━━━━━━━━━━━━━━━━━

Продолжаем?
"""

# -----------------------------------------------------------------------------
# Success messages
# -----------------------------------------------------------------------------

PROMOTION_ADDED = """
✨ <b>Готово!</b>

Блюдо <b>«{name}»</b> теперь в сезонном меню.
Гости оценят!
"""

PROMOTION_REMOVED = """
🍽 <b>Убрали</b>

Блюдо <b>«{name}»</b> вернулось в основное меню.
"""

BULK_UPDATE_SUCCESS = """
✅ <b>Обновили!</b>

Изменили сезонные блюда для <b>{count}</b> позиций.
"""

# -----------------------------------------------------------------------------
# Button labels
# -----------------------------------------------------------------------------
BTN_VIEW_PROMO = "🌿 Посмотреть сезонные"
BTN_ADD_PROMO = "➕ Добавить в сезонные"
BTN_REMOVE_PROMO = "➖ Убрать из сезонных"
BTN_BULK_ADD = "📦 Быстро добавить"
BTN_BULK_REMOVE = "📦 Быстро убрать"
BTN_DONE = "✅ Готово"
BTN_CANCEL = "❌ Отмена"
BTN_BACK = "🔙 Назад"
BTN_CONFIRM = "✅ Да, меняем"
BTN_SELECT_ALL = "🔘 Выбрать всё"
BTN_CLEAR_ALL = "🔄 Очистить"

# -----------------------------------------------------------------------------
# Callback data
# -----------------------------------------------------------------------------
CALLBACK_PROMO_MAIN = "promo_main"
CALLBACK_PROMO_VIEW = "promo_view"
CALLBACK_PROMO_ADD = "promo_add"
CALLBACK_PROMO_REMOVE = "promo_remove"
CALLBACK_PROMO_BULK_ADD = "promo_bulk_add"
CALLBACK_PROMO_BULK_REMOVE = "promo_bulk_remove"
CALLBACK_PROMO_SELECT_CAT = "promo_select_cat_"
CALLBACK_PROMO_SELECT_DISH = "promo_select_dish_"
CALLBACK_PROMO_TOGGLE = "promo_toggle_"
CALLBACK_PROMO_BULK_TOGGLE = "promo_bulk_toggle_"
CALLBACK_PROMO_BULK_DONE = "promo_bulk_done"
CALLBACK_PROMO_CONFIRM = "promo_confirm"
CALLBACK_PROMO_BACK = "promo_back"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

async def get_total_dishes_count(session: AsyncSession) -> int:
    """Сколько всего блюд в меню."""
    from database.orm_query.dish_orm import get_all_dishes_orm
    dishes = await get_all_dishes_orm(session)
    return len(dishes)


def format_promo_list(promo_dishes: List[Dict[str, Any]]) -> str:
    """Красивый список сезонных блюд."""
    if not promo_dishes:
        return "📭 Пока нет"
    
    text = "🌿 <b>Сейчас в сезоне:</b>\n\n"
    for i, dish in enumerate(promo_dishes, 1):
        text += f"{i}. {dish['name']} — {dish['price']} ₽\n"
    
    return text


# =============================================================================
# MAIN SEASONAL MENU HANDLER
# =============================================================================

@AdminPromotionRouter.callback_query(F.data == "promotions")
async def show_seasonal_main(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Главное меню сезонных блюд — выбираем, что будем делать.
    """
    await state.set_state(PromotionStates.main_menu)
    
    promo_count = await get_promotion_dishes_count_orm(session)
    total_dishes = await get_total_dishes_count(session)
    
    text = PROMOTION_MAIN_TEXT.format(
        promo_count=promo_count,
        total_dishes=total_dishes
    )
    
    buttons = {
        BTN_VIEW_PROMO: CALLBACK_PROMO_VIEW,
        BTN_ADD_PROMO: CALLBACK_PROMO_ADD,
        BTN_REMOVE_PROMO: CALLBACK_PROMO_REMOVE,
        BTN_BULK_ADD: CALLBACK_PROMO_BULK_ADD,
        BTN_BULK_REMOVE: CALLBACK_PROMO_BULK_REMOVE,
        BTN_BACK: "back_to_admin_panel"
    }
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=[1, 1, 1, 1, 1, 1]
    )


# =============================================================================
# VIEW SEASONAL DISHES HANDLER
# =============================================================================

@AdminPromotionRouter.callback_query(F.data == CALLBACK_PROMO_VIEW, StateFilter(PromotionStates.main_menu))
async def view_seasonal_dishes(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Смотрим, что сейчас в сезоне.
    """
    promo_dishes = await get_all_promotion_dishes_orm(session)
    
    if not promo_dishes:
        text = NO_PROMO_TEXT
    else:
        text = PROMO_LIST_TEXT + "\n\n" + format_promo_list(promo_dishes)
    
    buttons = {
        BTN_BACK: CALLBACK_PROMO_MAIN
    }
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=[1]
    )


# =============================================================================
# ADD TO SEASONAL - SELECT CATEGORY
# =============================================================================

@AdminPromotionRouter.callback_query(F.data == CALLBACK_PROMO_ADD, StateFilter(PromotionStates.main_menu))
async def add_seasonal_select_category(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Добавляем в сезонные — выбираем категорию.
    """
    await state.set_state(PromotionStates.select_category)
    await state.update_data(action="add")
    
    categories = await get_categories_orm(session)
    
    if not categories:
        await call.answer("❌ Нет категорий", show_alert=True)
        return
    
    buttons = {}
    for cat in categories:
        buttons[cat["name"]] = f"{CALLBACK_PROMO_SELECT_CAT}{cat['category_id']}"
    
    buttons[BTN_CANCEL] = CALLBACK_PROMO_MAIN
    
    cat_count = len(categories)
    sizes = [2] * (cat_count // 2)
    if cat_count % 2 == 1:
        sizes.append(1)
    sizes.append(1)
    
    await send_clean_message(
        target=call,
        text=CATEGORY_SELECT_TEXT,
        buttons=buttons,
        sizes=sizes
    )


# =============================================================================
# REMOVE FROM SEASONAL - SELECT CATEGORY
# =============================================================================

@AdminPromotionRouter.callback_query(F.data == CALLBACK_PROMO_REMOVE, StateFilter(PromotionStates.main_menu))
async def remove_seasonal_select_category(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Убираем из сезонных — выбираем категорию.
    """
    await state.set_state(PromotionStates.select_category)
    await state.update_data(action="remove")
    
    categories = await get_categories_orm(session)
    
    if not categories:
        await call.answer("❌ Нет категорий", show_alert=True)
        return
    
    buttons = {}
    for cat in categories:
        buttons[cat["name"]] = f"{CALLBACK_PROMO_SELECT_CAT}{cat['category_id']}"
    
    buttons[BTN_CANCEL] = CALLBACK_PROMO_MAIN
    
    cat_count = len(categories)
    sizes = [2] * (cat_count // 2)
    if cat_count % 2 == 1:
        sizes.append(1)
    sizes.append(1)
    
    await send_clean_message(
        target=call,
        text=CATEGORY_SELECT_TEXT,
        buttons=buttons,
        sizes=sizes
    )


# =============================================================================
# SELECT DISH FROM CATEGORY
# =============================================================================

@AdminPromotionRouter.callback_query(F.data.startswith(CALLBACK_PROMO_SELECT_CAT), 
                                    StateFilter(PromotionStates.select_category))
async def select_dish_from_category(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Показываем блюда в выбранной категории.
    """
    category_id = int(call.data.replace(CALLBACK_PROMO_SELECT_CAT, ""))
    data = await state.get_data()
    action = data.get("action", "add")
    
    dishes = await get_dish_by_category_orm(session, category_id)
    
    if not dishes:
        await call.answer("❌ В этой категории пока нет блюд", show_alert=True)
        return
    
    buttons = {}
    for dish in dishes:
        status = await get_status_promotion_by_dish_orm(session, dish['dish_id'])
        is_promo = (status == DishStatus.PROMOTION.value)
        
        prefix = "✅ " if is_promo else ""
        buttons[f"{prefix}{dish['name']}"] = f"{CALLBACK_PROMO_SELECT_DISH}{dish['dish_id']}"
    
    buttons[BTN_BACK] = CALLBACK_PROMO_ADD if action == "add" else CALLBACK_PROMO_REMOVE
    
    dish_count = len(dishes)
    sizes = [2] * (dish_count // 2)
    if dish_count % 2 == 1:
        sizes.append(1)
    sizes.append(1)
    
    text = DISH_SELECT_TEXT_ADD if action == "add" else DISH_SELECT_TEXT_REMOVE
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=sizes
    )


# =============================================================================
# TOGGLE SEASONAL STATUS FOR SINGLE DISH
# =============================================================================

@AdminPromotionRouter.callback_query(F.data.startswith(CALLBACK_PROMO_SELECT_DISH))
async def toggle_dish_seasonal(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Включаем или выключаем сезонный статус для одного блюда.
    """
    dish_id = int(call.data.replace(CALLBACK_PROMO_SELECT_DISH, ""))
    
    current_status = await get_status_promotion_by_dish_orm(session, dish_id)
    is_promo = (current_status == DishStatus.PROMOTION.value)
    
    dish = await get_dish_by_id_orm(session, dish_id)
    
    if not dish:
        await call.answer("❌ Блюдо не найдено", show_alert=True)
        return
    
    success = await set_dish_promotion_orm(session, dish_id, not is_promo)
    
    if success:
        if not is_promo:
            await call.answer(text="✨ Добавили в сезонные!", show_alert=False)
            text = PROMOTION_ADDED.format(name=dish['name'])
        else:
            await call.answer(text="🍽 Убрали из сезонных", show_alert=False)
            text = PROMOTION_REMOVED.format(name=dish['name'])
    else:
        await call.answer("❌ Что-то пошло не так", show_alert=True)
        return
    
    await state.set_state(PromotionStates.main_menu)
    
    buttons = {
        "🌿 К сезонным": CALLBACK_PROMO_MAIN
    }
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=[1]
    )


# =============================================================================
# BULK SEASONAL HANDLERS
# =============================================================================

@AdminPromotionRouter.callback_query(F.data == CALLBACK_PROMO_BULK_ADD, StateFilter(PromotionStates.main_menu))
async def bulk_add_start(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Начинаем быстрое добавление в сезонные.
    """
    await state.set_state(PromotionStates.bulk_select)
    await state.update_data(
        bulk_action="add",
        selected_dishes=[],
        all_dishes={}
    )
    
    await show_bulk_selection(call, state, session)


@AdminPromotionRouter.callback_query(F.data == CALLBACK_PROMO_BULK_REMOVE, StateFilter(PromotionStates.main_menu))
async def bulk_remove_start(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Начинаем быстрое удаление из сезонных.
    """
    await state.set_state(PromotionStates.bulk_select)
    await state.update_data(
        bulk_action="remove",
        selected_dishes=[],
        all_dishes={}
    )
    
    await show_bulk_selection(call, state, session)


async def show_bulk_selection(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Показываем все блюда для массового выбора.
    """
    data = await state.get_data()
    bulk_action = data.get("bulk_action", "add")
    selected = data.get("selected_dishes", [])
    
    from database.orm_query.dish_orm import get_all_dishes_orm
    all_dishes = await get_all_dishes_orm(session)
    
    dishes_dict = {dish['dish_id']: dish for dish in all_dishes}
    await state.update_data(all_dishes=dishes_dict)
    
    if not all_dishes:
        await call.answer("❌ Нет блюд в меню", show_alert=True)
        await show_seasonal_main(call, state, session)
        return
    
    buttons = {}
    for dish in all_dishes:
        is_selected = dish['dish_id'] in selected
        prefix = "✅ " if is_selected else "⬜ "
        buttons[f"{prefix}{dish['name']}"] = f"{CALLBACK_PROMO_BULK_TOGGLE}{dish['dish_id']}"
    
    buttons[BTN_SELECT_ALL] = CALLBACK_PROMO_BULK_TOGGLE + "all"
    buttons[BTN_CLEAR_ALL] = CALLBACK_PROMO_BULK_TOGGLE + "clear"
    buttons[BTN_DONE] = CALLBACK_PROMO_BULK_DONE
    buttons[BTN_CANCEL] = CALLBACK_PROMO_MAIN
    
    dish_count = len(all_dishes)
    sizes = [2] * (dish_count // 2)
    if dish_count % 2 == 1:
        sizes.append(1)
    sizes.extend([1, 1, 1])
    
    action_text = "добавления в сезонные" if bulk_action == "add" else "удаления из сезонных"
    text = f"📦 <b>Быстрое {action_text}</b>\n\nВыберите блюда:"
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=sizes
    )


@AdminPromotionRouter.callback_query(F.data.startswith(CALLBACK_PROMO_BULK_TOGGLE), 
                                    StateFilter(PromotionStates.bulk_select))
async def bulk_toggle_dish(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Выбираем или убираем блюдо при массовом редактировании.
    """
    dish_id_str = call.data.replace(CALLBACK_PROMO_BULK_TOGGLE, "")
    
    data = await state.get_data()
    selected = data.get("selected_dishes", [])
    all_dishes = data.get("all_dishes", {})
    
    if dish_id_str == "all":
        selected = list(all_dishes.keys())
        await call.answer(f"✅ Выбрали все ({len(selected)})")
        
    elif dish_id_str == "clear":
        selected = []
        await call.answer("🔄 Очистили")
        
    else:
        dish_id = int(dish_id_str)
        if dish_id in selected:
            selected.remove(dish_id)
            await call.answer("❌ Убрали")
        else:
            selected.append(dish_id)
            await call.answer("✅ Добавили")
    
    await state.update_data(selected_dishes=selected)
    await show_bulk_selection(call, state, session)


@AdminPromotionRouter.callback_query(F.data == CALLBACK_PROMO_BULK_DONE, StateFilter(PromotionStates.bulk_select))
async def bulk_done(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Завершили выбор — показываем подтверждение.
    """
    data = await state.get_data()
    selected = data.get("selected_dishes", [])
    bulk_action = data.get("bulk_action", "add")
    all_dishes = data.get("all_dishes", {})
    
    if not selected:
        await call.answer("❌ Ничего не выбрано", show_alert=True)
        return
    
    dishes_list = []
    for dish_id in selected[:5]:
        dish = all_dishes.get(dish_id, {})
        dishes_list.append(f"• {dish.get('name', 'Блюдо')}")
    
    if len(selected) > 5:
        dishes_list.append(f"• ... и ещё {len(selected) - 5}")
    
    action_text = "ДОБАВЛЯЕМ В СЕЗОННЫЕ" if bulk_action == "add" else "УБИРАЕМ ИЗ СЕЗОННЫХ"
    
    text = CONFIRM_BULK_TEXT.format(
        action=action_text,
        count=len(selected),
        dishes_list="\n".join(dishes_list)
    )
    
    await state.set_state(PromotionStates.confirm_bulk)
    
    buttons = {
        BTN_CONFIRM: CALLBACK_PROMO_CONFIRM,
        BTN_BACK: CALLBACK_PROMO_BULK_ADD if bulk_action == "add" else CALLBACK_PROMO_BULK_REMOVE,
        BTN_CANCEL: CALLBACK_PROMO_MAIN
    }
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=[1, 1, 1]
    )


@AdminPromotionRouter.callback_query(F.data == CALLBACK_PROMO_CONFIRM, StateFilter(PromotionStates.confirm_bulk))
async def bulk_confirm(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Подтверждаем и выполняем массовое обновление.
    """
    data = await state.get_data()
    selected = data.get("selected_dishes", [])
    bulk_action = data.get("bulk_action", "add")
    
    is_promo = (bulk_action == "add")
    updated_count = await bulk_set_promotion_orm(session, selected, is_promo)
    
    if updated_count > 0:
        text = BULK_UPDATE_SUCCESS.format(count=updated_count)
    else:
        text = "❌ Не получилось обновить"
    
    await state.clear()
    await state.set_state(PromotionStates.main_menu)
    
    buttons = {
        "🌿 К сезонным": CALLBACK_PROMO_MAIN
    }
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=buttons,
        sizes=[1]
    )


# =============================================================================
# BACK TO MAIN HANDLER
# =============================================================================

@AdminPromotionRouter.callback_query(F.data == CALLBACK_PROMO_MAIN)
async def back_to_seasonal_main(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Возвращаемся в главное меню сезонных блюд.
    """
    await state.clear()
    await show_seasonal_main(call, state, session)