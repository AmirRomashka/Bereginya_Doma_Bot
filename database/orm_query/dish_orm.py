"""
Dish ORM Module
===============

This module provides database operations for managing dishes in the menu.
"""






import logging
from typing import Dict, List, Optional, Any, Sequence
from icecream import ic
from sqlalchemy import func, select, delete, update, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.engine.result import RowMapping
from sqlalchemy.exc import SQLAlchemyError, IntegrityError


from database.enumirate.dish_enum import DishStatus
from ..enumirate.orders_enum import OrdersStatus
from database.models.order_items_model import OrderItem
from database.models.orders_model import Order
from database.models.dishes_model import Dishes

# =============================================================================
# INITIALISATION LOGGER
# =============================================================================


logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# Error messages
ERROR_ADD_DISH = "Failed to add dish: {}"
ERROR_GET_DISHES = "Failed to fetch dishes for category {}: {}"
ERROR_GET_DISH = "Failed to fetch dish {}: {}"
ERROR_DELETE_DISH = "Failed to delete dish {}: {}"
ERROR_UPDATE_DISH = "Failed to update dish {}: {}"
ERROR_INVALID_DATA = "Invalid dish data provided: missing required fields"

ERROR_FETCHING_PROMOTION = "Failed to fetch promotion status for dish {}: {}"
ERROR_UPDATING_PROMOTION = "Failed to update promotion status for dish {}: {}"
ERROR_FETCHING_PROMOTIONS = "Failed to fetch promotion dishes: {}"

SUCCESS_PROMOTION_UPDATED = "Promotion status updated for dish {} to {}"



# Success messages
SUCCESS_ADD_DISH = "Dish '{}' added successfully to category {}"
SUCCESS_DELETE_DISH = "Dish ID {} deleted successfully"
SUCCESS_UPDATE_DISH = "Dish ID {} updated successfully"




# =============================================================================
# DISH CREATION OPERATIONS
# =============================================================================

async def get_user_cart_items(
    session: AsyncSession,
    user_id: int
) -> List[dict]:
    """
    Получает список блюд из корзины пользователя для Telegram бота
    
    Args:
        session: AsyncSession - сессия БД
        user_id: int - Telegram ID пользователя
        
    Returns:
        List[dict]: Список блюд в формате:
        [
            {
                "dish_id": 1,           # ID блюда из Dishes
                "name": "Пицца",         # название из Dishes
                "description": "Вкусно",  # описание из Dishes
                "price": 500,            # цена из Dishes
                "quantity": 2,            # количество из OrderItem
                "item_id": 10             # ID записи в OrderItem (для удаления/изменения)
            },
            ...
        ]
        
    Пример использования в боте:
        items = await get_user_cart_items(session, user_id)
        for item in items:
            text = f"{item['name']} x{item['quantity']} = {item['price'] * item['quantity']}₽"
    """
    try:
        logger.info(f"📦 Получение корзины для пользователя {user_id}")
        
        # 1. Ищем активный заказ пользователя
        order_query = select(Order).where(
            and_(
                Order.user_id == user_id,
                Order.order_status == OrdersStatus.ASSEMBLY.value
            )
        )
        result = await session.execute(order_query)
        active_order = result.scalar_one_or_none()
        
        # Если нет активного заказа - корзина пуста
        if not active_order:
            logger.info(f"ℹ️ У пользователя {user_id} нет активного заказа")
            return []
        
        # 2. Получаем все позиции из заказа с данными о блюдах
        # Делаем JOIN таблиц OrderItem и Dishes
        query = (
            select(
                OrderItem.item_id,
                OrderItem.quantity,
                Dishes.dish_id,
                Dishes.name,
                Dishes.description,
                Dishes.price
            )
            .join(Dishes, Dishes.dish_id == OrderItem.dish_id)
            .where(OrderItem.order_id == active_order.order_id)
        )
        
        result = await session.execute(query)
        rows = result.all()
        
        if not rows:
            logger.info(f"ℹ️ Заказ {active_order.order_id} пуст")
            return []
        
        # 3. Преобразуем результат в список словарей
        cart_items = []
        total = 0
        
        for row in rows:
            item = {
                "item_id": row.item_id,           # ID записи в order_items
                "dish_id": row.dish_id,           # ID блюда
                "name": row.name,                  # Название блюда
                "description": row.description or "Без описания",  # Описание
                "price": row.price,                # Цена за единицу
                "quantity": row.quantity,          # Количество
            }
            cart_items.append(item)
            
            # Считаем общую сумму (опционально)
            total += row.price * row.quantity
        
        logger.info(f"✅ В корзине {len(cart_items)} позиций на сумму {total}₽")
        
        # Можно добавить общую информацию в конец списка
        cart_items.append({
            "total": total,
            "order_id": active_order.order_id,
            "items_count": len(cart_items)
        })
        
        return cart_items
        
    except Exception as e:
        logger.error(f"❌ Ошибка при получении корзины: {e}")
        return []






