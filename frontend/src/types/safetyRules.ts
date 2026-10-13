// Bharat FoodSafe — Regulatory Safety Rules & Source Types

export type RuleReviewStatus = 'DRAFT' | 'PENDING_REVIEW' | 'VERIFIED' | 'DEPRECATED' | 'UNKNOWN';

export type EvaluationOutcome = 'NORMAL' | 'DEVIATION' | 'CRITICAL' | 'UNEVALUATED' | 'UNAVAILABLE';

export type RegulatoryTier =
  | 'STATUTORY' // Legally mandated provision in official Gazette
  | 'INSPECTION_BENCHMARK' // Official FSSAI inspection / audit benchmark
  | 'RECOMMENDATION' // Recommendatory operational guidance
  | 'OPERATIONAL_THRESHOLD'; // Internal operational threshold pending approval

export interface RuleSource {
  id: string;
  source_code: string;
  title: string;
  issuing_authority: string;
  document_reference?: string | null;
  review_status: RuleReviewStatus;
  effective_date?: string | null;
  verified_by?: string | null;
  verified_at?: string | null;
}

export interface EvaluationDetail {
  rule_id: string;
  rule_code: string;
  rule_name: string;
  version_number: number;
  rule_source_id: string;
  source_code: string;
  source_title: string;
  field_evaluated: string;
  observed_value: number | string | Record<string, unknown> | null;
  observed_unit?: string | null;
  outcome: 'NORMAL' | 'DEVIATION' | 'CRITICAL';
  reason: string;
  condition_evaluated?: Record<string, unknown> | null;
}

export interface RuleEvaluationResult {
  overall_status: 'NORMAL' | 'DEVIATION' | 'CRITICAL';
  rules_evaluated_count: number;
  details: EvaluationDetail[];
}

export interface SafeEvaluationDisplayState {
  status: EvaluationOutcome;
  label: string;
  variant: 'success' | 'warning' | 'error' | 'neutral';
  isSafe: boolean;
  isUnevaluated: boolean;
  requiresCapa: boolean;
  description: string;
}

export interface RuleSourceDisplayState {
  status: RuleReviewStatus;
  label: string;
  variant: 'success' | 'warning' | 'error' | 'neutral';
  isActivatable: boolean;
  description: string;
}
