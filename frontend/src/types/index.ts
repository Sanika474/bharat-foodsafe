// Bharat FoodSafe Core Type Definitions

export interface User {
  id: string;
  name: string;
  email?: string | null;
  phone?: string | null;
  restaurant_id?: string | null;
  roles: string[];
}

export interface AuthData {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in_seconds: number;
  user: User;
}

export interface LoginStaffPayload {
  phone: string;
  pin: string;
}

export interface LoginAdminPayload {
  email: string;
  password: string;
}

export type LoginPayload = LoginStaffPayload | LoginAdminPayload;

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  meta: {
    request_id: string;
    pagination?: {
      total: number;
      page: number;
      page_size: number;
    } | null;
  };
}

export interface ApiErrorDetail {
  field?: string;
  issue: string;
}

export interface ApiErrorPayload {
  code: string;
  message: string;
  details?: ApiErrorDetail[];
}

export interface ApiErrorResponse {
  success: false;
  error: ApiErrorPayload;
  meta: {
    request_id: string;
  };
}
