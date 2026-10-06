import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.main import app
from app.models.identity import Restaurant, Role, User, UserRole
from app.models.tasks_and_rules import (
    Entry,
    EntrySafetyEvaluation,
    RuleSource,
    SafetyRule,
    SafetyRuleBinding,
    Task,
    TaskCategory,
    TaskTemplate,
    TaskTemplateVersion,
)
from app.modules.safety_rules import engine, repository, service
from app.modules.safety_rules.schema import EvaluationDetail, StandaloneEvaluateRequest

client = TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def rules_test_data(db_session: Session):
    # Ensure roles
    staff_role = db_session.query(Role).filter_by(name="STAFF").first()
    if not staff_role:
        staff_role = Role(id=uuid.uuid4(), name="STAFF", is_system_role=True)
        db_session.add(staff_role)

    manager_role = db_session.query(Role).filter_by(name="MANAGER").first()
    if not manager_role:
        manager_role = Role(id=uuid.uuid4(), name="MANAGER", is_system_role=True)
        db_session.add(manager_role)

    db_session.commit()

    # Restaurants A & B
    rest_a = Restaurant(
        id=uuid.uuid4(),
        name=f"Rules Test Rest A {uuid.uuid4().hex[:4]}",
        category="RESTAURANT",
        address_line1="123 Safety St",
        city="Bengaluru",
        state="Karnataka",
        pincode="560001",
        status="ACTIVE",
    )
    rest_b = Restaurant(
        id=uuid.uuid4(),
        name=f"Rules Test Rest B {uuid.uuid4().hex[:4]}",
        category="CLOUD_KITCHEN",
        address_line1="456 Other St",
        city="Mumbai",
        state="Maharashtra",
        pincode="400001",
        status="ACTIVE",
    )
    db_session.add_all([rest_a, rest_b])
    db_session.commit()

    # Staff & Manager Users
    user_a = User(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        name="Staff User A",
        phone=f"+9188{uuid.uuid4().hex[:8]}",
        status="ACTIVE",
    )
    db_session.add(user_a)
    db_session.commit()

    db_session.add(UserRole(id=uuid.uuid4(), user_id=user_a.id, role_id=staff_role.id, restaurant_id=rest_a.id))
    db_session.commit()

    token_a, _ = create_access_token(user_id=user_a.id, tenant_id=rest_a.id, roles=["STAFF"])

    # Rule Sources: Verified vs Draft
    source_verified = RuleSource(
        id=uuid.uuid4(),
        source_code=f"FSSAI_SCHED4_{uuid.uuid4().hex[:4]}",
        title="FSSAI Schedule 4 Standards",
        issuing_authority="FSSAI",
        review_status="VERIFIED",
        effective_date=datetime.now(timezone.utc),
    )
    source_draft = RuleSource(
        id=uuid.uuid4(),
        source_code=f"DRAFT_SOURCE_{uuid.uuid4().hex[:4]}",
        title="Draft Experimental Standards",
        issuing_authority="INTERNAL",
        review_status="DRAFT",
    )
    db_session.add_all([source_verified, source_draft])
    db_session.commit()

    # Categories
    cat_a = TaskCategory(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        name="Cold Storage Temp",
        code=f"COLD_TEMP_{uuid.uuid4().hex[:4]}",
    )
    db_session.add(cat_a)
    db_session.commit()

    # Task Template & Version
    tmpl_a = TaskTemplate(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        category_id=cat_a.id,
        name="Chiller Check",
        code=f"CHILLER_{uuid.uuid4().hex[:4]}",
    )
    db_session.add(tmpl_a)
    db_session.commit()

    tmpl_v1 = TaskTemplateVersion(
        id=uuid.uuid4(),
        template_id=tmpl_a.id,
        version_number=1,
        configuration_jsonb={"requires_evidence": False},
    )
    db_session.add(tmpl_v1)
    db_session.commit()

    # Safety Rules
    # Rule 1: Chiller Temp Rule (Multi-tier: normal <= 4.0, deviation 4.01-8.0, critical > 8.0)
    rule_chiller = SafetyRule(
        id=uuid.uuid4(),
        rule_source_id=source_verified.id,
        rule_code="RULE_CHILLER_TEMP",
        version_number=1,
        name="Chiller Temperature Limits",
        condition_jsonb={
            "field": "value_numeric",
            "normal": {"lte": 4.0},
            "deviation": {"gt": 4.0, "lte": 8.0},
            "critical": {"gt": 8.0},
        },
        action_jsonb={"default_severity": "CRITICAL"},
        is_active=True,
    )
    db_session.add(rule_chiller)

    # Rule 2: Bound to Draft source (Should be ignored)
    rule_draft = SafetyRule(
        id=uuid.uuid4(),
        rule_source_id=source_draft.id,
        rule_code="RULE_DRAFT_IGNORE",
        version_number=1,
        name="Draft Rule",
        condition_jsonb={"field": "value_numeric", "critical": {"gt": 0.0}},
        action_jsonb={},
        is_active=True,
    )
    db_session.add(rule_draft)
    db_session.commit()

    # Bindings
    b1 = SafetyRuleBinding(id=uuid.uuid4(), safety_rule_id=rule_chiller.id, category_id=cat_a.id)
    b2 = SafetyRuleBinding(id=uuid.uuid4(), safety_rule_id=rule_draft.id, category_id=cat_a.id)
    db_session.add_all([b1, b2])
    db_session.commit()

    # Task instance
    task = Task(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        template_id=tmpl_a.id,
        template_version_id=tmpl_v1.id,
        occurrence_key=f"2026-10-07_{uuid.uuid4().hex[:4]}",
        status="PENDING",
        due_at=datetime.now(timezone.utc),
    )
    db_session.add(task)
    db_session.commit()

    yield {
        "rest_a": rest_a,
        "rest_b": rest_b,
        "user_a": user_a,
        "token_a": token_a,
        "source_verified": source_verified,
        "cat_a": cat_a,
        "tmpl_a": tmpl_a,
        "rule_chiller": rule_chiller,
        "task": task,
    }

    # Cleanup
    db_session.query(EntrySafetyEvaluation).delete()
    db_session.query(Entry).delete()
    db_session.query(Task).delete()
    db_session.query(SafetyRuleBinding).delete()
    db_session.query(SafetyRule).delete()
    db_session.query(RuleSource).delete()
    db_session.query(TaskTemplateVersion).delete()
    db_session.query(TaskTemplate).delete()
    db_session.query(TaskCategory).delete()
    db_session.query(UserRole).delete()
    db_session.query(User).delete()
    db_session.query(Restaurant).delete()
    db_session.commit()


