# database/models/delivery_status_model.py

from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional

from database.models.orders_model import Order
from database.models.users_model import UserAdress

from .base_model import Base


class DeliveryStatus(Base):
    """
    Статусы доставки с ценами.
    Администратор может создавать и редактировать статусы.
    """
    __tablename__ = "delivery_statuses"
    
    status_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Название статуса (например: "Самовывоз", "Курьером", "Экспресс")
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Описание статуса
    description: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Цена доставки
    price: Mapped[int] = mapped_column(Integer, default=0)
    
    # Активен ли статус
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Порядок сортировки
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    
    # Требуется ли подтверждение адреса
    requires_address: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class OrderDeliveryStatus(Base):
    """
    Связь заказа с выбранным статусом доставки.
    """
    __tablename__ = "order_delivery_statuses"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    order_id: Mapped[int] = mapped_column(ForeignKey("order.order_id", ondelete="CASCADE"))
    status_id: Mapped[int] = mapped_column(ForeignKey("delivery_statuses.status_id"))
    
    # Цена на момент заказа (фиксируется)
    price_at_order: Mapped[int] = mapped_column(Integer)
    
    # Выбранный адрес доставки (если требуется)
    address_id: Mapped[int] = mapped_column(ForeignKey("user_adress.adress_id"), nullable=True)
    
    selected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    
    # Связи
    order: Mapped["Order"] = relationship(foreign_keys=[order_id])
    status: Mapped["DeliveryStatus"] = relationship(foreign_keys=[status_id])
    address: Mapped["UserAdress"] = relationship(foreign_keys=[address_id])