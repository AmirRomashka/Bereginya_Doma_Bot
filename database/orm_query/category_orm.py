from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.engine.result import MappingResult
from database.models.category_model import Categories
from icecream import ic
from typing import Dict, Optional

async def add_category_orm(session: AsyncSession, data: Dict) -> Optional[Categories]:
    """
    Добавляет новую категорию.
    
    Args:
        session: AsyncSession
        data: Словарь с данными категории (ключ "category_name")
    
    Returns:
        Optional[Categories]: Созданный объект категории или None при ошибке
    """
    try:
        obj = Categories(name=data["category_name"])
        session.add(obj)
        await session.commit()
        await session.refresh(obj)  # ← Обновляем объект, чтобы получить category_id
        return obj
    except Exception as e:
        ic(f"Error adding category: {e}")
        await session.rollback()
        return None

async def get_categories_orm(session: AsyncSession) -> MappingResult:
    query = select(Categories.category_id, Categories.name)
    result = await session.execute(query)
    return result.mappings().all()

async def update_category_orm(session: AsyncSession, category_id: int, new_name: str) -> bool:
    try:
        query = update(Categories).where(Categories.category_id == category_id).values(name=new_name)
        await session.execute(query)
        await session.commit()
        return True
    except Exception as e:
        print(f"Error updating category: {e}")
        return False

async def delete_category_orm(session: AsyncSession, category_id: int) -> bool:
    try:
        # ВНИМАНИЕ: Если в категории есть блюда, удаление вызовет ошибку ForeignKey.
        # Рекомендую либо включить каскадное удаление в БД, либо проверять наличие блюд перед удалением.
        query = delete(Categories).where(Categories.category_id == category_id)
        await session.execute(query)
        await session.commit()
        return True
    except Exception as e:
        print(f"Error deleting category: {e}")
        return False