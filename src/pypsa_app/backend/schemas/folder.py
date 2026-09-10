"""Schemas of registered result folders"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from pypsa_app.backend.models import Visibility
from pypsa_app.backend.schemas.auth import UserPublicResponse
from pypsa_app.backend.schemas.network import NetworkResponse


class FolderRegisterRequest(BaseModel):
    """Body for in-place registration of a result folder."""

    absolute_path: str = Field(
        ..., description="Absolute path of the folder holding the .nc files"
    )
    visibility: Visibility = Visibility.PRIVATE


class FolderResponse(BaseModel):
    """A registered result folder (scenario) with its networks (years)."""

    id: UUID
    name: str
    path: str
    visibility: Visibility
    created_at: datetime | None = None
    owner: UserPublicResponse
    networks: list[NetworkResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class FolderListResponse(BaseModel):
    data: list[FolderResponse]
