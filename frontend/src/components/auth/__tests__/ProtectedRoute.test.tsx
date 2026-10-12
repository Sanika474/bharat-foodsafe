import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';
import { ProtectedRoute } from '../ProtectedRoute';
import { useAuth } from '../../../hooks/useAuth';

vi.mock('../../../hooks/useAuth', () => ({
  useAuth: vi.fn(),
}));

describe('ProtectedRoute Component', () => {
  const mockLogout = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading skeleton when authentication is loading', () => {
    (useAuth as ReturnType<typeof vi.fn>).mockReturnValue({
      user: null,
      isAuthenticated: false,
      isLoading: true,
      logout: mockLogout,
    });

    const { container } = render(
      <MemoryRouter>
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    const busyElement = container.querySelector('[aria-busy="true"]');
    expect(busyElement).not.toBeNull();
    expect(screen.queryByText('Protected Content')).toBeNull();
  });

  it('redirects unauthenticated user to /login with state.from location', () => {
    (useAuth as ReturnType<typeof vi.fn>).mockReturnValue({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      logout: mockLogout,
    });

    const LocationDisplay = () => {
      const location = useLocation();
      return (
        <div>
          <span>Login Target</span>
          <span data-testid="from-path">
            {(location.state as { from?: { pathname: string } })?.from?.pathname || 'none'}
          </span>
        </div>
      );
    };

    render(
      <MemoryRouter initialEntries={['/kitchen/tasks']}>
        <Routes>
          <Route path="/login" element={<LocationDisplay />} />
          <Route
            path="/kitchen/tasks"
            element={
              <ProtectedRoute>
                <div>Secret Kitchen Tasks</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Login Target')).toBeDefined();
    expect(screen.getByTestId('from-path').textContent).toBe('/kitchen/tasks');
    expect(screen.queryByText('Secret Kitchen Tasks')).toBeNull();
  });

  it('redirects to /login when authenticated flag is true but user object is null', () => {
    (useAuth as ReturnType<typeof vi.fn>).mockReturnValue({
      user: null,
      isAuthenticated: true,
      isLoading: false,
      logout: mockLogout,
    });

    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route path="/login" element={<div>Login Page</div>} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <div>Dashboard View</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Login Page')).toBeDefined();
    expect(screen.queryByText('Dashboard View')).toBeNull();
  });

  it('renders children when authenticated and no specific roles are required', () => {
    (useAuth as ReturnType<typeof vi.fn>).mockReturnValue({
      user: { id: 'u1', name: 'Chef Test', roles: ['STAFF'] },
      isAuthenticated: true,
      isLoading: false,
      logout: mockLogout,
    });

    render(
      <MemoryRouter>
        <ProtectedRoute>
          <div>Universal Content</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    expect(screen.getByText('Universal Content')).toBeDefined();
  });

  it('renders children when user role matches allowedRoles', () => {
    (useAuth as ReturnType<typeof vi.fn>).mockReturnValue({
      user: { id: 'u1', name: 'Manager Dave', roles: ['MANAGER'] },
      isAuthenticated: true,
      isLoading: false,
      logout: mockLogout,
    });

    render(
      <MemoryRouter>
        <ProtectedRoute allowedRoles={['MANAGER', 'PLATFORM_ADMIN']}>
          <div>Manager Only Area</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    expect(screen.getByText('Manager Only Area')).toBeDefined();
  });

  it('renders Access Denied alert when user lacks required role', () => {
    (useAuth as ReturnType<typeof vi.fn>).mockReturnValue({
      user: { id: 'u1', name: 'Cook John', roles: ['STAFF'] },
      isAuthenticated: true,
      isLoading: false,
      logout: mockLogout,
    });

    render(
      <MemoryRouter>
        <ProtectedRoute allowedRoles={['MANAGER']}>
          <div>Manager Only Area</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    expect(screen.getByText('Access Denied')).toBeDefined();
    expect(screen.getByText(/Your account role \(STAFF\) does not have permission/)).toBeDefined();
    expect(screen.queryByText('Manager Only Area')).toBeNull();
  });

  it('navigates to appropriate dashboard on "Go to My Dashboard" click', () => {
    const originalLocation = window.location;
    // Mock window.location.href assignment
    const hrefSetter = vi.fn();
    // @ts-expect-error Mocking window.location
    delete window.location;
    window.location = {
      ...originalLocation,
      get href() {
        return 'http://localhost/';
      },
      set href(val: string) {
        hrefSetter(val);
      },
    } as unknown as Location;

    try {
      // Test 1: STAFF role redirection
      (useAuth as ReturnType<typeof vi.fn>).mockReturnValue({
        user: { id: 'u1', name: 'Staff User', roles: ['STAFF'] },
        isAuthenticated: true,
        isLoading: false,
        logout: mockLogout,
      });

      const { unmount } = render(
        <MemoryRouter>
          <ProtectedRoute allowedRoles={['MANAGER']}>
            <div>Denied</div>
          </ProtectedRoute>
        </MemoryRouter>
      );

      fireEvent.click(screen.getByRole('button', { name: 'Go to My Dashboard' }));
      expect(hrefSetter).toHaveBeenCalledWith('/staff/dashboard');
      unmount();

      // Test 2: MANAGER role redirection
      (useAuth as ReturnType<typeof vi.fn>).mockReturnValue({
        user: { id: 'u2', name: 'Manager User', roles: ['MANAGER'] },
        isAuthenticated: true,
        isLoading: false,
        logout: mockLogout,
      });

      const { unmount: unmountManager } = render(
        <MemoryRouter>
          <ProtectedRoute allowedRoles={['PLATFORM_ADMIN']}>
            <div>Denied</div>
          </ProtectedRoute>
        </MemoryRouter>
      );

      fireEvent.click(screen.getByRole('button', { name: 'Go to My Dashboard' }));
      expect(hrefSetter).toHaveBeenCalledWith('/manager/dashboard');
      unmountManager();

      // Test 3: PLATFORM_ADMIN role redirection
      (useAuth as ReturnType<typeof vi.fn>).mockReturnValue({
        user: { id: 'u3', name: 'Admin User', roles: ['PLATFORM_ADMIN'] },
        isAuthenticated: true,
        isLoading: false,
        logout: mockLogout,
      });

      const { unmount: unmountAdmin } = render(
        <MemoryRouter>
          <ProtectedRoute allowedRoles={['STAFF']}>
            <div>Denied</div>
          </ProtectedRoute>
        </MemoryRouter>
      );

      fireEvent.click(screen.getByRole('button', { name: 'Go to My Dashboard' }));
      expect(hrefSetter).toHaveBeenCalledWith('/admin/dashboard');
      unmountAdmin();

      // Test 4: Unknown role redirection to /login
      (useAuth as ReturnType<typeof vi.fn>).mockReturnValue({
        user: { id: 'u4', name: 'Guest User', roles: ['GUEST'] },
        isAuthenticated: true,
        isLoading: false,
        logout: mockLogout,
      });

      render(
        <MemoryRouter>
          <ProtectedRoute allowedRoles={['STAFF']}>
            <div>Denied</div>
          </ProtectedRoute>
        </MemoryRouter>
      );

      fireEvent.click(screen.getByRole('button', { name: 'Go to My Dashboard' }));
      expect(hrefSetter).toHaveBeenCalledWith('/login');
    } finally {
      window.location = originalLocation;
    }
  });

  it('calls logout when clicking "Sign Out" in Access Denied view', () => {
    (useAuth as ReturnType<typeof vi.fn>).mockReturnValue({
      user: { id: 'u1', name: 'Staff User', roles: ['STAFF'] },
      isAuthenticated: true,
      isLoading: false,
      logout: mockLogout,
    });

    render(
      <MemoryRouter>
        <ProtectedRoute allowedRoles={['MANAGER']}>
          <div>Denied</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: 'Sign Out' }));
    expect(mockLogout).toHaveBeenCalledTimes(1);
  });
});
