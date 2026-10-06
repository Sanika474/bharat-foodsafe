import logging
import uuid
from typing import Any
from sqlalchemy.orm import Session

from app.models.tasks_and_rules import Entry, RuleSource, SafetyRule, Task
from app.modules.safety_rules import repository
from app.modules.safety_rules.schema import EvaluationDetail, RuleEvaluationResult

logger = logging.getLogger(__name__)


def _extract_field_value(
    field_name: str,
    value_numeric: float | None = None,
    value_text: str | None = None,
    value_jsonb: Any = None,
) -> tuple[Any, bool]:
    """
    Extracts specified field from observation payload.
    Returns (extracted_value, is_present).
    """
    if field_name == "value_numeric":
        return value_numeric, value_numeric is not None
    elif field_name == "value_text":
        return value_text, value_text is not None
    elif field_name == "value_jsonb":
        return value_jsonb, value_jsonb is not None
    elif field_name.startswith("value_jsonb."):
        if not isinstance(value_jsonb, dict):
            return None, False
        subkey = field_name[12:]
        val = value_jsonb.get(subkey)
        return val, val is not None
    return value_numeric, value_numeric is not None


def _eval_op(val: Any, op: str, target: Any) -> bool:
    """Evaluates a comparison operator deterministically."""
    op_lower = op.lower()

    if op_lower in ("gt", ">"):
        return float(val) > float(target)
    elif op_lower in ("gte", ">="):
        return float(val) >= float(target)
    elif op_lower in ("lt", "<"):
        return float(val) < float(target)
    elif op_lower in ("lte", "<="):
        return float(val) <= float(target)
    elif op_lower in ("eq", "==", "equals"):
        if isinstance(val, (int, float)) and isinstance(target, (int, float, str)):
            try:
                return float(val) == float(target)
            except (ValueError, TypeError):
                pass
        return str(val) == str(target)
    elif op_lower in ("neq", "!=", "not_equals"):
        if isinstance(val, (int, float)) and isinstance(target, (int, float, str)):
            try:
                return float(val) != float(target)
            except (ValueError, TypeError):
                pass
        return str(val) != str(target)
    elif op_lower in ("in", "contains"):
        if isinstance(target, (list, tuple, set)):
            return val in target or str(val) in [str(x) for x in target]
        return str(val) in str(target)
    elif op_lower in ("not_in", "not_contains"):
        if isinstance(target, (list, tuple, set)):
            return val not in target and str(val) not in [str(x) for x in target]
        return str(val) not in str(target)
    elif op_lower in ("between", "range"):
        if isinstance(target, (list, tuple)) and len(target) >= 2:
            return float(target[0]) <= float(val) <= float(target[1])
        return False
    elif op_lower in ("out_of_range", "outside"):
        if isinstance(target, (list, tuple)) and len(target) >= 2:
            num = float(val)
            return num < float(target[0]) or num > float(target[1])
        return False

    return False


def _check_condition_block(val: Any, cond_spec: Any) -> bool:
    """Checks if value matches condition specification dictionary or shorthand."""
    if not isinstance(cond_spec, dict):
        return False

    # Standard { "operator": "gt", "target_value": 8.0 }
    if "operator" in cond_spec:
        op = cond_spec["operator"]
        target = cond_spec.get("target_value", cond_spec.get("value"))
        return _eval_op(val, op, target)

    # Shorthand { "gt": 8.0 } or { "lte": 4.0 } or { "min": 0, "max": 4 }
    for op_key, target_val in cond_spec.items():
        if op_key in ("min", "min_val"):
            if float(val) < float(target_val):
                return False
        elif op_key in ("max", "max_val"):
            if float(val) > float(target_val):
                return False
        else:
            if not _eval_op(val, op_key, target_val):
                return False
    return True


