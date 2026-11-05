from sqlalchemy import UniqueConstraint
from sqlmodel import Field

from .base import BaseModel


class SubjectPolicyAclConstraint(BaseModel, table=True):
    __tablename__ = "subject_policy_acl_constraint"
    __table_args__ = (
        UniqueConstraint("subject_policy_id", "privilege_allowed_id", "grant_scope_id"),
    )
    subject_policy_acl_constraint_id: int | None = Field(default=None, primary_key=True)
    subject_policy_id: int = Field(foreign_key="subject_policy.subject_policy_id")
    privilege_allowed_id: int = Field(foreign_key="privilege_allowed.privilege_allowed_id")
    grant_scope_id: int = Field(foreign_key="grant_scope.grant_scope_id")


class GrantScope(BaseModel, table=True):
    __tablename__ = "grant_scope"

    grant_scope_id: int | None = Field(default=None, primary_key=True)
    grant_scope_name: str


class SubjectPolicyBase(BaseModel):
    subject_policy_uuid: str
    subject_policy_type: str
    subject_policy_type_sort: int
    action: str
    full_queue_behavior: str
    max_queue_size_kb: int
    max_message_count: int
    max_priority: int


class SubjectPolicy(SubjectPolicyBase, table=True):
    __tablename__ = "subject_policy"
    __table_args__ = (UniqueConstraint("dataset_definition_id", "target_participant_id"),)

    subject_policy_id: int | None = Field(default=None, primary_key=True)
    dataset_definition_id: int = Field(foreign_key="dataset_definition.dataset_definition_id")
    target_participant_id: int = Field(foreign_key="participant.participant_id")


class SubjectPolicyAdd(SubjectPolicyBase):
    pass


class SubjectPolicyDelete(BaseModel):
    subject_policy_id: int


class SubjectAcl(BaseModel, table=True):
    __tablename__ = "subject_acl"
    __table_args__ = (UniqueConstraint("subject_id", "privilege_id", "grant_scope_id"),)
    subject_acl_id: int | None = Field(default=None, primary_key=True)
    subject_id: int = Field(foreign_key="subject.subject_id")
    privilege_id: int = Field(foreign_key="privilege.privilege_id")
    grant_scope_id: int = Field(foreign_key="grant_scope.grant_scope_id")


class SubjectAclGrant(BaseModel, table=True):
    __tablename__ = "subject_acl_grant"

    subject_acl_id: int = Field(foreign_key="subject_acl.subject_acl_id", primary_key=True)
    participant_id: int = Field(foreign_key="participant.participant_id", primary_key=True)


class SubjectAclGrantAdd(BaseModel):
    pass


class SubjectAclGrantDelete(BaseModel):
    pass


class SubjectPolicyGrantAllowed(BaseModel, table=True):
    __tablename__ = "subject_policy_grant_allowed"

    subject_policy_acl_constraint_id: int = Field(
        foreign_key="subject_policy_acl_constraint.subject_policy_acl_constraint_id",
        primary_key=True,
    )
    participant_id: int = Field(foreign_key="participant.participant_id", primary_key=True)
