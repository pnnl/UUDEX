import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import func, select

import uudex_server.models as m
from uudex_server.repos import Repository
from uudex_server.services.message_services.base import UntrustedBrokerName, trusted_exchange_name

_log = logging.getLogger(__name__)


class SubscriptionRepository(Repository[m.Subscription]):
    def __init__(self, session: AsyncSession):
        super().__init__(m.Subscription, session=session, id_field="subscription_id")

    async def select_user_subscriptions(self, user: m.AuthenticatedUser) -> list[m.Subscription]:
        statement = select(m.Subscription).where(
            m.Subscription.owner_endpoint_id == user.endpoint.endpoint_id
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def select_admin_subscriptions(self) -> list[m.Subscription]:
        statement = select(m.Subscription)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def select_subscription_by_uuid(self, subscription_uuid: str) -> m.Subscription | None:
        statement = select(m.Subscription).where(
            m.Subscription.subscription_uuid == subscription_uuid
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def select_visible_by_uuid(
        self, subscription_uuid: str, owner_endpoint_id: int | None
    ) -> m.Subscription | None:
        """The subscription if `owner_endpoint_id` owns it; None means no owner filter (admin)."""
        statement = select(m.Subscription).where(
            m.Subscription.subscription_uuid == subscription_uuid
        )
        if owner_endpoint_id is not None:
            statement = statement.where(m.Subscription.owner_endpoint_id == owner_endpoint_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()


class SubscriptionSubjectRepository(Repository[m.SubscriptionSubject]):
    def __init__(self, session: AsyncSession):
        super().__init__(m.SubscriptionSubject, session=session, id_field="subscription_subject_id")

    async def select_subjects_by_subscription_uuid(
        self, session: AsyncSession, subscription_uuid: str
    ) -> list[m.SubscriptionSubject]:
        statement = (
            select(m.SubscriptionSubject)
            .join(m.Subscription, isouter=True)
            .where(m.Subscription.subscription_uuid == subscription_uuid)
        )  # .where(SubscriptionSubject.subscription.subscription_uuid == subscription_uuid)
        res = await session.execute(statement)
        return list(res.scalars().all())

    async def select_subject_by_id(
        self, session: AsyncSession, subject_id: int
    ) -> m.Subject | None:
        statement = select(m.Subject).where(m.Subject.subject_id == subject_id)
        res = await session.execute(statement)
        return res.scalar_one_or_none()

    async def count_other_subjects_storing_queue(self, queue_name: str, subject_id: int) -> int:
        """How many links on subjects other than `subject_id` store this queue name."""
        statement = (
            select(func.count())
            .select_from(m.SubscriptionSubject)
            .where(
                m.SubscriptionSubject.backing_queue_name == queue_name,
                m.SubscriptionSubject.subject_id != subject_id,
            )
        )
        return (await self.session.execute(statement)).scalar_one()


class SubjectRepository(Repository[m.Subject]):
    def __init__(self, session: AsyncSession):
        super().__init__(m.Subject, session=session, id_field="subject_id")

    async def select_by_uuid_with_links(self, subject_uuid: str) -> m.Subject | None:
        """The subject with `subscription_links` loaded; a lazy load raises on the async session."""
        statement = (
            select(m.Subject)
            .where(m.Subject.subject_uuid == subject_uuid)
            .options(selectinload(m.Subject.subscription_links))  # type: ignore[arg-type]
        )
        return (await self.session.execute(statement)).scalar_one_or_none()


async def warn_untrusted_exchange_names(session: AsyncSession) -> None:
    """Log the subjects whose stored exchange name the server refuses to use; change nothing."""
    untrusted = []
    for subject in await SubjectRepository(session).select_all():
        try:
            trusted_exchange_name(subject)
        except UntrustedBrokerName:
            untrusted.append(subject.subject_uuid)
    if untrusted:
        _log.warning(
            "%d subject(s) hold a broker exchange name the server cannot trust; publish and "
            "queue-info refuse them and delete skips the broker: %s",
            len(untrusted),
            ", ".join(untrusted),
        )


async def select_all_subjects(
    session: AsyncSession, participant_id: int | None = None
) -> list[m.Subject]:
    stmt = select(m.Subject)
    if participant_id is not None:
        stmt = stmt.where(m.Subject.owner_participant_id == participant_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def select_subject_by_id(session: AsyncSession, subject_id: int) -> m.Subject | None:
    """Select a subject by its ID."""
    stmt = select(m.Subject).where(m.Subject.subject_id == subject_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


if __name__ == "__main__":

    async def main():
        from uudex_server.core.settings import get_settings
        from uudex_server.services.database_service import get_db_session

        get_settings(".env-develop")
        session = get_db_session()
        endpoints = select_all_subjects(session=session)
        print("LIST")
        for endpoint in endpoints:
            print(endpoint.model_dump_json())
        print("END LIST")

        item = await select_subject_by_id(session=session, subject_id=endpoints[0].subject_id)  # type: ignore
        print("SINGLE SELECT")
        print(item)
        print("END SINGLE SELECT")

    import asyncio

    asyncio.run(main())
