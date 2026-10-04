import { apiClient, setAccessToken } from './client';
import { ApiResponse, AuthData, LoginPayload, User } from '../../types';

export const authService = {
  async login(payload: LoginPayload): Promise<AuthData> {
    const response = await apiClient.post<ApiResponse<AuthData>>('/auth/login', payload);
    const authData = response.data.data;
    setAccessToken(authData.access_token);
    return authData;
  },

  async refresh(): Promise<AuthData> {
    const response = await apiClient.post<ApiResponse<AuthData>>('/auth/refresh');
    const authData = response.data.data;
    setAccessToken(authData.access_token);
    return authData;
  },

  async logout(): Promise<void> {
    try {
      await apiClient.post<ApiResponse<{ message: string }>>('/auth/logout');
    } finally {
      setAccessToken(null);
    }
  },

  async getMe(): Promise<User> {
    const response = await apiClient.get<ApiResponse<User>>('/auth/me');
    return response.data.data;
  },
};
