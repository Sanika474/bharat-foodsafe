import React from 'react';
import {
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  AlertOctagon,
  HelpCircle,
  Clock,
  CheckCircle2,
  XCircle,
  FileText,
} from 'lucide-react';
import {
  RegulatoryTier,
  RuleEvaluationResult,
} from '../../types/safetyRules';
import {
  getSafeEvaluationDisplay,
  getRuleSourceDisplay,
  getRegulatoryTierDisplay,
} from '../../utils/safetyStatus';

export interface SafetyStatusBadgeProps {
  /** If provided, renders an evaluation outcome badge fail-safely */
  evaluation?: RuleEvaluationResult | null;
  /** If provided, renders a regulatory rule source status badge */
  ruleSourceStatus?: string | null;
  /** If provided, renders a regulatory authority tier badge */
  regulatoryTier?: RegulatoryTier;
  /** Visual size of badge */
  size?: 'sm' | 'md';
  /** Whether to render subtitle description */
  showDescription?: boolean;
  className?: string;
}

export const SafetyStatusBadge: React.FC<SafetyStatusBadgeProps> = ({
  evaluation,
  ruleSourceStatus,
  regulatoryTier,
  size = 'md',
  showDescription = false,
  className = '',
}) => {
  const sizeClasses = {
    sm: 'text-xs px-2 py-0.5 gap-1.5',
    md: 'text-sm px-2.5 py-1 gap-2',
  };

  const iconSizes = {
    sm: 'w-3.5 h-3.5',
    md: 'w-4 h-4',
  };

  // Case 1: Evaluation outcome
  if (evaluation !== undefined) {
    const display = getSafeEvaluationDisplay(evaluation);

    const variantStyles = {
      success: {
        bg: 'bg-emerald-50 border-emerald-200 text-emerald-800',
        icon: ShieldCheck,
        iconColor: 'text-emerald-600',
      },
      warning: {
        bg: 'bg-amber-50 border-amber-200 text-amber-800',
        icon: display.isUnevaluated ? ShieldAlert : AlertTriangle,
        iconColor: 'text-amber-600',
      },
      error: {
        bg: 'bg-red-50 border-red-200 text-red-800',
        icon: AlertOctagon,
        iconColor: 'text-red-600',
      },
      neutral: {
        bg: 'bg-slate-50 border-slate-200 text-slate-700',
        icon: HelpCircle,
        iconColor: 'text-slate-500',
      },
    };

    const { bg, icon: Icon, iconColor } = variantStyles[display.variant];

    return (
      <div className={`inline-flex flex-col ${className}`} data-testid="safety-status-badge">
        <span
          className={`inline-flex items-center font-medium border rounded-md ${sizeClasses[size]} ${bg}`}
          title={display.description}
          data-status={display.status}
        >
          <Icon className={`${iconSizes[size]} shrink-0 ${iconColor}`} />
          <span>{display.label}</span>
          {display.requiresCapa && (
            <span className="ml-1 text-[10px] font-bold uppercase tracking-wider bg-red-200 text-red-900 px-1 py-0.2 rounded">
              CAPA Req.
            </span>
          )}
        </span>
        {showDescription && (
          <p className="mt-1 text-xs text-slate-500 leading-snug">{display.description}</p>
        )}
      </div>
    );
  }

  // Case 2: Rule Source status
  if (ruleSourceStatus !== undefined) {
    const display = getRuleSourceDisplay(ruleSourceStatus);

    const sourceStyles = {
      success: {
        bg: 'bg-emerald-50 border-emerald-200 text-emerald-800',
        icon: CheckCircle2,
        iconColor: 'text-emerald-600',
      },
      warning: {
        bg: 'bg-amber-50 border-amber-200 text-amber-800',
        icon: Clock,
        iconColor: 'text-amber-600',
      },
      error: {
        bg: 'bg-red-50 border-red-200 text-red-800',
        icon: XCircle,
        iconColor: 'text-red-600',
      },
      neutral: {
        bg: 'bg-slate-50 border-slate-200 text-slate-700',
        icon: FileText,
        iconColor: 'text-slate-500',
      },
    };

    const { bg, icon: Icon, iconColor } = sourceStyles[display.variant];

    return (
      <div className={`inline-flex flex-col ${className}`} data-testid="rule-source-badge">
        <span
          className={`inline-flex items-center font-medium border rounded-md ${sizeClasses[size]} ${bg}`}
          title={display.description}
          data-status={display.status}
        >
          <Icon className={`${iconSizes[size]} shrink-0 ${iconColor}`} />
          <span>{display.label}</span>
          {!display.isActivatable && (
            <span className="ml-1 text-[10px] font-bold uppercase tracking-wider bg-amber-200 text-amber-900 px-1 py-0.2 rounded">
              Inactive
            </span>
          )}
        </span>
        {showDescription && (
          <p className="mt-1 text-xs text-slate-500 leading-snug">{display.description}</p>
        )}
      </div>
    );
  }

  // Case 3: Regulatory tier
  if (regulatoryTier !== undefined) {
    const display = getRegulatoryTierDisplay(regulatoryTier);

    const tierColors: Record<RegulatoryTier, string> = {
      STATUTORY: 'bg-blue-50 border-blue-200 text-blue-800',
      INSPECTION_BENCHMARK: 'bg-purple-50 border-purple-200 text-purple-800',
      RECOMMENDATION: 'bg-cyan-50 border-cyan-200 text-cyan-800',
      OPERATIONAL_THRESHOLD: 'bg-amber-50 border-amber-200 text-amber-800',
    };

    return (
      <div className={`inline-flex flex-col ${className}`} data-testid="regulatory-tier-badge">
        <span
          className={`inline-flex items-center font-medium border rounded-md ${sizeClasses[size]} ${tierColors[regulatoryTier]}`}
          title={display.description}
          data-tier={regulatoryTier}
        >
          <FileText className={`${iconSizes[size]} shrink-0 opacity-75`} />
          <span>{display.badge}</span>
        </span>
        {showDescription && (
          <p className="mt-1 text-xs text-slate-500 leading-snug">{display.description}</p>
        )}
      </div>
    );
  }

  return null;
};
