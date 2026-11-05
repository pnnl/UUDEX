from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select as _select

from uudex_server.models import Dataset, DatasetDefinition
from uudex_server.repos import Repository


class DatasetRepository(Repository[Dataset]):
    def __init__(self, session: AsyncSession):
        super().__init__(Dataset, session=session, id_field="dataset_id")

    async def select_datasets_by_participant(
        self, session: AsyncSession, participant_id: int
    ) -> list[Dataset]:
        statement = _select(Dataset).where(Dataset.owner_participant_id == participant_id)
        res = await session.execute(statement)
        return list(res.scalars().all())


class DatasetDefinitionRepository(Repository[DatasetDefinition]):
    def __init__(self, session: AsyncSession):
        super().__init__(DatasetDefinition, session=session, id_field="dataset_definition_id")
