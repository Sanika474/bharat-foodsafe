import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { Alert } from '../ui/Alert';
import { Button } from '../ui/Button';
import { Skeleton } from '../ui/Skeleton';

export interface ProtectedRouteProps {
  children: React.ReactNode;
  allowedRoles?: string[];
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children, allowedRoles }) => {
  const { user, isAuthenticated, isLoading, logout } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-6" aria-busy="true">
        <div className="w-full max-w-md bg-white p-8 rounded-2xl shadow-sm border border-slate-200 flex flex-col gap-4">
          <Skeleton className="h-8 w-48 mx-auto" />
          <Skeleton className="h-4 w-64 mx-auto" />
          <Skeleton className="h-12 w-full mt-4" />
        </div>
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (allowedRoles && allowedRoles.length > 0) {
    const hasRole = allowedRoles.some((role) => user.roles.includes(role));
    if (!hasRole) {
      return (
        <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-6">
          <div className="w-full max-w-md bg-white p-8 rounded-2xl shadow-md border border-slate-200 flex flex-col gap-6 text-center">
            <Alert
              variant="error"
              title="Access Denied"
              message={`Your account role (${user.roles.join(', ')}) does not have permission to view this page.`}
            />
            <div className="flex flex-col gap-3">
              <Button
                variant="primary"
                size="md"
                onClick={() => {
                  if (user.roles.includes('STAFF')) {
                    window.location.href = '/staff/dashboard';
                  } else if (user.roles.includes('MANAGER')) {
                    window.location.href = '/manager/dashboard';
                  } else if (user.roles.includes('PLATFORM_ADMIN')) {
                    window.location.href = '/admin/dashboard';
                  } else {
                    window.location.href = '/login';
                  }
                }}
              >
                Go to My Dashboard
              </Button>
              <Button variant="outline" size="md" onClick={() => logout()}>
                Sign Out
              </Button>
            </div>
          </div>
        </div>
      );
    }
  }

  return <>{children}</>;
};
