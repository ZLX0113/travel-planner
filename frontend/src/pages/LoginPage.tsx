import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { apiJson } from '../api/client'

type Mode = 'login' | 'register'

export default function LoginPage() {
  const { login, register } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const redirectTo = (location.state as { from?: string } | null)?.from || '/'

  const [mode, setMode] = useState<Mode>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [nickname, setNickname] = useState('')
  const [inviteCode, setInviteCode] = useState('')
  // 服务端配置了 REGISTER_CODE 时才要求填邀请码
  const [requireInviteCode, setRequireInviteCode] = useState(false)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const isRegister = mode === 'register'

  useEffect(() => {
    const controller = new AbortController()
    apiJson<{ require_invite_code: boolean }>('/api/auth/registration-policy', {
      signal: controller.signal,
    })
      .then((res) => setRequireInviteCode(Boolean(res?.require_invite_code)))
      .catch(() => {
        // 取不到策略时按"不需要邀请码"处理，真正的校验在服务端
      })
    return () => controller.abort()
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (username.trim().length < 3) {
      setError('用户名至少 3 个字符')
      return
    }
    if (password.length < 6) {
      setError('密码至少 6 位')
      return
    }
    if (isRegister && requireInviteCode && !inviteCode.trim()) {
      setError('请填写邀请码')
      return
    }

    setSubmitting(true)
    try {
      if (isRegister) {
        await register(username.trim(), password, nickname.trim(), inviteCode.trim())
      } else {
        await login(username.trim(), password)
      }
      navigate(redirectTo, { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : '操作失败，请重试')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="text-4xl mb-2">✈️</div>
          <h1 className="text-xl font-bold text-gray-800">旅行规划师</h1>
          <p className="text-sm text-gray-400 mt-1">登录后开始你的智能行程规划</p>
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
          <div className="flex bg-gray-100 rounded-lg p-1 mb-6">
            {(['login', 'register'] as Mode[]).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => { setMode(m); setError('') }}
                className={`flex-1 py-2 rounded-md text-sm font-medium transition ${
                  mode === m ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500'
                }`}
              >
                {m === 'login' ? '登录' : '注册'}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-xs font-semibold text-gray-500 mb-1 block">用户名</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="3-32 位，字母或数字"
                autoComplete="username"
                className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
              />
            </div>

            {isRegister && (
              <div>
                <label className="text-xs font-semibold text-gray-500 mb-1 block">昵称（可选）</label>
                <input
                  type="text"
                  value={nickname}
                  onChange={(e) => setNickname(e.target.value)}
                  placeholder="不填则与用户名相同"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
                />
              </div>
            )}

            {isRegister && requireInviteCode && (
              <div>
                <label className="text-xs font-semibold text-gray-500 mb-1 block">邀请码</label>
                <input
                  type="text"
                  value={inviteCode}
                  onChange={(e) => setInviteCode(e.target.value)}
                  placeholder="请输入邀请码"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
                />
              </div>
            )}

            <div>
              <label className="text-xs font-semibold text-gray-500 mb-1 block">密码</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="至少 6 位"
                autoComplete={isRegister ? 'new-password' : 'current-password'}
                className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
              />
            </div>

            {error && (
              <div className="bg-red-50 text-red-600 text-xs rounded-lg px-3 py-2">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="w-full bg-blue-600 text-white py-3 rounded-lg text-sm font-semibold hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              {submitting ? '处理中...' : isRegister ? '注册并登录' : '登录'}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-gray-400 mt-4">
          登录后系统会记住你的出行偏好，并保存历史行程
        </p>
      </div>
    </div>
  )
}
