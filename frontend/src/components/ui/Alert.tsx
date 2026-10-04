import React from 'react';
import { CheckCircle2, AlertTriangle, AlertOctagon, Info } from 'lucide-react';

export interface AlertProps {
  variant: 'success' | 'warning' | 'error' | 'info';
  title?: string;
  message: string;
}

export const Alert: React.FC<AlertProps> = ({ variant, title, message }) => {
  const styles = {
    success: {
      container: 'bg-emerald-50 border-emerald-200 text-emerald-900',
      icon: CheckCircle2,
      iconColor: 'text-emerald-600',
    },
    warning: {
      container: 'bg-amber-50 border-amber-200 text-amber-900',
      icon: AlertTriangle,
      iconColor: 'text-amber-600',
    },
    error: {
      container: 'bg-red-50 border-red-200 text-red-900',
      icon: AlertOctagon,
      iconColor: 'text-red-600',
    },
    info: {
      container: 'bg-blue-50 border-blue-200 text-blue-900',
      icon: Info,
      iconColor: 'text-blue-600',
    },
  };

  const { container, icon: Icon, iconColor } = styles[variant];

  return (
    <div className={`flex items-start p-4 border rounded-xl gap-3 ${container}`} role="alert">
      <Icon className={`w-5 h-5 mt-0.5 shrink-0 ${iconColor}`} />
      <div className="flex-1 text-sm">
        {title && <h4 className="font-bold mb-0.5">{title}</h4>}
        <p className="leading-relaxed">{message}</p>
      </div>
    </div>
  );
};
