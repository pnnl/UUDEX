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
#     statement = select(AttachedDataType)
#     res = session.exec(statement=statement)
#     return list(res)
#
#
# async def select_by_data_definition_id(
#         session: Session, data_definition_id: int) -> Awaitable[AttachedDataType] | None:
#     statement = select(AttachedDataType).where(
#         AttachedDataType.dataset_definition_id == data_definition_id)
#     res = session.exec(statement=statement)
#     return res.first()    # type: ignore
#
#
# async def select_by_data_type_id(session: Session,
#                                  data_type_id: int) -> Awaitable[AttachedDataType] | None:
#     statement = select(AttachedDataType).where(
#         AttachedDataType.dataset_definition_id == data_type_id)
#     res = session.exec(statement=statement)
#     return res.first()    # type: ignore
#
#
# async def create(session: Session, attached_data_type: AttachedDataTypeCreate) -> AttachedDataType:
#     attached_data = AttachedDataType(**attached_data_type.model_dump())
#     session.add(attached_data)
#     session.commit()
#     session.refresh(attached_data)
#     return attached_data
#
#
# async def select_all(session: Session) -> list[AttachedDataType]:
#     statement = select(AttachedDataType)
#     res = session.exec(statement)
#     return list(res)
#
#
# async def select_by_ids(session: Session, dataset_definition_id: int,
#                         data_type_id: int) -> AttachedDataType | None:
#     statement = select(AttachedDataType).where(
#         (AttachedDataType.dataset_definition_id == dataset_definition_id)
#         & (AttachedDataType.data_type_id == data_type_id))
#     res = session.exec(statement)
#     return res.first()
#
#
# async def delete(session: Session, attached_data_type_remove: AttachedDataTypeDelete) -> None:
#     statement = _delete(AttachedDataType).where(
#         (AttachedDataType.dataset_definition_id == attached_data_type_remove.dataset_definition_id)
#         & (AttachedDataType.data_type_id == attached_data_type_remove.data_type_id))
#     session.exec(statement)
#     session.commit()
#
#
# async def update(session: Session, attached_data_type: AttachedDataType) -> AttachedDataType:
#     session.add(attached_data_type)
#     session.commit()
#     session.refresh(attached_data_type)
#     return attached_data_type
#
#
# if __name__ == '__main__':
#
#     async def main():
#
#         from uudex_server.core.settings import get_settings
#         from uudex_server.services.database_service import get_db_session
#
#         settings = get_settings(".env-develop")
#         session = get_db_session()
#         endpoints = select_all_attached_data_types(session=session)
#         print("LIST")
#         for endpoint in endpoints:
#             print(endpoint.model_dump_json())
#         print("END LIST")
#         item = await select_by_data_type_id(session=session,
#                                             data_type_id=endpoints[0].data_type_id
#                                             )    # type: ignore
#         print("SINGLE SELECT")
#         print(item)
#         print("END SINGLE SELECT")
#
#         item = await select_by_data_definition_id(
#             session=session, data_definition_id=endpoints[0].dataset_definition_id)
#
#         print("SINGLE SELECT")
#         print(item)
#         print("END SINGLE SELECT")
#
#         item = await select_by_data_definition_id(session=session, data_definition_id=-1)
#
#         print("SINGLE SELECT")
#         print(item)
#         print("END SINGLE SELECT")
#
#     import asyncio
#     asyncio.run(main())
