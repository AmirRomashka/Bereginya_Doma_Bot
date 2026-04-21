"""
Order Repository Module
======================

This module provides repository for order operations.
"""

from datetime import datetime
from typing import Optional, List, Union, Dict, Any

from icecream import ic
from sqlalchemy import and_, select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.orders_model import Order
from ..models.order_items_model import OrderItem
from ..models.dishes_model import Dishes
from ..enumirate.orders_enum import OrdersStatus


class OrderRepository:
    """
    Репозиторий для работы с заказами.
    
    Может быть создан с user_id или без него.
    Методы, требующие user_id, проверяют его наличие.
    """
    
    def __init__(self, session: AsyncSession, user_id: Optional[int] = None):
        """
        Инициализация репозитория.
        
        Args:
            session: Сессия базы данных
            user_id: ID пользователя (опционально, но нужен для методов,
                    требующих фильтрации по пользователю)
        """
        self.session = session
        self._user_id = user_id
    
    @property
    def user_id(self) -> int:
        """
        Геттер для user_id с проверкой наличия.
        
        Raises:
            ValueError: Если user_id не установлен
        """
        if self._user_id is None:
            raise ValueError(
                "OrderRepository: user_id не установлен. "
                "Этот метод требует указания user_id при создании репозитория."
            )
        return self._user_id
    
    def set_user_id(self, user_id: int) -> None:
        """Установка user_id после создания репозитория."""
        self._user_id = user_id
    
    # =========================================================================
    # БАЗОВЫЕ МЕТОДЫ (НЕ ТРЕБУЮТ USER_ID)
    # =========================================================================
    
    async def get_order_by_id(self, order_id: int) -> Optional[Order]:
        """
        Получение заказа по ID.
        НЕ ТРЕБУЕТ user_id.
        """
        query = select(Order).where(Order.order_id == order_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_orders_by_status(self, status: OrdersStatus) -> List[Order]:
        """
        Получение заказов по статусу.
        НЕ ТРЕБУЕТ user_id (для админки).
        """
        query = select(Order).where(Order.order_status == status.value)
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def update_order_status(self, order_id: int, new_status: OrdersStatus) -> Optional[Order]:
        """
        Обновление статуса заказа.
        НЕ ТРЕБУЕТ user_id (для админки).
        """
        query = (
            update(Order)
            .where(Order.order_id == order_id)
            .values(order_status=new_status.value)
            .returning(Order)
        )
        result = await self.session.execute(query)
        await self.session.flush()
        return result.scalar_one_or_none()
    
    async def delete_order(self, order_id: int) -> bool:
        """
        Удаление заказа.
        НЕ ТРЕБУЕТ user_id (для админки).
        """
        query = delete(Order).where(Order.order_id == order_id)
        result = await self.session.execute(query)
        await self.session.flush()
        return result.rowcount > 0
    
    # =========================================================================
    # МЕТОДЫ ДЛЯ ПОДСЧЁТА ЗАКАЗОВ (ДЛЯ АДМИНКИ)
    # =========================================================================
    
    async def get_new_orders_count(self) -> int:
        """
        Получение количества новых заказов (в статусе ASSEMBLY).
        НЕ ТРЕБУЕТ user_id (для админки).
        
        Returns:
            int: Количество заказов в статусе сборки
        """
        query = select(func.count()).select_from(Order).where(
            Order.order_status == OrdersStatus.ASSEMBLY.value
        )
        result = await self.session.execute(query)
        return result.scalar() or 0
    
    async def get_active_orders_count(self) -> int:
        """
        Получение количества активных заказов (VERIFICATION, ACCEPTED).
        НЕ ТРЕБУЕТ user_id (для админки).
        
        Returns:
            int: Количество заказов в обработке
        """
        active_statuses = [
            OrdersStatus.VERIFICATION.value,
            OrdersStatus.ACCEPTED.value
        ]
        query = select(func.count()).select_from(Order).where(
            Order.order_status.in_(active_statuses)
        )
        result = await self.session.execute(query)
        return result.scalar() or 0
    
    async def get_completed_orders_count(self, days: Optional[int] = None) -> int:
        """
        Получение количества завершённых заказов.
        НЕ ТРЕБУЕТ user_id (для админки).
        
        Args:
            days: Если указано, считает за последние N дней
            
        Returns:
            int: Количество завершённых заказов
        """
        query = select(func.count()).select_from(Order).where(
            Order.order_status == OrdersStatus.COMPLETED.value
        )
        
        if days:
            from datetime import datetime, timedelta
            cutoff_date = datetime.now() - timedelta(days=days)
            query = query.where(Order.created >= cutoff_date)
        
        result = await self.session.execute(query)
        return result.scalar() or 0
    
    async def get_completed_orders_count_today(self) -> int:
        """
        Получение количества завершённых заказов за сегодня.
        НЕ ТРЕБУЕТ user_id (для админки).
        
        Returns:
            int: Количество завершённых заказов за сегодня
        """
        from datetime import datetime, date
        today_start = datetime.combine(date.today(), datetime.min.time())
        
        query = select(func.count()).select_from(Order).where(
            and_(
                Order.order_status == OrdersStatus.COMPLETED.value,
                Order.created >= today_start
            )
        )
        result = await self.session.execute(query)
        return result.scalar() or 0
    
    async def get_refused_orders_count(self, days: Optional[int] = None) -> int:
        """
        Получение количества отказанных заказов.
        НЕ ТРЕБУЕТ user_id (для админки).
        """
        query = select(func.count()).select_from(Order).where(
            Order.order_status == OrdersStatus.REFUSED.value
        )
        
        if days:
            from datetime import datetime, timedelta
            cutoff_date = datetime.now() - timedelta(days=days)
            query = query.where(Order.created >= cutoff_date)
        
        result = await self.session.execute(query)
        return result.scalar() or 0
    
    async def get_total_orders_count(self) -> int:
        """
        Получение общего количества заказов.
        НЕ ТРЕБУЕТ user_id (для админки).
        """
        query = select(func.count()).select_from(Order)
        result = await self.session.execute(query)
        return result.scalar() or 0
    
    async def get_today_revenue(self) -> int:
        """
        Получение выручки за сегодня.
        НЕ ТРЕБУЕТ user_id (для админки).
        
        Returns:
            int: Сумма всех завершённых заказов за сегодня
        """
        from datetime import datetime, date
        today_start = datetime.combine(date.today(), datetime.min.time())
        
        orders_query = select(Order.order_id).where(
            and_(
                Order.order_status == OrdersStatus.COMPLETED.value,
                Order.created >= today_start
            )
        )
        orders_result = await self.session.execute(orders_query)
        order_ids = orders_result.scalars().all()
        
        if not order_ids:
            return 0
        
        revenue_query = select(
            func.sum(OrderItem.price * OrderItem.quantity)
        ).where(
            OrderItem.order_id.in_(order_ids)
        )
        
        revenue_result = await self.session.execute(revenue_query)
        return revenue_result.scalar() or 0
    
    async def get_orders_by_status_with_count(self) -> Dict[str, int]:
        """
        Получение количества заказов по всем статусам.
        НЕ ТРЕБУЕТ user_id (для админки).
        
        Returns:
            Dict[str, int]: Словарь {статус: количество}
        """
        result = {}
        
        for status in OrdersStatus:
            count = await self.get_orders_by_status_count(status)
            result[status.value] = count
        
        return result
    
    async def get_orders_by_status_count(self, status: OrdersStatus) -> int:
        """
        Получение количества заказов по конкретному статусу.
        НЕ ТРЕБУЕТ user_id (для админки).
        """
        query = select(func.count()).select_from(Order).where(
            Order.order_status == status.value
        )
        result = await self.session.execute(query)
        return result.scalar() or 0
    
    # =========================================================================
    # МЕТОДЫ ДЛЯ РАБОТЫ С ПОЗИЦИЯМИ ЗАКАЗА (НЕ ТРЕБУЮТ USER_ID)
    # =========================================================================
    
    async def add_order_item(
        self, 
        order_id: int, 
        dish_id: int, 
        quantity: int = 1,
        price: Optional[int] = None
    ) -> OrderItem:
        """
        Добавление позиции в заказ.
        
        Args:
            order_id: ID заказа
            dish_id: ID блюда
            quantity: Количество
            price: Цена (если не указана, будет получена из блюда)
        """
        if price is None:
            dish_query = select(Dishes.price).where(Dishes.dish_id == dish_id)
            dish_result = await self.session.execute(dish_query)
            price = dish_result.scalar_one()
        
        order_item = OrderItem(
            order_id=order_id,
            dish_id=dish_id,
            quantity=quantity,
            price=price
        )
        self.session.add(order_item)
        await self.session.flush()
        return order_item
    
    async def get_order_items(self, order_id: int) -> List[Dict[str, Any]]:
        """
        Получение всех позиций заказа с деталями блюд.
        """
        query = select(
            OrderItem, Dishes.name, Dishes.image
        ).join(
            Dishes, OrderItem.dish_id == Dishes.dish_id
        ).where(
            OrderItem.order_id == order_id
        )
        
        result = await self.session.execute(query)
        items = []
        
        for item, dish_name, dish_image in result:
            items.append({
                'item_id': item.item_id,
                'order_id': item.order_id,
                'dish_id': item.dish_id,
                'name': dish_name,
                'image': dish_image,
                'quantity': item.quantity,
                'price': item.price,
                'subtotal': item.quantity * item.price
            })
        
        return items
    
    async def update_order_item_quantity(self, item_id: int, quantity: int) -> bool:
        """
        Обновление количества позиции.
        """
        if quantity <= 0:
            return await self.remove_order_item(item_id)
        
        query = (
            update(OrderItem)
            .where(OrderItem.item_id == item_id)
            .values(quantity=quantity)
        )
        result = await self.session.execute(query)
        await self.session.flush()
        return result.rowcount > 0
    
    async def remove_order_item(self, item_id: int) -> bool:
        """
        Удаление позиции из заказа.
        """
        query = delete(OrderItem).where(OrderItem.item_id == item_id)
        result = await self.session.execute(query)
        await self.session.flush()
        return result.rowcount > 0
    
    async def get_order_total(self, order_id: int) -> int:
        """
        Подсчёт общей суммы заказа.
        """
        items = await self.get_order_items(order_id)
        return sum(item['subtotal'] for item in items)
    
    # =========================================================================
    # МЕТОДЫ, ТРЕБУЮЩИЕ USER_ID (ДЛЯ ПОЛЬЗОВАТЕЛЬСКИХ ОПЕРАЦИЙ)
    # =========================================================================
    
    async def create_order(self, comment: Optional[str] = None) -> Order:
        """
        Создание нового заказа.
        ТРЕБУЕТ user_id.
        """
        order = Order(
            user_id=self.user_id,
            comment=comment,
            order_status=OrdersStatus.ASSEMBLY.value
        )
        self.session.add(order)
        await self.session.flush()
        return order
    
    async def get_orders_by_user(self) -> List[Order]:
        """
        Получение ВСЕХ заказов пользователя.
        ТРЕБУЕТ user_id.
        """
        query = select(Order).where(Order.user_id == self.user_id)
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_orders_by_user_and_status(
        self,
        status: Union[OrdersStatus, List[OrdersStatus]]
    ) -> List[Order]:
        """
        Получение заказов пользователя по статусу.
        ТРЕБУЕТ user_id.
        """
        if isinstance(status, list):
            status_values = [s.value for s in status]
            where_condition = and_(
                Order.user_id == self.user_id,
                Order.order_status.in_(status_values)
            )
        else:
            where_condition = and_(
                Order.user_id == self.user_id,
                Order.order_status == status.value
            )
        
        query = select(Order).where(where_condition)
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_user_orders_count(self) -> int:
        """
        Количество заказов пользователя.
        ТРЕБУЕТ user_id.
        """
        query = select(Order).where(Order.user_id == self.user_id)
        result = await self.session.execute(query)
        return len(result.scalars().all())
    
    async def get_user_orders_count_by_status(
        self,
        status: Union[OrdersStatus, List[OrdersStatus]]
    ) -> int:
        """
        Количество заказов пользователя по статусу.
        ТРЕБУЕТ user_id.
        """
        if isinstance(status, list):
            status_values = [s.value for s in status]
            where_condition = and_(
                Order.user_id == self.user_id,
                Order.order_status.in_(status_values)
            )
        else:
            where_condition = and_(
                Order.user_id == self.user_id,
                Order.order_status == status.value
            )
        
        query = select(Order).where(where_condition)
        result = await self.session.execute(query)
        return len(result.scalars().all())
    
    async def get_user_active_orders(self) -> Optional[Order]:
        """
        Получение АКТИВНОЙ корзины пользователя.
        ТРЕБУЕТ user_id.
        
        Returns:
            Optional[Order]: Заказ в статусе ASSEMBLY или None
        """
        query = select(Order).where(
            and_(
                Order.user_id == self.user_id,
                Order.order_status == OrdersStatus.ASSEMBLY.value
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_user_completed_orders(self) -> List[Order]:
        """
        Получение завершённых заказов пользователя.
        ТРЕБУЕТ user_id.
        """
        query = select(Order).where(
            and_(
                Order.user_id == self.user_id,
                Order.order_status == OrdersStatus.COMPLETED.value
            )
        )
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_user_orders_sorted(
        self,
        limit: Optional[int] = None,
        descending: bool = True
    ) -> List[Order]:
        """
        Получение отсортированных заказов пользователя.
        ТРЕБУЕТ user_id.
        """
        query = select(Order).where(Order.user_id == self.user_id)
        
        if descending:
            query = query.order_by(Order.order_id.desc())
        else:
            query = query.order_by(Order.order_id.asc())
        
        if limit:
            query = query.limit(limit)
        
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_user_last_order(self) -> Optional[Order]:
        """
        Получение последнего заказа пользователя.
        ТРЕБУЕТ user_id.
        """
        query = select(Order).where(
            Order.user_id == self.user_id
        ).order_by(
            Order.order_id.desc()
        ).limit(1)
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    # =========================================================================
    # МЕТОДЫ ДЛЯ РАБОТЫ С КОРЗИНОЙ (ТРЕБУЮТ USER_ID)
    # =========================================================================
    
    async def get_or_create_cart(self) -> Order:
        """
        Получение существующей корзины или создание новой.
        ТРЕБУЕТ user_id.
        """
        cart = await self.get_user_active_orders()
        
        if not cart:
            cart = await self.create_order(comment="Корзина")
        
        return cart
    
    async def add_to_cart(self, dish_id: int, quantity: int = 1) -> bool:
        """
        Добавление блюда в корзину.
        ТРЕБУЕТ user_id.
        """
        cart = await self.get_or_create_cart()
        
        query = select(OrderItem).where(
            and_(
                OrderItem.order_id == cart.order_id,
                OrderItem.dish_id == dish_id
            )
        )
        result = await self.session.execute(query)
        existing = result.scalar_one_or_none()
        
        if existing:
            existing.quantity += quantity
            await self.session.flush()
            return True
        
        await self.add_order_item(cart.order_id, dish_id, quantity)
        return True
    
    async def get_cart_items(self) -> List[Dict[str, Any]]:
        """
        Получение всех элементов корзины.
        ТРЕБУЕТ user_id.
        """
        cart = await self.get_user_active_orders()
        
        if not cart:
            return []
        
        return await self.get_order_items(cart.order_id)
    
    async def get_cart_total(self) -> int:
        """
        Получение общей суммы корзины.
        ТРЕБУЕТ user_id.
        """
        cart = await self.get_user_active_orders()
        
        if not cart:
            return 0
        
        return await self.get_order_total(cart.order_id)
    
    async def clear_cart(self) -> int:
        """
        Очистка корзины.
        ТРЕБУЕТ user_id.
        """
        cart = await self.get_user_active_orders()
        
        if not cart:
            return 0
        
        query = delete(OrderItem).where(OrderItem.order_id == cart.order_id)
        result = await self.session.execute(query)
        await self.session.flush()
        
        return result.rowcount
    
    async def checkout(self) -> Optional[Order]:
        """
        Оформление заказа (превращение корзины в заказ).
        ТРЕБУЕТ user_id.
        """
        cart = await self.get_user_active_orders()
        
        if not cart:
            return None
        
        items = await self.get_order_items(cart.order_id)
        if not items:
            return None
        
        cart = await self.update_order_status(cart.order_id, OrdersStatus.VERIFICATION)
        
        if cart and cart.comment == "Корзина":
            cart.comment = None
            await self.session.flush()
        
        return cart
    
    # =========================================================================
    # МЕТОДЫ ДЛЯ АДМИНКИ (НЕ ТРЕБУЮТ USER_ID)
    # =========================================================================
    
    async def get_all_users_orders_summary(self) -> dict:
        """
        Сводка по заказам всех пользователей.
        """
        query = select(Order.user_id, Order.order_id)
        result = await self.session.execute(query)
        rows = result.all()
        
        summary = {}
        for user_id, order_id in rows:
            if user_id not in summary:
                summary[user_id] = 0
            summary[user_id] += 1
        
        return summary
    
    async def get_order_with_details(self, order_id: int) -> Optional[Dict[str, Any]]:
        """
        Получение полной информации о заказе (для админки).
        """
        order = await self.get_order_by_id(order_id)
        
        if not order:
            return None
        
        items = await self.get_order_items(order_id)
        total = sum(item['subtotal'] for item in items)
        
        return {
            'order_id': order.order_id,
            'user_id': order.user_id,
            'status': order.order_status,
            'comment': order.comment,
            'photo': order.photo,
            'address_id': order.address_id,
            'created': order.created,
            'items': items,
            'total': total,
            'delivery_hour_from': getattr(order, 'delivery_hour_from', None),
            'delivery_hour_to': getattr(order, 'delivery_hour_to', None)
        }
    
    # =========================================================================
    # ДОПОЛНИТЕЛЬНЫЕ МЕТОДЫ ДЛЯ РАБОТЫ С АДРЕСАМИ
    # =========================================================================
    
    async def update_order_address(self, order_id: int, address_id: int) -> Optional[Order]:
        """
        Обновление адреса заказа.
        
        Args:
            order_id: ID заказа
            address_id: ID адреса
        
        Returns:
            Optional[Order]: Обновлённый заказ или None
        """
        try:
            query = (
                update(Order)
                .where(Order.order_id == order_id)
                .values(address_id=address_id)
                .returning(Order)
            )
            result = await self.session.execute(query)
            await self.session.flush()
            return result.scalar_one_or_none()
        except Exception as e:
            ic(f"Error updating order address: {e}")
            return None
    
    # =========================================================================
    # МЕТОДЫ ДЛЯ РАБОТЫ С КОММЕНТАРИЯМИ И ФОТО
    # =========================================================================
    
    async def update_order_comment(self, order_id: int, comment: Optional[str]) -> Optional[Order]:
        """
        Обновление комментария к заказу.
        
        Args:
            order_id: ID заказа
            comment: Текст комментария (может быть None)
        
        Returns:
            Optional[Order]: Обновлённый заказ или None
        """
        try:
            query = (
                update(Order)
                .where(Order.order_id == order_id)
                .values(comment=comment)
                .returning(Order)
            )
            result = await self.session.execute(query)
            await self.session.flush()
            return result.scalar_one_or_none()
        except Exception as e:
            ic(f"Error updating order comment: {e}")
            return None

    async def update_order_photo(self, order_id: int, photo_id: str) -> Optional[Order]:
        """
        Обновление фото чека к заказу.
        
        Args:
            order_id: ID заказа
            photo_id: ID фото в Telegram
        
        Returns:
            Optional[Order]: Обновлённый заказ или None
        """
        try:
            query = (
                update(Order)
                .where(Order.order_id == order_id)
                .values(photo=photo_id)
                .returning(Order)
            )
            result = await self.session.execute(query)
            await self.session.flush()
            return result.scalar_one_or_none()
        except Exception as e:
            ic(f"Error updating order photo: {e}")
            return None

    async def confirm_order(
        self, 
        order_id: int, 
        comment: Optional[str] = None, 
        photo_id: Optional[str] = None
    ) -> Optional[Order]:
        """
        Подтверждение заказа — обновляет комментарий, фото и меняет статус на VERIFICATION.
        
        Args:
            order_id: ID заказа
            comment: Комментарий к заказу
            photo_id: ID фото чека
        
        Returns:
            Optional[Order]: Обновлённый заказ или None
        """
        try:
            update_data = {"order_status": OrdersStatus.VERIFICATION.value}
        
            if comment is not None:
                update_data["comment"] = comment
        
            if photo_id is not None:
                update_data["photo"] = photo_id
        
            query = (
                update(Order)
                .where(Order.order_id == order_id)
                .values(**update_data)
                .returning(Order)
            )
            result = await self.session.execute(query)
            await self.session.flush()
            return result.scalar_one_or_none()
        except Exception as e:
            ic(f"Error confirming order: {e}")
            return None
    
    # =========================================================================
    # МЕТОДЫ ДЛЯ ОЧИСТКИ (НЕ ТРЕБУЮТ USER_ID)
    # =========================================================================
    
    async def delete_old_orders_by_status(
        self, 
        status: Union[OrdersStatus, List[OrdersStatus]], 
        days: int = 30
    ) -> int:
        """
        Удаление старых заказов по статусу.
        """
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        if isinstance(status, list):
            status_values = [s.value for s in status]
            where_condition = and_(
                Order.order_status.in_(status_values),
                Order.created < cutoff_date
            )
        else:
            where_condition = and_(
                Order.order_status == status.value,
                Order.created < cutoff_date
            )
        
        query = delete(Order).where(where_condition)
        result = await self.session.execute(query)
        await self.session.flush()
        
        return result.rowcount
    
    async def delete_orders_by_user_and_status(
        self, 
        user_id: int, 
        status: Union[OrdersStatus, List[OrdersStatus]]
    ) -> int:
        """
        Удаление заказов пользователя по статусу.
        """
        if isinstance(status, list):
            status_values = [s.value for s in status]
            where_condition = and_(
                Order.user_id == user_id,
                Order.order_status.in_(status_values)
            )
        else:
            where_condition = and_(
                Order.user_id == user_id,
                Order.order_status == status.value
            )
        
        query = delete(Order).where(where_condition)
        result = await self.session.execute(query)
        await self.session.flush()
        
        return result.rowcount
    
    async def delete_orders_before_date(
        self, 
        date: datetime, 
        status: Optional[Union[OrdersStatus, List[OrdersStatus]]] = None
    ) -> int:
        """
        Удаление заказов до указанной даты.
        """
        where_condition = [Order.created < date]
        
        if status:
            if isinstance(status, list):
                status_values = [s.value for s in status]
                where_condition.append(Order.order_status.in_(status_values))
            else:
                where_condition.append(Order.order_status == status.value)
        
        query = delete(Order).where(and_(*where_condition))
        result = await self.session.execute(query)
        await self.session.flush()
        
        return result.rowcount

    # =========================================================================
    # МЕТОДЫ ДЛЯ СТАТИСТИКИ
    # =========================================================================
    
    async def get_total_revenue(self) -> int:
        """
        Получает общую выручку за всё время.
        
        Returns:
            int: Общая сумма всех завершённых заказов
        """
        try:
            # Получаем все завершённые заказы
            query = select(Order.order_id).where(
                Order.order_status == OrdersStatus.COMPLETED.value
            )
            result = await self.session.execute(query)
            order_ids = result.scalars().all()
            
            if not order_ids:
                return 0
            
            # Суммируем стоимость всех позиций в этих заказах
            revenue_query = select(
                func.sum(OrderItem.price * OrderItem.quantity)
            ).where(
                OrderItem.order_id.in_(order_ids)
            )
            
            revenue_result = await self.session.execute(revenue_query)
            return revenue_result.scalar() or 0
            
        except Exception as e:
            ic(f"Error getting total revenue: {e}")
            return 0
    
    async def get_revenue_for_period(self, start_date: datetime, end_date: datetime) -> int:
        """
        Получает выручку за указанный период.
        
        Args:
            start_date: Начало периода
            end_date: Конец периода
        
        Returns:
            int: Сумма всех завершённых заказов за период
        """
        try:
            # Получаем завершённые заказы за период
            query = select(Order.order_id).where(
                Order.order_status == OrdersStatus.COMPLETED.value,
                Order.created >= start_date,
                Order.created <= end_date
            )
            result = await self.session.execute(query)
            order_ids = result.scalars().all()
            
            if not order_ids:
                return 0
            
            # Суммируем стоимость всех позиций в этих заказах
            revenue_query = select(
                func.sum(OrderItem.price * OrderItem.quantity)
            ).where(
                OrderItem.order_id.in_(order_ids)
            )
            
            revenue_result = await self.session.execute(revenue_query)
            return revenue_result.scalar() or 0
            
        except Exception as e:
            ic(f"Error getting revenue for period: {e}")
            return 0
    
    async def get_completed_orders_count(self, days: Optional[int] = None) -> int:
        """
        Получение количества завершённых заказов.
        
        Args:
            days: Если указано, считает за последние N дней
            
        Returns:
            int: Количество завершённых заказов
        """
        try:
            query = select(func.count()).select_from(Order).where(
                Order.order_status == OrdersStatus.COMPLETED.value
            )
            
            if days:
                from datetime import datetime, timedelta
                cutoff_date = datetime.now() - timedelta(days=days)
                query = query.where(Order.created >= cutoff_date)
            
            result = await self.session.execute(query)
            return result.scalar() or 0
            
        except Exception as e:
            ic(f"Error getting completed orders count: {e}")
            return 0

    # =========================================================================
    # МЕТОДЫ ДЛЯ РАБОТЫ С ЧАСАМИ ДОСТАВКИ
    # =========================================================================
    
    async def update_delivery_hours(
        self, 
        order_id: int, 
        hour_from: int, 
        hour_to: Optional[int] = None
    ) -> Optional[Order]:
        """
        Обновление часов доставки заказа.
        
        Args:
            order_id: ID заказа
            hour_from: Час начала доставки (0-23)
            hour_to: Час окончания доставки (0-23), если None то только час начала
        
        Returns:
            Optional[Order]: Обновлённый заказ или None
        """
        try:
            update_data = {"delivery_hour_from": hour_from}
            if hour_to is not None:
                update_data["delivery_hour_to"] = hour_to
            
            query = (
                update(Order)
                .where(Order.order_id == order_id)
                .values(**update_data)
                .returning(Order)
            )
            result = await self.session.execute(query)
            await self.session.flush()
            return result.scalar_one_or_none()
        except Exception as e:
            ic(f"Error updating delivery hours: {e}")
            return None
    
    async def get_delivery_hours(self, order_id: int) -> Dict[str, Optional[int]]:
        """
        Получение часов доставки заказа.
        
        Returns:
            Dict: {'hour_from': int|None, 'hour_to': int|None}
        """
        try:
            query = select(
                Order.delivery_hour_from,
                Order.delivery_hour_to
            ).where(Order.order_id == order_id)
            
            result = await self.session.execute(query)
            row = result.first()
            
            if row:
                return {
                    'hour_from': row[0],
                    'hour_to': row[1]
                }
            return {'hour_from': None, 'hour_to': None}
        except Exception as e:
            ic(f"Error getting delivery hours: {e}")
            return {'hour_from': None, 'hour_to': None}