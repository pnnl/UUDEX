from sqlmodel import Session

from uudex_server.models.data_type_models import DataType
from uudex_server.repos import Repository


class DataTypeRepository(Repository[DataType]):
    def __init__(self, session: Session):
        super().__init__(DataType, session=session, id_field="data_type_id")


# def select_all_data_types(session: Session) -> list[DataType]:
#
#
# async def select_by_data_type_id(session: Session,
#                                  data_type_id: int) -> Awaitable[DataType] | None:
#
#
# async def create(session: Session, data_type: DataTypeCreate) -> DataType:
#
#
# async def select_all(session: Session) -> list[DataType]:
#
#
# async def select_by_id(session: Session, data_type_id: int) -> DataType | None:
#
#
# async def update(session: Session, data_type: DataType) -> DataType:
#
#
# async def delete(session: Session, data_type_remove: DataTypeDelete) -> None:
