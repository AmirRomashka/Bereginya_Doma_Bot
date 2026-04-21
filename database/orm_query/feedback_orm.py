"""
Feedback Repository Module
==========================

This module provides repository for feedback operations.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime

from sqlalchemy import select, update, delete, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from icecream import ic

from database.models.feedback_model import Feedback
from database.models.users_model import Users


class FeedbackRepository:
    """
    Репозиторий для работы с отзывами пользователей.
    """
    
    def __init__(self, session: AsyncSession):
        """
        Инициализация репозитория.
        
        Args:
            session: Сессия базы данных
        """
        self.session = session
    
    # =========================================================================
    # CREATE METHODS
    # =========================================================================
    
    async def create(
        self,
        user_id: int,
        text: str,
        rating: Optional[int] = None,
        feedback_type: str = "general",
        dish_id: Optional[int] = None,
        order_id: Optional[int] = None
    ) -> Optional[Feedback]:
        """
        Создаёт новый отзыв.
        
        Args:
            user_id: ID пользователя
            text: Текст отзыва
            rating: Оценка от 1 до 5 (опционально)
            feedback_type: Тип отзыва (general, dish, delivery)
            dish_id: ID блюда (если отзыв о блюде)
            order_id: ID заказа (если отзыв о заказе)
        
        Returns:
            Optional[Feedback]: Созданный отзыв или None при ошибке
        """
        try:
            # Валидация рейтинга
            if rating is not None and (rating < 1 or rating > 5):
                ic(f"Invalid rating: {rating}. Must be between 1 and 5")
                return None
            
            feedback = Feedback(
                user_id=user_id,
                text=text.strip(),
                rating=rating,
                feedback_type=feedback_type,
                dish_id=dish_id,
                order_id=order_id,
                is_published=True
            )
            self.session.add(feedback)
            await self.session.commit()
            await self.session.refresh(feedback)
            return feedback
        except Exception as e:
            ic(f"Error creating feedback: {e}")
            await self.session.rollback()
            return None
    
    # =========================================================================
    # READ METHODS
    # =========================================================================
    
    async def get_by_id(self, feedback_id: int) -> Optional[Feedback]:
        """
        Получает отзыв по ID.
        
        Args:
            feedback_id: ID отзыва
        
        Returns:
            Optional[Feedback]: Отзыв или None
        """
        try:
            query = select(Feedback).where(Feedback.feedback_id == feedback_id)
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            ic(f"Error getting feedback by id {feedback_id}: {e}")
            return None
    
    async def get_by_user_id(
        self, 
        user_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> List[Feedback]:
        """
        Получает все отзывы пользователя.
        
        Args:
            user_id: ID пользователя
            limit: Максимальное количество отзывов
            offset: Смещение для пагинации
        
        Returns:
            List[Feedback]: Список отзывов пользователя
        """
        try:
            query = (
                select(Feedback)
                .where(Feedback.user_id == user_id)
                .order_by(desc(Feedback.created))
                .limit(limit)
                .offset(offset)
            )
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            ic(f"Error getting feedback for user {user_id}: {e}")
            return []
    
    async def get_all_published(
        self,
        limit: int = 50,
        offset: int = 0,
        feedback_type: Optional[str] = None
    ) -> List[Feedback]:
        """
        Получает все опубликованные отзывы.
        
        Args:
            limit: Максимальное количество отзывов
            offset: Смещение для пагинации
            feedback_type: Фильтр по типу отзыва
        
        Returns:
            List[Feedback]: Список опубликованных отзывов
        """
        try:
            query = select(Feedback).where(Feedback.is_published == True)
            
            if feedback_type:
                query = query.where(Feedback.feedback_type == feedback_type)
            
            query = query.order_by(desc(Feedback.created)).limit(limit).offset(offset)
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            ic(f"Error getting published feedback: {e}")
            return []
    
    async def get_all(
        self,
        limit: int = 100,
        offset: int = 0,
        include_hidden: bool = False
    ) -> List[Feedback]:
        """
        Получает все отзывы (для админки).
        
        Args:
            limit: Максимальное количество отзывов
            offset: Смещение для пагинации
            include_hidden: Включать ли скрытые отзывы
        
        Returns:
            List[Feedback]: Список всех отзывов
        """
        try:
            query = select(Feedback)
            
            if not include_hidden:
                query = query.where(Feedback.is_published == True)
            
            query = query.order_by(desc(Feedback.created)).limit(limit).offset(offset)
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            ic(f"Error getting all feedback: {e}")
            return []
    
    async def get_by_rating(
        self,
        rating: int,
        limit: int = 50
    ) -> List[Feedback]:
        """
        Получает отзывы с определённой оценкой.
        
        Args:
            rating: Оценка (1-5)
            limit: Максимальное количество отзывов
        
        Returns:
            List[Feedback]: Список отзывов с указанной оценкой
        """
        try:
            query = (
                select(Feedback)
                .where(and_(Feedback.rating == rating, Feedback.is_published == True))
                .order_by(desc(Feedback.created))
                .limit(limit)
            )
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            ic(f"Error getting feedback by rating {rating}: {e}")
            return []
    
    async def get_by_dish_id(
        self,
        dish_id: int,
        limit: int = 50
    ) -> List[Feedback]:
        """
        Получает отзывы о конкретном блюде.
        
        Args:
            dish_id: ID блюда
            limit: Максимальное количество отзывов
        
        Returns:
            List[Feedback]: Список отзывов о блюде
        """
        try:
            query = (
                select(Feedback)
                .where(and_(Feedback.dish_id == dish_id, Feedback.is_published == True))
                .order_by(desc(Feedback.created))
                .limit(limit)
            )
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            ic(f"Error getting feedback for dish {dish_id}: {e}")
            return []
    
    async def get_recent(
        self,
        days: int = 7,
        limit: int = 20
    ) -> List[Feedback]:
        """
        Получает недавние отзывы.
        
        Args:
            days: Количество дней
            limit: Максимальное количество отзывов
        
        Returns:
            List[Feedback]: Список недавних отзывов
        """
        try:
            from datetime import datetime, timedelta
            cutoff_date = datetime.now() - timedelta(days=days)
            
            query = (
                select(Feedback)
                .where(and_(Feedback.created >= cutoff_date, Feedback.is_published == True))
                .order_by(desc(Feedback.created))
                .limit(limit)
            )
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            ic(f"Error getting recent feedback: {e}")
            return []
    
    async def get_feedback_with_user_info(
        self,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Получает отзывы с информацией о пользователе (для админки).
        
        Args:
            limit: Максимальное количество отзывов
            offset: Смещение для пагинации
        
        Returns:
            List[Dict[str, Any]]: Список отзывов с данными пользователя
        """
        try:
            query = (
                select(
                    Feedback.feedback_id,
                    Feedback.text,
                    Feedback.rating,
                    Feedback.feedback_type,
                    Feedback.is_published,
                    Feedback.admin_response,
                    Feedback.created,
                    Users.user_id,
                    Users.full_name,
                    Users.username,
                    Users.phone_number
                )
                .outerjoin(Users, Feedback.user_id == Users.user_id)
                .order_by(desc(Feedback.created))
                .limit(limit)
                .offset(offset)
            )
            result = await self.session.execute(query)
            return [dict(row._mapping) for row in result.all()]
        except Exception as e:
            ic(f"Error getting feedback with user info: {e}")
            return []
    
    # =========================================================================
    # UPDATE METHODS
    # =========================================================================
    
    async def update(
        self,
        feedback_id: int,
        text: Optional[str] = None,
        rating: Optional[int] = None,
        admin_response: Optional[str] = None,
        is_published: Optional[bool] = None
    ) -> bool:
        """
        Обновляет отзыв.
        
        Args:
            feedback_id: ID отзыва
            text: Новый текст отзыва
            rating: Новая оценка
            admin_response: Ответ администратора
            is_published: Статус публикации
        
        Returns:
            bool: True если обновление успешно, иначе False
        """
        try:
            update_data = {}
            
            if text is not None:
                update_data["text"] = text.strip()
            if rating is not None:
                if rating < 1 or rating > 5:
                    ic(f"Invalid rating: {rating}")
                    return False
                update_data["rating"] = rating
            if admin_response is not None:
                update_data["admin_response"] = admin_response.strip() if admin_response else None
            if is_published is not None:
                update_data["is_published"] = is_published
            
            if not update_data:
                return True
            
            query = (
                update(Feedback)
                .where(Feedback.feedback_id == feedback_id)
                .values(**update_data)
            )
            result = await self.session.execute(query)
            await self.session.commit()
            return result.rowcount > 0
        except Exception as e:
            ic(f"Error updating feedback {feedback_id}: {e}")
            await self.session.rollback()
            return False
    
    async def publish(self, feedback_id: int) -> bool:
        """
        Публикует отзыв.
        
        Args:
            feedback_id: ID отзыва
        
        Returns:
            bool: True если успешно, иначе False
        """
        return await self.update(feedback_id, is_published=True)
    
    async def hide(self, feedback_id: int) -> bool:
        """
        Скрывает отзыв.
        
        Args:
            feedback_id: ID отзыва
        
        Returns:
            bool: True если успешно, иначе False
        """
        return await self.update(feedback_id, is_published=False)
    
    async def add_admin_response(self, feedback_id: int, response: str) -> bool:
        """
        Добавляет ответ администратора на отзыв.
        
        Args:
            feedback_id: ID отзыва
            response: Текст ответа
        
        Returns:
            bool: True если успешно, иначе False
        """
        return await self.update(feedback_id, admin_response=response)
    
    # =========================================================================
    # DELETE METHODS
    # =========================================================================
    
    async def delete(self, feedback_id: int) -> bool:
        """
        Удаляет отзыв.
        
        Args:
            feedback_id: ID отзыва
        
        Returns:
            bool: True если удаление успешно, иначе False
        """
        try:
            query = delete(Feedback).where(Feedback.feedback_id == feedback_id)
            result = await self.session.execute(query)
            await self.session.commit()
            return result.rowcount > 0
        except Exception as e:
            ic(f"Error deleting feedback {feedback_id}: {e}")
            await self.session.rollback()
            return False
    
    async def delete_by_user(self, user_id: int) -> int:
        """
        Удаляет все отзывы пользователя.
        
        Args:
            user_id: ID пользователя
        
        Returns:
            int: Количество удалённых отзывов
        """
        try:
            query = delete(Feedback).where(Feedback.user_id == user_id)
            result = await self.session.execute(query)
            await self.session.commit()
            return result.rowcount
        except Exception as e:
            ic(f"Error deleting feedback for user {user_id}: {e}")
            await self.session.rollback()
            return 0
    
    # =========================================================================
    # STATISTICS METHODS
    # =========================================================================
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Получает статистику по отзывам.
        
        Returns:
            Dict[str, Any]: Статистика отзывов
        """
        try:
            # Общее количество отзывов
            total_query = select(func.count()).select_from(Feedback)
            total_result = await self.session.execute(total_query)
            total = total_result.scalar() or 0
            
            # Количество опубликованных отзывов
            published_query = select(func.count()).select_from(Feedback).where(Feedback.is_published == True)
            published_result = await self.session.execute(published_query)
            published = published_result.scalar() or 0
            
            # Количество скрытых отзывов
            hidden = total - published
            
            # Средний рейтинг
            avg_rating_query = select(func.avg(Feedback.rating)).where(Feedback.rating.is_not(None))
            avg_rating_result = await self.session.execute(avg_rating_query)
            avg_rating = avg_rating_result.scalar() or 0
            
            # Распределение по типам
            type_stats = {}
            for feedback_type in ["general", "dish", "delivery"]:
                type_query = select(func.count()).select_from(Feedback).where(Feedback.feedback_type == feedback_type)
                type_result = await self.session.execute(type_query)
                type_stats[feedback_type] = type_result.scalar() or 0
            
            # Распределение по оценкам
            rating_stats = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            for rating in range(1, 6):
                rating_query = select(func.count()).select_from(Feedback).where(Feedback.rating == rating)
                rating_result = await self.session.execute(rating_query)
                rating_stats[rating] = rating_result.scalar() or 0
            
            return {
                "total": total,
                "published": published,
                "hidden": hidden,
                "avg_rating": round(float(avg_rating), 2),
                "by_type": type_stats,
                "by_rating": rating_stats
            }
        except Exception as e:
            ic(f"Error getting feedback stats: {e}")
            return {
                "total": 0,
                "published": 0,
                "hidden": 0,
                "avg_rating": 0,
                "by_type": {},
                "by_rating": {}
            }
    
    async def get_rating_distribution(self) -> Dict[int, int]:
        """
        Получает распределение оценок.
        
        Returns:
            Dict[int, int]: Словарь {оценка: количество}
        """
        try:
            result = {}
            for rating in range(1, 6):
                query = select(func.count()).select_from(Feedback).where(
                    and_(Feedback.rating == rating, Feedback.is_published == True)
                )
                count_result = await self.session.execute(query)
                result[rating] = count_result.scalar() or 0
            return result
        except Exception as e:
            ic(f"Error getting rating distribution: {e}")
            return {}
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    async def exists(self, feedback_id: int) -> bool:
        """
        Проверяет существование отзыва.
        
        Args:
            feedback_id: ID отзыва
        
        Returns:
            bool: True если существует, иначе False
        """
        feedback = await self.get_by_id(feedback_id)
        return feedback is not None
    
    async def count_by_user(self, user_id: int) -> int:
        """
        Подсчитывает количество отзывов пользователя.
        
        Args:
            user_id: ID пользователя
        
        Returns:
            int: Количество отзывов
        """
        try:
            query = select(func.count()).select_from(Feedback).where(Feedback.user_id == user_id)
            result = await self.session.execute(query)
            return result.scalar() or 0
        except Exception as e:
            ic(f"Error counting feedback for user {user_id}: {e}")
            return 0
    
    async def has_user_feedback(self, user_id: int) -> bool:
        """
        Проверяет, оставлял ли пользователь отзывы.
        
        Args:
            user_id: ID пользователя
        
        Returns:
            bool: True если есть отзывы, иначе False
        """
        count = await self.count_by_user(user_id)
        return count > 0


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

async def get_feedback_repository(session: AsyncSession) -> FeedbackRepository:
    """
    Возвращает экземпляр репозитория для работы с отзывами.
    
    Args:
        session: Сессия базы данных
    
    Returns:
        FeedbackRepository: Экземпляр репозитория
    """
    return FeedbackRepository(session)