import pytest
from sqlalchemy.orm import Session
from sqlmodel import select

import uudex_server.models as m
from uudex_server.models import (
    AttachedDataType,
    AuthGroup,
    AuthRole,
    Contact,
    Dataset,
    DatasetDefinition,
    DataType,
    DataTypeHistory,
    EndPoint,
    GrantScope,
    Participant,
    Privilege,
    PrivilegeAllowed,
    Subject,
    SubjectAcl,
    SubjectAclGrant,
    SubjectPolicy,
    SubjectPolicyAclConstraint,
    SubjectPolicyGrantAllowed,
    Subscription,
    SubscriptionSubject,
)


def test_full_database_seeding(api_session: Session):  # SQLAlchemy ORM session type
    # Check each model to verify the database seeding
    participants = api_session.query(Participant).all()
    assert len(participants) > 0, "Participants should be loaded"

    endpoints = api_session.query(EndPoint).all()
    assert len(endpoints) > 0, "Endpoints should be loaded"

    auth_groups = api_session.query(AuthGroup).all()
    assert len(auth_groups) > 0, "AuthGroups should be loaded"

    roles = api_session.query(AuthRole).all()
    assert len(roles) > 0, "AuthRoles should be loaded"

    privileges = api_session.query(Privilege).all()
    assert len(privileges) > 0, "Privileges should be loaded"

    allowed_privileges = api_session.query(PrivilegeAllowed).all()
    assert len(allowed_privileges) > 0, "PrivilegeAllowed should be loaded"

    data_types = api_session.query(DataType).all()
    assert len(data_types) > 0, "DataTypes should be loaded"

    dataset_definitions = api_session.query(DatasetDefinition).all()
    assert len(dataset_definitions) > 0, "DatasetDefinitions should be loaded"

    contacts = api_session.query(Contact).all()
    assert len(contacts) > 0, "Contacts should be loaded"

    data_type_histories = api_session.query(DataTypeHistory).all()
    assert len(data_type_histories) > 0, "DataTypeHistories should be loaded"

    datasets = api_session.query(Dataset).all()
    assert len(datasets) > 0, "Datasets should be loaded"

    subscriptions = api_session.query(Subscription).all()
    assert len(subscriptions) > 0, "Subscriptions should be loaded"

    subscription_subjects = api_session.query(SubscriptionSubject).all()
    assert len(subscription_subjects) > 0, "SubscriptionSubjects should be loaded"

    subjects = api_session.query(Subject).all()
    assert len(subjects) > 0, "Subjects should be loaded"

    attached_data_types = api_session.query(AttachedDataType).all()
    assert len(attached_data_types) > 0, "AttachedDataTypes should be loaded"

    subject_policies = api_session.query(SubjectPolicy).all()
    assert len(subject_policies) > 0, "SubjectPolicies should be loaded"

    policy_grants = api_session.query(SubjectPolicyGrantAllowed).all()
    assert len(policy_grants) > 0, "SubjectPolicyGrantsAllowed should be loaded"

    subject_acls = api_session.query(SubjectAcl).all()
    assert len(subject_acls) > 0, "Subject Acls should be loaded"

    acl_grants = api_session.query(SubjectAclGrant).all()
    assert len(acl_grants) > 0, "Subject AclGrants should be loaded"

    grant_scopes = api_session.query(GrantScope).all()
    assert len(grant_scopes) > 0, "GrantScopes should be loaded"

    policy_acl_constraints = api_session.query(SubjectPolicyAclConstraint).all()
    assert len(policy_acl_constraints) > 0, "SubjectPolicyAclConstraints should be loaded"


@pytest.mark.parametrize(
    "model_class, relationship, expected_count",
    [
        # Correct the reference to relationships, use 'endpoints'
        (m.Participant, lambda p: p.endpoints, 1),
        (
            m.DataType,
            lambda dt: dt.data_type_history,
            1,
        ),  # Ensure valid relationship definitions exist
        (m.Subject, lambda s: s.attached_data_types, 1),  # Assuming such a relationship
    ],
)
@pytest.mark.xfail(reason="This needs to be re-evaluated!")
def test_database_relationships(api_session: Session, model_class, relationship, expected_count):
    stmt = select(model_class)
    instance = api_session.exec(stmt).first()
    # If instance is None, it means the test data is missing; check setup
    assert instance is not None, f"No data found for {model_class.__name__}"
    related_data = relationship(instance)
    assert (
        len(related_data) == expected_count
    ), f"Expected {expected_count} related records in for relationship in {model_class.__name__}"
