import { useNavigate } from 'react-router-dom'
import SearchBar from '../components/SearchBar'
import { POPULAR_CITIES } from '../constants/cities'

export default function HomePage() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen pb-14 md:pb-0">
      {/* Hero */}
      <div className="bg-gradient-to-br from-blue-800 via-blue-600 to-cyan-500 py-16 md:py-24 text-center text-white">
        <h1 className="text-3xl md:text-4xl font-bold mb-2">✈️ 旅行规划师</h1>
        <p className="text-sm md:text-base opacity-90 mb-8">国内智能旅行规划 · 从航班到景点，一站搞定</p>
        <SearchBar />
      </div>

      {/* 快速入口 */}
      <div className="max-w-4xl mx-auto px-4 py-12">
        <h2 className="text-lg font-semibold text-gray-800 mb-1 text-center">热门国内目的地</h2>
        <p className="text-xs text-gray-400 mb-6 text-center">目前仅支持国内城市，境外目的地暂不开放</p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {POPULAR_CITIES.map((city) => (
            <button
              key={city.name}
              onClick={() => navigate(`/search?q=${city.name}`)}
              className="bg-white rounded-xl p-6 shadow-sm border border-gray-100 hover:shadow-md hover:border-blue-200 transition text-center"
            >
              <div className="text-3xl mb-2">{city.icon}</div>
              <div className="text-sm font-medium text-gray-700">{city.name}</div>
              <div className="text-xs text-gray-400">{city.desc}</div>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}