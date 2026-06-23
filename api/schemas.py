from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DetectionRequest(BaseModel):
    server_id: str = Field(..., min_length=1)
    cpu_usage: float = Field(..., ge=0, le=100)
    memory_usage: float = Field(..., ge=0, le=100)
    request_count: float = Field(..., ge=0)
    error_rate: float = Field(..., ge=0, le=1)
    avg_latency_ms: float = Field(..., ge=0)
    p95_latency_ms: float = Field(..., ge=0)


class DetectionResponse(BaseModel):
    prediction: Literal["normal", "anomaly"]
    anomaly_score: float
    risk_level: Literal["low", "medium", "high"]
    model_version: str