async def add_dish_orm(session: AsyncSession, data: Dict[str, Any]) -> bool:
    """
    Add a new dish to the database.
    """
    # Validate required fields
    required_fields = ["name", "price", "category_id"]
    missing_fields = [field for field in required_fields if field not in data]
    
    if missing_fields:
        ic(f"Missing required fields: {missing_fields}")
        return False
    
    try:
        # Create dish object with all fields
        dish_kwargs = {
            "name": data["name"].strip(),
            "price": int(data["price"]),
            "category_id": int(data["category_id"]),
        }
        
        # Add optional fields if they exist
        if data.get("image"):
            dish_kwargs["image"] = data["image"]
        
        if data.get("description"):
            dish_kwargs["description"] = data["description"].strip()
        
        # Handle entities - convert to JSON-serializable format
        if data.get("entities"):
            entities_list = []
            for entity in data["entities"]:
                entity_dict = {
                    'type': entity.type,
                    'offset': entity.offset,
                    'length': entity.length,
                    'url': entity.url,
                    'language': entity.language,
                    'custom_emoji_id': entity.custom_emoji_id
                }
                # Убираем None значения
                entity_dict = {k: v for k, v in entity_dict.items() if v is not None}
                entities_list.append(entity_dict)
            
            dish_kwargs["description_entities"] = entities_list
        
        obj = Dishes(**dish_kwargs)
        
        # Save to database
        session.add(obj)
        await session.commit()
        
        ic(f"Dish '{obj.name}' added successfully to category {obj.category_id}")
        return True
        
    except Exception as e:
        ic(f"Error adding dish: {e}")
        await session.rollback()
        return False


# =============================================================================
# DISH RETRIEVAL OPERATIONS
# =============================================================================
async def get_list_dish_by_user_id_orm(session : AsyncSession, user_id : int) -> List[Dishes]:
    """
    Получает список блюд из активного заказа пользователя через user_id

    Args:
        session : AsyncSession,
        user_id : int
    Return:

    """













async def get_dish_by_category_orm(
    session: AsyncSession, 
    category_id: int
) -> Sequence[RowMapping]:
    """
    Get all dishes in a specific category.
    
    Args:
        session: SQLAlchemy async session
        category_id: ID of the category to fetch dishes from
    
    Returns:
        Sequence[RowMapping]: List of dishes with dish_id and name fields,
                             or empty list if none found or error occurs
    
    Example:
        >>> dishes = await get_dish_by_category_orm(session, 1)
        >>> for dish in dishes:
        ...     print(f"{dish['dish_id']}: {dish['name']}")
    """
    try:
        # Ensure category_id is integer
        cat_id = int(category_id)
        
        # Build and execute query
        query = select(
            Dishes.dish_id,
            Dishes.name,
            Dishes.price,
            Dishes.image
        ).where(
            Dishes.category_id == cat_id
        ).order_by(
            Dishes.name  # Sort alphabetically by name
        )
        
        result = await session.execute(query)
        dishes = result.mappings().all()
        
        ic(f"Found {len(dishes)} dishes in category {cat_id}")
        return dishes
        
    except ValueError as e:
        ic(f"Invalid category_id format: {category_id} - {e}")
        return []
        
    except SQLAlchemyError as e:
        ic(ERROR_GET_DISHES.format(category_id, e))
        return []
        
    except Exception as e:
        ic(f"Unexpected error fetching dishes: {e}")
        return []


