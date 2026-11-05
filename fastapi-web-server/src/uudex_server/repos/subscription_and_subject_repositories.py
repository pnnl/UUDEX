from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

import uudex_server.models as m
from uudex_server.repos import Repository


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


class SubjectRepository(Repository[m.Subject]):
    def __init__(self, session: AsyncSession):
        super().__init__(m.Subject, session=session, id_field="subject_id")


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

        settings = get_settings(".env-develop")
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
