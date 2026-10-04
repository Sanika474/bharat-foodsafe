import React, { createContext, useContext, useEffect, useState } from 'react';
import { authService } from '../services/api/authService';
import { getAccessToken, setAccessToken, setOnSessionExpired } from '../services/api/client';
import { LoginPayload, User } from '../types';

export interface AuthContextType {
  user: User | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  authError: string | null;
  login: (payload: LoginPayload) => Promise<User>;
  logout: () => Promise<void>;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [accessToken, setAccessTokenState] = useState<string | null>(getAccessToken());
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [authError, setAuthError] = useState<string | null>(null);

  const updateSessionState = (newUser: User | null, token: string | null) => {
    setUser(newUser);
    setAccessTokenState(token);
    setAccessToken(token);
    setIsAuthenticated(!!newUser);
  };

  useEffect(() => {
    setOnSessionExpired(() => {
      updateSessionState(null, null);
    });

    const initializeAuth = async () => {
      setIsLoading(true);
      try {
        // Try background token refresh on app boot
        const authData = await authService.refresh();
        updateSessionState(authData.user, authData.access_token);
      } catch {
        updateSessionState(null, null);
      } finally {
        setIsLoading(false);
      }
    };

    initializeAuth();
  }, []);

  const login = async (payload: LoginPayload): Promise<User> => {
    setAuthError(null);
    try {
      const authData = await authService.login(payload);
      updateSessionState(authData.user, authData.access_token);
      return authData.user;
    } catch (err: unknown) {
      let msg = 'Authentication failed. Please check your credentials.';
      if (
        err &&
        typeof err === 'object' &&
        'response' in err &&
        err.response &&
        typeof err.response === 'object' &&
        'data' in err.response &&
        err.response.data &&
        typeof err.response.data === 'object' &&
        'error' in err.response.data &&
        err.response.data.error &&
        typeof err.response.data.error === 'object' &&
        'message' in err.response.data.error
      ) {
        msg = String(err.response.data.error.message);
      }
      setAuthError(msg);
      throw new Error(msg);
    }
  };

  const logout = async (): Promise<void> => {
    try {
      await authService.logout();
    } finally {
      updateSessionState(null, null);
    }
  };

  const clearError = () => setAuthError(null);

  return (
    <AuthContext.Provider
      value={{
        user,
        accessToken,
        isAuthenticated,
        isLoading,
        authError,
        login,
        logout,
        clearError,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
