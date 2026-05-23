import axios from 'axios';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

export const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
});

export type User = {
  id: string;
  full_name: string;
  email: string;
  currency?: string;
  timezone?: string;
  profile_image?: string | null;
};

export type AuthMeResponse = {
  authenticated: boolean;
  user: User | null;
};

export type HealthStatus = {
  status: 'ok' | 'degraded';
  database_connected: boolean;
  database_error?: string | null;
  openrouter_connected: boolean;
  openrouter_configured: boolean;
  openrouter_model: string;
  ocr_engine: string;
  tesseract_cmd?: string | null;
  upload_dir: string;
  openrouter_error?: string | null;
  openrouter_sample?: string | null;
};

export type Notification = {
  id: string;
  title: string;
  message: string;
  is_read: boolean;
  created_at?: string;
};

export type Budget = {
  id: string;
  category_name: string;
  amount: number;
  period: 'weekly' | 'monthly' | 'custom';
  start_date?: string | null;
  end_date?: string | null;
  threshold_percent?: number;
  is_active?: boolean;
};

export type DashboardSummary = {
  monthly_expense: number;
  yearly_expense: number;
  savings: number;
  top_items: Array<{ name: string; value: number }>;
  top_merchants: Array<{ name: string; value: number }>;
  category_breakdown: Array<{ name: string; value: number }>;
  spending_trends: Array<{ month: string; amount: number }>;
  income_vs_expense: { income: number; expense: number };
  most_expensive_month: { month: string; amount: number } | null;
};

export type ExpenseItemDraft = {
  item_name: string;
  quantity: number;
  unit_price: number;
  total_price: number;
  item_category?: string | null;
};

export type ExpenseDraft = {
  vendor_name?: string | null;
  invoice_number?: string | null;
  date?: string | null;
  time?: string | null;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  items: ExpenseItemDraft[];
  subtotal: number;
  cgst: number;
  sgst: number;
  igst: number;
  discount: number;
  total_amount: number;
  payment_method?: string | null;
  category: string;
  llm_provider?: string | null;
  llm_model?: string | null;
  llm_error?: string | null;
  extraction_mode?: string | null;
};

export type UploadAnalysisResponse = {
  uploaded_file_id: string;
  file_type: string;
  structured_data: ExpenseDraft;
  extraction_mode: string;
  ocr_engine: string;
  llm_model: string;
  ocr_error?: string | null;
  message: string;
};

export function getApiErrorMessage(error: unknown): string {
  if (!axios.isAxiosError(error)) return 'Something went wrong';

  const data = error.response?.data as any;

  if (Array.isArray(data?.detail)) {
    return data.detail.map((item) => item?.msg ?? String(item)).join(', ');
  }

  if (typeof data?.detail === 'string') return data.detail;
  if (typeof data?.message === 'string') return data.message;
  if (typeof data?.error === 'string') return data.error;
  if (typeof error.response?.status === 'number') return `Request failed with status ${error.response.status}`;
  if (error.message) return error.message;

  return 'Something went wrong';
}
