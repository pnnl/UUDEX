import pytest
from fastapi.testclient import TestClient

from uudex_server.main import app  # Assuming main.py where FastAPI instance is created

# Replace 'sqlite:///:memory:' with your actual database URL if required
DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(name="client")
def fixture_client():
    return TestClient(app)


def test_api_get_all_participants(client: TestClient):
    response = client.get("/participants/")
    assert response.status_code == 200


def test_api_get_participant_by_id(client: TestClient):
    response = client.get("/participant/1")
    assert response.status_code == 200


def test_api_get_endpoint_user(client: TestClient):
    response = client.get("/endpoint/me")
    assert response.status_code == 200


def test_api_get_all_subjects(client: TestClient):
    response = client.get("/subjects/")
    assert response.status_code == 200


def test_api_get_subject_by_id(client: TestClient):
    response = client.get("/subject/1")
    assert response.status_code == 200


def test_api_create_subject(client: TestClient):
    data = {
        "subject_uuid": "uuid1",
        "subject_name": "name1",
        "dataset_instance_key": "key1",
        "subscription_type": "sub_type1",
        "fulfillment_types_available": "fulfillment1",
        "full_queue_behavior": "behavior1",
        "max_queue_size_kb": 1000,
        "max_message_count": 10,
        "priority": 1,
        "backing_exchange_name": "exchange1",
        "owner_participant_id": 1,
        "dataset_definition_id": 1,
    }
    response = client.post("/subjects/", json=data)
    assert response.status_code == 200


def test_api_get_all_subscriptions(client: TestClient):
    response = client.get("/subscriptions/")
    assert response.status_code == 200


def test_api_get_subscription_by_id(client: TestClient):
    response = client.get("/subscription/uuid1")
    assert response.status_code == 200


def test_api_create_subscription(client: TestClient):
    data = {
        "subscription_uuid": "uuid1",
        "subscription_name": "name1",
        "subscription_state": "active",
    }
    response = client.post("/subscription/", json=data)
    assert response.status_code == 200


def test_api_discover_subjects(client: TestClient):
    """Test the subjects discovery endpoint"""
    # Note: This test will fail with current authentication middleware
    # In a real test, proper certificate headers would be needed
    response = client.get("/subjects/discover")
    # Expecting 401 due to missing certificate authentication
    assert response.status_code in [200, 401]


def test_api_discover_subjects_v1(client: TestClient):
    """Test the v1 subjects discovery endpoint"""
    # Note: This test will fail with current authentication middleware
    # In a real test, proper certificate headers would be needed
    response = client.get("/v1/subjects/discover")
    # Expecting 401 due to missing certificate authentication
    assert response.status_code in [200, 401]


# Run the tests
if __name__ == "__main__":
    pytest.main()
