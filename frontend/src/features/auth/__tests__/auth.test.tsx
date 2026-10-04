import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from '../../../context/AuthContext';
import { ProtectedRoute } from '../../../components/auth/ProtectedRoute';
import { LoginPage } from '../LoginPage';
import { authService } from '../../../services/api/authService';

vi.mock('../../../services/api/authService', () => ({
  authService: {
    login: vi.fn(),
    refresh: vi.fn(),
    logout: vi.fn(),
    getMe: vi.fn(),
  },
}));

describe('LoginPage Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (authService.refresh as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('No active session'));
  });

  it('renders branding title and login mode tabs', async () => {
    render(
      <MemoryRouter>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </MemoryRouter>
    );

    expect(screen.getByText('Bharat FoodSafe')).toBeDefined();
    expect(screen.getByText('Kitchen Staff / Manager')).toBeDefined();
    expect(screen.getByText('Platform Admin')).toBeDefined();
    expect(screen.getByLabelText('Mobile Phone Number')).toBeDefined();
    expect(screen.getByLabelText('Security PIN')).toBeDefined();
  });

  it('switches to Platform Admin mode when Admin tab is clicked', async () => {
    render(
      <MemoryRouter>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </MemoryRouter>
    );

    const adminTab = screen.getByText('Platform Admin');
    fireEvent.click(adminTab);

    expect(screen.getByLabelText('Admin Email Address')).toBeDefined();
    expect(screen.getByLabelText('Password')).toBeDefined();
  });

  it('displays form validation error for invalid phone number', async () => {
    render(
      <MemoryRouter>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </MemoryRouter>
    );

    const phoneInput = screen.getByLabelText('Mobile Phone Number');
    const pinInput = screen.getByLabelText('Security PIN');
    const submitBtn = screen.getByRole('button', { name: 'Sign In with Phone & PIN' });

    fireEvent.change(phoneInput, { target: { value: '123' } });
    fireEvent.change(pinInput, { target: { value: '1234' } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('Please enter a valid 10-digit mobile phone number.')).toBeDefined();
    });
  });

  it('calls authService.login on valid form submission', async () => {
    const mockUser = {
      id: 'usr_1',
      name: 'Rajesh',
      restaurant_id: 'rest_1',
      roles: ['STAFF'],
    };
    (authService.login as ReturnType<typeof vi.fn>).mockResolvedValue({
      access_token: 'mock_access_token',
      refresh_token: 'mock_refresh_token',
      token_type: 'bearer',
      expires_in_seconds: 900,
      user: mockUser,
    });

    render(
      <MemoryRouter initialEntries={['/login']}>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </MemoryRouter>
    );

    const phoneInput = screen.getByLabelText('Mobile Phone Number');
    const pinInput = screen.getByLabelText('Security PIN');
    const submitBtn = screen.getByRole('button', { name: 'Sign In with Phone & PIN' });

    fireEvent.change(phoneInput, { target: { value: '9876543210' } });
    fireEvent.change(pinInput, { target: { value: '1234' } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(authService.login).toHaveBeenCalledWith({
        phone: '9876543210',
        pin: '1234',
      });
    });
  });
});

describe('ProtectedRoute Component', () => {
  const TestProtectedContent = () => <div>Protected Dashboard View</div>;

  it('redirects to /login when user is not authenticated', async () => {
    (authService.refresh as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Unauthenticated'));

    render(
      <MemoryRouter initialEntries={['/protected']}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<div>Login Page Mock</div>} />
            <Route
              path="/protected"
              element={
                <ProtectedRoute>
                  <TestProtectedContent />
                </ProtectedRoute>
              }
            />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Login Page Mock')).toBeDefined();
    });
  });
});
