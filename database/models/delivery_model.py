# database/models/delivery_model.py

from sqlalchemy import Integer, DateTime, Boolean, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, time
from .base_model import Base


class DeliveryDate(Base):
    """
    Доступные даты доставки.
    """
    __tablename__ = "delivery_dates"
    
    delivery_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Дата и время доставки (всегда устанавливается на 23:59:59)
    delivery_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    # Доступна ли для выбора
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Лимит заказов на эту дату (None = без лимита)
    order_limit: Mapped[int] = mapped_column(Integer, nullable=True)
    
    # Текущее количество заказов
    current_orders: Mapped[int] = mapped_column(Integer, default=0)
    
    # Дополнительная информация
    note: Mapped[str] = mapped_column(String(200), nullable=True)
    
    # Создана ли вручную или автоматически
    is_auto_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class OrderDelivery(Base):
    """
    Связь заказа с датой доставки.
    """
    __tablename__ = "order_deliveries"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    order_id: Mapped[int] = mapped_column(ForeignKey("order.order_id", ondelete="CASCADE"))
    delivery_id: Mapped[int] = mapped_column(ForeignKey("delivery_dates.delivery_id", ondelete="CASCADE"))
    
    selected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)