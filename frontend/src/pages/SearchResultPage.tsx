import { useState, useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { apiFetch } from '../api/client'

interface Overview {
  name: string
  country: string
  description: string
  best_season: string
  currency: string
  language: string
  timezone: string
  visa: string
  images: string[]
  hot_tags: string[]
  daily_budget: string
}

interface Attraction {
  name: string
  category: string
  description: string
  ticket_price: number
  rating: number
  review_count: number
  opening_hours: string
  closing_day: string
  need_booking: boolean
  suggested_duration: string
  images: string[]
  tags: string[]
  tips: string
  how_to_get: { mode: string; route: string; duration: string; price: number }[]
}

interface Hotel {
  name: string
  rating: number
  price_per_night: number
  address: string
  tags: string[]
  images: string[]
  distance_to_station: string
  match_reason: string
}

interface Flight {
  airline: string
  flight_no: string
  departure_time: string
  arrival_time: string
  price: number
  duration: string
  baggage: string
  seats_left: number
  departure_airport: string
  arrival_airport: string
}

interface SearchData {
  overview: Overview | null
  attractions: Attraction[]
  hotels: Hotel[]
  flights: Flight[]
}

export default function SearchResultPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const query = searchParams.get('q') || ''
  const [data, setData] = useState<SearchData>({ overview: null, attractions: [], hotels: [], flights: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState<'attractions' | 'hotels' | 'flights'>('attractions')

  useEffect(() => {
    if (!query) return
    setLoading(true)
    setError('')
    apiFetch(`/api/search?q=${encodeURIComponent(query)}`)
      .then(async (res) => {
        // 境外城市等原因被拒绝时，把原因展示出来
        if (!res.ok) {
          let detail = `搜索失败（HTTP ${res.status}）`
          try {
            const body = await res.json()
            if (body?.detail) detail = body.detail
          } catch {
            // 非 JSON 响应，用默认提示
          }
          throw new Error(detail)
        }
        return res.json()
      })
      .then(setData)
      .catch((err) => {
        // 境外城市被拒绝属于正常业务拦截，用 warn 而不是 error
        console.warn('搜索未通过校验:', err instanceof Error ? err.message : err)
        setError(err instanceof Error ? err.message : '搜索失败')
      })
      .finally(() => setLoading(false))
  }, [query])

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-400">正在搜索 "{query}" ...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50 gap-4 px-6 text-center">
        <div className="text-3xl">🚧</div>
        <p className="text-red-500 text-sm max-w-md">{error}</p>
        <p className="text-xs text-gray-400">目前仅支持国内目的地，境外城市暂不开放</p>
        <button onClick={() => navigate('/')} className="text-blue-600 hover:underline text-sm">
          返回首页
        </button>
      </div>
    )
  }

  const { overview, attractions, hotels, flights } = data

  if (!overview) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50 pb-14 md:pb-0">
        <p className="text-5xl mb-4">🔍</p>
        <p className="text-gray-500 text-lg mb-2">未找到 "{query}" 的相关信息</p>
        <p className="text-gray-400 text-sm mb-6">试试搜索其他城市</p>
        <button onClick={() => navigate('/')} className="text-blue-600 hover:underline text-sm">返回首页</button>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-14 md:pb-0">
      {/* Hero */}
      <div className="relative bg-gradient-to-br from-blue-900 via-blue-700 to-cyan-600 text-white">
        <div className="max-w-5xl mx-auto px-4 py-10 md:py-16">
          <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-6">
            <div>
              <div className="text-sm opacity-70 mb-1">{overview.country}</div>
              <h1 className="text-3xl md:text-4xl font-bold mb-3">{overview.name}</h1>
              <p className="text-sm md:text-base opacity-90 max-w-2xl leading-relaxed">{overview.description}</p>
              <div className="flex flex-wrap gap-2 mt-4">
                {overview.hot_tags.map((tag) => (
                  <span key={tag} className="bg-white/15 text-white/90 px-3 py-1 rounded-full text-xs">{tag}</span>
                ))}
              </div>
            </div>
            <button
              onClick={() => navigate(`/plan?destination=${encodeURIComponent(overview.name)}`)}
              className="shrink-0 bg-white text-blue-700 px-8 py-3 rounded-xl font-bold text-sm hover:bg-blue-50 transition shadow-lg"
            >
              ✈️ 开始规划行程
            </button>
          </div>
        </div>
      </div>

      {/* Quick Info */}
      <div className="max-w-5xl mx-auto px-4 -mt-6 relative z-10">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { icon: '💰', label: '货币', value: overview.currency },
            { icon: '🗣️', label: '语言', value: overview.language },
            { icon: '🌸', label: '最佳季节', value: overview.best_season },
            { icon: '🛂', label: '签证', value: overview.visa },
          ].map((item) => (
            <div key={item.label} className="bg-white rounded-xl p-4 shadow-sm border border-gray-100">
              <div className="text-xl mb-1">{item.icon}</div>
              <div className="text-xs text-gray-400">{item.label}</div>
              <div className="text-xs text-gray-700 mt-1 leading-relaxed">{item.value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="max-w-5xl mx-auto px-4 mt-8">
        <div className="flex gap-1 bg-white rounded-xl p-1 border border-gray-200 shadow-sm">
          {[
            { key: 'attractions' as const, label: '🏛️ 景点', count: attractions.length },
            { key: 'hotels' as const, label: '🏨 酒店', count: hotels.length },
            { key: 'flights' as const, label: '✈️ 航班', count: flights.length },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex-1 py-2.5 rounded-lg text-sm font-medium transition ${
                activeTab === tab.key
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-gray-500 hover:bg-gray-50'
              }`}
            >
              {tab.label} ({tab.count})
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="max-w-5xl mx-auto px-4 py-6">
        {/* Attractions */}
        {activeTab === 'attractions' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {attractions.map((a, i) => (
              <div key={i} className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm hover:shadow-md transition">
                <div className="flex">
                  <div className="w-1/3 shrink-0 bg-gray-100">
                    <img
                      src={a.images?.[0] || `https://picsum.photos/seed/${encodeURIComponent(a.name)}/400/300`}
                      alt={a.name}
                      className="w-full h-full object-cover"
                      loading="lazy"
                    />
                  </div>
                  <div className="flex-1 p-4">
                    <div className="flex items-start justify-between mb-1">
                      <h3 className="font-bold text-gray-800">{a.name}</h3>
                      <span className="text-xs bg-yellow-100 text-yellow-700 px-1.5 py-0.5 rounded font-medium">
                        ⭐ {a.rating}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 mb-2 line-clamp-2">{a.description}</p>
                    <div className="flex flex-wrap gap-1.5 mb-2">
                      {a.tags?.slice(0, 3).map((tag) => (
                        <span key={tag} className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full">{tag}</span>
                      ))}
                    </div>
                    <div className="flex items-center gap-4 text-xs text-gray-400">
                      <span>🕐 {a.opening_hours}</span>
                      <span>💰 {a.ticket_price === 0 ? '免费' : `¥${a.ticket_price}`}</span>
                      {a.need_booking && <span className="text-orange-500 font-medium">需预约</span>}
                    </div>
                    {a.tips && (
                      <div className="mt-2 text-xs text-gray-400 bg-gray-50 rounded-lg px-2 py-1.5">
                        💡 {a.tips}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Hotels */}
        {activeTab === 'hotels' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {hotels.map((h, i) => (
              <div key={i} className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm hover:shadow-md transition">
                <div className="flex">
                  <div className="w-1/3 shrink-0 bg-gray-100">
                    <img
                      src={h.images?.[0] || `https://picsum.photos/seed/${encodeURIComponent(h.name)}/400/300`}
                      alt={h.name}
                      className="w-full h-full object-cover"
                      loading="lazy"
                    />
                  </div>
                  <div className="flex-1 p-4">
                    <div className="flex items-start justify-between mb-1">
                      <h3 className="font-bold text-gray-800 text-sm">{h.name}</h3>
                      <span className="text-xs bg-yellow-100 text-yellow-700 px-1.5 py-0.5 rounded font-medium">
                        ⭐ {h.rating}
                      </span>
                    </div>
                    <p className="text-xs text-gray-400 mb-1">📍 {h.address}</p>
                    <div className="flex flex-wrap gap-1.5 mb-2">
                      {h.tags?.map((tag) => (
                        <span key={tag} className="text-xs bg-purple-50 text-purple-600 px-2 py-0.5 rounded-full">{tag}</span>
                      ))}
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-400">{h.distance_to_station}</span>
                      <span className="text-lg font-bold text-blue-600">¥{h.price_per_night}<span className="text-xs text-gray-400 font-normal">/晚</span></span>
                    </div>
                    <div className="mt-2 text-xs text-green-600 bg-green-50 rounded-lg px-2 py-1">
                      ✅ {h.match_reason}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Flights */}
        {activeTab === 'flights' && (
          <div className="space-y-3">
            {flights.map((f, i) => (
              <div key={i} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm hover:shadow-md transition">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="text-center">
                      <div className="text-lg font-bold text-gray-800">{f.departure_time}</div>
                      <div className="text-xs text-gray-400">{f.departure_airport}</div>
                    </div>
                    <div className="flex flex-col items-center">
                      <div className="text-xs text-gray-400">{f.duration}</div>
                      <div className="w-24 h-px bg-gray-300 my-1 relative">
                        <div className="absolute -top-1 left-1/2 -translate-x-1/2 text-xs">✈️</div>
                      </div>
                      <div className="text-xs text-gray-400">{f.flight_no}</div>
                    </div>
                    <div className="text-center">
                      <div className="text-lg font-bold text-gray-800">{f.arrival_time}</div>
                      <div className="text-xs text-gray-400">{f.arrival_airport}</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm text-gray-500">{f.airline}</div>
                    <div className="text-xs text-gray-400">{f.baggage}</div>
                    <div className="text-lg font-bold text-orange-600 mt-1">¥{f.price}</div>
                    <div className="text-xs text-gray-400">仅剩 {f.seats_left} 座</div>
                  </div>
                </div>
              </div>
            ))}
            {flights.length === 0 && (
              <div className="text-center py-12 text-gray-400">
                <p className="text-3xl mb-2">✈️</p>
                <p>暂无航班数据</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}