from typing import Any, Generic, List, Type, TypeVar, Optional, Union, Dict
from pydantic import BaseModel
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.db.base_class import Base

logger = structlog.get_logger(__name__)

# Generic variables representing the SQLAlchemy Model Type
ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Generic base repository encapsulating asynchronous CRUD expressions.
    
    Protects downstream service controllers from raw database query syntax
    and ensures uniform transaction boundary checks.
    """

    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session
        self.logger = logger.bind(model=model.__name__)

    async def get(self, id: Any, include_deleted: bool = False) -> Optional[ModelType]:
        """Fetch a single record by its primary key ID."""
        self.logger.debug("Fetching record", id=id, include_deleted=include_deleted)
        
        query = select(self.model).where(self.model.id == id)
        
        # Enforce soft delete filtering if requested
        if not include_deleted and hasattr(self.model, "is_deleted"):
            query = query.where(self.model.is_deleted == False)

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_multi(
        self, skip: int = 0, limit: int = 100, include_deleted: bool = False
    ) -> List[ModelType]:
        """Fetch multiple records with limit and offset boundaries."""
        self.logger.debug(
            "Fetching multiple records",
            skip=skip,
            limit=limit,
            include_deleted=include_deleted,
        )
        
        query = select(self.model).offset(skip).limit(limit)
        
        if not include_deleted and hasattr(self.model, "is_deleted"):
            query = query.where(self.model.is_deleted == False)
            
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create(self, obj_in: Union[BaseModel, Dict[str, Any]]) -> ModelType:
        """Create a new database record from a dynamic dictionary or Pydantic model."""
        self.logger.debug("Creating new database record")
        
        if isinstance(obj_in, BaseModel):
            obj_data = obj_in.model_dump()
        else:
            obj_data = obj_in.copy()
            
        db_obj = self.model(**obj_data)
        
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj

    async def update(
        self, db_obj: ModelType, obj_in: Union[BaseModel, Dict[str, Any]]
    ) -> ModelType:
        """Update an existing database record and commits changes."""
        self.logger.debug("Updating database record", id=db_obj.id)
        
        if isinstance(obj_in, BaseModel):
            update_data = obj_in.model_dump(exclude_unset=True)
        else:
            update_data = obj_in.copy()

        # Dynamically set new attribute values on model fields
        for field in update_data:
            if hasattr(db_obj, field):
                setattr(db_obj, field, update_data[field])

        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj

    async def delete(self, id: Any) -> bool:
        """Execute a hard database physical delete (removes row entirely)."""
        self.logger.warning("Executing hard physical delete on row", id=id)
        
        query = delete(self.model).where(self.model.id == id)
        result = await self.session.execute(query)
        await self.session.commit()
        
        return getattr(result, "rowcount", 0) > 0

    async def soft_delete(self, db_obj: ModelType) -> ModelType:
        """Logic transition of a record into a logical soft-deleted state."""
        self.logger.info("Executing soft logical delete on row", id=db_obj.id)
        
        if hasattr(db_obj, "trigger_soft_delete"):
            db_obj.trigger_soft_delete()
            self.session.add(db_obj)
            await self.session.commit()
            await self.session.refresh(db_obj)
        else:
            self.logger.warning(
                "Model does not inherit SoftDeleteModelMixin. Soft-delete request skipped.",
                id=db_obj.id,
            )
            
        return db_obj