def evaluate_single_rule(
    rule: SafetyRule,
    value_numeric: float | None = None,
    value_text: str | None = None,
    value_jsonb: Any = None,
    unit: str | None = None,
) -> EvaluationDetail:
    """
    Evaluates an observation against a single SafetyRule instance deterministically.
    Returns structured explainable EvaluationDetail.
    """
    cond = rule.condition_jsonb or {}
    field_name = cond.get("field", "value_numeric")
    val, is_present = _extract_field_value(field_name, value_numeric, value_text, value_jsonb)

    source_code = rule.rule_source.source_code if rule.rule_source else "UNKNOWN"
    source_title = rule.rule_source.title if rule.rule_source else "Unknown Source"

    # 1. Missing Value Check
    if not is_present:
        missing_sev = cond.get("missing_value_severity", "DEVIATION")
        return EvaluationDetail(
            rule_id=rule.id,
            rule_code=rule.rule_code,
            rule_name=rule.name,
            version_number=rule.version_number,
            rule_source_id=rule.rule_source_id,
            source_code=source_code,
            source_title=source_title,
            field_evaluated=field_name,
            observed_value=None,
            observed_unit=unit,
            outcome=missing_sev,
            reason=f"Missing required observation value for field '{field_name}' in rule '{rule.rule_code}'.",
            condition_evaluated=cond,
        )

    # 2. Data Type Conversion Validation for Numeric Rules
    is_numeric_rule = any(
        k in cond or k in str(cond) for k in ("gt", "gte", "lt", "lte", "min", "max", "value_numeric", "range")
    )
    if is_numeric_rule:
        try:
            val_float = float(val)
            val = val_float
        except (ValueError, TypeError):
            return EvaluationDetail(
                rule_id=rule.id,
                rule_code=rule.rule_code,
                rule_name=rule.name,
                version_number=rule.version_number,
                rule_source_id=rule.rule_source_id,
                source_code=source_code,
                source_title=source_title,
                field_evaluated=field_name,
                observed_value=val,
                observed_unit=unit,
                outcome="DEVIATION",
                reason=f"Invalid observation type for field '{field_name}'. Expected numeric, got '{type(val).__name__}' ({val}).",
                condition_evaluated=cond,
            )

    # 3. Multi-tier Condition Evaluation (Critical -> Deviation -> Normal)
    unit_str = f" {unit}" if unit else ""

    # Tier A: Explicit "critical" condition
    if "critical" in cond and _check_condition_block(val, cond["critical"]):
        return EvaluationDetail(
            rule_id=rule.id,
            rule_code=rule.rule_code,
            rule_name=rule.name,
            version_number=rule.version_number,
            rule_source_id=rule.rule_source_id,
            source_code=source_code,
            source_title=source_title,
            field_evaluated=field_name,
            observed_value=val,
            observed_unit=unit,
            outcome="CRITICAL",
            reason=f"Observed value {val}{unit_str} breached CRITICAL condition in rule '{rule.rule_code}' ({source_code}).",
            condition_evaluated=cond["critical"],
        )

    # Tier B: Explicit "deviation" condition
    if "deviation" in cond and _check_condition_block(val, cond["deviation"]):
        return EvaluationDetail(
            rule_id=rule.id,
            rule_code=rule.rule_code,
            rule_name=rule.name,
            version_number=rule.version_number,
            rule_source_id=rule.rule_source_id,
            source_code=source_code,
            source_title=source_title,
            field_evaluated=field_name,
            observed_value=val,
            observed_unit=unit,
            outcome="DEVIATION",
            reason=f"Observed value {val}{unit_str} breached DEVIATION condition in rule '{rule.rule_code}' ({source_code}).",
            condition_evaluated=cond["deviation"],
        )

    # Tier C: Explicit "normal" condition
    if "normal" in cond:
        if _check_condition_block(val, cond["normal"]):
            return EvaluationDetail(
                rule_id=rule.id,
                rule_code=rule.rule_code,
                rule_name=rule.name,
                version_number=rule.version_number,
                rule_source_id=rule.rule_source_id,
                source_code=source_code,
                source_title=source_title,
                field_evaluated=field_name,
                observed_value=val,
                observed_unit=unit,
                outcome="NORMAL",
                reason=f"Observed value {val}{unit_str} satisfies NORMAL condition in rule '{rule.rule_code}'.",
                condition_evaluated=cond["normal"],
            )
        else:
            # Failed normal condition -> default action status or DEVIATION
            default_status = rule.action_jsonb.get("safety_status", "DEVIATION")
            return EvaluationDetail(
                rule_id=rule.id,
                rule_code=rule.rule_code,
                rule_name=rule.name,
                version_number=rule.version_number,
                rule_source_id=rule.rule_source_id,
                source_code=source_code,
                source_title=source_title,
                field_evaluated=field_name,
                observed_value=val,
                observed_unit=unit,
                outcome=default_status,
                reason=f"Observed value {val}{unit_str} failed NORMAL bounds in rule '{rule.rule_code}' ({source_code}).",
                condition_evaluated=cond["normal"],
            )

    # Tier D: Single operator condition with action_jsonb
    if "operator" in cond:
        op = cond["operator"]
        target = cond.get("target_value", cond.get("value"))
        if _eval_op(val, op, target):
            action_status = rule.action_jsonb.get("safety_status", "CRITICAL")
            return EvaluationDetail(
                rule_id=rule.id,
                rule_code=rule.rule_code,
                rule_name=rule.name,
                version_number=rule.version_number,
                rule_source_id=rule.rule_source_id,
                source_code=source_code,
                source_title=source_title,
                field_evaluated=field_name,
                observed_value=val,
                observed_unit=unit,
                outcome=action_status,
                reason=f"Observed value {val}{unit_str} matched rule '{rule.rule_code}' ({op} {target}) resulting in {action_status}.",
                condition_evaluated=cond,
            )
        else:
            return EvaluationDetail(
                rule_id=rule.id,
                rule_code=rule.rule_code,
                rule_name=rule.name,
                version_number=rule.version_number,
                rule_source_id=rule.rule_source_id,
                source_code=source_code,
                source_title=source_title,
                field_evaluated=field_name,
                observed_value=val,
                observed_unit=unit,
                outcome="NORMAL",
                reason=f"Observed value {val}{unit_str} is within safe limits for rule '{rule.rule_code}'.",
                condition_evaluated=cond,
            )

    # Default fallback
    return EvaluationDetail(
        rule_id=rule.id,
        rule_code=rule.rule_code,
        rule_name=rule.name,
        version_number=rule.version_number,
        rule_source_id=rule.rule_source_id,
        source_code=source_code,
        source_title=source_title,
        field_evaluated=field_name,
        observed_value=val,
        observed_unit=unit,
        outcome="NORMAL",
        reason=f"Observed value {val}{unit_str} evaluated with rule '{rule.rule_code}'.",
        condition_evaluated=cond,
    )


