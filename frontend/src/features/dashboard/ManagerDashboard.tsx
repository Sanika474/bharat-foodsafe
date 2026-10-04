import React from 'react';
import { useAuth } from '../../hooks/useAuth';
import { Button } from '../../components/ui/Button';

export const ManagerDashboard: React.FC = () => {
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-6 text-center">
      <div className="w-full max-w-lg bg-white p-8 rounded-3xl shadow-sm border border-slate-200 flex flex-col items-center gap-4">
        <div className="w-16 h-16 bg-blue-100 text-blue-600 rounded-2xl flex items-center justify-center font-bold text-xl shadow-inner">
          MD
        </div>
        <div className="inline-flex items-center gap-2 px-3 py-1 bg-blue-50 text-blue-700 rounded-full text-xs font-bold border border-blue-200">
          <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
          Active Manager Session
        </div>
        <h1 className="text-2xl font-extrabold text-slate-900">
          Manager Portal: {user?.name}
        </h1>
        <p className="text-slate-600 text-sm">
          Outlet Operational Compliance & Incident Resolution Overview
        </p>
        <div className="w-full bg-slate-50 p-4 rounded-xl text-xs text-slate-600 flex flex-col gap-1 text-left font-mono">
          <div><span className="font-bold text-slate-800">User ID:</span> {user?.id}</div>
          <div><span className="font-bold text-slate-800">Tenant ID:</span> {user?.restaurant_id || 'Global'}</div>
          <div><span className="font-bold text-slate-800">Roles:</span> {user?.roles.join(', ')}</div>
        </div>
        <Button variant="outline" size="md" onClick={() => logout()} className="mt-2 w-full">
          Sign Out
        </Button>
      </div>
    </div>
  );
};
