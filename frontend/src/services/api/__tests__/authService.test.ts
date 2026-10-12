import { describe, it, expect, vi, beforeEach } from 'vitest';
import { authService } from '../authService';
import { apiClient, getAccessToken, setAccessToken } from '../client';

describe('authService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setAccessToken(null);
  });

  it('login sends payload, sets access token, and returns AuthData', async () => {
    const mockAuthData = {
      access_token: 'login-token-123',
      refresh_token: 'refresh-token-123',
      token_type: 'bearer',
      expires_in_seconds: 900,
      user: {
        id: 'u1',
        name: 'Staff Member',
        roles: ['STAFF'],
      },
    };

    const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValue({
      data: {
        success: true,
        data: mockAuthData,
      },
    } as any);

    const result = await authService.login({ phone: '9876543210', pin: '1234' });

    expect(postSpy).toHaveBeenCalledWith('/auth/login', { phone: '9876543210', pin: '1234' });
    expect(result).toEqual(mockAuthData);
    expect(getAccessToken()).toBe('login-token-123');

    postSpy.mockRestore();
  });

  it('refresh requests new token, updates in-memory token, and returns AuthData', async () => {
    const mockAuthData = {
      access_token: 'refreshed-token-456',
      refresh_token: 'refreshed-refresh-456',
      token_type: 'bearer',
      expires_in_seconds: 900,
      user: {
        id: 'u1',
        name: 'Staff Member',
        roles: ['STAFF'],
      },
    };

    const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValue({
      data: {
        success: true,
        data: mockAuthData,
      },
    } as any);

    const result = await authService.refresh();

    expect(postSpy).toHaveBeenCalledWith('/auth/refresh');
    expect(result).toEqual(mockAuthData);
    expect(getAccessToken()).toBe('refreshed-token-456');

    postSpy.mockRestore();
  });

  it('logout sends logout request and clears access token in memory', async () => {
    setAccessToken('existing-token');
    const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValue({
      data: { success: true, data: { message: 'Logged out' } },
    } as any);

    await authService.logout();

    expect(postSpy).toHaveBeenCalledWith('/auth/logout');
    expect(getAccessToken()).toBeNull();

    postSpy.mockRestore();
  });

  it('logout clears access token even if API call fails', async () => {
    setAccessToken('existing-token');
    const postSpy = vi.spyOn(apiClient, 'post').mockRejectedValue(new Error('Network error'));

    await expect(authService.logout()).rejects.toThrow('Network error');
    expect(getAccessToken()).toBeNull();

    postSpy.mockRestore();
  });

  it('getMe fetches current user profile data', async () => {
    const mockUser = {
      id: 'u1',
      name: 'Manager User',
      roles: ['MANAGER'],
      restaurant_id: 'r1',
    };

    const getSpy = vi.spyOn(apiClient, 'get').mockResolvedValue({
      data: {
        success: true,
        data: mockUser,
      },
    } as any);

    const result = await authService.getMe();

    expect(getSpy).toHaveBeenCalledWith('/auth/me');
    expect(result).toEqual(mockUser);

    getSpy.mockRestore();
  });
});
