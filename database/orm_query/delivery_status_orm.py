# database/orm_query/delivery_status_orm.py

"""
Delivery Status Repository Module
=================================

This module provides repository for delivery status operations.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy import select, update, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession
from icecream import ic

from database.models.delivery_status_model import DeliveryStatus, OrderDeliveryStatus
from database.models.users_model import UserAdress


class DeliveryStatusRepository:
    """
    Репозиторий для работы со статусами доставки (зонами доставки с ценами).
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    # =========================================================================
    # GET METHODS
    # =========================================================================
    
    async def get_all(self, only_active: bool = False) -> List[DeliveryStatus]:
        """Получает все статусы доставки."""
        try:
            query = select(DeliveryStatus).order_by(DeliveryStatus.sort_order)
            
            if only_active:
                query = query.where(DeliveryStatus.is_active == True)
            
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            ic(f"Error getting all delivery statuses: {e}")
            return []
    
    async def get_by_id(self, status_id: int) -> Optional[DeliveryStatus]:
        """Получает статус по ID."""
        try:
            query = select(DeliveryStatus).where(DeliveryStatus.status_id == status_id)
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            ic(f"Error getting delivery status by id {status_id}: {e}")
            return None
    
    async def get_by_name(self, name: str) -> Optional[DeliveryStatus]:
        """Получает статус по названию."""
        try:
            query = select(DeliveryStatus).where(DeliveryStatus.name == name)
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            ic(f"Error getting delivery status by name {name}: {e}")
            return None
    
    async def get_active(self) -> List[DeliveryStatus]:
        """Получает активные статусы доставки."""
        return await self.get_all(only_active=True)
    
    # =========================================================================
    # CREATE METHODS
    # =========================================================================
    
    async def create(
        self,
        name: str,
        price: int,
        description: Optional[str] = None,
        requires_address: bool = True,
        sort_order: int = 0
    ) -> Optional[DeliveryStatus]:
        """Создаёт новый статус доставки."""
        try:
            status = DeliveryStatus(
                name=name,
                price=price,
                description=description,
                requires_address=requires_address,
                sort_order=sort_order
            )
            self.session.add(status)
            await self.session.commit()
            return status
        except Exception as e:
            ic(f"Error creating delivery status: {e}")
            await self.session.rollback()
            return None
    
    # =========================================================================
    # UPDATE METHODS
    # =========================================================================
    
    async def update(
        self,
        status_id: int,
        name: Optional[str] = None,
        price: Optional[int] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None,
        requires_address: Optional[bool] = None,
        sort_order: Optional[int] = None
    ) -> bool:
        """Обновляет статус доставки."""
        try:
            update_data = {}
            if name is not None:
                update_data["name"] = name
            if price is not None:
                update_data["price"] = price
            if description is not None:
                update_data["description"] = description
            if is_active is not None:
                update_data["is_active"] = is_active
            if requires_address is not None:
                update_data["requires_address"] = requires_address
            if sort_order is not None:
                update_data["sort_order"] = sort_order
            
            if not update_data:
                return True
            
            query = (
                update(DeliveryStatus)
                .where(DeliveryStatus.status_id == status_id)
                .values(**update_data)
            )
            await self.session.execute(query)
            await self.session.commit()
            return True
        except Exception as e:
            ic(f"Error updating delivery status {status_id}: {e}")
            await self.session.rollback()
            return False
    
    async def update_price(self, status_id: int, price: int) -> bool:
        """Обновляет цену статуса доставки."""
        return await self.update(status_id, price=price)
    
    async def toggle_active(self, status_id: int) -> bool:
        """Включает/выключает статус."""
        status = await self.get_by_id(status_id)
        if not status:
            return False
        return await self.update(status_id, is_active=not status.is_active)
    
    # =========================================================================
    # DELETE METHODS
    # =========================================================================
    
    async def delete(self, status_id: int) -> bool:
        """Удаляет статус (только если нет связанных заказов или адресов)."""
        try:
            # Проверяем, есть ли заказы с этим статусом
            query = select(OrderDeliveryStatus).where(
                OrderDeliveryStatus.status_id == status_id
            )
            result = await self.session.execute(query)
            if result.first():
                ic(f"Cannot delete delivery status {status_id}: has orders")
                return False
            
            # Проверяем, есть ли адреса с этим статусом
            query = select(UserAdress).where(
                UserAdress.adress_status == str(status_id)
            )
            result = await self.session.execute(query)
            if result.first():
                ic(f"Cannot delete delivery status {status_id}: has addresses")
                return False
            
            query = delete(DeliveryStatus).where(DeliveryStatus.status_id == status_id)
            result = await self.session.execute(query)
            await self.session.commit()
            return result.rowcount > 0
        except Exception as e:
            ic(f"Error deleting delivery status {status_id}: {e}")
            await self.session.rollback()
            return False
    
    # =========================================================================
    # ORDER DELIVERY STATUS METHODS
    # =========================================================================
    
    async def assign_to_order(
        self,
        order_id: int,
        status_id: int,
        price_at_order: Optional[int] = None,
        address_id: Optional[int] = None
    ) -> bool:
        """Назначает статус доставки заказу."""
        try:
            # Получаем статус для цены
            status = await self.get_by_id(status_id)
            if not status:
                return False
            
            order_status = OrderDeliveryStatus(
                order_id=order_id,
                status_id=status_id,
                price_at_order=price_at_order or status.price,
                address_id=address_id
            )
            self.session.add(order_status)
            await self.session.commit()
            return True
        except Exception as e:
            ic(f"Error assigning delivery status to order: {e}")
            await self.session.rollback()
            return False
    
    async def get_order_delivery_status(self, order_id: int) -> Optional[Dict[str, Any]]:
        """Получает статус доставки для заказа."""
        try:
            query = select(
                OrderDeliveryStatus.id,
                OrderDeliveryStatus.order_id,
                OrderDeliveryStatus.status_id,
                OrderDeliveryStatus.price_at_order,
                OrderDeliveryStatus.address_id,
                DeliveryStatus.name.label("status_name"),
                DeliveryStatus.description.label("status_description")
            ).join(
                DeliveryStatus,
                OrderDeliveryStatus.status_id == DeliveryStatus.status_id
            ).where(
                OrderDeliveryStatus.order_id == order_id
            )
            result = await self.session.execute(query)
            row = result.first()
            
            if row:
                return {
                    "delivery_id": row.id,
                    "order_id": row.order_id,
                    "status_id": row.status_id,
                    "status_name": row.status_name,
                    "status_description": row.status_description,
                    "price": row.price_at_order,
                    "address_id": row.address_id
                }
            return None
        except Exception as e:
            ic(f"Error getting order delivery status: {e}")
            return None
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    async def get_stats(self) -> Dict[str, Any]:
        """Получает статистику по статусам доставки."""
        try:
            all_statuses = await self.get_all()
            active_statuses = await self.get_active()
            
            # Считаем количество адресов с каждым статусом
            address_counts = {}
            for status in all_statuses:
                query = select(UserAdress).where(
                    UserAdress.adress_status == str(status.status_id)
                )
                result = await self.session.execute(query)
                address_counts[status.status_id] = len(result.scalars().all())
            
            return {
                "total": len(all_statuses),
                "active": len(active_statuses),
                "inactive": len(all_statuses) - len(active_statuses),
                "addresses_by_status": address_counts
            }
        except Exception as e:
            ic(f"Error getting delivery status stats: {e}")
            return {
                "total": 0,
                "active": 0,
                "inactive": 0,
                "addresses_by_status": {}
            }
    
    async def get_by_address_count(self) -> List[Dict[str, Any]]:
        """Получает статусы с количеством привязанных адресов."""
        try:
            statuses = await self.get_all()
            result = []
            
            for status in statuses:
                query = select(UserAdress).where(
                    UserAdress.adress_status == str(status.status_id)
                )
                addr_result = await self.session.execute(query)
                count = len(addr_result.scalars().all())
                
                result.append({
                    "status_id": status.status_id,
                    "name": status.name,
                    "price": status.price,
                    "address_count": count,
                    "is_active": status.is_active
                })
            
            return result
        except Exception as e:
            ic(f"Error getting statuses by address count: {e}")
            return []