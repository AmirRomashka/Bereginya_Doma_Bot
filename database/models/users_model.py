# database/models/users_model.py

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Date, String, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import Base
from ..enumirate.users_enum import UserStatus


class Users(Base):
    """Модель пользователя."""
    
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    username: Mapped[str] = mapped_column(String(50), nullable=True)  
    phone_number: Mapped[str] = mapped_column(String(20), nullable=True)
    birth_date: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(10), default=UserStatus.COMMON.value)
    
    # Связь с адресами (используется)
    addresses: Mapped[list["UserAdress"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )


class UserAdress(Base):
    """
    Адрес пользователя.
    
    Связан с пользователем через user_id и со статусом доставки через adress_status.
    """
    
    __tablename__ = "user_adress"

    adress_id: Mapped[int] = mapped_column(
        BigInteger, 
        primary_key=True, 
        autoincrement=True
    )
    
    adress_name: Mapped[str] = mapped_column(String(100), nullable=False)
    coordinates: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # =========================================================================
    # ДЕТАЛИ АДРЕСА
    # =========================================================================
    street: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)      # Улица
    house: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)        # Дом
    building: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)     # Корпус/строение
    apartment: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)    # Квартира/офис
    floor: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)        # Этаж
    entrance: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)     # Подъезд
    intercom: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)     # Домофон
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)            # Комментарий (как пройти)
    
    adress_status: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey(
            "delivery_statuses.status_id", 
            ondelete="CASCADE"
        ),
        nullable=True
    )
    
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Связь с пользователем (используется)
    user: Mapped["Users"] = relationship(back_populates="addresses")