def evaluate_rules_set(
    rules: list[SafetyRule],
    value_numeric: float | None = None,
    value_text: str | None = None,
    value_jsonb: Any = None,
    unit: str | None = None,
) -> RuleEvaluationResult:
    """
    Evaluates an observation across all applicable rules.
    Aggregates overall safety status: CRITICAL > DEVIATION > NORMAL.
    """
    if not rules:
        return RuleEvaluationResult(
            overall_status="NORMAL",
            rules_evaluated_count=0,
            details=[],
        )

    details: list[EvaluationDetail] = []
    has_critical = False
    has_deviation = False

    for rule in rules:
        detail = evaluate_single_rule(
            rule=rule,
            value_numeric=value_numeric,
            value_text=value_text,
            value_jsonb=value_jsonb,
            unit=unit,
        )
        details.append(detail)
        if detail.outcome == "CRITICAL":
            has_critical = True
        elif detail.outcome == "DEVIATION":
            has_deviation = True

    if has_critical:
        overall = "CRITICAL"
    elif has_deviation:
        overall = "DEVIATION"
    else:
        overall = "NORMAL"

    return RuleEvaluationResult(
        overall_status=overall,
        rules_evaluated_count=len(rules),
        details=details,
    )


def evaluate_and_persist_entry_safety(
    db: Session,
    entry: Entry,
    task: Task,
) -> RuleEvaluationResult:
    """
    Evaluates an Entry against all bound & active safety rules,
    writes EntrySafetyEvaluation records to DB, and updates Entry.safety_status.
    Runs inside the task execution DB transaction.
    """
    template_id = task.template_id
    category_id = task.template.category_id if task.template else None

    # Fetch applicable rules gated by RuleSource.review_status == 'VERIFIED'
    rules = repository.get_applicable_rules(
        db=db,
        template_id=template_id,
        category_id=category_id,
        restaurant_id=task.restaurant_id,
    )

    # Evaluate observation against rules
    result = evaluate_rules_set(
        rules=rules,
        value_numeric=float(entry.value_numeric) if entry.value_numeric is not None else None,
        value_text=entry.value_text,
        value_jsonb=entry.value_jsonb,
        unit=entry.unit,
    )

    # Update Entry safety status
    entry.safety_status = result.overall_status

    # Persist EntrySafetyEvaluation snapshot records
    for detail in result.details:
        repository.create_entry_safety_evaluation(
            db=db,
            entry_id=entry.id,
            safety_rule_id=detail.rule_id,
            rule_source_id=detail.rule_source_id,
            evaluation_result=detail.outcome,
            details_jsonb=detail.model_dump(mode="json"),
        )

    db.flush()
    return result
