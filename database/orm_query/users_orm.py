from icecream import ic
from sqlalchemy import Date, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, List, Optional, Union
from database.models.users_model import Users


# =============================================================================
# USER OPERATIONS
# =============================================================================

async def add_user_orm(session: AsyncSession, data: Dict) -> Union[bool, str]:
    """
    Add a new user to the database.
    
    Args:
        session: SQLAlchemy async session
        data: Dictionary with user data (user_id, full_name, username)
    
    Returns:
        True if successful, error message string if failed
    """
    try:
        obj = Users(
            user_id=data["user_id"],
            full_name=data["full_name"],
            username=data["username"]
        )
        session.add(obj)
        await session.flush()
        return obj
    except Exception as e:
        return str(e)


async def update_user_phone_number_orm(session: AsyncSession, user_id: int, phone_number: str) -> bool:
    """
    Update user's phone number.
    
    Args:
        session: SQLAlchemy async session
        user_id: ID of the user
        phone_number: New phone number
    
    Returns:
        True if successful, False if failed
    """
    try:
        await session.execute(
            update(Users)
            .where(Users.user_id == user_id)
            .values(phone_number=phone_number)
        )
        await session.commit()
        return True
    except Exception as e:
        ic(f"Error updating phone number for user {user_id}: {e}")
        return False


async def get_user_orm(session: AsyncSession, user_id: int) -> Optional[Users]:
    """
    Get a single user by ID.
    
    Args:
        session: SQLAlchemy async session
        user_id: ID of the user
    
    Returns:
        Users object if found, None if not found or error
    """
    try:
        query = select(Users).where(Users.user_id == user_id)
        result = await session.execute(query)
        return result.scalar()
    except Exception as e:
        ic(f"Error fetching user {user_id}: {e}")
        return None


# =============================================================================
# GET ALL USERS
# =============================================================================

async def get_all_users_orm(session: AsyncSession) -> List[Users]:
    """
    Get all users from the database.
    
    Args:
        session: SQLAlchemy async session
    
    Returns:
        List[Users]: List of all user objects.
                    Returns empty list if no users found or error occurs.
    
    Example:
        >>> users = await get_all_users_orm(session)
        >>> for user in users:
        ...     print(f"{user.user_id}: {user.full_name}")
    
    Notes:
        - Returns actual Users objects (not dictionaries)
        - Ordered by user_id for consistency
        - Handles exceptions gracefully
    """
    try:
        # Build query to get all users, ordered by user_id
        query = select(Users).order_by(Users.user_id)
        
        # Execute query
        result = await session.execute(query)
        
        # Get all results as list of Users objects
        users = result.scalars().all()
        
        ic(f"Fetched {len(users)} users from database")
        return users
        
    except Exception as e:
        ic(f"Error fetching all users: {e}")
        return []


# =============================================================================
# ADDITIONAL USER QUERIES
# =============================================================================

async def get_all_users_dict_orm(session: AsyncSession) -> List[Dict]:
    """
    Get all users as dictionaries (useful for JSON responses).
    
    Args:
        session: SQLAlchemy async session
    
    Returns:
        List[Dict]: List of user dictionaries with selected fields
    """
    try:
        query = select(
            Users.user_id,
            Users.full_name,
            Users.username,
            Users.phone_number,
            Users.status,
            Users.created,
            Users.updated
        ).order_by(Users.user_id)
        
        result = await session.execute(query)
        # Convert to list of dictionaries
        users = [dict(row._mapping) for row in result.all()]
        
        ic(f"Fetched {len(users)} users as dictionaries")
        return users
        
    except Exception as e:
        ic(f"Error fetching users as dict: {e}")
        return []


async def get_users_count_orm(session: AsyncSession) -> int:
    """
    Get total number of users in database.
    
    Args:
        session: SQLAlchemy async session
    
    Returns:
        int: Number of users, 0 if error
    """
    try:
        query = select(func.count()).select_from(Users)
        result = await session.execute(query)
        count = result.scalar() or 0
        
        ic(f"Total users count: {count}")
        return count
        
    except Exception as e:
        ic(f"Error counting users: {e}")
        return 0


async def get_users_by_status_orm(session: AsyncSession, status: str) -> List[Users]:
    """
    Get users by status (COMMON or ADMIN).
    
    Args:
        session: SQLAlchemy async session
        status: Status string ('common' or 'admin')
    
    Returns:
        List[Users]: List of users with specified status
    """
    try:
        query = select(Users).where(Users.status == status).order_by(Users.user_id)
        result = await session.execute(query)
        users = result.scalars().all()
        
        ic(f"Fetched {len(users)} users with status '{status}'")
        return users
        
    except Exception as e:
        ic(f"Error fetching users by status {status}: {e}")
        return []


async def search_users_by_name_orm(session: AsyncSession, search_term: str) -> List[Users]:
    """
    Search users by full name (case-insensitive partial match).
    
    Args:
        session: SQLAlchemy async session
        search_term: String to search for in user names
    
    Returns:
        List[Users]: List of matching users
    """
    try:
        query = select(Users).where(
            Users.full_name.ilike(f"%{search_term}%")
        ).order_by(Users.full_name)
        
        result = await session.execute(query)
        users = result.scalars().all()
        
        ic(f"Found {len(users)} users matching '{search_term}'")
        return users
        
    except Exception as e:
        ic(f"Error searching users: {e}")
        return []
    
async def update_user_birth_date_orm(session : AsyncSession, user_id : int, birth_date : Date) -> bool:

    try:
        await session.execute(
            update(Users).where(
                Users.user_id == user_id
            ).values(
                birth_date = birth_date
            )
        )
        await session.commit()
        return True

    except Exception as e:
        ic(f"Error update user birthday info: {e}")
        return False