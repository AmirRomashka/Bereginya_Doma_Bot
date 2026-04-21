# repositories/order_item_repository.py
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, and_, func
from sqlalchemy.sql import Select

from ..models.order_items_model import OrderItem


class OrderItemRepository:
    """Репозиторий для работы с элементами заказов"""
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.model = OrderItem
    
    # CREATE
    async def create(self, **kwargs) -> OrderItem:
        """
        Создает новый элемент заказа
        
        ОБЯЗАТЕЛЬНЫЕ ПОЛЯ:
        -----------------
        order_id: int - ID заказа (Foreign Key to order.order_id)
            Пример: order_id=1
            
        dish_id: int - ID блюда (Foreign Key to dishes.dish_id)
            Пример: dish_id=5
            
        price: int - Цена за единицу (не может быть null)
            Пример: price=500
        
        ОПЦИОНАЛЬНЫЕ ПОЛЯ:
        -----------------
        quantity: int - Количество (default=1)
            Пример: quantity=2
        
        ПРИМЕР ИСПОЛЬЗОВАНИЯ:
        --------------------
        # Минимальный набор полей
        item = await repo.create(
            order_id=1,
            dish_id=5,
            price=500
        )
        
        # Полный набор полей
        item = await repo.create(
            order_id=1,
            dish_id=5,
            quantity=3,
            price=500
        )
        
        Returns:
            OrderItem: Созданный элемент заказа
        """
        order_item = self.model(**kwargs)
        self.db_session.add(order_item)
        await self.db_session.commit()
        await self.db_session.refresh(order_item)
        return order_item
    
    async def create_many(self, items: List[Dict[str, Any]]) -> List[OrderItem]:
        """
        Создает несколько элементов заказа
        
        Args:
            items: Список словарей с данными для создания
        
        Returns:
            List[OrderItem]: Список созданных элементов
        """
        order_items = [self.model(**item) for item in items]
        self.db_session.add_all(order_items)
        await self.db_session.commit()
        
        for item in order_items:
            await self.db_session.refresh(item)
        
        return order_items
    
    # READ

    async def get_by_id(self, item_id: int) -> Optional[OrderItem]:
        """
        Получает элемент заказа по ID
        
        Args:
            item_id: ID элемента заказа
        
        Returns:
            Optional[OrderItem]: Элемент заказа или None
        """
        query = select(self.model).where(self.model.item_id == item_id)
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_order(self, order_id: int) -> List[OrderItem]:
        """
        Получает все элементы конкретного заказа
        
        Args:
            order_id: ID заказа
        
        Returns:
            List[OrderItem]: Список элементов заказа
        """
        query = select(self.model).where(self.model.order_id == order_id)
        result = await self.db_session.execute(query)
        return result.scalars().all()
    
    async def get_by_dish(self, dish_id: int) -> List[OrderItem]:
        """
        Получает все элементы с конкретным блюдом
        
        Args:
            dish_id: ID блюда
        
        Returns:
            List[OrderItem]: Список элементов заказа
        """
        query = select(self.model).where(self.model.dish_id == dish_id)
        result = await self.db_session.execute(query)
        return result.scalars().all()
    
    async def get_all(
        self, 
        skip: int = 0, 
        limit: int = 100,
        order_by: str = "item_id",
        ascending: bool = True,
        **filters
    ) -> List[OrderItem]:
        """
        Получает все элементы заказа с фильтрацией и пагинацией
        
        Args:
            skip: Количество пропускаемых записей
            limit: Максимальное количество записей
            order_by: Поле для сортировки
            ascending: Направление сортировки
            **filters: Поля для фильтрации
        
        Returns:
            List[OrderItem]: Список элементов заказа
        """
        query = select(self.model)
        
        # Применяем фильтры
        for field, value in filters.items():
            if hasattr(self.model, field) and value is not None:
                query = query.where(getattr(self.model, field) == value)
        
        # Применяем сортировку
        if hasattr(self.model, order_by):
            order_column = getattr(self.model, order_by)
            if ascending:
                query = query.order_by(order_column)
            else:
                query = query.order_by(order_column.desc())
        
        # Применяем пагинацию
        query = query.offset(skip).limit(limit)
        
        result = await self.db_session.execute(query)
        return result.scalars().all()
    
    async def get_by_order_and_dish(
        self, 
        order_id: int, 
        dish_id: int
    ) -> Optional[OrderItem]:
        """
        Получает элемент заказа по ID заказа и ID блюда
        
        Args:
            order_id: ID заказа
            dish_id: ID блюда
        
        Returns:
            Optional[OrderItem]: Элемент заказа или None
        """
        query = select(self.model).where(
            and_(
                self.model.order_id == order_id,
                self.model.dish_id == dish_id
            )
        )
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()
    
    # UPDATE
    async def update(self, item_id: int, **kwargs) -> Optional[OrderItem]:
        """
        Обновляет элемент заказа
        
        Args:
            item_id: ID элемента заказа
            **kwargs: Поля для обновления
        
        Returns:
            Optional[OrderItem]: Обновленный элемент или None
        """
        order_item = await self.get_by_id(item_id)
        if not order_item:
            return None
        
        for key, value in kwargs.items():
            if hasattr(order_item, key):
                setattr(order_item, key, value)
        
        await self.db_session.commit()
        await self.db_session.refresh(order_item)
        return order_item
    
    async def update_quantity(self, item_id: int, quantity: int) -> Optional[OrderItem]:
        """
        Обновляет количество в элементе заказа
        
        Args:
            item_id: ID элемента заказа
            quantity: Новое количество
        
        Returns:
            Optional[OrderItem]: Обновленный элемент или None
        """
        return await self.update(item_id, quantity=quantity)
    
    async def update_price(self, item_id: int, price: int) -> Optional[OrderItem]:
        """
        Обновляет цену в элементе заказа
        
        Args:
            item_id: ID элемента заказа
            price: Новая цена
        
        Returns:
            Optional[OrderItem]: Обновленный элемент или None
        """
        return await self.update(item_id, price=price)
    
    async def update_many(
        self, 
        items_data: List[Dict[str, Any]]
    ) -> List[Optional[OrderItem]]:
        """
        Массовое обновление элементов заказа
        
        Args:
            items_data: Список словарей с item_id и полями для обновления
        
        Returns:
            List[Optional[OrderItem]]: Список обновленных элементов
        """
        updated_items = []
        for item_data in items_data:
            item_id = item_data.pop("item_id", None)
            if item_id:
                updated_item = await self.update(item_id, **item_data)
                updated_items.append(updated_item)
        return updated_items
    
    # DELETE
    async def delete(self, item_id: int) -> bool:
        """
        Удаляет элемент заказа
        
        Args:
            item_id: ID элемента заказа
        
        Returns:
            bool: True если удален, False если не найден
        """
        order_item = await self.get_by_id(item_id)
        if order_item:
            await self.db_session.delete(order_item)
            await self.db_session.commit()
            return True
        return False
    
    async def delete_many(self, item_ids: List[int]) -> int:
        """
        Удаляет несколько элементов заказа
        
        Args:
            item_ids: Список ID элементов для удаления
        
        Returns:
            int: Количество удаленных элементов
        """
        query = delete(self.model).where(self.model.item_id.in_(item_ids))
        result = await self.db_session.execute(query)
        await self.db_session.commit()
        return result.rowcount
    
    async def delete_by_order(self, order_id: int) -> int:
        """
        Удаляет все элементы конкретного заказа
        
        Args:
            order_id: ID заказа
        
        Returns:
            int: Количество удаленных элементов
        """
        query = delete(self.model).where(self.model.order_id == order_id)
        result = await self.db_session.execute(query)
        await self.db_session.commit()
        return result.rowcount
    
    async def delete_by_dish(self, dish_id: int) -> int:
        """
        Удаляет все элементы с конкретным блюдом
        
        Args:
            dish_id: ID блюда
        
        Returns:
            int: Количество удаленных элементов
        """
        query = delete(self.model).where(self.model.dish_id == dish_id)
        result = await self.db_session.execute(query)
        await self.db_session.commit()
        return result.rowcount
    
    # UTILITY METHODS
    async def count(self, **filters) -> int:
        """
        Подсчитывает количество элементов с фильтрацией
        
        Args:
            **filters: Поля для фильтрации
        
        Returns:
            int: Количество элементов
        """
        query = select(func.count()).select_from(self.model)
        
        for field, value in filters.items():
            if hasattr(self.model, field) and value is not None:
                query = query.where(getattr(self.model, field) == value)
        
        result = await self.db_session.execute(query)
        return result.scalar()
    
    async def exists(self, item_id: int) -> bool:
        """
        Проверяет существование элемента заказа
        
        Args:
            item_id: ID элемента заказа
        
        Returns:
            bool: True если существует, иначе False
        """
        order_item = await self.get_by_id(item_id)
        return order_item is not None
    
    async def get_order_total(self, order_id: int) -> int:
        """
        Рассчитывает общую сумму заказа
        
        Args:
            order_id: ID заказа
        
        Returns:
            int: Общая сумма заказа
        """
        query = select(
            func.sum(self.model.price * self.model.quantity)
        ).where(self.model.order_id == order_id)
        
        result = await self.db_session.execute(query)
        return result.scalar() or 0
    
    async def get_order_items_summary(self, order_id: int) -> Dict[str, Any]:
        """
        Получает сводку по элементам заказа
        
        Args:
            order_id: ID заказа
        
        Returns:
            Dict[str, Any]: Сводка по заказу
        """
        items = await self.get_by_order(order_id)
        
        total_items = len(items)
        total_quantity = sum(item.quantity for item in items)
        total_price = sum(item.price * item.quantity for item in items)
        average_price = total_price / total_quantity if total_quantity > 0 else 0
        
        return {
            "order_id": order_id,
            "total_unique_items": total_items,
            "total_quantity": total_quantity,
            "total_price": total_price,
            "average_price_per_item": round(average_price, 2),
            "items": [
                {
                    "item_id": item.item_id,
                    "dish_id": item.dish_id,
                    "quantity": item.quantity,
                    "price": item.price,
                    "subtotal": item.price * item.quantity
                }
                for item in items
            ]
        }
    
    async def add_to_order(
        self, 
        order_id: int, 
        dish_id: int, 
        quantity: int = 1, 
        price: int = None
    ) -> OrderItem:
        """
        Добавляет блюдо в заказ или увеличивает количество если уже есть
        
        Args:
            order_id: ID заказа
            dish_id: ID блюда
            quantity: Количество для добавления
            price: Цена блюда
        
        Returns:
            OrderItem: Обновленный или созданный элемент
        """
        existing_item = await self.get_by_order_and_dish(order_id, dish_id)
        
        if existing_item:
            existing_item.quantity += quantity
            if price is not None:
                existing_item.price = price
            await self.db_session.commit()
            await self.db_session.refresh(existing_item)
            return existing_item
        
        return await self.create(
            order_id=order_id,
            dish_id=dish_id,
            quantity=quantity,
            price=price
        )
    
    async def remove_from_order(
        self, 
        order_id: int, 
        dish_id: int,
        quantity: int = None
    ) -> Tuple[bool, Optional[OrderItem]]:
        """
        Удаляет блюдо из заказа или уменьшает количество
        
        Args:
            order_id: ID заказа
            dish_id: ID блюда
            quantity: Количество для удаления (если None - удаляет полностью)
        
        Returns:
            Tuple[bool, Optional[OrderItem]]: (успех, обновленный элемент или None)
        """
        item = await self.get_by_order_and_dish(order_id, dish_id)
        
        if not item:
            return False, None
        
        if quantity and item.quantity > quantity:
            item.quantity -= quantity
            await self.db_session.commit()
            await self.db_session.refresh(item)
            return True, item
        elif quantity and item.quantity <= quantity:
            await self.delete(item.item_id)
            return True, None
        else:
            await self.delete(item.item_id)
            return True, None
    
    async def get_most_popular_dishes(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Получает самые популярные блюда по количеству заказов
        
        Args:
            limit: Максимальное количество результатов
        
        Returns:
            List[Dict[str, Any]]: Список популярных блюд
        """
        query = select(
            self.model.dish_id,
            func.sum(self.model.quantity).label('total_quantity'),
            func.count(self.model.item_id).label('order_count')
        ).group_by(
            self.model.dish_id
        ).order_by(
            func.sum(self.model.quantity).desc()
        ).limit(limit)
        
        result = await self.db_session.execute(query)
        rows = result.all()
        
        return [
            {
                "dish_id": row.dish_id,
                "total_quantity": row.total_quantity,
                "order_count": row.order_count
            }
            for row in rows
        ]
    
    async def execute_raw_query(self, query: Select) -> List[OrderItem]:
        """
        Выполняет сырой запрос
        
        Args:
            query: Объект запроса SQLAlchemy
        
        Returns:
            List[OrderItem]: Результаты запроса
        """
        result = await self.db_session.execute(query)
        return result.scalars().all()


# Фабрика для создания репозитория
async def get_order_item_repository(db_session: AsyncSession) -> OrderItemRepository:
    """
    Возвращает экземпляр репозитория для работы с элементами заказов
    
    Args:
        db_session: Сессия базы данных
    
    Returns:
        OrderItemRepository: Экземпляр репозитория
    """
    return OrderItemRepository(db_session)