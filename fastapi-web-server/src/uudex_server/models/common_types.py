from enum import Enum

from sqlalchemy import Enum as SQLEnum


class YNSwitch(str, Enum):
    """Enum for Y/N fields in database"""

    Y = "Y"
    N = "N"

    @classmethod
    def db_type(cls):
        """Return SQLAlchemy Enum type for database column"""
        return SQLEnum(cls, name="ynswitch", create_constraint=True, native_enum=False)

    def __str__(self):
        return self.value
