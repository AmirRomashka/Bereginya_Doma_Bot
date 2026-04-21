from sqlalchemy import String, Text, ForeignKey, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column

from ..enumirate.dish_enum import DishStatus
from .base_model import Base

class Dishes(Base):

    __tablename__ = "dishes"

    dish_id : Mapped[int] = mapped_column(primary_key = True, autoincrement = True)

    image : Mapped[str] = mapped_column(Text, nullable = True)

    name : Mapped[str] = mapped_column(String(50), unique = True, nullable = False)

    description : Mapped[str] = mapped_column(Text, nullable = True)

    description_entities: Mapped[dict] = mapped_column(JSON, nullable=True)

    price : Mapped[int] = mapped_column(Integer(), nullable = False)

    status : Mapped[str] = mapped_column(String(20), default = DishStatus.COMMON.value)

    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.category_id", ondelete="CASCADE")
    )