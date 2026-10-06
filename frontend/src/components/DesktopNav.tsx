import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const NAV_ITEMS = [
  { path: '/', label: '首页', icon: '🏠' },
  { path: '/plan', label: '规划行程', icon: '📋' },
  { path: '/chat', label: 'AI 对话', icon: '💬' },
  { path: '/compare', label: '方案对比', icon: '📊' },
  { path: '/history', label: '历史行程', icon: '🗂️' },
]

export default function DesktopNav() {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, logout } = useAuth()

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    // 固定高度 h-16（64px）：页面内的 sticky 标题栏按这个高度做偏移，避免被导航盖住
    <nav className="hidden md:flex h-16 items-center justify-between px-6 bg-white border-b border-gray-200 sticky top-0 z-40">
      <button
        onClick={() => navigate('/')}
        className="flex items-center gap-2 text-lg font-bold text-gray-800 hover:text-blue-600 transition"
      >
        <span>✈️</span>
        <span>旅行规划师</span>
      </button>
      <div className="flex items-center gap-1">
        {NAV_ITEMS.map((item) => {
          const isActive = location.pathname === item.path
          return (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition ${
                isActive
                  ? 'bg-blue-50 text-blue-600'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-800'
              }`}
            >
              <span className="text-base">{item.icon}</span>
              <span>{item.label}</span>
            </button>
          )
        })}
      </div>

      <div className="flex items-center gap-3">
        <span className="text-sm text-gray-600">
          👤 {user?.nickname || user?.username || '未登录'}
        </span>
        <button
          onClick={handleLogout}
          className="text-xs px-3 py-1.5 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 transition"
        >
          退出
        </button>
      </div>
    </nav>
  )
}
