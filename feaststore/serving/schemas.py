"""Pydantic request/response models for the serving API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class OnlineFeaturesRequest(BaseModel):
    features: list[str] = Field(
        ...,
        min_length=1,
        description="Feature references of the form 'feature_view:feature_name'.",
        examples=[["driver_hourly_stats:conv_rate", "driver_hourly_stats:acc_rate"]],
    )
    entities: list[dict[str, Any]] = Field(
        ...,
        min_length=1,
        description="One dict per entity row, mapping join key -> value.",
        examples=[[{"driver_id": 1001}, {"driver_id": 1002}]],
    )

    @field_validator("features")
    @classmethod
    def _validate_refs(cls, v: list[str]) -> list[str]:
        bad = [ref for ref in v if ":" not in ref]
        if bad:
            raise ValueError(f"malformed feature references (need 'view:feature'): {bad}")
        return v


class OnlineFeaturesResponse(BaseModel):
    metadata: dict[str, Any] = Field(default_factory=dict)
    results: list[dict[str, Any]]


class FeatureViewSummary(BaseModel):
    name: str
    entities: list[str]
    features: list[str]
    source_table: str
    ttl_seconds: int | None


class HealthResponse(BaseModel):
    status: str
    online_store: str
    version: str
