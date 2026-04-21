from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column


from .base_model import Base


class OrderItem(Base):
    __tablename__ = "order_items"
    
    item_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("order.order_id", ondelete="CASCADE"))
    dish_id: Mapped[int] = mapped_column(ForeignKey("dishes.dish_id", ondelete="CASCADE"))
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  
    price: Mapped[int] = mapped_column(Integer, nullable=False) 