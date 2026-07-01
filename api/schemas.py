from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class DetectionRequest(BaseModel):
    server_id: str = Field(..., min_length=1)
    cpu_usage: float = Field(..., ge=0, le=100)
    memory_usage: float = Field(..., ge=0, le=100)
    request_count: float = Field(..., ge=0)
    error_rate: float = Field(..., ge=0, le=1)
    avg_latency_ms: float = Field(..., ge=0)
    p95_latency_ms: float = Field(..., ge=0)

    @model_validator(mode="after")
    def validate_latency_order(self) -> DetectionRequest:
        if self.p95_latency_ms < self.avg_latency_ms:
            raise ValueError("p95_latency_ms must be greater than or equal to avg_latency_ms")
        return self


class DetectionResponse(BaseModel):
    prediction: Literal["normal", "anomaly"]
    anomaly_score: float
    risk_level: Literal["low", "medium", "high"]
    model_version: str


class RetrainRequest(BaseModel):
    force: bool = False
    drift_threshold: float | None = Field(default=None, ge=0)
    reload_after_train: bool = True


class FairnessRequest(BaseModel):
    group_column: str | None = Field(default=None, min_length=1)
    gap_threshold: float | None = Field(default=None, ge=0, le=1)
