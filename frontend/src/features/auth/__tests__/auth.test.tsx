import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from '../../../context/AuthContext';
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

  const renderLoginPage = async (initialEntries = ['/login']) => {
    const utils = render(
      <MemoryRouter initialEntries={initialEntries}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/staff/dashboard" element={<div>Staff Dashboard Mock</div>} />
            <Route path="/manager/dashboard" element={<div>Manager Dashboard Mock</div>} />
            <Route path="/admin/dashboard" element={<div>Admin Dashboard Mock</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );

    // Wait for AuthProvider's background refresh on mount to settle
    await waitFor(() => {
      expect(authService.refresh).toHaveBeenCalled();
    });
    await act(async () => {
      await Promise.resolve();
    });

    return utils;
  };

  it('renders branding title and login mode tabs', async () => {
    await renderLoginPage();

    expect(screen.getByText('Bharat FoodSafe')).toBeDefined();
    expect(screen.getByText('Kitchen Staff / Manager')).toBeDefined();
    expect(screen.getByText('Platform Admin')).toBeDefined();
    expect(screen.getByLabelText('Mobile Phone Number')).toBeDefined();
    expect(screen.getByLabelText('Security PIN')).toBeDefined();
  });

  it('switches to Platform Admin mode when Admin tab is clicked and switches back', async () => {
    await renderLoginPage();

    const adminTab = screen.getByText('Platform Admin');
    fireEvent.click(adminTab);

    expect(screen.getByLabelText('Admin Email Address')).toBeDefined();
    expect(screen.getByLabelText('Password')).toBeDefined();

    // Switch back to staff mode
    const staffTab = screen.getByText('Kitchen Staff / Manager');
    fireEvent.click(staffTab);

    expect(screen.getByLabelText('Mobile Phone Number')).toBeDefined();
    expect(screen.getByLabelText('Security PIN')).toBeDefined();
  });

  it('displays form validation error for invalid phone number', async () => {
    await renderLoginPage();

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

  it('displays form validation error for invalid PIN (non-digit or incorrect length)', async () => {
    await renderLoginPage();

    const phoneInput = screen.getByLabelText('Mobile Phone Number');
    const pinInput = screen.getByLabelText('Security PIN');
    const submitBtn = screen.getByRole('button', { name: 'Sign In with Phone & PIN' });

    // Too short PIN
    fireEvent.change(phoneInput, { target: { value: '9876543210' } });
    fireEvent.change(pinInput, { target: { value: '12' } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('Please enter a valid 4 to 6 digit security PIN.')).toBeDefined();
    });

    // Non-digit PIN
    fireEvent.change(pinInput, { target: { value: 'abcd' } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('Please enter a valid 4 to 6 digit security PIN.')).toBeDefined();
    });
  });

  it('validates admin form fields and displays appropriate validation errors', async () => {
    await renderLoginPage();

    fireEvent.click(screen.getByText('Platform Admin'));

    const emailInput = screen.getByLabelText('Admin Email Address');
    const passwordInput = screen.getByLabelText('Password');
    const form = emailInput.closest('form')!;

    // Invalid email without @
    fireEvent.change(emailInput, { target: { value: 'adminnotanemail' } });
    fireEvent.change(passwordInput, { target: { value: 'secret123' } });
    fireEvent.submit(form);

    await waitFor(() => {
      expect(screen.getByText('Please enter a valid email address.')).toBeDefined();
    });

    // Password too short (< 6 chars)
    fireEvent.change(emailInput, { target: { value: 'admin@bharatfoodsafe.io' } });
    fireEvent.change(passwordInput, { target: { value: '123' } });
    fireEvent.submit(form);

    await waitFor(() => {
      expect(screen.getByText('Please enter your admin password.')).toBeDefined();
    });
  });

  it('calls authService.login on valid staff submission and redirects to /staff/dashboard', async () => {
    const mockUser = {
      id: 'usr_staff_01',
      name: 'Rajesh Staff',
      restaurant_id: 'rest_01',
      roles: ['STAFF'],
    };
    (authService.login as ReturnType<typeof vi.fn>).mockResolvedValue({
      access_token: 'mock_staff_token',
      refresh_token: 'mock_staff_refresh',
      token_type: 'bearer',
      expires_in_seconds: 900,
      user: mockUser,
    });

    await renderLoginPage();

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
      expect(screen.getByText('Staff Dashboard Mock')).toBeDefined();
    });
  });

  it('redirects to /manager/dashboard when logged in user has MANAGER role', async () => {
    const mockUser = {
      id: 'usr_mgr_01',
      name: 'Manoj Manager',
      restaurant_id: 'rest_01',
      roles: ['MANAGER'],
    };
    (authService.login as ReturnType<typeof vi.fn>).mockResolvedValue({
      access_token: 'mock_mgr_token',
      refresh_token: 'mock_mgr_refresh',
      token_type: 'bearer',
      expires_in_seconds: 900,
      user: mockUser,
    });

    await renderLoginPage();

    fireEvent.change(screen.getByLabelText('Mobile Phone Number'), {
      target: { value: '9876543210' },
    });
    fireEvent.change(screen.getByLabelText('Security PIN'), {
      target: { value: '1234' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Sign In with Phone & PIN' }));

    await waitFor(() => {
      expect(screen.getByText('Manager Dashboard Mock')).toBeDefined();
    });
  });

  it('submits admin form and redirects to /admin/dashboard on PLATFORM_ADMIN role', async () => {
    const mockUser = {
      id: 'usr_admin_01',
      name: 'Admin Boss',
      roles: ['PLATFORM_ADMIN'],
    };
    (authService.login as ReturnType<typeof vi.fn>).mockResolvedValue({
      access_token: 'mock_admin_token',
      refresh_token: 'mock_admin_refresh',
      token_type: 'bearer',
      expires_in_seconds: 900,
      user: mockUser,
    });

    await renderLoginPage();

    fireEvent.click(screen.getByText('Platform Admin'));

    fireEvent.change(screen.getByLabelText('Admin Email Address'), {
      target: { value: 'superadmin@bharatfoodsafe.io' },
    });
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'supersecretpass' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Sign In as Admin' }));

    await waitFor(() => {
      expect(authService.login).toHaveBeenCalledWith({
        email: 'superadmin@bharatfoodsafe.io',
        password: 'supersecretpass',
      });
      expect(screen.getByText('Admin Dashboard Mock')).toBeDefined();
    });
  });

  it('redirects to /staff/dashboard if user has roles other than manager or admin', async () => {
    const mockUser = {
      id: 'usr_auditor_01',
      name: 'Auditor External',
      roles: ['AUDITOR'],
    };
    (authService.login as ReturnType<typeof vi.fn>).mockResolvedValue({
      access_token: 'mock_auditor_token',
      refresh_token: 'mock_auditor_refresh',
      token_type: 'bearer',
      expires_in_seconds: 900,
      user: mockUser,
    });

    await renderLoginPage();

    fireEvent.change(screen.getByLabelText('Mobile Phone Number'), {
      target: { value: '9876543210' },
    });
    fireEvent.change(screen.getByLabelText('Security PIN'), {
      target: { value: '1234' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Sign In with Phone & PIN' }));

    await waitFor(() => {
      expect(screen.getByText('Staff Dashboard Mock')).toBeDefined();
    });
  });

  it('displays auth error message when login fails with server error', async () => {
    (authService.login as ReturnType<typeof vi.fn>).mockRejectedValue({
      response: {
        data: {
          error: {
            message: 'Invalid credentials provided.',
          },
        },
      },
    });

    await renderLoginPage();

    fireEvent.change(screen.getByLabelText('Mobile Phone Number'), {
      target: { value: '9876543210' },
    });
    fireEvent.change(screen.getByLabelText('Security PIN'), {
      target: { value: '1234' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Sign In with Phone & PIN' }));

    await waitFor(() => {
      expect(screen.getByText('Invalid credentials provided.')).toBeDefined();
    });
  });
});