# ------------------------------------------------------------------------------
# 1. Deterministic Rule Outcomes & Threshold Boundaries
# ------------------------------------------------------------------------------

def test_normal_outcome(rules_test_data):
    rule = rules_test_data["rule_chiller"]
    detail = engine.evaluate_single_rule(rule, value_numeric=3.5, unit="C")

    assert detail.outcome == "NORMAL"
    assert detail.observed_value == 3.5
    assert "satisfies NORMAL condition" in detail.reason


def test_deviation_outcome(rules_test_data):
    rule = rules_test_data["rule_chiller"]
    detail = engine.evaluate_single_rule(rule, value_numeric=6.5, unit="C")

    assert detail.outcome == "DEVIATION"
    assert detail.observed_value == 6.5
    assert "DEVIATION" in detail.reason


def test_critical_outcome(rules_test_data):
    rule = rules_test_data["rule_chiller"]
    detail = engine.evaluate_single_rule(rule, value_numeric=9.2, unit="C")

    assert detail.outcome == "CRITICAL"
    assert detail.observed_value == 9.2
    assert "CRITICAL" in detail.reason


def test_exact_threshold_boundaries(rules_test_data):
    rule = rules_test_data["rule_chiller"]

    # Boundary 1: Exact max normal limit (4.0) -> NORMAL
    d_exact_4 = engine.evaluate_single_rule(rule, value_numeric=4.0, unit="C")
    assert d_exact_4.outcome == "NORMAL"

    # Boundary 2: Slightly over normal limit (4.001) -> DEVIATION
    d_over_4 = engine.evaluate_single_rule(rule, value_numeric=4.001, unit="C")
    assert d_over_4.outcome == "DEVIATION"

    # Boundary 3: Exact critical limit boundary (8.0) -> DEVIATION (<= 8.0 is deviation, > 8.0 is critical)
    d_exact_8 = engine.evaluate_single_rule(rule, value_numeric=8.0, unit="C")
    assert d_exact_8.outcome == "DEVIATION"

    # Boundary 4: Slightly over critical limit (8.001) -> CRITICAL
    d_over_8 = engine.evaluate_single_rule(rule, value_numeric=8.001, unit="C")
    assert d_over_8.outcome == "CRITICAL"


