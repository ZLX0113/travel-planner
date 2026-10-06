import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import ItineraryTimeline from '../components/ItineraryTimeline'
import AttractionModal from '../components/AttractionModal'
import { apiJson } from '../api/client'
import type { DayPlan, TimeNode, BudgetBreakdown } from '../types'

interface TripDetail {
  id: number
  destination: string
  departure_city: string
  days: number
  budget: number | null
  travelers: number
  preferences: string[]
  summary: string
  created_at: string
  content: string
}

interface PlanContent {
  type: 'plan'
  destination?: string
  total?: number
  budget?: BudgetBreakdown
  days?: DayPlan[]
}

interface VersionItem {
  id: string
  label: string
  description?: string
  total?: number
  budget?: BudgetBreakdown
  days?: DayPlan[]
}

interface VersionsContent {
  type: 'versions'
  destination?: string
  versions?: VersionItem[]
}

const BUDGET_LABELS: Record<string, string> = {
  flights: '机票',
  hotels: '住宿',
  attractions: '门票',
  meals: '餐饮',
  transport: '交通',
  insurance: '保险',
  misc: '其他',
  flight: '机票',
  hotel: '住宿',
  tickets: '门票',
  dining: '餐饮',
  transit: '交通',
}

export default function HistoryDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [record, setRecord] = useState<TripDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [currentDay, setCurrentDay] = useState(0)
  const [currentVersion, setCurrentVersion] = useState(0)
  const [selectedNode, setSelectedNode] = useState<TimeNode | null>(null)

  useEffect(() => {
    if (!id) return
    apiJson<TripDetail>(`/api/user/trips/${id}`)
      .then(setRecord)
      .catch((err) => setError(err instanceof Error ? err.message : '加载失败'))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 text-gray-400 text-sm">
        加载中...
      </div>
    )
  }

  if (error || !record) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="text-3xl mb-3">😕</div>
          <div className="text-gray-500 text-sm mb-4">{error || '记录不存在'}</div>
          <button
            onClick={() => navigate('/history')}
            className="text-blue-600 text-sm hover:underline"
          >
            返回历史列表
          </button>
        </div>
      </div>
    )
  }

  // 解析保存的完整行程
  let parsed: PlanContent | VersionsContent | null = null
  try {
    parsed = JSON.parse(record.content)
  } catch {
    parsed = null
  }

  const versions: VersionItem[] =
    parsed && parsed.type === 'versions' ? (parsed as VersionsContent).versions || [] : []
  const activeVersion = versions[currentVersion]
  const dayPlans: DayPlan[] =
    (parsed && parsed.type === 'versions'
      ? activeVersion?.days
      : (parsed as PlanContent | null)?.days) || []
  const budget: BudgetBreakdown | undefined =
    parsed && parsed.type === 'versions' ? activeVersion?.budget : (parsed as PlanContent | null)?.budget
  const total: number =
    (parsed && parsed.type === 'versions' ? activeVersion?.total : (parsed as PlanContent | null)?.total) || 0

  const day = dayPlans[currentDay]

  return (
    <div className="min-h-screen bg-gray-50 pb-24 md:pb-8">
      <div className="bg-white border-b border-gray-200 px-4 py-4">
        <div className="max-w-4xl mx-auto">
          <button
            onClick={() => navigate('/history')}
            className="text-xs text-gray-400 hover:text-gray-600 mb-2"
          >
            ← 返回历史列表
          </button>
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-lg font-bold text-gray-800">{record.destination}</h1>
            <span className="text-xs text-gray-400">{record.days} 天</span>
            {record.budget ? (
              <span className="text-xs text-gray-400">
                预算 ¥{record.budget.toLocaleString()}
              </span>
            ) : null}
            <span className="text-xs text-gray-400">{record.travelers} 人</span>
            <span className="text-xs text-gray-400">{record.created_at}</span>
          </div>
          {record.departure_city && (
            <div className="text-xs text-gray-400 mt-1">出发地：{record.departure_city}</div>
          )}
          {record.preferences.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {record.preferences.map((tag) => (
                <span key={tag} className="text-[11px] px-2 py-0.5 rounded-full bg-blue-50 text-blue-600">
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 py-6 space-y-4">
        {/* 多版本切换 */}
        {versions.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-100 p-3">
            <div className="text-xs text-gray-400 mb-2">方案版本</div>
            <div className="flex flex-wrap gap-2">
              {versions.map((v, i) => (
                <button
                  key={v.id}
                  onClick={() => {
                    setCurrentVersion(i)
                    setCurrentDay(0)
                  }}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                    currentVersion === i
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-50 text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  {v.label}
                  {v.total ? ` · ¥${v.total.toLocaleString()}` : ''}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* 预算明细 */}
        {budget && (
          <div className="bg-white rounded-xl border border-gray-100 p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-semibold text-gray-700">💰 预算明细</span>
              <span className="text-sm font-bold text-orange-600">
                ¥{(total || budget.total || 0).toLocaleString()}
              </span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs text-gray-500">
              {Object.entries(budget)
                .filter(([key, value]) => key !== 'total' && typeof value === 'number' && value > 0)
                .map(([key, value]) => (
                  <div key={key} className="bg-gray-50 rounded-lg px-3 py-2">
                    <div className="text-gray-400">{BUDGET_LABELS[key] || key}</div>
                    <div className="text-gray-700 font-medium">¥{Number(value).toLocaleString()}</div>
                  </div>
                ))}
            </div>
          </div>
        )}

        {/* 每日行程 */}
        {dayPlans.length === 0 ? (
          <div className="bg-white rounded-xl border border-gray-100 p-8 text-center text-sm text-gray-400">
            这条记录没有保存详细行程（可能是旧版本保存的）
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-gray-100 p-4">
            <div className="flex flex-wrap gap-2 mb-4">
              {dayPlans.map((d, i) => (
                <button
                  key={i}
                  onClick={() => setCurrentDay(i)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                    currentDay === i
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-50 text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  Day {d.day || i + 1}
                </button>
              ))}
            </div>

            {day?.theme && (
              <div className="text-xs text-blue-600 bg-blue-50 rounded-lg px-3 py-2 mb-3">
                🎯 主题：{day.theme}
                {day.notes ? ` · ${day.notes}` : ''}
              </div>
            )}

            {day && (
              <ItineraryTimeline
                day={day}
                onNodeClick={(node) => {
                  // 历史详情页没有地图，这里只保留景点的详情弹窗
                  if (node.type === 'attraction') setSelectedNode(node)
                }}
              />
            )}
          </div>
        )}
      </div>

      <AttractionModal node={selectedNode} onClose={() => setSelectedNode(null)} />
    </div>
  )
}
