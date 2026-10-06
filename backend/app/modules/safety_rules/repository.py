import uuid
from datetime import datetime, timezone
from typing import Sequence
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.tasks_and_rules import (
    EntrySafetyEvaluation,
    RuleSource,
    SafetyRule,
    SafetyRuleBinding,
    TaskCategory,
    TaskTemplate,
)


def get_rule_source_by_code(db: Session, source_code: str) -> RuleSource | None:
    stmt = select(RuleSource).where(RuleSource.source_code == source_code)
    return db.scalar(stmt)


def create_rule_source(
    db: Session,
    source_code: str,
    title: str,
    issuing_authority: str,
    document_reference: str | None = None,
    review_status: str = "VERIFIED",
) -> RuleSource:
    source = RuleSource(
        id=uuid.uuid4(),
        source_code=source_code,
        title=title,
        issuing_authority=issuing_authority,
        document_reference=document_reference,
        review_status=review_status,
        effective_date=datetime.now(timezone.utc),
        verified_at=datetime.now(timezone.utc) if review_status == "VERIFIED" else None,
    )
    db.add(source)
    db.flush()
    return source


def create_safety_rule(
    db: Session,
    rule_source_id: uuid.UUID,
    rule_code: str,
    name: str,
    condition_jsonb: dict,
    action_jsonb: dict,
    version_number: int = 1,
    description: str | None = None,
    is_active: bool = True,
    supersedes_rule_id: uuid.UUID | None = None,
) -> SafetyRule:
    rule = SafetyRule(
        id=uuid.uuid4(),
        rule_source_id=rule_source_id,
        rule_code=rule_code,
        version_number=version_number,
        name=name,
        description=description,
        condition_jsonb=condition_jsonb,
        action_jsonb=action_jsonb,
        is_active=is_active,
        supersedes_rule_id=supersedes_rule_id,
    )
    db.add(rule)
    db.flush()
    return rule


def bind_safety_rule(
    db: Session,
    safety_rule_id: uuid.UUID,
    category_id: uuid.UUID | None = None,
    template_id: uuid.UUID | None = None,
) -> SafetyRuleBinding:
    binding = SafetyRuleBinding(
        id=uuid.uuid4(),
        safety_rule_id=safety_rule_id,
        category_id=category_id,
        template_id=template_id,
    )
    db.add(binding)
    db.flush()
    return binding


def get_applicable_rules(
    db: Session,
    template_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    restaurant_id: uuid.UUID | None = None,
) -> list[SafetyRule]:
    """
    Finds all active rules bound to the given template or category,
    gated by RuleSource.review_status == 'VERIFIED'.
    Deduplicates by rule_code, returning the highest version_number.
    """
    if not template_id and not category_id:
        return []

    # Build binding match condition
    binding_conditions = []
    if template_id:
        binding_conditions.append(SafetyRuleBinding.template_id == template_id)
    if category_id:
        binding_conditions.append(SafetyRuleBinding.category_id == category_id)

    stmt = (
        select(SafetyRule)
        .join(SafetyRuleBinding, SafetyRule.id == SafetyRuleBinding.safety_rule_id)
        .join(RuleSource, SafetyRule.rule_source_id == RuleSource.id)
        .options(joinedload(SafetyRule.rule_source))
        .where(
            and_(
                SafetyRule.is_active == True,
                RuleSource.review_status == "VERIFIED",
                or_(*binding_conditions),
            )
        )
    )

    rules = db.scalars(stmt).unique().all()

    # Tenant filtering if category is tenant-scoped
    filtered_rules = []
    for r in rules:
        # Check tenant scope if category_id exists on rule bindings
        tenant_match = True
        for b in r.bindings:
            if b.category and b.category.restaurant_id and restaurant_id:
                if b.category.restaurant_id != restaurant_id:
                    tenant_match = False
                    break
        if tenant_match:
            filtered_rules.append(r)

    # Deduplicate by rule_code -> keep highest version_number
    rule_map: dict[str, SafetyRule] = {}
    for r in filtered_rules:
        if r.rule_code not in rule_map or r.version_number > rule_map[r.rule_code].version_number:
            rule_map[r.rule_code] = r

    return list(rule_map.values())


def list_active_rules(
    db: Session,
    restaurant_id: uuid.UUID | None = None,
) -> Sequence[SafetyRule]:
    stmt = (
        select(SafetyRule)
        .join(RuleSource, SafetyRule.rule_source_id == RuleSource.id)
        .options(joinedload(SafetyRule.rule_source), joinedload(SafetyRule.bindings))
        .where(
            and_(
                SafetyRule.is_active == True,
                RuleSource.review_status == "VERIFIED",
            )
        )
    )
    return db.scalars(stmt).unique().all()


def list_rule_sources(db: Session) -> Sequence[RuleSource]:
    stmt = select(RuleSource).order_by(RuleSource.created_at.desc())
    return db.scalars(stmt).all()


def create_entry_safety_evaluation(
    db: Session,
    entry_id: uuid.UUID,
    safety_rule_id: uuid.UUID,
    rule_source_id: uuid.UUID,
    evaluation_result: str,
    details_jsonb: dict,
) -> EntrySafetyEvaluation:
    eval_rec = EntrySafetyEvaluation(
        id=uuid.uuid4(),
        entry_id=entry_id,
        safety_rule_id=safety_rule_id,
        rule_source_id=rule_source_id,
        evaluation_result=evaluation_result,
        details_jsonb=details_jsonb,
        evaluated_at=datetime.now(timezone.utc),
    )
    db.add(eval_rec)
    db.flush()
    return eval_rec


def get_evaluations_by_entry_id(
    db: Session,
    entry_id: uuid.UUID,
) -> Sequence[EntrySafetyEvaluation]:
    stmt = (
        select(EntrySafetyEvaluation)
        .options(
            joinedload(EntrySafetyEvaluation.safety_rule),
            joinedload(EntrySafetyEvaluation.rule_source),
        )
        .where(EntrySafetyEvaluation.entry_id == entry_id)
        .order_by(EntrySafetyEvaluation.created_at.asc())
    )
    return db.scalars(stmt).unique().all()
