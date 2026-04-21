"""
Feedback Model Module
=====================

This module defines the Feedback model for storing user reviews and feedback.
"""

from typing import Optional

from sqlalchemy import String, Text, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class Feedback(Base):
    """
    Модель отзыва пользователя.
    
    Хранит отзывы и оценки пользователей о качестве обслуживания,
    блюдах и доставке.
    """
    
    __tablename__ = "feedback"
    
    feedback_id: Mapped[int] = mapped_column(
        primary_key=True, 
        autoincrement=True,
        comment="Уникальный ID отзыва"
    )
    
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        comment="ID пользователя, оставившего отзыв"
    )
    
    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Текст отзыва"
    )
    

    
    def __repr__(self) -> str:
        """Строковое представление отзыва."""
        return f"<Feedback {self.feedback_id}: User {self.user_id}>"