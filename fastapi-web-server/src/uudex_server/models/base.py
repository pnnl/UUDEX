from datetime import datetime

import pytz
from pydantic import ConfigDict
from sqlalchemy import TIMESTAMP, text
from sqlmodel import Field, SQLModel

TZ_UTC = pytz.timezone("UTC")


class BaseModel(SQLModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)


class TimeStampMixin(SQLModel):
    create_datetime: datetime | None = Field(
        sa_type=TIMESTAMP(timezone=True),
        sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")},
        nullable=False,
    )
    # update_datetime: datetime | None = Field(
    #     sa_type=TIMESTAMP(timezone=True),
    #     sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")},
    #     nullable=False)


class ActiveSwitchMixin:
    active_sw: str = Field(default="Y", max_length=1)  # 'Y' or 'N'
