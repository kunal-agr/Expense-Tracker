const API_BASE = (import.meta as any).env?.VITE_API_URL || '/api/v1';

let authToken: string | null = localStorage.getItem('access_token');
let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];

export function setAuthToken(token: string | null) {
  authToken = token;
  if (token) {
    localStorage.setItem('access_token', token);
  } else {
    localStorage.removeItem('access_token');
  }
}

export function getAuthToken(): string | null {
  return authToken;
}

function onRefreshed(token: string) {
  refreshSubscribers.forEach((callback) => callback(token));
  refreshSubscribers = [];
}

export class ApiError extends Error {
  code: string;
  status: number;
  details?: any;

  constructor(message: string, code: string = 'API_ERROR', status: number = 400, details?: any) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  const contentType = res.headers.get('content-type');
  let data: any = null;

  if (contentType && contentType.includes('application/json')) {
    data = await res.json();
    if (data !== null && typeof data === 'object') {
      if (!('data' in data)) {
        try {
          Object.defineProperty(data, 'data', {
            value: data,
            enumerable: false,
            configurable: true,
          });
        } catch {
          // ignore
        }
      }
    }
  } else if (contentType && (contentType.includes('text/') || contentType.includes('application/'))) {
    data = await res.blob();
    return data as T;
  }

  if (!res.ok) {
    const errorMsg = data?.message || data?.detail || res.statusText || 'Request failed';
    const errorCode = data?.code || 'ERROR';
    throw new ApiError(errorMsg, errorCode, res.status, data?.details);
  }

  return data as T;
}

export interface ApiRequestOptions extends RequestInit {
  data?: any;
  responseType?: 'json' | 'blob' | 'text';
}

export async function apiRequest<T = any>(
  endpoint: string,
  options: ApiRequestOptions = {}
): Promise<T> {
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`;
  const headers = new Headers(options.headers || {});

  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  if (authToken && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${authToken}`);
  }

  let body = options.body;
  if (!body && options.data) {
    body = JSON.stringify(options.data);
  }

  const config: RequestInit = {
    ...options,
    body,
    headers,
    credentials: 'include', // for httpOnly refresh cookie
  };

  try {
    const response = await fetch(url, config);

    // Automatic token refresh handling on 401
    if (
      response.status === 401 &&
      !endpoint.includes('/auth/login') &&
      !endpoint.includes('/auth/register') &&
      !endpoint.includes('/auth/refresh')
    ) {
      if (!isRefreshing) {
        isRefreshing = true;
        try {
          const refreshRes = await fetch(`${API_BASE}/auth/refresh`, {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
          });

          if (refreshRes.ok) {
            const refreshData = await refreshRes.json();
            const newToken = refreshData.access_token;
            setAuthToken(newToken);
            isRefreshing = false;
            onRefreshed(newToken);

            // Retry original request
            headers.set('Authorization', `Bearer ${newToken}`);
            const retryRes = await fetch(url, { ...config, headers });
            return await handleResponse<T>(retryRes);
          } else {
            setAuthToken(null);
            isRefreshing = false;
            window.dispatchEvent(new CustomEvent('auth:expired'));
          }
        } catch (refreshErr) {
          setAuthToken(null);
          isRefreshing = false;
          window.dispatchEvent(new CustomEvent('auth:expired'));
        }
      } else {
        // Wait for token refresh to complete
        return new Promise((resolve, reject) => {
          refreshSubscribers.push(async (token: string) => {
            headers.set('Authorization', `Bearer ${token}`);
            try {
              const retryRes = await fetch(url, { ...config, headers });
              resolve(await handleResponse<T>(retryRes));
            } catch (err) {
              reject(err);
            }
          });
        });
      }
    }

    if (options.responseType === 'blob') {
      const blob = await response.blob();
      return { data: blob, status: response.status } as any;
    }

    return await handleResponse<T>(response);
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError((error as Error).message || 'Network request failed', 'NETWORK_ERROR', 0);
  }
}

export const api = {
  get: <T = any>(endpoint: string, options?: ApiRequestOptions) =>
    apiRequest<T>(endpoint, { ...options, method: 'GET' }),
  post: <T = any>(endpoint: string, body?: any, options?: ApiRequestOptions) =>
    apiRequest<T>(endpoint, {
      ...options,
      method: 'POST',
      body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
    }),
  put: <T = any>(endpoint: string, body?: any, options?: ApiRequestOptions) =>
    apiRequest<T>(endpoint, {
      ...options,
      method: 'PUT',
      body: body ? JSON.stringify(body) : undefined,
    }),
  patch: <T = any>(endpoint: string, body?: any, options?: ApiRequestOptions) =>
    apiRequest<T>(endpoint, {
      ...options,
      method: 'PATCH',
      body: body ? JSON.stringify(body) : undefined,
    }),
  del: <T = any>(endpoint: string, options?: ApiRequestOptions) =>
    apiRequest<T>(endpoint, {
      ...options,
      method: 'DELETE',
    }),
  delete: <T = any>(endpoint: string, options?: ApiRequestOptions) =>
    apiRequest<T>(endpoint, {
      ...options,
      method: 'DELETE',
    }),
};
