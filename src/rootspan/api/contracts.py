"""HTTP-only request and list response contracts."""

from pydantic import BaseModel, ConfigDict, Field

from rootspan.domain import IncidentBrief


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReplayIncidentRequest(ApiModel):
    scenario: str = Field(default="inventory-cohort-timeout", min_length=1, max_length=80)


class IncidentListResponse(ApiModel):
    incidents: tuple[IncidentBrief, ...]
