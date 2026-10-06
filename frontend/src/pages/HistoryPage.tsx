import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiJson } from '../api/client'

interface TripSummary {
  id: number
  destination: string
  departure_city: string
  days: number
  budget: number | null
  travelers: number
  preferences: string[]
  summary: string
  created_at: string
}

export default function HistoryPage() {
  const navigate = useNavigate()
  const [records, setRecords] = useState<TripSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    loadRecords()
  }, [])

  const loadRecords = async () => {
    try {
      const data = await apiJson<TripSummary[]>('/api/user/trips')
      setRecords(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await apiJson(`/api/user/trips/${id}`, { method: 'DELETE' })
      setRecords((prev) => prev.filter((r) => r.id !== id))
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败')
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-24 md:pb-8">
      <div className="bg-white border-b border-gray-200 px-4 py-4">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-gray-800">我的历史行程</h1>
            <p className="text-xs text-gray-400 mt-0.5">点「查看详情」可以打开完整行程</p>
          </div>
          <button
            onClick={() => navigate('/plan')}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition"
          >
            + 新建规划
          </button>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-4 py-6 space-y-3">
        {loading && <div className="text-center text-gray-400 text-sm py-10">加载中...</div>}

        {!loading && error && (
          <div className="bg-red-50 text-red-600 text-sm rounded-lg px-4 py-3">{error}</div>
        )}

        {!loading && !error && records.length === 0 && (
          <div className="text-center py-16">
            <div className="text-4xl mb-3">🗂️</div>
            <p className="text-gray-400 text-sm">还没有历史行程，去规划一次试试吧</p>
          </div>
        )}

        {records.map((record) => (
          <div key={record.id} className="bg-white rounded-xl border border-gray-100 shadow-sm p-4">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-gray-800">{record.destination}</span>
                  <span className="text-xs text-gray-400">{record.days} 天</span>
                  {record.budget ? (
                    <span className="text-xs text-gray-400">
                      预算 ¥{record.budget.toLocaleString()}
                    </span>
                  ) : null}
                  <span className="text-xs text-gray-400">{record.travelers} 人</span>
                </div>
                <div className="text-xs text-gray-400 mt-1">
                  {record.departure_city ? `从 ${record.departure_city} 出发 · ` : ''}
                  {record.created_at}
                </div>
                {record.preferences.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {record.preferences.map((tag) => (
                      <span
                        key={tag}
                        className="text-[11px] px-2 py-0.5 rounded-full bg-blue-50 text-blue-600"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => navigate(`/history/${record.id}`)}
                  className="text-xs px-3 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition"
                >
                  查看详情
                </button>
                <button
                  onClick={() => handleDelete(record.id)}
                  className="text-xs px-3 py-1.5 rounded-lg border border-gray-200 text-red-500 hover:bg-red-50 transition"
                >
                  删除
                </button>
              </div>
            </div>

            {record.summary && (
              <p className="text-xs text-gray-500 mt-3 bg-gray-50 rounded-lg px-3 py-2">
                {record.summary}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
