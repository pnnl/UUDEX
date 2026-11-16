from sqlmodel import Session

from uudex_server.models import DatasetDefinition
from uudex_server.repos import Repository


class DatasetDefinitionRepository(Repository[DatasetDefinition]):
    def __init__(self, session: Session):
        super().__init__(DatasetDefinition, session=session, id_field="dataset_definition_id")


#
# async def select_by_data_definition_id(
#         session: Session, data_definition_id: int) -> Awaitable[DatasetDefinition] | None:
#         DatasetDefinition.dataset_definition_id == data_definition_id)
#
#
# async def create(session: Session, dataset_definition: DatasetDefinitionCreate) -> DatasetDefinition:
#
# async def select_all(session: Session) -> list[DatasetDefinition]:
#
# async def select_by_id(session: Session, dataset_definition_id: int) -> DatasetDefinition | None:
#
# async def update(session: Session, dataset_definition: DatasetDefinition) -> DatasetDefinition:
#
# async def delete(session: Session, dataset_definition_remove: DatasetDefinitionDelete) -> None:

# if __name__ == '__main__':
#
#     async def main():
#
#
#         for endpoint in endpoints:
#         # item = await select_by_data_definition_id(session=session,
#         #                                           )    # type: ignore
#
#             session=session, data_definition_id=endpoints[0].dataset_definition_id)
#
#
#
#
