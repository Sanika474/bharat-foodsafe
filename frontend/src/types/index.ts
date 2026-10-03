// Bharat FoodSafe Core Type Definitions Placeholder
export interface User {
  id: string;
  name: string;
  email?: string;
  phone?: string;
  restaurant_id?: string;
  roles: string[];
}

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
