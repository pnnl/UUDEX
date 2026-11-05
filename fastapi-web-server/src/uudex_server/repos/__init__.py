from typing import Generic, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel
from sqlmodel import delete as _delete
from sqlmodel import select as _select
from sqlmodel import update as _update

# Use BaseModel as the bound for the generic type
from ..models.base import BaseModel

T = TypeVar("T", bound=SQLModel)


class Repository(Generic[T]):
    def __init__(self, model: type[T], session: AsyncSession, id_field: str | list[str]):
        self._session = session
        self._model = model
        self._id_fields = [id_field] if isinstance(id_field, str) else id_field

    @property
    def model(self) -> type[T]:
        return self._model

    @property
    def session(self) -> AsyncSession:
        return self._session

    @property
    def id_fields(self) -> list[str]:
        return self._id_fields

    async def select_all(self) -> list[T]:
        statement = _select(self.model)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def select_by_id(self, record_id: int) -> T | None:
        statement = _select(self.model).where(getattr(self.model, self._id_fields[0]) == record_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def select_by_ids(self, **ids: int) -> T | None:
        statements = [getattr(self.model, field) == ids[field] for field in self.id_fields]
        statement = _select(self.model).where(*statements)
        res = self.session.exec(statement)
        return res.first()

    async def select_by_fields(self, **ids: int) -> T | None:
        statements = [
            getattr(self.model, field) == ids[field]
            for field in self.model.model_fields
            if field in ids
        ]
        statement = _select(self.model).where(*statements)
        res = self.session.exec(statement)
        return res.first()

    async def delete(self, obj: BaseModel) -> None:
        statements = [getattr(self.model, field) == getattr(obj, field) for field in self.id_fields]
        statement = _delete(self.model).where(*statements)
        self.session.exec(statement)
        self.session.commit()

    async def update(self, obj: T) -> T:
        statements = [getattr(self.model, field) == getattr(obj, field) for field in self.id_fields]
        statement = (
            _update(self.model).where(*statements).values(**obj.model_dump(exclude_unset=True))
        )
        self.session.exec(statement)
        self.session.commit()
        self.session.refresh(obj)
        return obj

    async def create(self, obj: T) -> T:
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj


# Importing repository modules with standardized function names