async def get_dish_by_id_orm(
    session: AsyncSession, 
    dish_id: int
) -> Optional[RowMapping]:
    """
    Get a single dish by its ID with all fields.
    
    Args:
        session: SQLAlchemy async session
        dish_id: ID of the dish to fetch
    
    Returns:
        Optional[RowMapping]: Complete dish data or None if not found
    
    Example:
        >>> dish = await get_dish_by_id_orm(session, 42)
        >>> if dish:
        ...     print(dish['name'], dish['price'])
    """
    try:
        query = select(
            Dishes.dish_id,
            Dishes.name,
            Dishes.description,
            Dishes.description_entities,
            Dishes.price,
            Dishes.image,
            Dishes.category_id
        ).where(Dishes.dish_id == dish_id)
        
        result = await session.execute(query)
        dish = result.mappings().first()
        
        if dish:
            ic(f"Found dish: {dish['name']} (ID: {dish_id})")
        else:
            ic(f"Dish ID {dish_id} not found")
            
        return dish
        
    except SQLAlchemyError as e:
        ic(ERROR_GET_DISH.format(dish_id, e))
        return None


async def get_all_dishes_orm(session: AsyncSession) -> Sequence[RowMapping]:
    """
    Get all dishes from all categories with basic info.
    
    Args:
        session: SQLAlchemy async session
    
    Returns:
        Sequence[RowMapping]: List of all dishes with basic fields
    """
    try:
        query = select(
            Dishes.dish_id,
            Dishes.name,
            Dishes.price,
            Dishes.category_id
        ).order_by(
            Dishes.category_id,
            Dishes.name
        )
        
        result = await session.execute(query)
        dishes = result.mappings().all()
        
        ic(f"Found {len(dishes)} total dishes")
        return dishes
        
    except SQLAlchemyError as e:
        ic(f"Error fetching all dishes: {e}")
        return []


# =============================================================================
# DISH DELETION OPERATIONS
# =============================================================================

async def delete_dish_orm(session: AsyncSession, dish_id: int) -> bool:
    """
    Delete a dish from the database.
    
    Args:
        session: SQLAlchemy async session
        dish_id: ID of the dish to delete
    
    Returns:
        bool: True if dish was deleted successfully, False otherwise
    """
    try:
        # Ensure dish_id is integer
        d_id = int(dish_id)
        
        # Build and execute delete query
        query = delete(Dishes).where(Dishes.dish_id == d_id)
        
        result = await session.execute(query)
        await session.commit()
        
        # Check if any row was actually deleted
        if result.rowcount > 0:
            ic(SUCCESS_DELETE_DISH.format(d_id))
            return True
        else:
            ic(f"Dish ID {d_id} not found")
            return False
        
    except ValueError as e:
        ic(f"Invalid dish_id format: {dish_id} - {e}")
        return False
        
    except IntegrityError as e:
        ic(f"Cannot delete dish {dish_id} due to existing references: {e}")
        await session.rollback()
        return False
        
    except SQLAlchemyError as e:
        ic(ERROR_DELETE_DISH.format(dish_id, e))
        await session.rollback()
        return False
        
    except Exception as e:
        ic(f"Unexpected error deleting dish {dish_id}: {e}")
        await session.rollback()
        return False


# =============================================================================
# DISH UPDATE OPERATIONS
# =============================================================================

async def update_dish_orm(
    session: AsyncSession, 
    dish_id: int, 
    update_data: Dict[str, Any]
) -> bool:
    """
    Update an existing dish.
    
    Args:
        session: SQLAlchemy async session
        dish_id: ID of the dish to update
        update_data: Dictionary with fields to update
            Supported fields: name, description, entities, price, image, category_id
    
    Returns:
        bool: True if updated successfully, False otherwise
    """
    try:
        # Map incoming field names to model field names
        field_mapping = {
            "name": "name",
            "description": "description",
            "entities": "description_entities",
            "price": "price",
            "image": "image",
            "category_id": "category_id"
        }
        
        # Prepare update values
        update_values = {}
        for key, value in update_data.items():
            if key in field_mapping and value is not None:
                model_field = field_mapping[key]
                
                # Handle different field types
                if key == "name" or key == "description":
                    update_values[model_field] = value.strip() if isinstance(value, str) else value
                
                elif key == "price":
                    update_values[model_field] = int(value)
                
                elif key == "category_id":
                    update_values[model_field] = int(value)
                
                elif key == "entities":
                    # Convert MessageEntity objects to JSON-serializable format
                    if value:
                        # Преобразуем entities в список словарей
                        entities_list = []
                        for entity in value:
                            entity_dict = {
                                'type': entity.type,
                                'offset': entity.offset,
                                'length': entity.length,
                                'url': entity.url,
                                'language': entity.language,
                                'custom_emoji_id': entity.custom_emoji_id
                            }
                            # Убираем None значения
                            entity_dict = {k: v for k, v in entity_dict.items() if v is not None}
                            entities_list.append(entity_dict)
                        
                        update_values[model_field] = entities_list
                    else:
                        update_values[model_field] = None
                
                elif key == "image":
                    update_values[model_field] = value
                else:
                    update_values[model_field] = value
        
        if not update_values:
            ic("No valid fields to update")
            return False
        
        # Build and execute update query
        query = (
            update(Dishes)
            .where(Dishes.dish_id == dish_id)
            .values(**update_values)
            .returning(Dishes.dish_id)
        )
        
        result = await session.execute(query)
        await session.commit()
        
        updated = result.scalar_one_or_none() is not None
        
        if updated:
            ic(f"Dish {dish_id} updated successfully")
        else:
            ic(f"Dish {dish_id} not found")
            
        return updated
        
    except Exception as e:
        ic(f"Error updating dish {dish_id}: {e}")
        await session.rollback()
        return False


