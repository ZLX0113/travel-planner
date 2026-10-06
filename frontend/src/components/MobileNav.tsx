import { useLocation, useNavigate } from 'react-router-dom'

const NAV_ITEMS = [
  { path: '/', label: '首页', icon: '🏠' },
  { path: '/plan', label: '规划', icon: '📋' },
  { path: '/chat', label: '对话', icon: '💬' },
  { path: '/history', label: '历史', icon: '🗂️' },
]

export default function MobileNav() {
  const location = useLocation()
  const navigate = useNavigate()

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 z-50">
      <div className="flex justify-around py-2">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.path}
            onClick={() => navigate(item.path)}
            className={`flex flex-col items-center px-4 py-1 ${
              location.pathname === item.path ? 'text-blue-600' : 'text-gray-400'
            }`}
          >
            <span className="text-xl">{item.icon}</span>
            <span className="text-xs mt-0.5">{item.label}</span>
          </button>
        ))}
      </div>
    </nav>
  )
}