# ------------------------------------------------------------------------------
# 2. Edge Cases: Missing Observations & Invalid Types
# ------------------------------------------------------------------------------

def test_missing_observation_field(rules_test_data):
    rule = rules_test_data["rule_chiller"]
    # No numeric value supplied for numeric rule
    detail = engine.evaluate_single_rule(rule, value_numeric=None, value_text="No reading")

    assert detail.outcome == "DEVIATION"
    assert "Missing required observation value" in detail.reason


def test_invalid_observation_type(rules_test_data):
    rule = rules_test_data["rule_chiller"]
    # Pass non-convertible string value for numeric field
    detail = engine.evaluate_single_rule(rule, value_numeric=None, value_text="NOT_A_NUMBER")

    assert detail.outcome == "DEVIATION"
    assert "Missing required observation value" in detail.reason


# ------------------------------------------------------------------------------
# 3. Multiple Rules & Severity Precedence (CRITICAL > DEVIATION > NORMAL)
# ------------------------------------------------------------------------------

def test_severity_precedence_aggregation(rules_test_data, db_session: Session):
    source = rules_test_data["source_verified"]

    # Rule A evaluates DEVIATION
    rule_dev = SafetyRule(
        id=uuid.uuid4(),
        rule_source_id=source.id,
        rule_code="RULE_DEV",
        version_number=1,
        name="Deviation Rule",
        condition_jsonb={"field": "value_numeric", "operator": "gt", "target_value": 5.0},
        action_jsonb={"safety_status": "DEVIATION"},
        is_active=True,
    )
    # Rule B evaluates CRITICAL
    rule_crit = SafetyRule(
        id=uuid.uuid4(),
        rule_source_id=source.id,
        rule_code="RULE_CRIT",
        version_number=1,
        name="Critical Rule",
        condition_jsonb={"field": "value_numeric", "operator": "gt", "target_value": 10.0},
        action_jsonb={"safety_status": "CRITICAL"},
        is_active=True,
    )

    res = engine.evaluate_rules_set([rule_dev, rule_crit], value_numeric=12.0)
    # Both matched -> CRITICAL takes precedence
    assert res.overall_status == "CRITICAL"
    assert res.rules_evaluated_count == 2

    res_dev_only = engine.evaluate_rules_set([rule_dev, rule_crit], value_numeric=6.0)
    # Only rule_dev matched -> DEVIATION
    assert res_dev_only.overall_status == "DEVIATION"


# ------------------------------------------------------------------------------
# 4. Rule Version Selection & Gated Activation
# ------------------------------------------------------------------------------

