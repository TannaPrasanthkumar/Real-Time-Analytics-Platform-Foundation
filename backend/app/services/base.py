from typing import Any, Generic, List, TypeVar, Optional, Union, Dict
from pydantic import BaseModel
import structlog

from app.db.base_class import Base
from app.repositories.base import BaseRepository
from app.core.exceptions import NotFoundException

logger = structlog.get_logger(__name__)

# Generic variables representing SQLAlchemy Model and corresponding Repository type
ModelType = TypeVar("ModelType", bound=Base)
RepositoryType = TypeVar("RepositoryType", bound=BaseRepository[Any])


class BaseService(Generic[ModelType, RepositoryType]):
    """Generic base service class hosting core orchestrations and exception maps.
    
    Protects API boundary routes from details of data storage access models
    and ensures business rules are validated uniformly.
    """

    def __init__(self, repository: RepositoryType):
        self.repository = repository
        self.logger = logger.bind(
            service=self.__class__.__name__,
            model=repository.model.__name__,
        )

    async def get_by_id(self, id: Any) -> ModelType:
        """Fetch a single record by primary key, raising NotFoundException on failure."""
        self.logger.debug("Executing service get_by_id query", id=id)
        
        db_obj = await self.repository.get(id)
        if not db_obj:
            self.logger.warning("Resource query returned empty set", id=id)
            raise NotFoundException(
                message=f"Requested {self.repository.model.__name__} resource with key {id} was not found."
            )
        return db_obj

    async def get_multi(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """Fetch multiple records in specified range bounds."""
        self.logger.debug("Executing service get_multi query", skip=skip, limit=limit)
        return await self.repository.get_multi(skip=skip, limit=limit)

    async def create_item(self, schema: Union[BaseModel, Dict[str, Any]]) -> ModelType:
        """Orchestrate item creation, passing data parameters through Pydantic parsers."""
        self.logger.info("Executing service resource creation request")
        return await self.repository.create(schema)

    async def update_item(
        self, id: Any, schema: Union[BaseModel, Dict[str, Any]]
    ) -> ModelType:
        """Fetch existing item by ID and apply incremental changes."""
        self.logger.info("Executing service resource update request", id=id)
        
        db_obj = await self.get_by_id(id)
        return await self.repository.update(db_obj, schema)

    async def delete_item(self, id: Any) -> bool:
        """Hard physical deletion request orchestration."""
        self.logger.warning("Executing service resource hard delete request", id=id)
        
        # Verify resource existence before deletion to preserve clean exceptions
        await self.get_by_id(id)
        return await self.repository.delete(id)

    async def soft_delete_item(self, id: Any) -> ModelType:
        """Logical soft deletion request orchestration."""
        self.logger.info("Executing service resource soft delete request", id=id)
        
        db_obj = await self.get_by_id(id)
        return await self.repository.soft_delete(db_obj)
