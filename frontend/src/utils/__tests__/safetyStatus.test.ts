import { describe, it, expect } from 'vitest';
import {
  getSafeEvaluationDisplay,
  getRuleSourceDisplay,
  getRegulatoryTierDisplay,
} from '../safetyStatus';
import { RuleEvaluationResult } from '../../types/safetyRules';

describe('Safety Status Utilities — Fail-Safe Verification', () => {
  describe('getSafeEvaluationDisplay', () => {
    it('returns UNAVAILABLE when evaluation result is null or undefined', () => {
      const displayNull = getSafeEvaluationDisplay(null);
      expect(displayNull.status).toBe('UNAVAILABLE');
      expect(displayNull.isSafe).toBe(false);
      expect(displayNull.isUnevaluated).toBe(true);
      expect(displayNull.requiresCapa).toBe(false);

      const displayUndefined = getSafeEvaluationDisplay(undefined);
      expect(displayUndefined.status).toBe('UNAVAILABLE');
      expect(displayUndefined.isSafe).toBe(false);
      expect(displayUndefined.isUnevaluated).toBe(true);
    });

    it('FAIL-SAFE CRITICAL: returns UNEVALUATED when rules_evaluated_count is 0 even if overall_status is NORMAL', () => {
      // Backend returns overall_status: "NORMAL" with rules_evaluated_count: 0 when no rules are active.
      // Frontend MUST NEVER present this as "Safe" / "Normal"!
      const zeroRulesResult: RuleEvaluationResult = {
        overall_status: 'NORMAL',
        rules_evaluated_count: 0,
        details: [],
      };

      const display = getSafeEvaluationDisplay(zeroRulesResult);

      expect(display.status).toBe('UNEVALUATED');
      expect(display.label).toBe('No Active Verified Rules');
      expect(display.variant).toBe('warning');
      expect(display.isSafe).toBe(false);
      expect(display.isUnevaluated).toBe(true);
      expect(display.requiresCapa).toBe(false);
      expect(display.description).toContain('Review status is pending');
    });

    it('FAIL-SAFE CRITICAL: handles malformed, negative, or non-numeric rules_evaluated_count without defaulting to safe', () => {
      const nullCountResult: any = {
        overall_status: 'NORMAL',
        rules_evaluated_count: null,
      };
      expect(getSafeEvaluationDisplay(nullCountResult).status).toBe('UNEVALUATED');
      expect(getSafeEvaluationDisplay(nullCountResult).isSafe).toBe(false);

      const negativeCountResult: any = {
        overall_status: 'NORMAL',
        rules_evaluated_count: -1,
      };
      expect(getSafeEvaluationDisplay(negativeCountResult).status).toBe('UNEVALUATED');
      expect(getSafeEvaluationDisplay(negativeCountResult).isSafe).toBe(false);

      const nonNumberCountResult: any = {
        overall_status: 'NORMAL',
        rules_evaluated_count: 'invalid',
      };
      expect(getSafeEvaluationDisplay(nonNumberCountResult).status).toBe('UNEVALUATED');
      expect(getSafeEvaluationDisplay(nonNumberCountResult).isSafe).toBe(false);
    });

    it('FAIL-SAFE CRITICAL: returns UNAVAILABLE for unknown or malformed overall_status', () => {
      const unknownStatusResult: any = {
        overall_status: 'SOME_UNRECOGNIZED_STATUS',
        rules_evaluated_count: 5,
      };
      const display = getSafeEvaluationDisplay(unknownStatusResult);
      expect(display.status).toBe('UNAVAILABLE');
      expect(display.isSafe).toBe(false);
      expect(display.label).toBe('Unknown Safety Status');
    });

    it('returns NORMAL only when rules_evaluated_count > 0 and overall_status is NORMAL', () => {
      const safeResult: RuleEvaluationResult = {
        overall_status: 'NORMAL',
        rules_evaluated_count: 2,
        details: [
          {
            rule_id: 'r1',
            rule_code: 'R-01',
            rule_name: 'Chilled Storage',
            version_number: 1,
            rule_source_id: 's1',
            source_code: 'FSSAI_SCH4',
            source_title: 'FSSAI Schedule 4',
            field_evaluated: 'temperature',
            observed_value: 3.5,
            observed_unit: '°C',
            outcome: 'NORMAL',
            reason: 'Within range',
          },
        ],
      };

      const display = getSafeEvaluationDisplay(safeResult);

      expect(display.status).toBe('NORMAL');
      expect(display.label).toBe('Within Safe Bounds');
      expect(display.variant).toBe('success');
      expect(display.isSafe).toBe(true);
      expect(display.isUnevaluated).toBe(false);
      expect(display.requiresCapa).toBe(false);
      expect(display.description).toContain('2 active regulatory rule(s)');
    });

    it('returns DEVIATION with warning and no CAPA requirement', () => {
      const deviationResult: RuleEvaluationResult = {
        overall_status: 'DEVIATION',
        rules_evaluated_count: 1,
        details: [],
      };

      const display = getSafeEvaluationDisplay(deviationResult);

      expect(display.status).toBe('DEVIATION');
      expect(display.label).toBe('Operational Deviation');
      expect(display.variant).toBe('warning');
      expect(display.isSafe).toBe(false);
      expect(display.requiresCapa).toBe(false);
    });

    it('returns CRITICAL with error and mandatory CAPA requirement', () => {
      const criticalResult: RuleEvaluationResult = {
        overall_status: 'CRITICAL',
        rules_evaluated_count: 1,
        details: [],
      };

      const display = getSafeEvaluationDisplay(criticalResult);

      expect(display.status).toBe('CRITICAL');
      expect(display.label).toBe('Critical Violation');
      expect(display.variant).toBe('error');
      expect(display.isSafe).toBe(false);
      expect(display.requiresCapa).toBe(true);
      expect(display.description).toContain('Corrective action (CAPA) is mandatory');
    });
  });

  describe('getRuleSourceDisplay', () => {
    it('marks VERIFIED sources as activatable', () => {
      const display = getRuleSourceDisplay('VERIFIED');
      expect(display.status).toBe('VERIFIED');
      expect(display.label).toBe('Verified Rule Source');
      expect(display.variant).toBe('success');
      expect(display.isActivatable).toBe(true);
    });

    it('marks PENDING_REVIEW sources as inactive and pending', () => {
      const display = getRuleSourceDisplay('PENDING_REVIEW');
      expect(display.status).toBe('PENDING_REVIEW');
      expect(display.variant).toBe('warning');
      expect(display.isActivatable).toBe(false);
      expect(display.description).toContain('awaiting qualified compliance officer sign-off');
    });

    it('marks DRAFT and DEPRECATED sources as inactive', () => {
      const draft = getRuleSourceDisplay('DRAFT');
      expect(draft.isActivatable).toBe(false);
      expect(draft.variant).toBe('neutral');

      const deprecated = getRuleSourceDisplay('DEPRECATED');
      expect(deprecated.isActivatable).toBe(false);
      expect(deprecated.variant).toBe('error');
    });

    it('marks unknown or null statuses as UNKNOWN and non-activatable', () => {
      const nullDisplay = getRuleSourceDisplay(null);
      expect(nullDisplay.status).toBe('UNKNOWN');
      expect(nullDisplay.isActivatable).toBe(false);

      const unknownDisplay = getRuleSourceDisplay('CUSTOM_UNVERIFIED');
      expect(unknownDisplay.status).toBe('UNKNOWN');
      expect(unknownDisplay.isActivatable).toBe(false);
    });
  });

  describe('getRegulatoryTierDisplay', () => {
    it('accurately distinguishes all four regulatory tiers', () => {
      const statutory = getRegulatoryTierDisplay('STATUTORY');
      expect(statutory.badge).toBe('Legal Mandate');
      expect(statutory.description).toContain('Gazette of India');

      const benchmark = getRegulatoryTierDisplay('INSPECTION_BENCHMARK');
      expect(benchmark.badge).toBe('Audit Benchmark');
      expect(benchmark.description).toContain('Food Safety Officers');

      const recommendation = getRegulatoryTierDisplay('RECOMMENDATION');
      expect(recommendation.badge).toBe('Guidance');
      expect(recommendation.description).toContain('non-statutory');

      const operational = getRegulatoryTierDisplay('OPERATIONAL_THRESHOLD');
      expect(operational.badge).toBe('Internal Threshold');
      expect(operational.description).toContain('awaiting formal regulatory approval');
    });
  });
});
