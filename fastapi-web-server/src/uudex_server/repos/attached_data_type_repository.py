from sqlmodel import Session
from sqlmodel import delete as _delete
from sqlmodel import select as _select

from uudex_server.models import AttachedDataType
from uudex_server.models.attached_data_type_models import AttachedDataType
from uudex_server.repos import Repository

from ..models.base import BaseModel


class AttachedDataTypeRepository(Repository[AttachedDataType]):
    def __init__(self, session: Session):
        super().__init__(
            AttachedDataType, session=session, id_field=["dataset_definition_id", "data_type_id"]
        )

    async def select_by_dataset_definition_id(
        self, session: Session, dataset_definition_id: int
    ) -> AttachedDataType | None:
        statement = _select(self._model).where(
            self._model.dataset_definition_id == dataset_definition_id
        )
        res = session.exec(statement)
        return res.first()

    async def select_by_data_type_id(self, data_type_id: int) -> AttachedDataType | None:
        statement = _select(self._model).where(self._model.data_type_id == data_type_id)
        res = self.session.exec(statement)
        return res.first()

    async def select_by_ids(
        self, dataset_definition_id: int, data_type_id: int
    ) -> AttachedDataType | None:
        statement = _select(self._model).where(
            (self._model.dataset_definition_id == dataset_definition_id)
            & (self._model.data_type_id == data_type_id)
        )
        res = self.session.exec(statement)
        return res.first()

    async def delete(self, obj: BaseModel) -> None:
        statement = _delete(self._model).where(
            (self._model.dataset_definition_id == obj.dataset_definition_id)
            & (self._model.data_type_id == obj.data_type_id)
        )
        self.session.exec(statement)
        self.session.commit()


#
# async def select_all_attached_data_types(session: Session) -> list[AttachedDataType]:
#
#
# async def select_by_data_definition_id(
#         session: Session, data_definition_id: int) -> Awaitable[AttachedDataType] | None:
#         AttachedDataType.dataset_definition_id == data_definition_id)
#
#
# async def select_by_data_type_id(session: Session,
#                                  data_type_id: int) -> Awaitable[AttachedDataType] | None:
#         AttachedDataType.dataset_definition_id == data_type_id)
#
#
# async def create(session: Session, attached_data_type: AttachedDataTypeCreate) -> AttachedDataType:
#
#
# async def select_all(session: Session) -> list[AttachedDataType]:
#
#
# async def select_by_ids(session: Session, dataset_definition_id: int,
#                         data_type_id: int) -> AttachedDataType | None:
#         & (AttachedDataType.data_type_id == data_type_id))
#
#
# async def delete(session: Session, attached_data_type_remove: AttachedDataTypeDelete) -> None:
#         & (AttachedDataType.data_type_id == attached_data_type_remove.data_type_id))
#
#
# async def update(session: Session, attached_data_type: AttachedDataType) -> AttachedDataType:
#
#
# if __name__ == '__main__':
#
#     async def main():
#
#
#         for endpoint in endpoints:
#         item = await select_by_data_type_id(session=session,
#                                             )    # type: ignore
#
#             session=session, data_definition_id=endpoints[0].dataset_definition_id)
#
#
#
#
