from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.engine.result import ScalarResult
from database.enumirate.users_enum import UserStatus
from database.models.users_model import  Users

async def get_admin_status(session : AsyncSession, user_id : int) -> bool:
    
    try:
        await session.execute(update(Users).where(
            Users.user_id == user_id
        ).values(
        status = UserStatus.ADMIN.value
        ))
        await session.commit()
        return True
    
    except Exception as e:
        print(f"Error updating user status: {e}")
        return False
    
async def get_admin_list(session : AsyncSession) -> ScalarResult:
    pass