def test_highest_version_selected(db_session: Session, rules_test_data):
    cat = rules_test_data["cat_a"]
    source = rules_test_data["source_verified"]

    # Rule Version 1
    r_v1 = SafetyRule(
        id=uuid.uuid4(),
        rule_source_id=source.id,
        rule_code="RULE_VERSIONED",
        version_number=1,
        name="Version 1",
        condition_jsonb={"field": "value_numeric"},
        action_jsonb={},
        is_active=True,
    )
    # Rule Version 2 (Latest)
    r_v2 = SafetyRule(
        id=uuid.uuid4(),
        rule_source_id=source.id,
        rule_code="RULE_VERSIONED",
        version_number=2,
        name="Version 2",
        condition_jsonb={"field": "value_numeric"},
        action_jsonb={},
        is_active=True,
    )
    db_session.add_all([r_v1, r_v2])
    db_session.commit()

    db_session.add(SafetyRuleBinding(id=uuid.uuid4(), safety_rule_id=r_v1.id, category_id=cat.id))
    db_session.add(SafetyRuleBinding(id=uuid.uuid4(), safety_rule_id=r_v2.id, category_id=cat.id))
    db_session.commit()

    applicable = repository.get_applicable_rules(db_session, category_id=cat.id)
    versioned_rules = [r for r in applicable if r.rule_code == "RULE_VERSIONED"]
    assert len(versioned_rules) == 1
    assert versioned_rules[0].version_number == 2


def test_draft_rule_source_ignored(db_session: Session, rules_test_data):
    cat = rules_test_data["cat_a"]
    applicable = repository.get_applicable_rules(db_session, category_id=cat.id)
    codes = [r.rule_code for r in applicable]

    assert "RULE_CHILLER_TEMP" in codes
    assert "RULE_DRAFT_IGNORE" not in codes


# ------------------------------------------------------------------------------
# 5. Deterministic Repeated Evaluation
# ------------------------------------------------------------------------------

def test_deterministic_repeated_evaluation(rules_test_data):
    rule = rules_test_data["rule_chiller"]

    res1 = engine.evaluate_rules_set([rule], value_numeric=5.5, unit="C")
    res2 = engine.evaluate_rules_set([rule], value_numeric=5.5, unit="C")

    assert res1.overall_status == res2.overall_status == "DEVIATION"
    assert res1.details[0].reason == res2.details[0].reason
    assert res1.rules_evaluated_count == res2.rules_evaluated_count == 1


# ------------------------------------------------------------------------------
# 6. Task Entry Execution Integration & Persistence
# ------------------------------------------------------------------------------

