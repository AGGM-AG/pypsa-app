"""Schemas of the view extension routes"""

from typing import Any

from pydantic import BaseModel, Field


class ViewSpecResponse(BaseModel):
    """A view offered by an extension"""

    name: str
    extension: str
    title: str
    description: str = ""
    chart: str = ""
    per_year: bool = False
    params_schema: dict[str, Any] = Field(default_factory=dict)


class ViewListResponse(BaseModel):
    data: list[ViewSpecResponse]
    extensions: list[str]


class ViewGenerateRequest(BaseModel):
    """Request schema for rendering one view chart"""

    network_ids: list[str] = Field(
        ..., min_length=1, description="Networks (planning years of one scenario)"
    )
    view: str = Field(..., description="View name from GET /views")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="View parameters as described by the view's params_schema",
    )


class ViewSelectionsRequest(BaseModel):
    """Request schema for the selections a set of networks supports"""

    network_ids: list[str] = Field(..., min_length=1)
    extension: str = Field(..., description="Extension name from GET /views")
