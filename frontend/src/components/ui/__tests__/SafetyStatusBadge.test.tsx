import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SafetyStatusBadge } from '../SafetyStatusBadge';
import { RuleEvaluationResult } from '../../../types/safetyRules';

describe('SafetyStatusBadge Component', () => {
  describe('Evaluation Result Rendering', () => {
    it('renders fail-safe UNEVALUATED warning when rules_evaluated_count is 0', () => {
      const evaluation: RuleEvaluationResult = {
        overall_status: 'NORMAL',
        rules_evaluated_count: 0,
        details: [],
      };

      render(<SafetyStatusBadge evaluation={evaluation} showDescription />);

      const badge = screen.getByTestId('safety-status-badge');
      expect(badge).toBeDefined();
      expect(screen.getByText('No Active Verified Rules')).toBeDefined();
      expect(
        screen.getByText(/No active, verified regulatory rules were applicable/i)
      ).toBeDefined();
    });

    it('renders safe green badge when rules evaluated > 0 and overall_status is NORMAL', () => {
      const evaluation: RuleEvaluationResult = {
        overall_status: 'NORMAL',
        rules_evaluated_count: 3,
        details: [],
      };

      render(<SafetyStatusBadge evaluation={evaluation} showDescription />);

      expect(screen.getByText('Within Safe Bounds')).toBeDefined();
      expect(screen.getByText(/3 active regulatory rule\(s\)/i)).toBeDefined();
    });

    it('renders critical violation with mandatory CAPA tag', () => {
      const evaluation: RuleEvaluationResult = {
        overall_status: 'CRITICAL',
        rules_evaluated_count: 1,
        details: [],
      };

      render(<SafetyStatusBadge evaluation={evaluation} />);

      expect(screen.getByText('Critical Violation')).toBeDefined();
      expect(screen.getByText('CAPA Req.')).toBeDefined();
    });

    it('renders unavailable state when evaluation is null', () => {
      render(<SafetyStatusBadge evaluation={null} />);

      expect(screen.getByText('Evaluation Unavailable')).toBeDefined();
    });
  });

  describe('Rule Source Status Rendering', () => {
    it('renders PENDING_REVIEW with Inactive tag', () => {
      render(<SafetyStatusBadge ruleSourceStatus="PENDING_REVIEW" showDescription />);

      expect(screen.getByText('Pending Regulatory Review')).toBeDefined();
      expect(screen.getByText('Inactive')).toBeDefined();
      expect(screen.getByText(/awaiting qualified compliance officer sign-off/i)).toBeDefined();
    });

    it('renders VERIFIED without Inactive tag', () => {
      render(<SafetyStatusBadge ruleSourceStatus="VERIFIED" />);

      expect(screen.getByText('Verified Rule Source')).toBeDefined();
      expect(screen.queryByText('Inactive')).toBeNull();
    });

    it('renders UNKNOWN for unrecognized source status', () => {
      render(<SafetyStatusBadge ruleSourceStatus="SOME_CUSTOM_STATUS" />);

      expect(screen.getByText('Unverified / Unknown Status')).toBeDefined();
      expect(screen.getByText('Inactive')).toBeDefined();
    });
  });

  describe('Regulatory Tier Rendering', () => {
    it('renders statutory legal mandate tier badge', () => {
      render(<SafetyStatusBadge regulatoryTier="STATUTORY" showDescription />);

      expect(screen.getByText('Legal Mandate')).toBeDefined();
      expect(screen.getByText(/Gazette of India/i)).toBeDefined();
    });

    it('renders inspection benchmark tier badge', () => {
      render(<SafetyStatusBadge regulatoryTier="INSPECTION_BENCHMARK" />);

      expect(screen.getByText('Audit Benchmark')).toBeDefined();
    });

    it('renders recommendation tier badge', () => {
      render(<SafetyStatusBadge regulatoryTier="RECOMMENDATION" />);

      expect(screen.getByText('Guidance')).toBeDefined();
    });

    it('renders internal operational threshold tier badge', () => {
      render(<SafetyStatusBadge regulatoryTier="OPERATIONAL_THRESHOLD" />);

      expect(screen.getByText('Internal Threshold')).toBeDefined();
    });
  });
});
