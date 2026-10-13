import {
  RegulatoryTier,
  RuleEvaluationResult,
  RuleSourceDisplayState,
  SafeEvaluationDisplayState,
} from '../types/safetyRules';

/**
 * Evaluates an entry's safety result fail-safely.
 *
 * CRITICAL ARCHITECTURAL SAFEGUARD:
 * If rules_evaluated_count === 0, the result must NEVER be converted to 'NORMAL' / 'Safe'.
 * It must explicitly display as 'UNEVALUATED' with a warning badge indicating that
 * no active verified regulatory rules were applied.
 */
export function getSafeEvaluationDisplay(
  result: RuleEvaluationResult | null | undefined
): SafeEvaluationDisplayState {
  if (!result) {
    return {
      status: 'UNAVAILABLE',
      label: 'Evaluation Unavailable',
      variant: 'neutral',
      isSafe: false,
      isUnevaluated: true,
      requiresCapa: false,
      description: 'Safety rule evaluation was not performed or response is unavailable.',
    };
  }

  // FAIL-SAFE INVARIANT: Zero rules evaluated must NEVER be shown as safe/normal!
  // Any missing, null, undefined, NaN, or non-positive count is treated as unevaluated.
  const count = typeof result.rules_evaluated_count === 'number' ? result.rules_evaluated_count : 0;
  if (count <= 0) {
    return {
      status: 'UNEVALUATED',
      label: 'No Active Verified Rules',
      variant: 'warning',
      isSafe: false,
      isUnevaluated: true,
      requiresCapa: false,
      description:
        'No active, verified regulatory rules were applicable for this entry. Review status is pending.',
    };
  }

  if (result.overall_status === 'CRITICAL') {
    return {
      status: 'CRITICAL',
      label: 'Critical Violation',
      variant: 'error',
      isSafe: false,
      isUnevaluated: false,
      requiresCapa: true,
      description:
        'Observed value breached critical food-safety thresholds. Corrective action (CAPA) is mandatory.',
    };
  }

  if (result.overall_status === 'DEVIATION') {
    return {
      status: 'DEVIATION',
      label: 'Operational Deviation',
      variant: 'warning',
      isSafe: false,
      isUnevaluated: false,
      requiresCapa: false,
      description:
        'Observed value is within tolerance deviation. Review equipment or operational process.',
    };
  }

  // Only permit NORMAL / Safe if overall_status is strictly 'NORMAL' AND count > 0!
  if (result.overall_status === 'NORMAL') {
    return {
      status: 'NORMAL',
      label: 'Within Safe Bounds',
      variant: 'success',
      isSafe: true,
      isUnevaluated: false,
      requiresCapa: false,
      description: `Evaluated and verified compliant against ${count} active regulatory rule(s).`,
    };
  }

  // Any unrecognized, malformed, or missing overall_status MUST fall back to warning/unsafe!
  return {
    status: 'UNAVAILABLE',
    label: 'Unknown Safety Status',
    variant: 'warning',
    isSafe: false,
    isUnevaluated: true,
    requiresCapa: false,
    description: 'Unknown outcome encountered during safety evaluation.',
  };
}

/**
 * Returns fail-safe display metadata for a regulatory RuleSource review status.
 *
 * CRITICAL ARCHITECTURAL SAFEGUARD:
 * Only 'VERIFIED' sources are activatable.
 * 'PENDING_REVIEW' sources are explicitly marked as inactive awaiting authorized sign-off.
 * Unknown or missing statuses must NEVER infer approval.
 * Source verification permits activation, but does NOT imply every individual child rule
 * is a statutory mandate; individual rule tiers must be inspected separately.
 */
export function getRuleSourceDisplay(status: string | null | undefined): RuleSourceDisplayState {
  const normalized = (status || '').toUpperCase().trim();

  switch (normalized) {
    case 'VERIFIED':
      return {
        status: 'VERIFIED',
        label: 'Verified Rule Source',
        variant: 'success',
        isActivatable: true,
        description:
          'Source document officially verified. Rules linked to this source are eligible for activation.',
      };
    case 'PENDING_REVIEW':
      return {
        status: 'PENDING_REVIEW',
        label: 'Pending Regulatory Review',
        variant: 'warning',
        isActivatable: false,
        description:
          'Source metadata recorded but awaiting qualified compliance officer sign-off. Rules are inactive.',
      };
    case 'DRAFT':
      return {
        status: 'DRAFT',
        label: 'Draft Source',
        variant: 'neutral',
        isActivatable: false,
        description: 'Source is in initial drafting state. Rules cannot be activated.',
      };
    case 'DEPRECATED':
      return {
        status: 'DEPRECATED',
        label: 'Deprecated / Superseded',
        variant: 'error',
        isActivatable: false,
        description: 'Source has been superseded by newer regulations. Rules are disabled.',
      };
    default:
      return {
        status: 'UNKNOWN',
        label: 'Unverified / Unknown Status',
        variant: 'error',
        isActivatable: false,
        description: 'Source review status is unverified or unknown. Cannot be activated.',
      };
  }
}

/**
 * Distinguishes the legal authority tier of a safety requirement.
 */
export function getRegulatoryTierDisplay(tier: RegulatoryTier): {
  label: string;
  badge: string;
  description: string;
} {
  switch (tier) {
    case 'STATUTORY':
      return {
        label: 'Statutory Legal Mandate',
        badge: 'Legal Mandate',
        description: 'Mandated by parliamentary act or official Gazette of India notification.',
      };
    case 'INSPECTION_BENCHMARK':
      return {
        label: 'FSSAI Inspection Benchmark',
        badge: 'Audit Benchmark',
        description: 'Enforced by Food Safety Officers (FSOs) during official licensing audits.',
      };
    case 'RECOMMENDATION':
      return {
        label: 'Recommendatory Guidance',
        badge: 'Guidance',
        description: 'Official sector best practice recommendation; non-statutory.',
      };
    case 'OPERATIONAL_THRESHOLD':
      return {
        label: 'Internal Operational Threshold',
        badge: 'Internal Threshold',
        description: 'Internal early-warning threshold awaiting formal regulatory approval.',
      };
  }
}
