from sqlmodel import Session

import uudex_server.models as m
from uudex_server.repos import Repository


class SubjectAclRepository(Repository[m.SubjectAcl]):
    def __init__(self, session: Session):
        super().__init__(m.SubjectAcl, session=session, id_field="subject_acl_id")


class GrantScopeRepository(Repository[m.GrantScope]):
    def __init__(self, session: Session):
        super().__init__(m.GrantScope, session=session, id_field="grant_scope_id")


class SubjectAclGrantRepository(Repository[m.SubjectAclGrant]):
    def __init__(self, session: Session):
        super().__init__(
            m.SubjectAclGrant, session=session, id_field=["subject_acl_id", "participant_id"]
        )


class SubjectPolicyRepository(Repository[m.SubjectPolicy]):
    def __init__(self, session: Session):
        super().__init__(m.SubjectPolicy, session=session, id_field="subject_policy_id")


class SubjectPolicyAclConstraintRepository(Repository[m.SubjectPolicyAclConstraint]):
    def __init__(self, session: Session):
        super().__init__(
            m.SubjectPolicyAclConstraint, session=session, id_field="subject_policy_id"
        )


class SubjectPolicyGrantAllowedRepository(Repository[m.SubjectPolicyGrantAllowed]):
    def __init__(self, session: Session):
        super().__init__(
            m.SubjectPolicyGrantAllowed,
            session=session,
            id_field=["subject_policy_acl_constraint_id", "participant_id"],
        )
