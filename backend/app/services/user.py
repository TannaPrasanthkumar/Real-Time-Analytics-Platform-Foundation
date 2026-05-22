from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.base import BaseService
from app.repositories.user import UserRepository
from app.models.user import User
from app.schemas.user import UserCreate
from app.core.security import get_password_hash
from app.core.exceptions import NotFoundException, BadRequestException


class UserService(BaseService[User, UserRepository]):
    """Service orchestrating core business operations regarding User records."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(UserRepository(session))

    async def get_by_email(self, email: str) -> User:
        """Fetch active user by email, raising NotFoundException on empty results."""
        user = await self.repository.get_by_email(email)
        if not user:
            raise NotFoundException(
                message=f"User with email {email} was not found."
            )
        return user

    async def create_user(self, schema: UserCreate) -> User:
        """Hash credentials, check duplicate emails, and insert active User."""
        existing = await self.repository.get_by_email(schema.email)
        if existing:
            raise BadRequestException(
                message=f"A user with email {schema.email} is already registered."
            )
        
        # Build user dictionary with hashed password
        user_data = schema.model_dump(exclude={"password"})
        user_data["hashed_password"] = get_password_hash(schema.password)
        
        return await self.repository.create(user_data)
