import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import axios from 'axios';
import {
  apiClient,
  setAccessToken,
  getAccessToken,
  setOnSessionExpired,
  getApiErrorMessage,
} from '../client';

describe('API Client & Interceptors', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setAccessToken(null);
  });

  afterEach(() => {
    setAccessToken(null);
  });

  describe('Token management', () => {
    it('sets and retrieves access token correctly', () => {
      expect(getAccessToken()).toBeNull();
      setAccessToken('test-token-123');
      expect(getAccessToken()).toBe('test-token-123');
      expect(apiClient.defaults.headers.common.Authorization).toBe('Bearer test-token-123');
      setAccessToken(null);
      expect(getAccessToken()).toBeNull();
      expect(apiClient.defaults.headers.common.Authorization).toBeUndefined();
    });

    it('registers onSessionExpired callback', () => {
      const cb = vi.fn();
      setOnSessionExpired(cb);
      // Callback is retained in module scope
    });
  });

  describe('getApiErrorMessage helper', () => {
    it('extracts error.message from backend ApiResponse payload', () => {
      const axiosErr: any = {
        isAxiosError: true,
        response: {
          data: {
            error: {
              code: 'RULE_VIOLATION',
              message: 'Temperature exceeds safety threshold.',
            },
          },
        },
      };
      expect(getApiErrorMessage(axiosErr)).toBe('Temperature exceeds safety threshold.');
    });

    it('extracts detail string when provided', () => {
      const axiosErr: any = {
        isAxiosError: true,
        response: {
          data: {
            detail: 'Item not found in tenant database.',
          },
        },
      };
      expect(getApiErrorMessage(axiosErr)).toBe('Item not found in tenant database.');
    });

    it('extracts first validation error msg from detail array', () => {
      const axiosErr: any = {
        isAxiosError: true,
        response: {
          data: {
            detail: [{ msg: 'Field is required' }],
          },
        },
      };
      expect(getApiErrorMessage(axiosErr)).toBe('Field is required');
    });

    it('returns friendly messages for standard HTTP status codes without payload', () => {
      expect(getApiErrorMessage({ isAxiosError: true, response: { status: 401 } })).toBe(
        'Session expired or unauthenticated. Please sign in again.'
      );
      expect(getApiErrorMessage({ isAxiosError: true, response: { status: 403 } })).toBe(
        'You do not have permission to perform this action.'
      );
      expect(getApiErrorMessage({ isAxiosError: true, response: { status: 404 } })).toBe(
        'The requested resource was not found.'
      );
      expect(getApiErrorMessage({ isAxiosError: true, response: { status: 500 } })).toBe(
        'A server error occurred. Please try again later.'
      );
      expect(getApiErrorMessage({ isAxiosError: true, code: 'ERR_NETWORK' })).toBe(
        'Network connection error. Please check your internet connection.'
      );
    });

    it('falls back to standard Error message and default string', () => {
      expect(getApiErrorMessage(new Error('Local error'))).toBe('Local error');
      expect(getApiErrorMessage('Something unexpected')).toBe('An unexpected error occurred.');
    });
  });

  describe('Request Interceptor', () => {
    it('attaches Authorization header when access token is present', async () => {
      setAccessToken('bearer-token-abc');

      // Interceptor is index 0
      const requestInterceptor = (apiClient.interceptors.request as any).handlers[0];
      const config = {
        headers: {},
      };

      const modifiedConfig = await requestInterceptor.fulfilled(config);
      expect(modifiedConfig.headers.Authorization).toBe('Bearer bearer-token-abc');
    });

    it('does not overwrite existing Authorization header', async () => {
      setAccessToken('bearer-token-abc');

      const requestInterceptor = (apiClient.interceptors.request as any).handlers[0];
      const config = {
        headers: { Authorization: 'CustomApiKey' },
      };

      const modifiedConfig = await requestInterceptor.fulfilled(config);
      expect(modifiedConfig.headers.Authorization).toBe('CustomApiKey');
    });

    it('leaves headers unchanged if no token is in memory', async () => {
      setAccessToken(null);

      const requestInterceptor = (apiClient.interceptors.request as any).handlers[0];
      const config = {
        headers: {},
      };

      const modifiedConfig = await requestInterceptor.fulfilled(config);
      expect(modifiedConfig.headers.Authorization).toBeUndefined();
    });

    it('propagates request errors through rejected handler', async () => {
      const requestInterceptor = (apiClient.interceptors.request as any).handlers[0];
      const error = new Error('Network Setup Failed');
      await expect(requestInterceptor.rejected(error)).rejects.toThrow('Network Setup Failed');
    });
  });

  describe('Response Interceptor: 401 & Refresh Handling', () => {
    it('passes through successful 2xx responses unmodified', () => {
      const responseInterceptor = (apiClient.interceptors.response as any).handlers[0];
      const mockResponse = { status: 200, data: { success: true } };
      expect(responseInterceptor.fulfilled(mockResponse)).toBe(mockResponse);
    });

    it('passes through non-401 errors without attempting refresh', async () => {
      const responseInterceptor = (apiClient.interceptors.response as any).handlers[0];
      const error = {
        response: { status: 404, data: { message: 'Not Found' } },
        config: { url: '/tasks/123' },
      };

      await expect(responseInterceptor.rejected(error)).rejects.toEqual(error);
    });

    it('does not attempt refresh for /auth/login endpoints', async () => {
      const responseInterceptor = (apiClient.interceptors.response as any).handlers[0];
      const error = {
        response: { status: 401, data: { message: 'Invalid credentials' } },
        config: { url: '/auth/login' },
      };

      await expect(responseInterceptor.rejected(error)).rejects.toEqual(error);
    });

    it('does not attempt refresh for /auth/refresh endpoints', async () => {
      const responseInterceptor = (apiClient.interceptors.response as any).handlers[0];
      const error = {
        response: { status: 401, data: { message: 'Token expired' } },
        config: { url: '/auth/refresh' },
      };

      await expect(responseInterceptor.rejected(error)).rejects.toEqual(error);
    });

    it('does not attempt refresh if request was already retried (_retry flag)', async () => {
      const responseInterceptor = (apiClient.interceptors.response as any).handlers[0];
      const error = {
        response: { status: 401 },
        config: { url: '/tasks', _retry: true },
      };

      await expect(responseInterceptor.rejected(error)).rejects.toEqual(error);
    });

    it('attempts refresh on 401 for protected endpoint and replays request on success', async () => {
      const responseInterceptor = (apiClient.interceptors.response as any).handlers[0];
      
      const postSpy = vi.spyOn(axios, 'post').mockResolvedValue({
        data: {
          success: true,
          data: {
            access_token: 'new-refreshed-token',
            refresh_token: 'new-refresh-token',
          },
        },
      } as any);

      const mockAdapter = vi.fn().mockResolvedValue({
        status: 200,
        data: { success: true, data: { task: 1 } },
      });

      const originalRequest: any = {
        url: '/tasks/current',
        headers: {},
        adapter: mockAdapter,
      };

      const error = {
        response: { status: 401 },
        config: originalRequest,
      };

      const responsePromise = responseInterceptor.rejected(error);
      const res = await responsePromise;

      expect(postSpy).toHaveBeenCalled();
      expect(getAccessToken()).toBe('new-refreshed-token');
      expect(originalRequest.headers.Authorization).toBe('Bearer new-refreshed-token');
      expect(res.data.success).toBe(true);

      postSpy.mockRestore();
    });

    it('handles refresh failure by invoking onSessionExpired and rejecting', async () => {
      const responseInterceptor = (apiClient.interceptors.response as any).handlers[0];
      const sessionExpiredSpy = vi.fn();
      setOnSessionExpired(sessionExpiredSpy);

      const postSpy = vi.spyOn(axios, 'post').mockRejectedValue(new Error('Session Revoked'));

      const error = {
        response: { status: 401 },
        config: {
          url: '/manager/kpis',
          headers: {},
        },
      };

      await expect(responseInterceptor.rejected(error)).rejects.toThrow('Session Revoked');
      expect(sessionExpiredSpy).toHaveBeenCalled();
      expect(getAccessToken()).toBeNull();

      postSpy.mockRestore();
    });

    it('queues concurrent 401 requests while refresh is in flight and replays them upon success', async () => {
      const responseInterceptor = (apiClient.interceptors.response as any).handlers[0];

      let resolveRefresh: (val: any) => void;
      const refreshPromise = new Promise((resolve) => {
        resolveRefresh = resolve;
      });

      const postSpy = vi.spyOn(axios, 'post').mockImplementation(() => refreshPromise as any);

      const mockAdapter1 = vi.fn().mockResolvedValue({ status: 200, data: 'req1-ok' });
      const mockAdapter2 = vi.fn().mockResolvedValue({ status: 200, data: 'req2-ok' });

      const req1: any = { url: '/req1', headers: {}, adapter: mockAdapter1 };
      const req2: any = { url: '/req2', headers: {}, adapter: mockAdapter2 };

      // First 401 triggers refresh
      const prom1 = responseInterceptor.rejected({ response: { status: 401 }, config: req1 });

      // Second 401 while refreshing gets queued
      const prom2 = responseInterceptor.rejected({ response: { status: 401 }, config: req2 });

      // Now resolve the in-flight refresh
      resolveRefresh!({
        data: {
          data: {
            access_token: 'concurrent-token',
          },
        },
      });

      const [res1, res2] = await Promise.all([prom1, prom2]);
      expect(res1.data).toBe('req1-ok');
      expect(res2.data).toBe('req2-ok');
      expect(req1.headers.Authorization).toBe('Bearer concurrent-token');
      expect(req2.headers.Authorization).toBe('Bearer concurrent-token');

      postSpy.mockRestore();
    });

    it('queues concurrent 401 requests and rejects all in queue if refresh fails', async () => {
      const responseInterceptor = (apiClient.interceptors.response as any).handlers[0];

      let rejectRefresh: (err: any) => void;
      const refreshPromise = new Promise((_, reject) => {
        rejectRefresh = reject;
      });

      const postSpy = vi.spyOn(axios, 'post').mockImplementation(() => refreshPromise as any);

      const req1: any = { url: '/req1', headers: {} };
      const req2: any = { url: '/req2', headers: {} };

      // First 401 triggers refresh
      const prom1 = responseInterceptor.rejected({ response: { status: 401 }, config: req1 });

      // Second 401 gets queued
      const prom2 = responseInterceptor.rejected({ response: { status: 401 }, config: req2 });

      rejectRefresh!(new Error('Refresh Failed Completely'));

      await expect(prom1).rejects.toThrow('Refresh Failed Completely');
      await expect(prom2).rejects.toThrow('Refresh Failed Completely');

      postSpy.mockRestore();
    });

    it('discards refreshed token if logout occurs while refresh is in flight', async () => {
      const responseInterceptor = (apiClient.interceptors.response as any).handlers[0];

      let resolveRefresh: (val: any) => void;
      const refreshPromise = new Promise((resolve) => {
        resolveRefresh = resolve;
      });

      const postSpy = vi.spyOn(axios, 'post').mockImplementation(() => refreshPromise as any);

      const req: any = { url: '/req1', headers: {} };
      const prom = responseInterceptor.rejected({ response: { status: 401 }, config: req });

      // User logs out while refresh is in flight
      setAccessToken(null);

      // In-flight refresh completes after logout
      resolveRefresh!({
        data: {
          data: {
            access_token: 'stale-restored-token',
          },
        },
      });

      await expect(prom).rejects.toThrow('Session terminated during token refresh.');
      expect(getAccessToken()).toBeNull();
      expect(apiClient.defaults.headers.common.Authorization).toBeUndefined();

      postSpy.mockRestore();
    });
  });
});