# =============================================================================
# ADDITIONAL HELPER FUNCTIONS
# =============================================================================

async def get_dishes_count_by_category_orm(
    session: AsyncSession, 
    category_id: int
) -> int:
    """
    Get the number of dishes in a category.
    
    Args:
        session: SQLAlchemy async session
        category_id: ID of the category
    
    Returns:
        int: Number of dishes in the category
    """
    try:
        query = select(func.count()).select_from(Dishes).where(
            Dishes.category_id == category_id
        )
        result = await session.execute(query)
        count = result.scalar() or 0
        
        ic(f"Category {category_id} has {count} dishes")
        return count
        
    except SQLAlchemyError as e:
        ic(f"Error counting dishes in category {category_id}: {e}")
        return 0


async def search_dishes_by_name_orm(
    session: AsyncSession, 
    search_term: str
) -> Sequence[RowMapping]:
    """
    Search dishes by name (case-insensitive partial match).
    
    Args:
        session: SQLAlchemy async session
        search_term: String to search for in dish names
    
    Returns:
        Sequence[RowMapping]: List of matching dishes
    """
    try:
        query = select(
            Dishes.dish_id,
            Dishes.name,
            Dishes.price,
            Dishes.category_id
        ).where(
            Dishes.name.ilike(f"%{search_term}%")
        ).order_by(
            Dishes.name
        )
        
        result = await session.execute(query)
        dishes = result.mappings().all()
        
        ic(f"Found {len(dishes)} dishes matching '{search_term}'")
        return dishes
        
    except SQLAlchemyError as e:
        ic(f"Error searching dishes: {e}")
        return []
    




# =============================================================================
# PROMOTION STATUS FUNCTIONS
# =============================================================================

async def get_status_promotion_by_dish_orm(
    session: AsyncSession, 
    dish_id: int
) -> Optional[str]:
    """
    Get promotion status for a specific dish.
    
    Args:
        session: SQLAlchemy async session
        dish_id: ID of the dish
    
    Returns:
        Optional[str]: Promotion status (PROMOTION or COMMON) or None if dish not found
    
    Example:
        >>> status = await get_status_promotion_by_dish_orm(session, 42)
        >>> if status == DishStatus.PROMOTION.value:
        ...     print("This dish is on promotion!")
    """
    try:
        query = select(Dishes.status).where(Dishes.dish_id == dish_id)
        result = await session.execute(query)
        status = result.scalar_one_or_none()
        
        if status:
            ic(f"Dish {dish_id} promotion status: {status}")
        else:
            ic(f"Dish {dish_id} not found")
            
        return status
        
    except Exception as e:
        ic(ERROR_FETCHING_PROMOTION.format(dish_id, e))
        return None


async def get_all_promotion_dishes_orm(
    session: AsyncSession
) -> Sequence[RowMapping]:
    """
    Get all dishes that are currently on promotion.
    
    Args:
        session: SQLAlchemy async session
    
    Returns:
        Sequence[RowMapping]: List of promotion dishes with details
    
    Example:
        >>> promo_dishes = await get_all_promotion_dishes_orm(session)
        >>> for dish in promo_dishes:
        ...     print(f"{dish['name']} - {dish['price']} ₽")
    """
    try:
        query = select(
            Dishes.dish_id,
            Dishes.name,
            Dishes.description,
            Dishes.price,
            Dishes.image,
            Dishes.category_id
        ).where(
            Dishes.status == DishStatus.PROMOTION.value
        ).order_by(Dishes.name)
        
        result = await session.execute(query)
        dishes = result.mappings().all()
        
        ic(f"Found {len(dishes)} dishes on promotion")
        return dishes
        
    except Exception as e:
        ic(ERROR_FETCHING_PROMOTIONS.format(e))
        return []


