import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { ApiResponse, AuthData } from '../../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

let accessTokenInMemory: string | null = null;
let onSessionExpiredCallback: (() => void) | null = null;

export const setAccessToken = (token: string | null): void => {
  accessTokenInMemory = token;
};

export const getAccessToken = (): string | null => {
  return accessTokenInMemory;
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

// Variables for managing refresh queue
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

    isRefreshing = true;

    try {
      const refreshResponse = await axios.post<ApiResponse<AuthData>>(
        `${API_BASE_URL}/auth/refresh`,
        {},
        { withCredentials: true }
      );

      const newAuthData = refreshResponse.data.data;
      const newToken = newAuthData.access_token;

      setAccessToken(newToken);
      apiClient.defaults.headers.common.Authorization = `Bearer ${newToken}`;

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
