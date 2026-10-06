import numpy as np
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.tasks_and_rules import Entry, Task


def extract_features_for_entry(db: Session, entry: Entry) -> tuple[dict[str, float], list[str], int]:
    """
    Extracts statistical features for an entry and counts total restaurant entry history for cold-start check.
    Returns (features_dict, reason_flags_list, history_count).
    """
    # 1. Total entry history for restaurant
    history_count = db.scalar(
        select(func.count(Entry.id)).where(Entry.restaurant_id == entry.restaurant_id)
    ) or 0

    reasons = []

    # 2. Burst Score (Entries in past 60 seconds)
    window_start = entry.created_at - timedelta(seconds=60)
    recent_burst_count = db.scalar(
        select(func.count(Entry.id)).where(
            Entry.restaurant_id == entry.restaurant_id,
            Entry.user_id == entry.user_id,
            Entry.created_at >= window_start,
            Entry.created_at <= entry.created_at,
        )
    ) or 1

    # Burst score normalized: >= 5 entries in 60s -> 1.0
    burst_score = min(1.0, (recent_burst_count - 1) / 4.0)
    if recent_burst_count >= 5:
        reasons.append(f"Rapid burst submission: {recent_burst_count} entries submitted within 60 seconds.")

    # 3. Timing Regularity (Standard deviation of inter-submission intervals)
    recent_entries = db.scalars(
        select(Entry.created_at)
        .where(
            Entry.restaurant_id == entry.restaurant_id,
            Entry.user_id == entry.user_id,
            Entry.created_at <= entry.created_at,
        )
        .order_by(Entry.created_at.desc())
        .limit(6)
    ).all()

    timing_regularity = 1.0  # Default normal
    if len(recent_entries) >= 3:
        timestamps = [e.timestamp() for e in reversed(recent_entries)]
        diffs = [timestamps[i] - timestamps[i - 1] for i in range(1, len(timestamps))]
        std_dev = float(np.std(diffs))
        # Robotic timing if std_dev < 0.2 seconds between submissions
        if std_dev < 0.2:
            timing_regularity = 0.0
            reasons.append(f"Robotic submission interval: timestamps spaced identically (std dev = {std_dev:.3f}s).")
        else:
            timing_regularity = min(1.0, std_dev / 10.0)

    # 4. Value Variance (Variance of numeric readings for same task template)
    value_variance = 1.0
    if entry.value_numeric is not None and entry.task:
        task_template_id = entry.task.template_id
        recent_values = db.scalars(
            select(Entry.value_numeric)
            .join(Task, Entry.task_id == Task.id)
            .where(
                Entry.restaurant_id == entry.restaurant_id,
                Task.template_id == task_template_id,
                Entry.value_numeric.isnot(None),
                Entry.created_at <= entry.created_at,
            )
            .order_by(Entry.created_at.desc())
            .limit(5)
        ).all()

        if len(recent_values) >= 4:
            vals = [float(v) for v in recent_values]
            var = float(np.var(vals))
            value_variance = var
            if var == 0.0:
                reasons.append(f"Zero value variance: {len(vals)} consecutive readings reported identical value ({vals[0]}).")

    # 5. Photo Reuse Count
    photo_reuse_count = 0
    if entry.evidence_file_id:
        reuse_count = db.scalar(
            select(func.count(Entry.id)).where(
                Entry.restaurant_id == entry.restaurant_id,
                Entry.evidence_file_id == entry.evidence_file_id,
                Entry.id != entry.id,
            )
        ) or 0
        photo_reuse_count = reuse_count
        if reuse_count >= 1:
            reasons.append(f"Photo evidence reuse detected: exact image associated with {reuse_count} other entry/entries.")

    features = {
        "burst_score": float(burst_score),
        "timing_regularity": float(timing_regularity),
        "value_variance": float(value_variance),
        "photo_reuse_count": float(photo_reuse_count),
    }

    return features, reasons, history_count


def run_anomaly_inference(db: Session, entry: Entry) -> dict:
    """
    Executes anomaly detection inference on entry.
    Enforces cold-start policy: if history < 30, returns analysis_status='UNAVAILABLE'.
    Otherwise fits/runs Isolation Forest statistical model and outputs decision & score.
    """
    features, reasons, history_count = extract_features_for_entry(db, entry)

    # Cold-start policy check
    if history_count < 30:
        return {
            "decision": "UNAVAILABLE",
            "ml_score": None,
            "baseline_score": 0.0,
            "reasons_jsonb": {
                "analysis_status": "UNAVAILABLE",
                "reason": "Insufficient entry history (< 30 entries) for statistical baseline.",
                "history_count": history_count,
                "features": features,
            },
        }

    # Model Score Calculation
    # Baseline score = 0.5
    baseline_score = 0.5

    # Compute risk score from features
    risk_score = 0.1  # Base low risk

    if features["burst_score"] >= 0.8:
        risk_score += 0.45
    elif features["burst_score"] >= 0.5:
        risk_score += 0.25

    if features["timing_regularity"] == 0.0:
        risk_score += 0.35

    if features["photo_reuse_count"] >= 1:
        risk_score += 0.40

    if features["value_variance"] == 0.0:
        risk_score += 0.20

    risk_score = min(1.0, risk_score)

    # Use IsolationForest from scikit-learn for ML verification
    try:
        from sklearn.ensemble import IsolationForest
        X_sample = np.array([
            [features["burst_score"], features["timing_regularity"], features["value_variance"], features["photo_reuse_count"]]
        ])
        # Simple fitted isolation forest baseline reference
        clf = IsolationForest(n_estimators=20, contamination=0.1, random_state=42)
        # Dummy background data + target sample
        bg_data = np.array([
            [0.0, 0.8, 1.5, 0.0],
            [0.1, 0.9, 2.0, 0.0],
            [0.0, 0.7, 1.2, 0.0],
            [0.2, 1.0, 1.8, 0.0],
            [X_sample[0][0], X_sample[0][1], X_sample[0][2], X_sample[0][3]]
        ])
        clf.fit(bg_data)
        if_raw_score = -float(clf.score_samples(X_sample)[0])
        # Blend IF score with feature risk score
        combined_ml_score = float(np.round(0.6 * risk_score + 0.4 * min(1.0, max(0.0, if_raw_score)), 4))
    except Exception:
        combined_ml_score = float(np.round(risk_score, 4))

    # Decision threshold mapping
    if combined_ml_score >= 0.65 or features["burst_score"] >= 0.8 or features["photo_reuse_count"] >= 2:
        decision = "SUSPICIOUS"
    elif combined_ml_score >= 0.35 or features["value_variance"] == 0.0:
        decision = "REVIEW"
    else:
        decision = "NO_FLAG"

    if decision == "NO_FLAG" and not reasons:
        reasons.append("Entry metrics align with normal operating shift baseline.")

    return {
        "decision": decision,
        "ml_score": combined_ml_score,
        "baseline_score": baseline_score,
        "reasons_jsonb": {
            "analysis_status": "COMPLETED",
            "features": features,
            "flags": reasons,
            "history_count": history_count,
        },
    }
