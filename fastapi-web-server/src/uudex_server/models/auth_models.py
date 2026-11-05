from typing import Optional

from sqlmodel import Field, Relationship

from .base import BaseModel, TimeStampMixin


class AuthGroupBase(BaseModel):
    group_uuid: str    # UUID stored as string
    group_name: str
    description: str | None = None


class AuthGroup(AuthGroupBase, TimeStampMixin, table=True):
    __tablename__ = "auth_group"
    __table_args__ = {"extend_existing": True}

    group_id: int | None = Field(default=None, primary_key=True)
    active_sw: str = Field(default='Y', max_length=1)    # 'Y' or 'N'


class AuthGroupCreate(AuthGroupBase):
    pass


class AuthGroupDelete(BaseModel):
    group_id: int


class AuthRoleBase(BaseModel):
    role_uuid: str
    role_name: str
    description: str | None = None


class AuthRole(AuthRoleBase, TimeStampMixin, table=True):
    __tablename__ = "auth_role"
    __table_args__ = {"extend_existing": True}

    role_id: int | None = Field(default=None, primary_key=True)
    active_sw: str = Field(default='Y', max_length=1)    # 'Y' or 'N'


class AuthRoleCreate(AuthRoleBase):
    pass


class AuthRoleDelete(BaseModel):
    role_id: int


class PrivilegeBase(BaseModel):
    privilege_name: str


class Privilege(PrivilegeBase, TimeStampMixin, table=True):
    __tablename__ = "privilege"
    __table_args__ = {"extend_existing": True}

    privilege_id: int | None = Field(default=None, primary_key=True)


class PrivilegeCreate(PrivilegeBase):
    pass


class PrivilegeAllowedBase(BaseModel):
    privilege_allowed_name: str


class PrivilegeDelete(BaseModel):
    privilege_id: int


class PrivilegeAllowed(PrivilegeAllowedBase, table=True):
    __tablename__ = "privilege_allowed"
    __table_args__ = {"extend_existing": True}

    privilege_allowed_id: int | None = Field(default=None, primary_key=True)


class PrivilegeAllowedCreate(PrivilegeAllowedBase):
    pass


class PrivilegeAllowedDelete(BaseModel):
    privilege_allowed_id: int


class ContactBase(BaseModel):
    contact_name: str
    contact_number: str


class Contact(ContactBase, table=True):
    __tablename__ = "contact"
    __table_args__ = {"extend_existing": True}

    contact_id: int | None = Field(default=None, primary_key=True)
    participant_id: int = Field(foreign_key="participant.participant_id")

    # Relationships
    participant: Optional["Participant"] = Relationship(back_populates="contacts")


class ContactCreate(ContactBase):
    pass


class ContactDelete(BaseModel):
    contact_id: int
