import React from 'react';

export interface CardProps {
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
}

export const Card: React.FC<CardProps> = ({ children, className = '', onClick }) => {
  return (
    <div
      onClick={onClick}
      className={`bg-white border border-slate-200 rounded-xl p-4 sm:p-6 shadow-sm ${
        onClick ? 'cursor-pointer hover:border-slate-300 hover:shadow-md transition-all' : ''
      } ${className}`}
    >
      {children}
    </div>
  );
};
