/**
 * 最近一次规划请求的本地留存
 *
 * 方案对比页原本只从路由 state 读取请求，从导航栏直接进入时拿不到，
 * 会退化成写死的 3 天北京行程。这里把它存到 sessionStorage，切页面也不丢。
 */

const STORAGE_KEY = 'travel_planner_last_request'

export function saveLastRequest(request: unknown): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(request))
  } catch {
    // 隐私模式等场景下可能写入失败，不影响主流程
  }
}

export function loadLastRequest<T = any>(): T | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as T) : null
  } catch {
    return null
  }
}
