"""GET /subscriptions/admin is limited to UUDEX administrators."""

import uuid

from sqlmodel import select

import uudex_server.models as m
from conftest import identity_headers
from test_caller import cn, seed_endpoint, seed_participant, trusted_client  # noqa: F401
from uudex_server.services.database_service import get_db_session


async def seed_subscription(endpoint_uuid: str) -> str:
    subscription_uuid = str(uuid.uuid4())
    async with get_db_session() as session:
        result = await session.execute(
            select(m.EndPoint).where(m.EndPoint.endpoint_uuid == endpoint_uuid)
        )
        owner = result.scalar_one()
        session.add(
            m.Subscription(
                subscription_uuid=subscription_uuid,
                subscription_name="s",
                subscription_state="active",
                owner_endpoint_id=owner.endpoint_id,
                create_datetime=None,
            )
        )
    return subscription_uuid


async def test_non_admin_gets_403_on_admin_subscriptions(cn):  # noqa: F811
    owner_p, caller_p = await seed_participant(), await seed_participant()
    owner_ep = await seed_endpoint(owner_p, f"{cn}-owner")
    await seed_endpoint(caller_p, cn)
    sub_uuid = await seed_subscription(owner_ep)
    async with trusted_client() as c:
        response = await c.get("/subscriptions/admin", headers=identity_headers(cn))
    assert response.status_code == 403
    assert response.json() == {"detail": "Administrator access required"}
    assert sub_uuid not in response.text


async def test_admin_lists_every_subscription(cn):  # noqa: F811
    p1, p2 = await seed_participant(), await seed_participant()
    admin_ep = await seed_endpoint(p1, cn, admin=True)
    other_ep = await seed_endpoint(p2, f"{cn}-other")
    mine, theirs = await seed_subscription(admin_ep), await seed_subscription(other_ep)
    async with trusted_client() as c:
        response = await c.get("/subscriptions/admin", headers=identity_headers(cn))
    assert response.status_code == 200
    assert {mine, theirs} <= {s["subscription_uuid"] for s in response.json()}
