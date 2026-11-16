from sqlmodel import Session

from uudex_server.models import DataType
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

if __name__ == "__main__":

    async def main():
        from uudex_server.core.settings import get_settings
        from uudex_server.services.database_service import get_db_session

        settings = get_settings(".env-develop")
        session = get_db_session()
        endpoints = select_all_data_types(session=session)
        print("LIST")
        for endpoint in endpoints:
            print(endpoint.model_dump_json())
        print("END LIST")
        # item = await select_by_data_type_id(session=session,
        #                                           )    # type: ignore

        item = await select_by_data_type_id(session=session, data_type_id=endpoints[0].data_type_id)

        print("SINGLE SELECT")
        print(item)
        print("END SINGLE SELECT")

        item = await select_by_data_type_id(session=session, data_type_id=-1)

        print("SINGLE SELECT")
        print(item)
        print("END SINGLE SELECT")

    import asyncio

    asyncio.run(main())
