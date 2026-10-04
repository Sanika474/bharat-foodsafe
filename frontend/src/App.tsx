import React from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ProtectedRoute } from './components/auth/ProtectedRoute';
import { LoginPage } from './features/auth/LoginPage';
import { StaffDashboard } from './features/dashboard/StaffDashboard';
import { ManagerDashboard } from './features/dashboard/ManagerDashboard';
import { AdminDashboard } from './features/dashboard/AdminDashboard';
import { Skeleton } from './components/ui/Skeleton';

const DefaultRedirect: React.FC = () => {
  const { user, isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6" aria-busy="true">
        <Skeleton className="h-12 w-64 rounded-xl" />
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace />;
  }

  if (user.roles.includes('PLATFORM_ADMIN')) {
    return <Navigate to="/admin/dashboard" replace />;
  } else if (user.roles.includes('MANAGER')) {
    return <Navigate to="/manager/dashboard" replace />;
  } else {
    return <Navigate to="/staff/dashboard" replace />;
  }
};

export const AppRoutes: React.FC = () => {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route
        path="/staff/dashboard"
        element={
          <ProtectedRoute allowedRoles={['STAFF', 'MANAGER', 'PLATFORM_ADMIN']}>
            <StaffDashboard />
          </ProtectedRoute>
        }
      />

      <Route
        path="/manager/dashboard"
        element={
          <ProtectedRoute allowedRoles={['MANAGER', 'PLATFORM_ADMIN']}>
            <ManagerDashboard />
          </ProtectedRoute>
        }
      />

      <Route
        path="/admin/dashboard"
        element={
          <ProtectedRoute allowedRoles={['PLATFORM_ADMIN']}>
            <AdminDashboard />
          </ProtectedRoute>
        }
      />

      <Route path="/" element={<DefaultRedirect />} />
      <Route path="*" element={<DefaultRedirect />} />
    </Routes>
  );
};

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
};

export default App;