def test_task_entry_execution_persists_safety_evaluations(rules_test_data, db_session: Session):
    token = rules_test_data["token_a"]
    task_id = str(rules_test_data["task"].id)

    payload = {"value_numeric": 3.5, "unit": "C"}
    res = client.post(
        f"/api/v1/tasks/{task_id}/entries",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 201
    body = res.json()
    assert body["success"] is True
    entry_id = body["data"]["id"]
    assert body["data"]["safety_status"] == "NORMAL"

    # Verify EntrySafetyEvaluation persistence in DB
    db_session.expire_all()
    evals = db_session.query(EntrySafetyEvaluation).filter_by(entry_id=entry_id).all()
    assert len(evals) >= 1
    assert evals[0].evaluation_result == "NORMAL"
    entry = db_session.query(Entry).filter_by(id=entry_id).first()
    assert entry.safety_status == "NORMAL"


# ------------------------------------------------------------------------------
# 7. Standalone & Rules API Endpoints
# ------------------------------------------------------------------------------

def test_standalone_evaluate_api(rules_test_data):
    token = rules_test_data["token_a"]
    task_id = str(rules_test_data["task"].id)

    payload = {
        "task_id": task_id,
        "value_numeric": 9.5,
        "unit": "C",
    }
    res = client.post(
        "/api/v1/safety-rules/evaluate",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["data"]["overall_status"] == "CRITICAL"
    assert len(body["data"]["details"]) >= 1


def test_list_safety_rules_api(rules_test_data):
    token = rules_test_data["token_a"]

    res = client.get(
        "/api/v1/safety-rules",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert isinstance(body["data"], list)


def test_list_rule_sources_api(rules_test_data):
    token = rules_test_data["token_a"]

    res = client.get(
        "/api/v1/safety-rules/sources",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert len(body["data"]) >= 1
    codes = [s["source_code"] for s in body["data"]]
    assert rules_test_data["source_verified"].source_code in codes


# ------------------------------------------------------------------------------
# 8. Various Operators & Text/JSON Observation Rules
# ------------------------------------------------------------------------------

def test_text_observation_rules(db_session: Session, rules_test_data):
    source = rules_test_data["source_verified"]

    rule_text = SafetyRule(
        id=uuid.uuid4(),
        rule_source_id=source.id,
        rule_code="RULE_HYGIENE_TEXT",
        version_number=1,
        name="Hygiene Text Check",
        condition_jsonb={"field": "value_text", "operator": "eq", "target_value": "FAILED"},
        action_jsonb={"safety_status": "CRITICAL"},
        is_active=True,
    )

    d_fail = engine.evaluate_single_rule(rule_text, value_text="FAILED")
    assert d_fail.outcome == "CRITICAL"

    d_pass = engine.evaluate_single_rule(rule_text, value_text="PASSED")
    assert d_pass.outcome == "NORMAL"


def test_jsonb_nested_field_rules(db_session: Session, rules_test_data):
    source = rules_test_data["source_verified"]

    rule_json = SafetyRule(
        id=uuid.uuid4(),
        rule_source_id=source.id,
        rule_code="RULE_JSONB_CHECK",
        version_number=1,
        name="Checklist JSON Check",
        condition_jsonb={"field": "value_jsonb.sanitized", "operator": "eq", "target_value": False},
        action_jsonb={"safety_status": "DEVIATION"},
        is_active=True,
    )

    d_not_clean = engine.evaluate_single_rule(rule_json, value_jsonb={"sanitized": False, "temp": 3.0})
    assert d_not_clean.outcome == "DEVIATION"

    d_clean = engine.evaluate_single_rule(rule_json, value_jsonb={"sanitized": True, "temp": 3.0})
    assert d_clean.outcome == "NORMAL"


def test_operators_coverage():
    # Test operators: gte, lt, lte, neq, in, not_in, between, out_of_range
    r_gte = SafetyRule(id=uuid.uuid4(), rule_source_id=uuid.uuid4(), rule_code="R1", version_number=1, name="R1", condition_jsonb={"field": "value_numeric", "operator": "gte", "target_value": 5.0}, action_jsonb={"safety_status": "CRITICAL"})
    assert engine.evaluate_single_rule(r_gte, value_numeric=5.0).outcome == "CRITICAL"
    assert engine.evaluate_single_rule(r_gte, value_numeric=4.9).outcome == "NORMAL"

    r_lt = SafetyRule(id=uuid.uuid4(), rule_source_id=uuid.uuid4(), rule_code="R2", version_number=1, name="R2", condition_jsonb={"field": "value_numeric", "operator": "lt", "target_value": 0.0}, action_jsonb={"safety_status": "CRITICAL"})
    assert engine.evaluate_single_rule(r_lt, value_numeric=-1.0).outcome == "CRITICAL"

    r_neq = SafetyRule(id=uuid.uuid4(), rule_source_id=uuid.uuid4(), rule_code="R3", version_number=1, name="R3", condition_jsonb={"field": "value_text", "operator": "neq", "target_value": "OK"}, action_jsonb={"safety_status": "DEVIATION"})
    assert engine.evaluate_single_rule(r_neq, value_text="BAD").outcome == "DEVIATION"

    r_in = SafetyRule(id=uuid.uuid4(), rule_source_id=uuid.uuid4(), rule_code="R4", version_number=1, name="R4", condition_jsonb={"field": "value_text", "operator": "in", "target_value": ["POOR", "DIRTY"]}, action_jsonb={"safety_status": "CRITICAL"})
    assert engine.evaluate_single_rule(r_in, value_text="DIRTY").outcome == "CRITICAL"

    r_between = SafetyRule(id=uuid.uuid4(), rule_source_id=uuid.uuid4(), rule_code="R5", version_number=1, name="R5", condition_jsonb={"field": "value_numeric", "operator": "between", "target_value": [10.0, 20.0]}, action_jsonb={"safety_status": "DEVIATION"})
    assert engine.evaluate_single_rule(r_between, value_numeric=15.0).outcome == "DEVIATION"
    assert engine.evaluate_single_rule(r_between, value_numeric=25.0).outcome == "NORMAL"

    r_out = SafetyRule(id=uuid.uuid4(), rule_source_id=uuid.uuid4(), rule_code="R6", version_number=1, name="R6", condition_jsonb={"field": "value_numeric", "operator": "out_of_range", "target_value": [0.0, 4.0]}, action_jsonb={"safety_status": "CRITICAL"})
    assert engine.evaluate_single_rule(r_out, value_numeric=5.0).outcome == "CRITICAL"


# ------------------------------------------------------------------------------
# 9. Additional Full Branch Coverage Unit Tests
# ------------------------------------------------------------------------------

def test_extract_field_value_jsonb_direct():
    v, present = engine._extract_field_value("value_jsonb", value_jsonb={"foo": "bar"})
    assert present is True
    assert v == {"foo": "bar"}

    # value_jsonb subkey when value_jsonb is not a dict
    v_sub, present_sub = engine._extract_field_value("value_jsonb.sub", value_jsonb="not_a_dict")
    assert present_sub is False
    assert v_sub is None


def test_eval_op_float_conversion_error_and_invalid_targets():
    # float comparison where target cannot be converted to float in eq / neq
    assert engine._eval_op(10, "eq", "not_a_float") is False
    assert engine._eval_op(10, "neq", "not_a_float") is True

    # in / not_in with string non-iterable target
    assert engine._eval_op("abc", "in", "abcdef") is True
    assert engine._eval_op("xyz", "not_in", "abcdef") is True

    # between / out_of_range with invalid target (not a 2-element list)
    assert engine._eval_op(5, "between", "invalid_target") is False
    assert engine._eval_op(5, "out_of_range", [1.0]) is False


def test_check_condition_block_shorthand_min_max():
    # Non-dict cond_spec
    assert engine._check_condition_block(5.0, "not_a_dict") is False

    # Shorthand min / max
    cond_min = {"min": 10.0}
    assert engine._check_condition_block(5.0, cond_min) is False
    assert engine._check_condition_block(15.0, cond_min) is True

    cond_max = {"max": 10.0}
    assert engine._check_condition_block(15.0, cond_max) is False
    assert engine._check_condition_block(5.0, cond_max) is True


def test_evaluate_single_rule_unconvertible_object():
    rule = SafetyRule(
        id=uuid.uuid4(),
        rule_source_id=uuid.uuid4(),
        rule_code="R_OBJECT",
        version_number=1,
        name="Object Test",
        condition_jsonb={"field": "value_numeric", "operator": "gt", "target_value": 0.0},
        action_jsonb={},
    )
    # Pass an unconvertible object as value_numeric
    detail = engine.evaluate_single_rule(rule, value_numeric={"unconvertible": True})
    assert detail.outcome == "DEVIATION"
    assert "Expected numeric" in detail.reason


def test_evaluate_single_rule_fallback_and_failed_normal():
    # Tier C normal condition fails -> default_status
    rule_normal_fail = SafetyRule(
        id=uuid.uuid4(),
        rule_source_id=uuid.uuid4(),
        rule_code="R_NORM_FAIL",
        version_number=1,
        name="Normal Fail",
        condition_jsonb={"field": "value_numeric", "normal": {"lte": 4.0}},
        action_jsonb={"safety_status": "CRITICAL"},
    )
    detail = engine.evaluate_single_rule(rule_normal_fail, value_numeric=10.0)
    assert detail.outcome == "CRITICAL"

    # Default fallback when condition has no operator/tiers
    rule_empty_cond = SafetyRule(
        id=uuid.uuid4(),
        rule_source_id=uuid.uuid4(),
        rule_code="R_EMPTY",
        version_number=1,
        name="Empty Cond",
        condition_jsonb={"field": "value_numeric"},
        action_jsonb={},
    )
    detail_empty = engine.evaluate_single_rule(rule_empty_cond, value_numeric=2.0)
    assert detail_empty.outcome == "NORMAL"


def test_evaluate_rules_set_empty():
    res = engine.evaluate_rules_set([], value_numeric=5.0)
    assert res.overall_status == "NORMAL"
    assert res.rules_evaluated_count == 0
    assert res.details == []


def test_standalone_evaluate_with_category_and_template_id(rules_test_data):
    token = rules_test_data["token_a"]
    cat_id = str(rules_test_data["cat_a"].id)
    tmpl_id = str(rules_test_data["tmpl_a"].id)

    payload = {
        "category_id": cat_id,
        "template_id": tmpl_id,
        "value_numeric": 3.0,
        "unit": "C",
    }
    res = client.post(
        "/api/v1/safety-rules/evaluate",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["data"]["overall_status"] == "NORMAL"


def test_standalone_evaluate_invalid_task_id(rules_test_data):
    token = rules_test_data["token_a"]
    bogus_id = str(uuid.uuid4())

    res = client.post(
        "/api/v1/safety-rules/evaluate",
        json={"task_id": bogus_id, "value_numeric": 3.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "TASK_NOT_FOUND"


def test_get_entry_evaluations_invalid_entry_id(rules_test_data):
    token = rules_test_data["token_a"]
    bogus_id = str(uuid.uuid4())

    res = client.get(
        f"/api/v1/safety-rules/entries/{bogus_id}/evaluations",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "ENTRY_NOT_FOUND"


def test_engine_remaining_branches_100_percent():
    # Line 35: fallback field extraction
    val, present = engine._extract_field_value("unknown_field_name", value_numeric=5.5)
    assert present is True
    assert val == 5.5

    # Line 70: not_in with list target
    assert engine._eval_op("apple", "not_in", ["banana", "orange"]) is True
    assert engine._eval_op("banana", "not_in", ["banana", "orange"]) is False

    # Line 82: unsupported operator
    assert engine._eval_op(10, "bogus_op", 10) is False

    # Lines 92-94: _check_condition_block with {"operator": "gt", "target_value": 5.0}
    assert engine._check_condition_block(10.0, {"operator": "gt", "target_value": 5.0}) is True
    assert engine._check_condition_block(2.0, {"operator": "gt", "target_value": 5.0}) is False


def test_repository_and_service_direct_functions(db_session: Session, rules_test_data):
    from app.core.tenant import TenantContext
    ctx_a = TenantContext(user_id=rules_test_data["user_a"].id, restaurant_id=rules_test_data["rest_a"].id, roles=["STAFF"])

    # Repository & Service functions
    sources = repository.list_rule_sources(db_session)
    assert len(sources) >= 1

    svc_sources = service.list_rule_sources(db_session, ctx_a)
    assert len(svc_sources) >= 1

    active_rules = service.list_active_rules(db_session, ctx_a)
    assert len(active_rules) >= 1

    # Create & bind custom rule via repository
    src = repository.create_rule_source(db_session, source_code=f"SRC_{uuid.uuid4().hex[:4]}", title="Title", issuing_authority="AUTH")
    rule = repository.create_safety_rule(db_session, rule_source_id=src.id, rule_code=f"R_{uuid.uuid4().hex[:4]}", name="R", condition_jsonb={}, action_jsonb={})
    binding = repository.bind_safety_rule(db_session, safety_rule_id=rule.id, category_id=rules_test_data["cat_a"].id)
    assert binding is not None
    assert repository.get_rule_source_by_code(db_session, src.source_code) is not None


