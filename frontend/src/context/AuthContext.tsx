import { createContext, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { apiJson, clearToken, getToken, setToken } from '../api/client'

export interface UserInfo {
  id: number
  username: string
  nickname: string
}

interface AuthContextValue {
  user: UserInfo | null
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  register: (
    username: string,
    password: string,
    nickname: string,
    inviteCode?: string
  ) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null)
  const [loading, setLoading] = useState(true)

  // 首次进入时用本地令牌换取用户信息，校验登录态是否有效
  useEffect(() => {
    if (!getToken()) {
      setLoading(false)
      return
    }
    apiJson<UserInfo>('/api/auth/me')
      .then(setUser)
      .catch(() => {
        clearToken()
        setUser(null)
      })
      .finally(() => setLoading(false))
  }, [])

  const login = async (username: string, password: string) => {
    const res = await apiJson<{ access_token: string; user: UserInfo }>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    })
    setToken(res.access_token)
    setUser(res.user)
  }

  const register = async (
    username: string,
    password: string,
    nickname: string,
    inviteCode = ''
  ) => {
    const res = await apiJson<{ access_token: string; user: UserInfo }>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username, password, nickname, invite_code: inviteCode }),
    })
    setToken(res.access_token)
    setUser(res.user)
  }

  const logout = () => {
    clearToken()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth 必须在 AuthProvider 内使用')
  return ctx
}
