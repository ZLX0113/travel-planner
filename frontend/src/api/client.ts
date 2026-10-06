/** 统一 API 请求封装：自动带登录令牌，401 时清理并跳转登录 */

const TOKEN_KEY = 'travel_planner_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

export async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const token = getToken()
  const headers = new Headers(options.headers || {})
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(path, { ...options, headers })

  if (response.status === 401) {
    clearToken()
    if (!window.location.pathname.startsWith('/login')) {
      window.location.href = '/login'
    }
  }
  return response
}

/** 请求并解析 JSON，非 2xx 时抛出可读错误 */
export async function apiJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await apiFetch(path, options)
  if (!response.ok) {
    let detail = `请求失败 (HTTP ${response.status})`
    try {
      const data = await response.json()
      if (data?.detail) detail = data.detail
    } catch {
      // 忽略解析失败，使用默认错误信息
    }
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}
