"""
Delivery Repository Module
==========================

This module provides repository for delivery date operations.
"""

from datetime import datetime, timedelta, time
from typing import List, Optional, Dict, Any
from sqlalchemy import select, update, delete, text
from sqlalchemy.ext.asyncio import AsyncSession
from icecream import ic

from database.models.delivery_model import DeliveryDate, OrderDelivery
from database.enumirate.orders_enum import OrdersStatus


class DeliveryRepository:
    """
    Репозиторий для работы с датами доставки.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    # =========================================================================
    # HELPER FUNCTIONS
    # =========================================================================
    
    def _set_end_of_day(self, dt: datetime) -> datetime:
        """Устанавливает время на 23:59:59 для указанной даты."""
        return datetime(dt.year, dt.month, dt.day, 23, 59, 59)
    
    # =========================================================================
    # GET METHODS
    # =========================================================================
    
    async def get_available_dates(
        self,
        min_hours_ahead: int = 2
    ) -> List[DeliveryDate]:
        """
        Получает доступные даты доставки.
        Минимальное время до доставки — min_hours_ahead часов.
        """
        now = datetime.now()
        min_date = now + timedelta(hours=min_hours_ahead)
        
        query = select(DeliveryDate).where(
            DeliveryDate.is_available == True,
            DeliveryDate.delivery_date >= min_date,
            DeliveryDate.delivery_date >= now
        ).order_by(DeliveryDate.delivery_date.asc())
        
        result = await self.session.execute(query)
        dates = result.scalars().all()
        
        # Фильтруем те, где не превышен лимит
        available = []
        for date in dates:
            if date.order_limit is None or date.current_orders < date.order_limit:
                available.append(date)
        
        return available
    
    async def get_by_id(self, delivery_id: int) -> Optional[DeliveryDate]:
        """Получает дату доставки по ID."""
        query = select(DeliveryDate).where(DeliveryDate.delivery_id == delivery_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_all(
        self,
        include_unavailable: bool = False,
        limit: int = 50
    ) -> List[DeliveryDate]:
        """Получает все даты доставки."""
        query = select(DeliveryDate).order_by(DeliveryDate.delivery_date.asc())
        
        if not include_unavailable:
            query = query.where(DeliveryDate.is_available == True)
        
        query = query.limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_upcoming(self, days: int = 14) -> List[DeliveryDate]:
        """Получает предстоящие даты доставки."""
        now = datetime.now()
        future = now + timedelta(days=days)
        
        query = select(DeliveryDate).where(
            DeliveryDate.delivery_date >= now,
            DeliveryDate.delivery_date <= future
        ).order_by(DeliveryDate.delivery_date.asc())
        
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_order_delivery(self, order_id: int) -> Optional[DeliveryDate]:
        """Получает дату доставки заказа."""
        query = (
            select(DeliveryDate)
            .join(OrderDelivery, OrderDelivery.delivery_id == DeliveryDate.delivery_id)
            .where(OrderDelivery.order_id == order_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_orders_by_delivery_date(
        self,
        delivery_id: int,
        include_details: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Получает все заказы, привязанные к дате доставки.
        
        Args:
            delivery_id: ID даты доставки
            include_details: Если True, получает полные детали заказа
        
        Returns:
            List[Dict[str, Any]]: Список заказов с деталями
        """
        try:
            # Получаем заказы, привязанные к дате
            query = text("""
                SELECT 
                    o.order_id, 
                    o.order_status, 
                    o.user_id, 
                    o.comment, 
                    o.photo,
                    o.address_id
                FROM "order" o
                JOIN order_deliveries od ON o.order_id = od.order_id
                WHERE od.delivery_id = :delivery_id
            """)
            
            result = await self.session.execute(query, {"delivery_id": delivery_id})
            orders_raw = result.all()
            
            orders = []
            for row in orders_raw:
                order_data = {
                    "order_id": row[0],
                    "order_status": row[1],
                    "user_id": row[2],
                    "comment": row[3],
                    "photo": row[4],
                    "address_id": row[5]
                }
                
                # Если нужны детали, получаем их из OrderRepository
                if include_details:
                    from database.orm_query.orders_orm import OrderRepository
                    order_repo = OrderRepository(self.session)
                    order_details = await order_repo.get_order_with_details(row[0])
                    if order_details:
                        order_data.update({
                            "total": order_details.get("total", 0),
                            "items": order_details.get("items", [])
                        })
                
                orders.append(order_data)
            
            return orders
        except Exception as e:
            ic(f"Error getting orders by delivery date {delivery_id}: {e}")
            return []
    
    async def get_ready_orders_by_delivery_date(
        self
    ) -> Dict[int, Dict[str, Any]]:
        """
        Получает заказы в статусе READY_FOR_DELIVERY, сгруппированные по датам доставки.
        
        Returns:
            Dict[int, Dict]: Словарь вида {delivery_id: {delivery_date, orders}}
        """
        try:
            from database.orm_query.orders_orm import OrderRepository
            order_repo = OrderRepository(self.session)
            
            # Получаем все заказы в статусе READY_FOR_DELIVERY
            ready_orders = await order_repo.get_orders_by_status(OrdersStatus.READY_FOR_DELIVERY)
            
            result = {}
            for order in ready_orders:
                delivery_date = await self.get_order_delivery(order.order_id)
                if delivery_date:
                    delivery_id = delivery_date.delivery_id
                    
                    if delivery_id not in result:
                        result[delivery_id] = {
                            "delivery_id": delivery_id,
                            "delivery_date": delivery_date,
                            "orders": []
                        }
                    
                    order_details = await order_repo.get_order_with_details(order.order_id)
                    result[delivery_id]["orders"].append({
                        "order_id": order.order_id,
                        "user_id": order.user_id,
                        "total": order_details.get("total", 0) if order_details else 0,
                        "comment": order.comment,
                        "items": order_details.get("items", []) if order_details else []
                    })
            
            return result
        except Exception as e:
            ic(f"Error getting ready orders by delivery date: {e}")
            return {}
    
    async def get_delivery_stats_with_orders(self) -> Dict[str, Any]:
        """
        Получает расширенную статистику по датам доставки с разбивкой по статусам заказов.
        """
        try:
            all_dates = await self.get_all(include_unavailable=True)
            now = datetime.now()
            
            stats = {
                "total": len(all_dates),
                "available": 0,
                "upcoming": 0,
                "past": 0,
                "total_orders": 0,
                "dates_with_ready_orders": 0
            }
            
            for date in all_dates:
                if date.is_available:
                    stats["available"] += 1
                
                if date.delivery_date > now:
                    stats["upcoming"] += 1
                else:
                    stats["past"] += 1
                
                stats["total_orders"] += date.current_orders
                
                # Проверяем, есть ли заказы в статусе READY_FOR_DELIVERY
                orders = await self.get_orders_by_delivery_date(date.delivery_id, include_details=False)
                for order in orders:
                    if order.get("order_status") == OrdersStatus.READY_FOR_DELIVERY.value:
                        stats["dates_with_ready_orders"] += 1
                        break
            
            return stats
        except Exception as e:
            ic(f"Error getting delivery stats with orders: {e}")
            return {
                "total": 0,
                "available": 0,
                "upcoming": 0,
                "past": 0,
                "total_orders": 0,
                "dates_with_ready_orders": 0
            }
    
    # =========================================================================
    # CREATE METHODS
    # =========================================================================
    
    async def create(
        self,
        delivery_date: datetime,
        order_limit: Optional[int] = None,
        note: Optional[str] = None,
        is_auto_generated: bool = False
    ) -> Optional[DeliveryDate]:
        """Добавляет новую дату доставки с временем 23:59:59."""
        try:
            # Устанавливаем время на 23:59:59
            delivery_date = self._set_end_of_day(delivery_date)
            
            delivery = DeliveryDate(
                delivery_date=delivery_date,
                order_limit=order_limit,
                note=note,
                is_auto_generated=is_auto_generated
            )
            self.session.add(delivery)
            await self.session.commit()
            return delivery
        except Exception as e:
            ic(f"Error adding delivery date: {e}")
            await self.session.rollback()
            return None
    
    async def create_many(
        self,
        dates: List[datetime],
        order_limit: Optional[int] = None,
        note: Optional[str] = None
    ) -> int:
        """Создаёт несколько дат доставки."""
        created = 0
        for delivery_date in dates:
            result = await self.create(delivery_date, order_limit, note, is_auto_generated=True)
            if result:
                created += 1
        return created
    
    async def auto_generate(
        self,
        days_ahead: int = 14,
        default_limit: int = 20
    ) -> int:
        """
        Автоматически генерирует даты доставки на days_ahead дней вперёд.
        Время доставки всегда устанавливается на 23:59:59.
        """
        now = datetime.now()
        created = 0
        
        for i in range(1, days_ahead + 1):
            # Время 23:59:59
            delivery_date = datetime(
                year=now.year,
                month=now.month,
                day=now.day,
                hour=23,
                minute=59,
                second=59
            ) + timedelta(days=i)
            
            # Если сегодняшняя дата уже прошла 23:59:59, то завтра
            if delivery_date <= now:
                delivery_date += timedelta(days=1)
            
            # Проверяем, существует ли уже
            existing = await self.get_by_date(delivery_date)
            if existing:
                continue
            
            # Создаём
            delivery = DeliveryDate(
                delivery_date=delivery_date,
                order_limit=default_limit,
                is_auto_generated=True,
                is_available=True
            )
            self.session.add(delivery)
            created += 1
        
        await self.session.commit()
        return created
    
    async def get_by_date(self, date: datetime) -> Optional[DeliveryDate]:
        """Получает дату доставки по точной дате (игнорируя время)."""
        # Приводим к началу дня для поиска
        start_of_day = datetime(date.year, date.month, date.day, 0, 0, 0)
        end_of_day = datetime(date.year, date.month, date.day, 23, 59, 59)
        
        query = select(DeliveryDate).where(
            DeliveryDate.delivery_date >= start_of_day,
            DeliveryDate.delivery_date <= end_of_day
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    # =========================================================================
    # UPDATE METHODS
    # =========================================================================
    
    async def update(
        self,
        delivery_id: int,
        is_available: Optional[bool] = None,
        order_limit: Optional[int] = None,
        note: Optional[str] = None,
        delivery_date: Optional[datetime] = None
    ) -> bool:
        """Обновляет дату доставки."""
        try:
            update_data = {}
            if is_available is not None:
                update_data["is_available"] = is_available
            if order_limit is not None:
                update_data["order_limit"] = order_limit
            if note is not None:
                update_data["note"] = note
            if delivery_date is not None:
                # Устанавливаем время на 23:59:59
                update_data["delivery_date"] = self._set_end_of_day(delivery_date)
            
            if not update_data:
                return True
            
            query = (
                update(DeliveryDate)
                .where(DeliveryDate.delivery_id == delivery_id)
                .values(**update_data)
            )
            await self.session.execute(query)
            await self.session.commit()
            return True
        except Exception as e:
            ic(f"Error updating delivery date: {e}")
            await self.session.rollback()
            return False
    
    async def set_available(self, delivery_id: int, is_available: bool) -> bool:
        """Устанавливает доступность даты."""
        return await self.update(delivery_id, is_available=is_available)
    
    async def increment_orders_count(self, delivery_id: int) -> bool:
        """Увеличивает счётчик заказов на дату."""
        try:
            delivery = await self.get_by_id(delivery_id)
            if not delivery:
                return False
            
            delivery.current_orders += 1
            if delivery.order_limit and delivery.current_orders >= delivery.order_limit:
                delivery.is_available = False
            
            await self.session.commit()
            return True
        except Exception as e:
            ic(f"Error incrementing orders count: {e}")
            await self.session.rollback()
            return False
    
    async def decrement_orders_count(self, delivery_id: int) -> bool:
        """Уменьшает счётчик заказов на дату."""
        try:
            delivery = await self.get_by_id(delivery_id)
            if not delivery:
                return False
            
            delivery.current_orders = max(0, delivery.current_orders - 1)
            if not delivery.is_available and delivery.current_orders < delivery.order_limit:
                delivery.is_available = True
            
            await self.session.commit()
            return True
        except Exception as e:
            ic(f"Error decrementing orders count: {e}")
            await self.session.rollback()
            return False
    
    # =========================================================================
    # DELETE METHODS
    # =========================================================================
    
    async def delete(self, delivery_id: int, force: bool = False) -> bool:
        """
        Удаляет дату доставки.
        Если force=False — только если нет заказов.
        """
        try:
            # Проверяем, есть ли заказы на эту дату
            if not force:
                query = select(OrderDelivery).where(OrderDelivery.delivery_id == delivery_id)
                result = await self.session.execute(query)
                if result.first():
                    return False
            
            query = delete(DeliveryDate).where(DeliveryDate.delivery_id == delivery_id)
            result = await self.session.execute(query)
            await self.session.commit()
            return result.rowcount > 0
        except Exception as e:
            ic(f"Error deleting delivery date: {e}")
            await self.session.rollback()
            return False
    
    async def delete_old(self, days: int = 30) -> int:
        """Удаляет старые даты доставки."""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Сначала проверяем, есть ли заказы
            query = select(DeliveryDate).where(
                DeliveryDate.delivery_date < cutoff_date,
                DeliveryDate.current_orders == 0
            )
            result = await self.session.execute(query)
            to_delete = result.scalars().all()
            
            deleted = 0
            for date in to_delete:
                if await self.delete(date.delivery_id, force=True):
                    deleted += 1
            
            return deleted
        except Exception as e:
            ic(f"Error deleting old dates: {e}")
            await self.session.rollback()
            return 0
    
    # =========================================================================
    # ORDER DELIVERY METHODS
    # =========================================================================
    
    async def assign_to_order(
        self,
        order_id: int,
        delivery_id: int
    ) -> bool:
        """Назначает дату доставки заказу."""
        try:
            # Проверяем доступность
            delivery = await self.get_by_id(delivery_id)
            if not delivery or not delivery.is_available:
                return False
            
            if delivery.order_limit and delivery.current_orders >= delivery.order_limit:
                return False
            
            # Проверяем, нет ли уже даты у заказа
            existing = await self.get_order_delivery(order_id)
            if existing:
                return False
            
            # Создаём связь
            order_delivery = OrderDelivery(
                order_id=order_id,
                delivery_id=delivery_id
            )
            self.session.add(order_delivery)
            
            # Увеличиваем счётчик
            delivery.current_orders += 1
            if delivery.order_limit and delivery.current_orders >= delivery.order_limit:
                delivery.is_available = False
            
            await self.session.commit()
            return True
        except Exception as e:
            ic(f"Error assigning delivery to order: {e}")
            await self.session.rollback()
            return False
    
    async def unassign_from_order(self, order_id: int) -> bool:
        """Отменяет назначение даты доставки заказу."""
        try:
            # Находим связь
            query = select(OrderDelivery).where(OrderDelivery.order_id == order_id)
            result = await self.session.execute(query)
            order_delivery = result.scalar_one_or_none()
            
            if not order_delivery:
                return False
            
            # Уменьшаем счётчик у даты
            await self.decrement_orders_count(order_delivery.delivery_id)
            
            # Удаляем связь
            await self.session.delete(order_delivery)
            await self.session.commit()
            return True
        except Exception as e:
            ic(f"Error unassigning delivery from order: {e}")
            await self.session.rollback()
            return False
    
    async def get_delivery_with_orders_count(self, delivery_id: int) -> Dict[str, Any]:
        """
        Получает информацию о дате доставки с количеством заказов по статусам.
        """
        try:
            delivery = await self.get_by_id(delivery_id)
            if not delivery:
                return {}
            
            orders = await self.get_orders_by_delivery_date(delivery_id, include_details=False)
            
            status_counts = {
                "accepted": 0,
                "ready": 0,
                "verification": 0,
                "other": 0
            }
            
            for order in orders:
                status = order.get("order_status", "")
                if status == OrdersStatus.ACCEPTED.value:
                    status_counts["accepted"] += 1
                elif status == OrdersStatus.READY_FOR_DELIVERY.value:
                    status_counts["ready"] += 1
                elif status == OrdersStatus.VERIFICATION.value:
                    status_counts["verification"] += 1
                else:
                    status_counts["other"] += 1
            
            return {
                "delivery_id": delivery.delivery_id,
                "delivery_date": delivery.delivery_date,
                "is_available": delivery.is_available,
                "order_limit": delivery.order_limit,
                "current_orders": delivery.current_orders,
                "status_counts": status_counts,
                "orders": orders
            }
        except Exception as e:
            ic(f"Error getting delivery with orders count: {e}")
            return {}
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    async def get_stats(self) -> dict:
        """Получает статистику по датам доставки."""
        all_dates = await self.get_all(include_unavailable=True)
        
        now = datetime.now()
        upcoming = [d for d in all_dates if d.delivery_date > now]
        past = [d for d in all_dates if d.delivery_date <= now]
        
        return {
            "total": len(all_dates),
            "available": len([d for d in all_dates if d.is_available]),
            "upcoming": len(upcoming),
            "past": len(past),
            "total_orders": sum(d.current_orders for d in all_dates)
        }
    
    async def is_date_available(self, delivery_date: datetime) -> bool:
        """Проверяет, доступна ли конкретная дата."""
        # Приводим к началу дня для сравнения
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        delivery_start = delivery_date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Проверяем, не в прошлом ли
        if delivery_start < today_start:
            return False
        
        # Ищем дату в БД
        query = select(DeliveryDate).where(
            DeliveryDate.delivery_date >= delivery_start,
            DeliveryDate.delivery_date <= delivery_start.replace(hour=23, minute=59, second=59)
        )
        result = await self.session.execute(query)
        date_record = result.scalar_one_or_none()
        
        if not date_record:
            return True  # Если даты нет — она доступна по умолчанию
        
        return date_record.is_available and (
            date_record.order_limit is None or
            date_record.current_orders < date_record.order_limit
        )
    
    async def get_next_available_date(self) -> Optional[DeliveryDate]:
        """
        Получает следующую доступную дату доставки.
        """
        now = datetime.now()
        min_date = now + timedelta(hours=2)
        
        query = select(DeliveryDate).where(
            DeliveryDate.is_available == True,
            DeliveryDate.delivery_date >= min_date,
            DeliveryDate.delivery_date >= now
        ).order_by(DeliveryDate.delivery_date.asc()).limit(1)
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()