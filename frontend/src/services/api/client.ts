import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { ApiResponse, AuthData } from '../../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

let accessTokenInMemory: string | null = null;
let onSessionExpiredCallback: (() => void) | null = null;
let sessionEpoch = 0;
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: unknown) => void;
}> = [];

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (token) {
      prom.resolve(token);
    } else {
      prom.reject(error);
    }
  });
  failedQueue = [];
};

export const setAccessToken = (token: string | null): void => {
  accessTokenInMemory = token;
  if (token) {
    apiClient.defaults.headers.common.Authorization = `Bearer ${token}`;
  } else {
    sessionEpoch++;
    delete apiClient.defaults.headers.common.Authorization;
    if (failedQueue.length > 0) {
      processQueue(new Error('Session terminated.'), null);
    }
  }
};

export const getAccessToken = (): string | null => {
  return accessTokenInMemory;
};

/**
 * Extracts a user-friendly error message from backend ApiResponse or Axios error.
 * Fail-safely handles validation errors, unauthenticated, forbidden, and network failures.
 */
export const getApiErrorMessage = (error: unknown): string => {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as
      | {
          error?: { message?: string; details?: Array<{ field?: string; issue?: string }> };
          message?: string;
          detail?: string | Array<{ msg?: string }>;
        }
      | undefined;

    if (data?.error?.message) {
      if (data.error.details && Array.isArray(data.error.details) && data.error.details.length > 0) {
        const first = data.error.details[0];
        if (first?.issue) {
          return `${data.error.message} (${first.field ? `${first.field}: ` : ''}${first.issue})`;
        }
      }
      return data.error.message;
    }
    if (typeof data?.detail === 'string') {
      return data.detail;
    }
    if (Array.isArray(data?.detail) && data.detail.length > 0) {
      return data.detail[0]?.msg || 'Validation failed.';
    }
    if (data?.message) {
      return data.message;
    }
    if (error.response?.status === 401) {
      return 'Session expired or unauthenticated. Please sign in again.';
    }
    if (error.response?.status === 403) {
      return 'You do not have permission to perform this action.';
    }
    if (error.response?.status === 404) {
      return 'The requested resource was not found.';
    }
    if (error.response?.status && error.response.status >= 500) {
      return 'A server error occurred. Please try again later.';
    }
    if (error.code === 'ERR_NETWORK') {
      return 'Network connection error. Please check your internet connection.';
    }
    return error.message || 'An unexpected error occurred.';
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'An unexpected error occurred.';
};

export const setOnSessionExpired = (callback: () => void): void => {
  onSessionExpiredCallback = callback;
};

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request Interceptor: Attach Access Token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (accessTokenInMemory && !config.headers.Authorization) {
      config.headers.Authorization = `Bearer ${accessTokenInMemory}`;
    }
    return config;
  },
  (error: unknown) => Promise.reject(error)
);

// Response Interceptor: Handle 401 & Automatic Refresh
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    if (!error.response || error.response.status !== 401 || !originalRequest) {
      return Promise.reject(error);
    }

    const url = originalRequest.url || '';
    const isAuthEndpoint =
      url.includes('/auth/login') ||
      url.includes('/auth/refresh') ||
      url.includes('/auth/logout');

    if (isAuthEndpoint || originalRequest._retry) {
      return Promise.reject(error);
    }

    originalRequest._retry = true;

    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        failedQueue.push({ resolve, reject });
      })
        .then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return apiClient(originalRequest);
        })
        .catch((err) => Promise.reject(err));
    }

    const requestEpoch = sessionEpoch;
    isRefreshing = true;

    try {
      const refreshResponse = await axios.post<ApiResponse<AuthData>>(
        `${API_BASE_URL}/auth/refresh`,
        {},
        { withCredentials: true }
      );

      // Fail-safe: if logout occurred while refresh was in flight, discard refreshed token
      if (sessionEpoch !== requestEpoch) {
        processQueue(new Error('Session terminated during token refresh.'), null);
        return Promise.reject(new Error('Session terminated during token refresh.'));
      }

      const newAuthData = refreshResponse.data.data;
      const newToken = newAuthData.access_token;

      setAccessToken(newToken);

      processQueue(null, newToken);

      originalRequest.headers.Authorization = `Bearer ${newToken}`;
      return apiClient(originalRequest);
    } catch (refreshErr) {
      processQueue(refreshErr, null);
      setAccessToken(null);
      if (onSessionExpiredCallback) {
        onSessionExpiredCallback();
      }
      return Promise.reject(refreshErr);
    } finally {
      isRefreshing = false;
    }
  }
);
