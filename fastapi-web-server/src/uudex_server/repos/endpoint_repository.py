from sqlalchemy import exists, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from uudex_server.models import EndPoint
from uudex_server.models.common_types import YNSwitch
from uudex_server.repos import Repository


class EndpointRepository(Repository[EndPoint]):
    def __init__(self, session: AsyncSession):
        super().__init__(EndPoint, session=session, id_field="endpoint_id")

    async def select_endpoint_by_certificate_dn(self, certificate_dn: str) -> EndPoint | None:
        statement = select(EndPoint).where(EndPoint.certificate_dn == certificate_dn)
        result = await self.session.execute(statement)
        endpoint = result.scalar_one_or_none()

        # Load the participant relationship if endpoint exists
        if endpoint:
            await self.session.refresh(endpoint, ["participant"])

        return endpoint

    async def select_participant_by_endpoint_id(self, endpoint_id: int) -> EndPoint | None:
        statement = select(EndPoint).where(EndPoint.endpoint_id == endpoint_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def select_all_endpoints(self) -> list[EndPoint]:
        statement = select(EndPoint)
        result = await self.session.execute(statement)
        return result.scalars().all()

    async def has_any_admin_endpoints(self) -> bool:
        """True when at least one active endpoint is a UUDEX administrator.

        The active switch is a plain string compared in upper case, as login does, so a row that
        can log in as an active administrator is never missed. The administrator switch is an
        enum column that holds only Y or N, and PostgreSQL has no upper() for an enum.
        """
        statement = select(
            exists().where(
                EndPoint.uudex_administrator_sw == YNSwitch.Y,
                func.upper(EndPoint.active_sw) == "Y",
            )
        )
        result = await self.session.execute(statement)
        return bool(result.scalar())

    async def certificate_dn_exists(self, certificate_dn: str) -> bool:
        """True when any endpoint, active or not, already has this certificate DN."""
        statement = select(exists().where(EndPoint.certificate_dn == certificate_dn))
        result = await self.session.execute(statement)
        return bool(result.scalar())

    async def create_endpoint(self, endpoint: EndPoint) -> EndPoint:
        self.session.add(endpoint)
        await self.session.commit()
        await self.session.refresh(endpoint)
        return endpoint
