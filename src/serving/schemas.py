"""Pydantic request/response models for the serving API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Decision = Literal["approve", "review", "deny"]


class LoanApplication(BaseModel):
    """A single applicant record using the canonical UCI Taiwan field names."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "limit_bal": 50000,
                "sex": 1,
                "education": 2,
                "marriage": 1,
                "age": 35,
                "pay_0": 0,
                "pay_2": 0,
                "pay_3": 0,
                "pay_4": 0,
                "pay_5": 0,
                "pay_6": 0,
                "bill_amt1": 1500,
                "bill_amt2": 1400,
                "bill_amt3": 1300,
                "bill_amt4": 1200,
                "bill_amt5": 1100,
                "bill_amt6": 1000,
                "pay_amt1": 500,
                "pay_amt2": 500,
                "pay_amt3": 500,
                "pay_amt4": 500,
                "pay_amt5": 500,
                "pay_amt6": 500,
            }
        }
    )

    limit_bal: float = Field(gt=0, description="Credit limit, NT dollars")
    sex: int = Field(ge=1, le=2, description="1=male, 2=female")
    education: int = Field(ge=1, le=4)
    marriage: int = Field(ge=1, le=3)
    age: int = Field(ge=18, le=100)
    pay_0: int = Field(ge=-2, le=9)
    pay_2: int = Field(ge=-2, le=9)
    pay_3: int = Field(ge=-2, le=9)
    pay_4: int = Field(ge=-2, le=9)
    pay_5: int = Field(ge=-2, le=9)
    pay_6: int = Field(ge=-2, le=9)
    bill_amt1: float
    bill_amt2: float
    bill_amt3: float
    bill_amt4: float
    bill_amt5: float
    bill_amt6: float
    pay_amt1: float = Field(ge=0)
    pay_amt2: float = Field(ge=0)
    pay_amt3: float = Field(ge=0)
    pay_amt4: float = Field(ge=0)
    pay_amt5: float = Field(ge=0)
    pay_amt6: float = Field(ge=0)


class PredictionRequest(BaseModel):
    applications: list[LoanApplication] = Field(min_length=1, max_length=1000)


class PredictionResult(BaseModel):
    probability_of_default: float
    decision: Decision


class PredictionResponse(BaseModel):
    request_id: str
    model_version: str
    predictions: list[PredictionResult]


class ExplanationRequest(BaseModel):
    application: LoanApplication


class FeatureContribution(BaseModel):
    feature: str
    shap_value: float


class ExplanationResponse(BaseModel):
    request_id: str
    model_version: str
    probability_of_default: float
    decision: Decision
    top_drivers: list[FeatureContribution]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    model_version: str
    feature_count: int
