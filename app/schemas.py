"""Request validation for bulk jobs."""

from datetime import date
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class RecipientInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: NonEmptyText


class JobInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_title: NonEmptyText
    completion_date: date
    recipients: list[Any] = Field(min_length=1, max_length=1000)
