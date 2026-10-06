import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

const HOT_CITIES = ['北京', '上海', '成都', '西安', '杭州', '三亚', '厦门', '重庆']

export default function SearchBar() {
  const [query, setQuery] = useState('')
  const navigate = useNavigate()

  const handleSearch = () => {
    if (query.trim()) {
      navigate(`/search?q=${encodeURIComponent(query)}`)
    }
  }

  return (
    <div className="w-full max-w-2xl mx-auto px-4">
      <div className="flex items-center bg-white rounded-full shadow-lg p-2">
        <span className="text-xl px-3">🔍</span>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          placeholder="搜索国内城市，如 北京、成都、三亚..."
          className="flex-1 border-none outline-none text-sm px-2 py-2 text-gray-700 placeholder-gray-400"
        />
        <button
          onClick={handleSearch}
          className="bg-blue-600 text-white px-6 py-2.5 rounded-full text-sm font-semibold hover:bg-blue-700 transition"
        >
          搜索
        </button>
      </div>
      <div className="flex flex-wrap justify-center gap-2 mt-4">
        {HOT_CITIES.map((city) => (
          <button
            key={city}
            onClick={() => navigate(`/search?q=${encodeURIComponent(city)}`)}
            className="bg-white/20 text-white px-4 py-1 rounded-full text-xs hover:bg-white/30 transition"
          >
            {city}
          </button>
        ))}
      </div>
    </div>
  )
}