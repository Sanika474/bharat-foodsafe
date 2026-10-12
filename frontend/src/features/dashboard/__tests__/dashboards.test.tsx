import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { StaffDashboard } from '../StaffDashboard';
import { ManagerDashboard } from '../ManagerDashboard';
import { AdminDashboard } from '../AdminDashboard';
import { useAuth } from '../../../hooks/useAuth';

vi.mock('../../../hooks/useAuth', () => ({
  useAuth: vi.fn(),
}));

describe('Dashboard Components', () => {
  const mockLogout = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('StaffDashboard', () => {
    it('renders staff user information and session details', () => {
      (useAuth as ReturnType<typeof vi.fn>).mockReturnValue({
        user: {
          id: 'usr_staff_01',
          name: 'Sunil Cook',
          restaurant_id: 'rest_blr_01',
          roles: ['STAFF'],
        },
        logout: mockLogout,
      });

      render(<StaffDashboard />);

      expect(screen.getByText('Active Staff Session')).toBeDefined();
      expect(screen.getByText('Welcome, Sunil Cook')).toBeDefined();
      expect(screen.getByText('Kitchen Staff Task Execution Portal')).toBeDefined();
      expect(screen.getByText(/usr_staff_01/)).toBeDefined();
      expect(screen.getByText(/rest_blr_01/)).toBeDefined();
      expect(screen.getByText(/STAFF/)).toBeDefined();
    });

    it('displays fallback Global when restaurant_id is null', () => {
      (useAuth as ReturnType<typeof vi.fn>).mockReturnValue({
        user: {
          id: 'usr_staff_02',
          name: 'Floating Staff',
          restaurant_id: null,
          roles: ['STAFF'],
        },
        logout: mockLogout,
      });

      render(<StaffDashboard />);

      expect(screen.getByText(/Global/)).toBeDefined();
    });

    it('triggers logout when Sign Out button is clicked', () => {
      (useAuth as ReturnType<typeof vi.fn>).mockReturnValue({
        user: {
          id: 'usr_staff_01',
          name: 'Sunil Cook',
          restaurant_id: 'rest_blr_01',
          roles: ['STAFF'],
        },
        logout: mockLogout,
      });

      render(<StaffDashboard />);

      const signOutBtn = screen.getByRole('button', { name: 'Sign Out' });
      fireEvent.click(signOutBtn);

      expect(mockLogout).toHaveBeenCalledTimes(1);
    });
  });

  describe('ManagerDashboard', () => {
    it('renders manager overview and outlet details', () => {
      (useAuth as ReturnType<typeof vi.fn>).mockReturnValue({
        user: {
          id: 'usr_mgr_01',
          name: 'Priya Manager',
          restaurant_id: 'rest_mumbai_02',
          roles: ['MANAGER'],
        },
        logout: mockLogout,
      });

      render(<ManagerDashboard />);

      expect(screen.getByText('Active Manager Session')).toBeDefined();
      expect(screen.getByText('Manager Portal: Priya Manager')).toBeDefined();
      expect(
        screen.getByText('Outlet Operational Compliance & Incident Resolution Overview')
      ).toBeDefined();
      expect(screen.getByText(/usr_mgr_01/)).toBeDefined();
      expect(screen.getByText(/rest_mumbai_02/)).toBeDefined();
      expect(screen.getByText(/MANAGER/)).toBeDefined();
    });

    it('displays fallback Global when manager restaurant_id is undefined', () => {
      (useAuth as ReturnType<typeof vi.fn>).mockReturnValue({
        user: {
          id: 'usr_mgr_02',
          name: 'Regional Lead',
          restaurant_id: undefined,
          roles: ['MANAGER'],
        },
        logout: mockLogout,
      });

      render(<ManagerDashboard />);

      expect(screen.getByText(/Global/)).toBeDefined();
    });

    it('triggers logout when Sign Out button is clicked in manager view', () => {
      (useAuth as ReturnType<typeof vi.fn>).mockReturnValue({
        user: {
          id: 'usr_mgr_01',
          name: 'Priya Manager',
          roles: ['MANAGER'],
        },
        logout: mockLogout,
      });

      render(<ManagerDashboard />);

      fireEvent.click(screen.getByRole('button', { name: 'Sign Out' }));
      expect(mockLogout).toHaveBeenCalledTimes(1);
    });
  });

  describe('AdminDashboard', () => {
    it('renders platform admin portal and global scope details', () => {
      (useAuth as ReturnType<typeof vi.fn>).mockReturnValue({
        user: {
          id: 'usr_admin_01',
          name: 'Super Admin Vikram',
          roles: ['PLATFORM_ADMIN'],
        },
        logout: mockLogout,
      });

      render(<AdminDashboard />);

      expect(screen.getByText('Platform Admin Session')).toBeDefined();
      expect(screen.getByText('Platform Administration: Super Admin Vikram')).toBeDefined();
      expect(
        screen.getByText('System Multi-Tenant Management & Rule Engine Config')
      ).toBeDefined();
      expect(screen.getByText(/usr_admin_01/)).toBeDefined();
      expect(screen.getByText(/Global Admin/)).toBeDefined();
      expect(screen.getByText(/PLATFORM_ADMIN/)).toBeDefined();
    });

    it('triggers logout when Sign Out button is clicked in admin view', () => {
      (useAuth as ReturnType<typeof vi.fn>).mockReturnValue({
        user: {
          id: 'usr_admin_01',
          name: 'Super Admin Vikram',
          roles: ['PLATFORM_ADMIN'],
        },
        logout: mockLogout,
      });

      render(<AdminDashboard />);

      fireEvent.click(screen.getByRole('button', { name: 'Sign Out' }));
      expect(mockLogout).toHaveBeenCalledTimes(1);
    });
  });
});
