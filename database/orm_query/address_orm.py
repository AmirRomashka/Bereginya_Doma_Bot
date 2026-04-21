# database/orm_query/address_orm.py
"""
Address Repository Module
=========================

This module provides repository for user address operations.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from icecream import ic

from database.models.users_model import UserAdress, Users
from database.models.delivery_status_model import DeliveryStatus


class AddressRepository:
    """
    Репозиторий для работы с адресами пользователей.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    # =========================================================================
    # GET METHODS
    # =========================================================================
    
    async def get_by_id(self, address_id: int) -> Optional[UserAdress]:
        """Получает адрес по ID."""
        try:
            query = select(UserAdress).where(UserAdress.adress_id == address_id)
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            ic(f"Error getting address by id {address_id}: {e}")
            return None
    
    async def get_by_user_id(self, user_id: int) -> List[UserAdress]:
        """Получает все адреса пользователя."""
        try:
            query = select(UserAdress).where(UserAdress.user_id == user_id)
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            ic(f"Error getting addresses for user {user_id}: {e}")
            return []
    
    async def get_all(self, limit: int = 100) -> List[UserAdress]:
        """Получает все адреса (для админки)."""
        try:
            query = select(UserAdress).limit(limit)
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            ic(f"Error getting all addresses: {e}")
            return []
    
    async def get_all_with_users(self) -> List[Dict[str, Any]]:
        """Получает все адреса с информацией о пользователях и статусах доставки."""
        try:
            query = select(
                UserAdress.adress_id,
                UserAdress.adress_name,
                UserAdress.coordinates,
                UserAdress.street,
                UserAdress.house,
                UserAdress.building,
                UserAdress.apartment,
                UserAdress.floor,
                UserAdress.entrance,
                UserAdress.intercom,
                UserAdress.comment,
                UserAdress.adress_status,
                UserAdress.user_id,
                Users.full_name.label("user_name"),
                Users.username,
                Users.phone_number,
                DeliveryStatus.name.label("status_name"),
                DeliveryStatus.price.label("status_price")
            ).outerjoin(
                Users, UserAdress.user_id == Users.user_id
            ).outerjoin(
                DeliveryStatus, UserAdress.adress_status == DeliveryStatus.status_id
            ).order_by(UserAdress.adress_id)
            
            result = await self.session.execute(query)
            return [dict(row._mapping) for row in result.all()]
        except Exception as e:
            ic(f"Error getting addresses with users: {e}")
            return []
    
    async def get_by_status(self, status_id: int) -> List[UserAdress]:
        """Получает адреса с определённым статусом доставки."""
        try:
            query = select(UserAdress).where(
                UserAdress.adress_status == status_id  # ✅ int, а не str
            )
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            ic(f"Error getting addresses by status {status_id}: {e}")
            return []
    
    # =========================================================================
    # CREATE METHODS
    # =========================================================================
    
    async def create(
        self,
        user_id: int,
        adress_name: str,
        coordinates: str,
        street: Optional[str] = None,
        house: Optional[str] = None,
        building: Optional[str] = None,
        apartment: Optional[str] = None,
        floor: Optional[str] = None,
        entrance: Optional[str] = None,
        intercom: Optional[str] = None,
        comment: Optional[str] = None,
        status_id: Optional[int] = None
    ) -> Optional[UserAdress]:
        """
        Создаёт новый адрес пользователя с деталями.
        
        Args:
            user_id: ID пользователя
            adress_name: Название адреса (Дом, Работа, Дача)
            coordinates: Координаты адреса
            street: Улица
            house: Номер дома
            building: Корпус/строение
            apartment: Квартира/офис
            floor: Этаж
            entrance: Подъезд
            intercom: Код домофона
            comment: Комментарий для курьера
            status_id: ID статуса доставки (зоны)
        """
        try:
            address = UserAdress(
                user_id=user_id,
                adress_name=adress_name,
                coordinates=coordinates,
                street=street,
                house=house,
                building=building,
                apartment=apartment,
                floor=floor,
                entrance=entrance,
                intercom=intercom,
                comment=comment,
                adress_status=status_id if status_id else None  # ✅ int, а не str
            )
            self.session.add(address)
            await self.session.commit()
            return address
        except Exception as e:
            ic(f"Error creating address: {e}")
            await self.session.rollback()
            return None
    
    # =========================================================================
    # UPDATE METHODS
    # =========================================================================
    
    async def update(
        self,
        address_id: int,
        adress_name: Optional[str] = None,
        coordinates: Optional[str] = None,
        street: Optional[str] = None,
        house: Optional[str] = None,
        building: Optional[str] = None,
        apartment: Optional[str] = None,
        floor: Optional[str] = None,
        entrance: Optional[str] = None,
        intercom: Optional[str] = None,
        comment: Optional[str] = None,
        status_id: Optional[int] = None
    ) -> bool:
        """
        Обновляет адрес пользователя.
        """
        try:
            update_data = {}
            
            if adress_name is not None:
                update_data["adress_name"] = adress_name
            if coordinates is not None:
                update_data["coordinates"] = coordinates
            if street is not None:
                update_data["street"] = street
            if house is not None:
                update_data["house"] = house
            if building is not None:
                update_data["building"] = building
            if apartment is not None:
                update_data["apartment"] = apartment
            if floor is not None:
                update_data["floor"] = floor
            if entrance is not None:
                update_data["entrance"] = entrance
            if intercom is not None:
                update_data["intercom"] = intercom
            if comment is not None:
                update_data["comment"] = comment
            if status_id is not None:
                update_data["adress_status"] = status_id if status_id else None  # ✅ int, а не str
            
            if not update_data:
                return True
            
            query = (
                update(UserAdress)
                .where(UserAdress.adress_id == address_id)
                .values(**update_data)
            )
            await self.session.execute(query)
            await self.session.commit()
            return True
        except Exception as e:
            ic(f"Error updating address {address_id}: {e}")
            await self.session.rollback()
            return False
    
    async def update_status(
        self,
        address_id: int,
        status_id: Optional[int] = None
    ) -> bool:
        """
        Обновляет статус адреса (привязывает к зоне доставки).
        """
        return await self.update(address_id, status_id=status_id)
    
    async def update_coordinates(
        self,
        address_id: int,
        coordinates: str
    ) -> bool:
        """Обновляет координаты адреса."""
        return await self.update(address_id, coordinates=coordinates)
    
    async def update_name(
        self,
        address_id: int,
        name: str
    ) -> bool:
        """Обновляет название адреса."""
        return await self.update(address_id, adress_name=name)
    
    async def update_details(
        self,
        address_id: int,
        street: Optional[str] = None,
        house: Optional[str] = None,
        building: Optional[str] = None,
        apartment: Optional[str] = None,
        floor: Optional[str] = None,
        entrance: Optional[str] = None,
        intercom: Optional[str] = None,
        comment: Optional[str] = None
    ) -> bool:
        """Обновляет детали адреса."""
        return await self.update(
            address_id,
            street=street,
            house=house,
            building=building,
            apartment=apartment,
            floor=floor,
            entrance=entrance,
            intercom=intercom,
            comment=comment
        )
    
    # =========================================================================
    # DELETE METHODS
    # =========================================================================
    
    async def delete(self, address_id: int) -> bool:
        """Удаляет адрес."""
        try:
            # Проверяем, есть ли заказы с этим адресом
            from database.models.orders_model import Order
            query = select(Order).where(Order.address_id == address_id)
            result = await self.session.execute(query)
            if result.first():
                ic(f"Cannot delete address {address_id}: has orders")
                return False
            
            query = delete(UserAdress).where(UserAdress.adress_id == address_id)
            result = await self.session.execute(query)
            await self.session.commit()
            return result.rowcount > 0
        except Exception as e:
            ic(f"Error deleting address: {e}")
            await self.session.rollback()
            return False
    
    async def delete_by_user(self, user_id: int) -> int:
        """Удаляет все адреса пользователя."""
        try:
            query = delete(UserAdress).where(UserAdress.user_id == user_id)
            result = await self.session.execute(query)
            await self.session.commit()
            return result.rowcount
        except Exception as e:
            ic(f"Error deleting addresses for user {user_id}: {e}")
            await self.session.rollback()
            return 0
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    async def get_default_address(self, user_id: int) -> Optional[UserAdress]:
        """Получает основной адрес пользователя (первый по дате создания)."""
        try:
            query = select(UserAdress).where(
                UserAdress.user_id == user_id
            ).order_by(UserAdress.created.asc()).limit(1)
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            ic(f"Error getting default address for user {user_id}: {e}")
            return None
    
    async def get_addresses_count(self, user_id: int) -> int:
        """Получает количество адресов пользователя."""
        try:
            query = select(UserAdress).where(UserAdress.user_id == user_id)
            result = await self.session.execute(query)
            return len(result.scalars().all())
        except Exception as e:
            ic(f"Error counting addresses for user {user_id}: {e}")
            return 0
    
    async def search_by_name(self, search_term: str) -> List[UserAdress]:
        """Ищет адреса по названию (частичное совпадение)."""
        try:
            query = select(UserAdress).where(
                UserAdress.adress_name.ilike(f"%{search_term}%")
            )
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            ic(f"Error searching addresses by name: {e}")
            return []
    
    async def search_by_street(self, search_term: str) -> List[UserAdress]:
        """Ищет адреса по улице (частичное совпадение)."""
        try:
            query = select(UserAdress).where(
                UserAdress.street.ilike(f"%{search_term}%")
            )
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            ic(f"Error searching addresses by street: {e}")
            return []
    
    async def get_addresses_summary(self, user_id: int) -> List[Dict[str, Any]]:
        """Получает краткую информацию об адресах пользователя для отображения."""
        addresses = await self.get_by_user_id(user_id)
        result = []
        
        for addr in addresses:
            # Формируем краткий адрес для отображения
            short_address = f"{addr.street}, {addr.house}" if addr.street else addr.adress_name
            if addr.apartment:
                short_address += f", кв. {addr.apartment}"
            if addr.building:
                short_address += f", корп. {addr.building}"
            
            result.append({
                "id": addr.adress_id,
                "name": addr.adress_name,
                "address": short_address,
                "full_address": self._format_full_address(addr),
                "coordinates": addr.coordinates,
                "has_zone": addr.adress_status is not None
            })
        
        return result
    
    def _format_full_address(self, address: UserAdress) -> str:
        """Форматирует полный адрес для отображения."""
        parts = []
        
        if address.street:
            parts.append(address.street)
        if address.house:
            parts.append(address.house)
        if address.building:
            parts.append(f"корп. {address.building}")
        if address.apartment:
            parts.append(f"кв. {address.apartment}")
        
        address_line = ", ".join(parts)
        
        details = []
        if address.floor:
            details.append(f"этаж {address.floor}")
        if address.entrance:
            details.append(f"подъезд {address.entrance}")
        if address.intercom:
            details.append(f"домофон {address.intercom}")
        
        details_line = ", ".join(details) if details else ""
        
        result = address_line
        if details_line:
            result += f"\n📍 {details_line}"
        if address.comment:
            result += f"\n📝 {address.comment}"
        
        return result