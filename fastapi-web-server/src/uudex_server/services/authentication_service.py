from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from uudex_server.models.endpoint_models import EndPoint


class AuthenticationService:
    async def get_endpoint_by_certificate_dn(
        self, certificate_dn: str, db_session: AsyncSession
    ) -> EndPoint | None:
        """
        Get the active endpoint of an active participant for a certificate DN.
        Read on every request so a deactivated caller loses access at once.
        """
        from uudex_server.repos.endpoint_repository import EndpointRepository

        repo = EndpointRepository(db_session)
        endpoint = await repo.select_endpoint_by_certificate_dn(certificate_dn)

        if not endpoint or endpoint.active_sw.upper() != "Y":
            return None

        if endpoint.participant.active_sw.upper() != "Y":
            return None

        return endpoint