async def set_dish_promotion_orm(
    session: AsyncSession,
    dish_id: int,
    promotion_status: bool
) -> bool:
    """
    Set promotion status for a dish.
    
    Args:
        session: SQLAlchemy async session
        dish_id: ID of the dish
        promotion_status: True for promotion, False for common
    
    Returns:
        bool: True if updated successfully, False otherwise
    
    Example:
        >>> # Set dish on promotion
        >>> await set_dish_promotion_orm(session, 42, True)
        >>> # Remove from promotion
        >>> await set_dish_promotion_orm(session, 42, False)
    """
    try:
        new_status = DishStatus.PROMOTION.value if promotion_status else DishStatus.COMMON.value
        
        query = (
            update(Dishes)
            .where(Dishes.dish_id == dish_id)
            .values(status=new_status)
            .returning(Dishes.dish_id)
        )
        
        result = await session.execute(query)
        await session.commit()
        
        updated = result.scalar_one_or_none() is not None
        
        if updated:
            ic(SUCCESS_PROMOTION_UPDATED.format(dish_id, new_status))
        else:
            ic(f"Dish {dish_id} not found")
            
        return updated
        
    except Exception as e:
        ic(ERROR_UPDATING_PROMOTION.format(dish_id, e))
        await session.rollback()
        return False


async def get_dishes_by_promotion_status_orm(
    session: AsyncSession,
    is_promotion: bool
) -> Sequence[RowMapping]:
    """
    Get dishes filtered by promotion status.
    
    Args:
        session: SQLAlchemy async session
        is_promotion: True for promotion dishes, False for common dishes
    
    Returns:
        Sequence[RowMapping]: List of dishes with specified promotion status
    
    Example:
        >>> promo = await get_dishes_by_promotion_status_orm(session, True)
        >>> common = await get_dishes_by_promotion_status_orm(session, False)
    """
    try:
        status = DishStatus.PROMOTION.value if is_promotion else DishStatus.COMMON.value
        
        query = select(
            Dishes.dish_id,
            Dishes.name,
            Dishes.price,
            Dishes.image,
            Dishes.category_id
        ).where(
            Dishes.status == status
        ).order_by(Dishes.name)
        
        result = await session.execute(query)
        dishes = result.mappings().all()
        
        status_text = "promotion" if is_promotion else "common"
        ic(f"Found {len(dishes)} {status_text} dishes")
        return dishes
        
    except Exception as e:
        ic(f"Error fetching dishes by promotion status: {e}")
        return []


async def get_promotion_dishes_count_orm(session: AsyncSession) -> int:
    """
    Get count of dishes currently on promotion.
    
    Args:
        session: SQLAlchemy async session
    
    Returns:
        int: Number of promotion dishes
    """
    try:
        query = select(Dishes.dish_id).where(
            Dishes.status == DishStatus.PROMOTION.value
        )
        result = await session.execute(query)
        dishes = result.scalars().all()
        count = len(dishes)
        
        ic(f"Promotion dishes count: {count}")
        return count
        
    except Exception as e:
        ic(f"Error counting promotion dishes: {e}")
        return 0


async def bulk_set_promotion_orm(
    session: AsyncSession,
    dish_ids: List[int],
    promotion_status: bool
) -> int:
    """
    Set promotion status for multiple dishes at once.
    
    Args:
        session: SQLAlchemy async session
        dish_ids: List of dish IDs to update
        promotion_status: True for promotion, False for common
    
    Returns:
        int: Number of dishes updated
    
    Example:
        >>> # Set multiple dishes on promotion
        >>> updated = await bulk_set_promotion_orm(session, [42, 43, 44], True)
        >>> print(f"{updated} dishes updated")
    """
    try:
        new_status = DishStatus.PROMOTION.value if promotion_status else DishStatus.COMMON.value
        
        query = (
            update(Dishes)
            .where(Dishes.dish_id.in_(dish_ids))
            .values(status=new_status)
            .returning(Dishes.dish_id)
        )
        
        result = await session.execute(query)
        await session.commit()
        
        updated_ids = result.scalars().all()
        updated_count = len(updated_ids)
        
        status_text = "promotion" if promotion_status else "common"
        ic(f"Updated {updated_count} dishes to {status_text}")
        return updated_count
        
    except Exception as e:
        ic(f"Error in bulk promotion update: {e}")
        await session.rollback()
        return 0
