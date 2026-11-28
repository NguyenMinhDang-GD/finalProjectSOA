const TOKEN_KEY = 'pkb_access_token';
const USER_KEY = 'pkb_user';

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setAuthStorage(token: string, user: unknown): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuthStorage(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

function extractApiErrorMessage(data: unknown, status: number): string {
  if (!data || typeof data !== 'object') {
    return `HTTP ${status}`;
  }
  const obj = data as { detail?: unknown; message?: unknown };
  if (typeof obj.detail === 'string' && obj.detail.trim()) {
    return obj.detail;
  }
  if (Array.isArray(obj.detail)) {
    const msgs = obj.detail
      .map((item) => {
        if (typeof item === 'string') return item;
        if (item && typeof item === 'object' && 'msg' in item) {
          const msg = (item as { msg?: unknown }).msg;
          return typeof msg === 'string' ? msg : '';
        }
        return '';
      })
      .filter(Boolean);
    if (msgs.length > 0) return msgs.join('; ');
  }
  if (typeof obj.message === 'string' && obj.message.trim()) {
    return obj.message;
  }
  return `HTTP ${status}`;
}

export async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getStoredToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> | undefined),
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const res = await fetch(path, { ...options, headers });
  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { detail: text };
  }

  if (!res.ok) {
    throw new Error(extractApiErrorMessage(data, res.status));
  }
  return data as T;
}

export function formatVND(amount: number): string {
  return new Intl.NumberFormat('vi-VN').format(Math.round(amount)) + ' đ';
}

export function formatHourRange(startHour: number, endHour: number): string {
  return `${String(startHour).padStart(2, '0')}:00 – ${String(endHour).padStart(2, '0')}:00`;
}

export function formatDateVN(isoDate: string): string {
  const parts = isoDate.split('-');
  if (parts.length !== 3) return isoDate;
  return `${parts[2]}/${parts[1]}/${parts[0]}`;
}

export function todayVN(): string {
  const now = new Date();
  const vnTime = new Date(now.getTime() + 7 * 60 * 60 * 1000);
  return vnTime.toISOString().slice(0, 10);
}
