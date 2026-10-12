import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act, waitFor } from '@testing-library/react';
import React from 'react';
import { AuthProvider, useAuth } from '../AuthContext';
import { authService } from '../../services/api/authService';

vi.mock('../../services/api/authService', () => ({
  authService: {
    login: vi.fn(),
    refresh: vi.fn(),
    logout: vi.fn(),
    getMe: vi.fn(),
  },
}));

// Test consumer component
const Consumer: React.FC = () => {
  const {
    user,
    accessToken,
    isAuthenticated,
    isLoading,
    authError,
    login,
    logout,
    clearError,
  } = useAuth();

  return (
    <div>
      <div data-testid="loading">{isLoading ? 'loading' : 'idle'}</div>
      <div data-testid="auth">{isAuthenticated ? 'authenticated' : 'unauthenticated'}</div>
      <div data-testid="user">{user ? user.name : 'no-user'}</div>
      <div data-testid="token">{accessToken || 'no-token'}</div>
      <div data-testid="error">{authError || 'no-error'}</div>
      <button
        onClick={() => {
          login({ phone: '9876543210', pin: '1234' }).catch(() => {});
        }}
      >
        Login Staff
      </button>
      <button onClick={() => logout()}>Logout</button>
      <button onClick={() => clearError()}>Clear Error</button>
    </div>
  );
};

describe('AuthContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('restores active session on app boot if refresh succeeds', async () => {
    const mockUser = { id: 'u1', name: 'Restored Chef', roles: ['STAFF'] };
    (authService.refresh as ReturnType<typeof vi.fn>).mockResolvedValue({
      access_token: 'boot-token',
      refresh_token: 'boot-refresh',
      user: mockUser,
    });

    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>
    );

    expect(screen.getByTestId('loading').textContent).toBe('loading');

    await waitFor(() => {
      expect(screen.getByTestId('loading').textContent).toBe('idle');
    });

    expect(screen.getByTestId('auth').textContent).toBe('authenticated');
    expect(screen.getByTestId('user').textContent).toBe('Restored Chef');
    expect(screen.getByTestId('token').textContent).toBe('boot-token');
  });

  it('handles failed initial refresh by setting unauthenticated idle state', async () => {
    (authService.refresh as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('No token'));

    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('loading').textContent).toBe('idle');
    });

    expect(screen.getByTestId('auth').textContent).toBe('unauthenticated');
    expect(screen.getByTestId('user').textContent).toBe('no-user');
  });

  it('updates session state upon successful login', async () => {
    (authService.refresh as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('No session'));
    const mockUser = { id: 'u2', name: 'Logged In User', roles: ['MANAGER'] };
    (authService.login as ReturnType<typeof vi.fn>).mockResolvedValue({
      access_token: 'login-token-xyz',
      refresh_token: 'login-refresh-xyz',
      user: mockUser,
    });

    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('loading').textContent).toBe('idle');
    });

    await act(async () => {
      screen.getByText('Login Staff').click();
    });

    expect(screen.getByTestId('auth').textContent).toBe('authenticated');
    expect(screen.getByTestId('user').textContent).toBe('Logged In User');
    expect(screen.getByTestId('token').textContent).toBe('login-token-xyz');
    expect(screen.getByTestId('error').textContent).toBe('no-error');
  });

  it('captures API error response message upon failed login', async () => {
    (authService.refresh as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('No session'));
    const apiError = {
      response: {
        data: {
          error: {
            message: 'Invalid phone or PIN entered.',
          },
        },
      },
    };
    (authService.login as ReturnType<typeof vi.fn>).mockRejectedValue(apiError);

    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('loading').textContent).toBe('idle');
    });

    await act(async () => {
      screen.getByText('Login Staff').click();
    });

    expect(screen.getByTestId('error').textContent).toBe('Invalid phone or PIN entered.');
    expect(screen.getByTestId('auth').textContent).toBe('unauthenticated');

    // clearError resets the error
    act(() => {
      screen.getByText('Clear Error').click();
    });
    expect(screen.getByTestId('error').textContent).toBe('no-error');
  });

  it('captures generic error message if login throws non-Axios error', async () => {
    (authService.refresh as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('No session'));
    (authService.login as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Connection refused'));

    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('loading').textContent).toBe('idle');
    });

    await act(async () => {
      screen.getByText('Login Staff').click();
    });

    expect(screen.getByTestId('error').textContent).toBe(
      'Authentication failed. Please check your credentials.'
    );
  });

  it('clears session on logout', async () => {
    const mockUser = { id: 'u1', name: 'Active User', roles: ['STAFF'] };
    (authService.refresh as ReturnType<typeof vi.fn>).mockResolvedValue({
      access_token: 'active-token',
      refresh_token: 'active-refresh',
      user: mockUser,
    });
    (authService.logout as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);

    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('auth').textContent).toBe('authenticated');
    });

    await act(async () => {
      screen.getByText('Logout').click();
    });

    expect(authService.logout).toHaveBeenCalled();
    expect(screen.getByTestId('auth').textContent).toBe('unauthenticated');
    expect(screen.getByTestId('user').textContent).toBe('no-user');
  });

  it('throws an error when useAuth is consumed outside AuthProvider', () => {
    const BadConsumer: React.FC = () => {
      useAuth();
      return <div>Bad</div>;
    };

    // Suppress React boundary console.error for expected throw
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    expect(() => render(<BadConsumer />)).toThrow('useAuth must be used within an AuthProvider');

    consoleSpy.mockRestore();
  });
});
