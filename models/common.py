from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlmodel import Field, SQLModel


class UUIDMixin(SQLModel):
    """Mixin for models with UUID primary key"""

    id: UUID | None = Field(default_factory=uuid4, primary_key=True)


class TimestampMixin(SQLModel):
    """Mixin for models with created_at and updated_at timestamps"""

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        nullable=False,
        sa_column_kwargs={"server_default": "CURRENT_TIMESTAMP"},
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        nullable=False,
        sa_column_kwargs={
            "server_default": "CURRENT_TIMESTAMP",
            "onupdate": lambda: datetime.now(UTC),
        },
    )


class ListQueryParams(BaseModel):
    """A container for parsed list query parameters"""

    filters: dict[str, Any]
    range_list: list[int]
    sort_field: str
    sort_order: str
