"""
Order Model Module
==================

This module defines the Order model for storing customer orders.
"""

from typing import Optional

from sqlalchemy import String, Text, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from ..enumirate.orders_enum import OrdersStatus
from .base_model import Base


class Order(Base):
    """
    Модель заказа.
    
    Содержит информацию о заказе пользователя: статус, комментарий,
    фото чека, а также связи с пользователем и адресом доставки.
    """
    
    __tablename__ = "order"

    order_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    order_status: Mapped[str] = mapped_column(
        String(50), 
        default=OrdersStatus.ASSEMBLY.value
    )

    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    photo: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE")
    )

    address_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("user_adress.adress_id", ondelete="SET NULL"),
        nullable=True
    )

    # =========================================================================
    # ДОСТАВКА — ВРЕМЕННОЙ ДИАПАЗОН
    # =========================================================================
    
    # Час начала доставки (0-23)
    delivery_hour_from: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Час начала доставки (0-23)"
    )
    
    # Час окончания доставки (0-23)
    delivery_hour_to: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Час окончания доставки (0-23)"
    )