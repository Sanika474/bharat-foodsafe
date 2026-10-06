import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class EvaluationDetail(BaseModel):
    rule_id: uuid.UUID
    rule_code: str
    rule_name: str
    version_number: int
    rule_source_id: uuid.UUID
    source_code: str
    source_title: str
    field_evaluated: str
    observed_value: Any | None = None
    observed_unit: str | None = None
    outcome: str = Field(..., description="NORMAL, DEVIATION, or CRITICAL")
    reason: str
    condition_evaluated: dict[str, Any] | None = None


class RuleEvaluationResult(BaseModel):
    overall_status: str = Field(..., description="NORMAL, DEVIATION, or CRITICAL")
    rules_evaluated_count: int
    details: list[EvaluationDetail] = []


class StandaloneEvaluateRequest(BaseModel):
    task_id: uuid.UUID | None = Field(default=None, description="Task ID to resolve template/category bindings")
    category_id: uuid.UUID | None = Field(default=None, description="Task category ID for binding lookup")
    template_id: uuid.UUID | None = Field(default=None, description="Task template ID for binding lookup")
    value_numeric: float | None = Field(default=None, description="Numeric observation value")
    value_text: str | None = Field(default=None, description="Text observation value")
    value_jsonb: Any | None = Field(default=None, description="JSON observation payload")
    unit: str | None = Field(default=None, description="Measurement unit (e.g. C, F, %)")


class SafetyRuleResponse(BaseModel):
    id: uuid.UUID
    rule_code: str
    rule_source_id: uuid.UUID
    version_number: int
    name: str
    description: str | None = None
    condition_jsonb: dict[str, Any]
    action_jsonb: dict[str, Any]
    is_active: bool
    created_at: datetime
    source_code: str | None = None
    source_title: str | None = None

    class Config:
        from_attributes = True


class SafetyRuleCreateRequest(BaseModel):
    source_code: str = Field(..., description="Associated rule source code (e.g. FSSAI_SCHEDULE_4)")
    rule_code: str = Field(..., description="Unique rule code identifier")
    name: str = Field(..., description="Rule title/name")
    description: str | None = Field(default=None, description="Rule description")
    condition_jsonb: dict[str, Any] = Field(..., description="Deterministic rule evaluation conditions")
    action_jsonb: dict[str, Any] = Field(..., description="Rule action and default safety status")
    category_id: uuid.UUID | None = Field(default=None, description="Bind rule to category")
    template_id: uuid.UUID | None = Field(default=None, description="Bind rule to specific task template")


class RuleSourceResponse(BaseModel):
    id: uuid.UUID
    source_code: str
    title: str
    issuing_authority: str
    document_reference: str | None = None
    review_status: str
    effective_date: datetime | None = None

    class Config:
        from_attributes = True


class EntryEvaluationResponse(BaseModel):
    id: uuid.UUID
    entry_id: uuid.UUID
    safety_rule_id: uuid.UUID
    rule_source_id: uuid.UUID
    evaluation_result: str
    details_jsonb: dict[str, Any] | None = None
    evaluated_at: datetime

    class Config:
        from_attributes = True
