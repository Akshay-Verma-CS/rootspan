"""HTTP-only request and response contracts."""

from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from rootspan.domain import IncidentBrief, IncidentProgress


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReplayIncidentRequest(ApiModel):
    scenario: str = Field(default="inventory-cohort-timeout", min_length=1, max_length=80)


class LiveIncidentRequest(ApiModel):
    """A bounded manual live investigation request."""

    start: datetime | None = None
    end: datetime | None = None
    lookback_minutes: int = Field(default=15, ge=1, le=1440)
    cohort_size: int = Field(default=10, ge=2, le=100)
    target_operation: str = Field(default="gateway.checkout", min_length=1, max_length=160)

    @model_validator(mode="after")
    def validate_explicit_window(self) -> "LiveIncidentRequest":
        if (self.start is None) != (self.end is None):
            raise ValueError("start and end must be supplied together")
        if self.start is not None and self.end is not None:
            if self.start.tzinfo is None or self.end.tzinfo is None:
                raise ValueError("start and end must be timezone-aware")
            if self.end <= self.start:
                raise ValueError("end must be after start")
            if self.end - self.start > timedelta(hours=24):
                raise ValueError("explicit live windows must not exceed 24 hours")
        return self


class AlertmanagerAlert(BaseModel):
    """Alert fields RootSpan consumes; provider extensions remain ignored."""

    model_config = ConfigDict(extra="ignore")

    status: Literal["firing", "resolved"]
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    startsAt: datetime
    fingerprint: str = Field(min_length=1, max_length=500)

    @field_validator("startsAt")
    @classmethod
    def validate_starts_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("startsAt must be timezone-aware")
        return value


class AlertmanagerWebhook(BaseModel):
    """Compatible subset of the Alertmanager/SigNoz webhook envelope."""

    model_config = ConfigDict(extra="ignore")

    status: Literal["firing", "resolved"]
    alerts: tuple[AlertmanagerAlert, ...]


class IncidentListResponse(ApiModel):
    incidents: tuple[IncidentBrief, ...]


class IncidentProgressResponse(ApiModel):
    events: tuple[IncidentProgress, ...]


class WebhookResponse(ApiModel):
    incident_ids: tuple[str, ...]
    closed_incident_ids: tuple[str, ...] = ()
    ignored_resolved: int = Field(ge=0)
