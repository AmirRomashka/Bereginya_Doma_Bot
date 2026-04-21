from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base

class Categories(Base):

    __tablename__ = "categories"

    category_id : Mapped[int] = mapped_column(primary_key = True, autoincrement = True)

    name : Mapped[str] = mapped_column(String(50), unique = True, nullable = False)

    
