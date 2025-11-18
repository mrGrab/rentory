from uuid import UUID, uuid4
from datetime import datetime, timezone
from pydantic import BaseModel
from typing import List, Dict, Any
from sqlmodel import Field, SQLModel


class UUIDMixin(SQLModel):
    """Mixin for models with UUID primary key"""
    id: UUID | None = Field(default_factory=uuid4, primary_key=True)


class TimestampMixin(SQLModel):
    """Mixin for models with created_at and updated_at timestamps"""

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        sa_column_kwargs={"server_default": "CURRENT_TIMESTAMP"})

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        sa_column_kwargs={
            "server_default": "CURRENT_TIMESTAMP",
            "onupdate": lambda: datetime.now(timezone.utc)
        })


class ListQueryParams(BaseModel):
    """A container for parsed list query parameters"""
    filters: Dict[str, Any]
    range_list: List[int]
    sort_field: str
    sort_order: str
