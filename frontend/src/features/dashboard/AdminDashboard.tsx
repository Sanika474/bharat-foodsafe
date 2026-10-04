import React from 'react';
import { useAuth } from '../../hooks/useAuth';
import { Button } from '../../components/ui/Button';

export const AdminDashboard: React.FC = () => {
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen bg-slate-900 text-white flex flex-col items-center justify-center p-6 text-center">
      <div className="w-full max-w-lg bg-slate-800 p-8 rounded-3xl shadow-xl border border-slate-700 flex flex-col items-center gap-4">
        <div className="w-16 h-16 bg-purple-500/20 text-purple-400 rounded-2xl flex items-center justify-center font-bold text-xl shadow-inner border border-purple-500/30">
          AD
        </div>
        <div className="inline-flex items-center gap-2 px-3 py-1 bg-purple-500/10 text-purple-300 rounded-full text-xs font-bold border border-purple-500/30">
          <span className="w-2 h-2 rounded-full bg-purple-400 animate-pulse"></span>
          Platform Admin Session
        </div>
        <h1 className="text-2xl font-extrabold text-white">
          Platform Administration: {user?.name}
        </h1>
        <p className="text-slate-400 text-sm">
          System Multi-Tenant Management & Rule Engine Config
        </p>
        <div className="w-full bg-slate-900/60 p-4 rounded-xl text-xs text-slate-300 flex flex-col gap-1 text-left font-mono border border-slate-700">
          <div><span className="font-bold text-purple-300">User ID:</span> {user?.id}</div>
          <div><span className="font-bold text-purple-300">Tenant Scope:</span> Global Admin</div>
          <div><span className="font-bold text-purple-300">Roles:</span> {user?.roles.join(', ')}</div>
        </div>
        <Button variant="danger" size="md" onClick={() => logout()} className="mt-2 w-full">
          Sign Out
        </Button>
      </div>
    </div>
  );
};
