import { useState, useEffect, useMemo, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { apiFetch, apiJson } from '../api/client'
import { stylesToTags } from '../constants/preferences'
import { loadLastRequest } from '../utils/lastRequest'
import ItineraryTimeline from '../components/ItineraryTimeline'
import HotelCard from '../components/HotelCard'
import AttractionModal from '../components/AttractionModal'
import TripMap, { nodeCoord, type MapFocus } from '../components/TripMap'
import type { DayPlan, TimeNode, BudgetBreakdown } from '../types'

const VERSION_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  budget: { bg: '#10b981', text: '#10b981', border: 'border-emerald-500' },
  comfort: { bg: '#2563eb', text: '#2563eb', border: 'border-blue-600' },
  trendy: { bg: '#8b5cf6', text: '#8b5cf6', border: 'border-purple-500' },
}

const VERSION_LABELS: Record<string, string> = {
  budget: '💰 省钱版',
  comfort: '⭐ 舒适版',
  trendy: '📸 网红打卡版',
}

/** 各版本选中的航班（后端返回的是原始字段名） */
interface VersionFlight {
  airline?: string
  flight_no?: string
  departure_time?: string
  arrival_time?: string
  duration?: string
  price?: number
  baggage?: string
  departure_airport?: string
  arrival_airport?: string
  is_reference?: boolean
  note?: string
}

interface VersionData {
  id: string
  label: string
  description: string
  itinerary: DayPlan[]
  budget: BudgetBreakdown
  flight?: VersionFlight | null
}

export default function ComparePage() {
  const location = useLocation()
  const navigate = useNavigate()
  const [versions, setVersions] = useState<VersionData[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  // 收起状态：未记录即为展开，默认把全部天数都列出来
  const [collapsedDays, setCollapsedDays] = useState<Record<number, boolean>>({})
  // 当前查看详情的版本下标，null 表示停留在对比视图
  const [detailVersion, setDetailVersion] = useState<number | null>(null)
  const [detailDay, setDetailDay] = useState(0)
  const [mapFocus, setMapFocus] = useState<MapFocus | null>(null)
  const [selectedNode, setSelectedNode] = useState<TimeNode | null>(null)
  // 防止 React 严格模式下 effect 执行两次，导致重复生成与重复写入历史
  const generatedRef = useRef(false)

  // 路由 state 里没有请求时（比如从导航栏直接进来），退回上次规划的请求
  const request = useMemo(
    () => location.state?.request ?? loadLastRequest(),
    [location.state]
  )

  useEffect(() => {
    if (generatedRef.current || !request) return
    generatedRef.current = true
    fetchVersions(request)
  }, [request])

  /** 由请求推导天数：与行程页保持一致 */
  const daysOf = (req: any): number =>
    req?.departureDate && req?.returnDate
      ? Math.max(
          1,
          Math.ceil(
            (new Date(req.returnDate).getTime() - new Date(req.departureDate).getTime()) /
              (1000 * 60 * 60 * 24)
          ) + 1
        )
      : 3

  const fetchVersions = async (req: any) => {
    const destination = req.destination || '北京'
    const days = daysOf(req)
    const budget = parseInt(String(req.budget || '').replace(/[^0-9]/g, '').split('-')[0] || '8000')
    const travelers = (req.adults || 1) + (req.children || 0) + (req.seniors || 0)
    const preferences = stylesToTags(req.styles || [])

    try {
      const response = await apiFetch('/api/trip/versions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          destination,
          departure: req.origin || '北京',
          days,
          budget,
          travelers,
          preferences,
          special_needs: req.specialNeeds || [],
          start_date: req.departureDate || undefined,
        }),
      })
      if (!response.ok) {
        let detail = `生成失败（HTTP ${response.status}）`
        try {
          const body = await response.json()
          if (body?.detail) detail = body.detail
        } catch {
          // 非 JSON 响应，用默认提示
        }
        throw new Error(detail)
      }
      const data = await response.json()
      if (data.versions && Array.isArray(data.versions)) {
        setVersions(data.versions)
        // 生成成功后写入历史行程（失败不影响页面展示）
        saveTripRecord(data.versions, {
          destination,
          departure: req.origin || '北京',
          days,
          budget,
          preferences,
          travelers,
        })
      }
    } catch (err) {
      console.error('获取方案失败:', err)
      setError(err instanceof Error ? err.message : '生成方案失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }

  const saveTripRecord = async (
    versionList: VersionData[],
    meta: {
      destination: string
      departure: string
      days: number
      budget: number
      preferences: string[]
      travelers: number
    }
  ) => {
    try {
      await apiJson('/api/user/trips', {
        method: 'POST',
        body: JSON.stringify({
          destination: meta.destination,
          departure_city: meta.departure,
          days: meta.days,
          budget: meta.budget || null,
          travelers: meta.travelers || 1,
          preferences: meta.preferences,
          summary: `${meta.destination} ${meta.days} 天，已生成 ${versionList.length} 套对比方案`,
          // 保存每个版本的完整行程，历史详情页可切换查看
          content: JSON.stringify({
            type: 'versions',
            destination: meta.destination,
            versions: versionList.map((v) => ({
              id: v.id,
              label: v.label,
              description: v.description,
              total: v.budget?.total || 0,
              budget: v.budget,
              flight: v.flight || null,
              days: v.itinerary,
            })),
          }),
        }),
      })
    } catch (err) {
      console.error('保存历史行程失败:', err)
    }
  }

  // ===== 版本详情：保持引用稳定，避免地图的 fitBounds 覆盖定位 =====
  const detailPlan = detailVersion !== null ? versions[detailVersion]?.itinerary?.[detailDay] : undefined
  const detailMapPlans = useMemo(() => (detailPlan ? [detailPlan] : []), [detailPlan])

  const handleDetailNodeClick = (node: TimeNode) => {
    const coord = nodeCoord(node)
    if (coord) {
      setMapFocus({
        id: `${node.title}@${node.time}`,
        name: node.title,
        lat: coord[0],
        lon: coord[1],
      })
    }
    if (node.type === 'attraction') setSelectedNode(node)
  }

  const openDetail = (index: number) => {
    setDetailVersion(index)
    setDetailDay(0)
    setMapFocus(null)
  }

  // 没有可用的规划请求：不生成任何东西，引导用户先去规划
  if (!request) {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center gap-4 px-6 text-center pb-24 md:pb-0">
        <div className="text-4xl">📊</div>
        <p className="text-gray-500 text-sm">还没有可对比的方案</p>
        <p className="text-xs text-gray-400 max-w-sm">
          先完成一次行程规划，这里会给出省钱版 / 舒适版 / 网红打卡版三个方案的对比
        </p>
        <button
          onClick={() => navigate('/plan')}
          className="mt-2 bg-blue-600 text-white px-5 py-2.5 rounded-lg text-sm font-semibold hover:bg-blue-700 transition"
        >
          去规划行程
        </button>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="text-4xl animate-bounce mb-4">📊</div>
          <div className="text-gray-500">正在生成多方案对比...</div>
        </div>
      </div>
    )
  }

  if (error && versions.length === 0) {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center gap-4 px-6 text-center pb-24 md:pb-0">
        <div className="text-3xl">🚧</div>
        <p className="text-red-500 text-sm max-w-md">{error}</p>
        <button onClick={() => navigate('/plan')} className="text-blue-600 hover:underline text-sm">
          重新规划
        </button>
      </div>
    )
  }

  // ==================== 版本详情视图 ====================
  if (detailVersion !== null && versions[detailVersion]) {
    const version = versions[detailVersion]
    const colors = VERSION_COLORS[version.id] || VERSION_COLORS.comfort
    const flight = version.flight
    const dayCount = version.itinerary?.length || 0

    return (
      <div className="min-h-screen bg-gray-50 pb-24 md:pb-0">
        {/* 桌面端顶部导航高 64px（h-16），这里跟着偏移，否则返回按钮会被导航盖住 */}
        <div className="bg-white border-b border-gray-200 sticky top-0 md:top-16 z-10">
          <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between gap-3">
            <button
              onClick={() => { setDetailVersion(null); setMapFocus(null) }}
              className="text-sm text-gray-500 hover:text-gray-700"
            >
              ← 返回对比
            </button>
            <h1 className="text-base font-bold" style={{ color: colors.text }}>
              {VERSION_LABELS[version.id] || version.label}
            </h1>
            <span className="text-orange-600 font-bold text-sm">
              ¥{(version.budget?.total || 0).toLocaleString()}
            </span>
          </div>

          <div className="max-w-6xl mx-auto px-4 pb-2 flex gap-1 overflow-x-auto">
            {version.itinerary?.map((d, i) => (
              <button
                key={i}
                onClick={() => { setDetailDay(i); setMapFocus(null) }}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium whitespace-nowrap transition ${
                  detailDay === i ? 'bg-blue-600 text-white' : 'text-gray-500 hover:bg-gray-100'
                }`}
              >
                Day {d.day || i + 1}
              </button>
            ))}
          </div>
        </div>

        <div className="max-w-6xl mx-auto px-4 py-6 space-y-5">
          {/* 机票 / 酒店 / 预算 概览 */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {flight && (
              <div className="bg-white rounded-xl border border-gray-200 p-4">
                <div className="text-xs font-semibold text-gray-500 mb-2">✈️ 机票</div>
                <div className="text-sm font-semibold text-gray-800">
                  {flight.airline} {flight.flight_no}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {flight.departure_time} → {flight.arrival_time}
                  {flight.duration ? ` · ${flight.duration}` : ''}
                </div>
                {flight.departure_airport && (
                  <div className="text-xs text-gray-400 mt-1">
                    {flight.departure_airport} → {flight.arrival_airport}
                  </div>
                )}
                <div className="flex items-center gap-2 mt-2">
                  <span className="text-orange-600 font-bold text-sm">
                    ¥{(flight.price || 0).toLocaleString()}
                  </span>
                  {flight.baggage && <span className="text-xs text-gray-400">{flight.baggage}</span>}
                </div>
                {flight.is_reference && (
                  <div className="text-[11px] text-amber-600 mt-1">
                    ⚠️ {flight.note || '参考航班，非实时数据'}
                  </div>
                )}
              </div>
            )}

            {detailPlan?.hotel && (
              <div className="bg-white rounded-xl border border-gray-200 p-4">
                <div className="text-xs font-semibold text-gray-500 mb-2">🏨 住宿</div>
                <div className="text-sm font-semibold text-gray-800">{detailPlan.hotel.name}</div>
                <div className="text-xs text-gray-500 mt-1">📍 {detailPlan.hotel.address}</div>
                <div className="text-orange-600 font-bold text-sm mt-2">
                  ¥{(detailPlan.hotel.pricePerNight || 0).toLocaleString()}/晚
                </div>
              </div>
            )}

            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <div className="text-xs font-semibold text-gray-500 mb-2">💰 预算明细</div>
              <div className="space-y-1 text-xs text-gray-500">
                <div className="flex justify-between"><span>✈️ 机票</span><span>¥{(version.budget?.flights || 0).toLocaleString()}</span></div>
                <div className="flex justify-between"><span>🏨 酒店</span><span>¥{(version.budget?.hotels || 0).toLocaleString()}</span></div>
                <div className="flex justify-between"><span>🎫 门票</span><span>¥{(version.budget?.attractions || 0).toLocaleString()}</span></div>
                <div className="flex justify-between"><span>🍽️ 餐饮</span><span>¥{(version.budget?.meals || 0).toLocaleString()}</span></div>
                <div className="flex justify-between"><span>🚇 交通</span><span>¥{(version.budget?.transport || 0).toLocaleString()}</span></div>
              </div>
            </div>
          </div>

          <div className="flex flex-col lg:flex-row gap-6">
            <div className="flex-1 min-w-0">
              <div className="text-sm font-semibold text-gray-700 mb-3">
                📅 Day {detailDay + 1} / 共 {dayCount} 天
              </div>
              {detailPlan ? (
                <ItineraryTimeline day={detailPlan} onNodeClick={handleDetailNodeClick} />
              ) : (
                <div className="text-sm text-gray-400">这一天没有行程数据</div>
              )}
              {detailPlan?.hotel && (
                <div className="mt-6">
                  <div className="text-sm font-semibold text-gray-700 mb-3">🏨 今晚住宿</div>
                  <HotelCard
                    hotel={detailPlan.hotel}
                    onClick={() => {
                      const { lat, lon, name } = detailPlan.hotel
                      if (lat && lon) setMapFocus({ id: `hotel@${name}`, name, lat, lon })
                    }}
                  />
                </div>
              )}
            </div>

            <div className="lg:w-96 flex-shrink-0">
              {/* 让开导航（64px）与吸顶标题栏（约 93px），避免侧栏被压在标题栏下面 */}
              <div className="sticky top-16 md:top-44">
                <TripMap
                  key={`${detailVersion}-${detailDay}`}
                  itinerary={detailMapPlans}
                  destination={request.destination || ''}
                  focus={mapFocus}
                />
              </div>
            </div>
          </div>
        </div>

        {selectedNode && (
          <AttractionModal node={selectedNode} onClose={() => setSelectedNode(null)} />
        )}
      </div>
    )
  }

  // ==================== 对比视图 ====================
  const dayCount = versions[0]?.itinerary?.length || 0
  const allCollapsed = dayCount > 0 && Array.from({ length: dayCount }, (_, i) => collapsedDays[i]).every(Boolean)

  return (
    <div className="min-h-screen bg-gray-50 pb-24 md:pb-0">
      <div className="bg-white border-b border-gray-200 px-4 py-4">
        <h1 className="text-lg font-bold text-gray-800 text-center">
          📊 多方案对比 · {request.destination || ''} {dayCount > 0 ? `${dayCount} 天` : ''}
        </h1>
        <p className="text-xs text-gray-400 text-center mt-1">点击任意方案卡片查看该方案的完整行程</p>
      </div>

      <div className="max-w-6xl mx-auto px-4 py-6">
        {error && (
          <div className="mb-4 text-xs text-red-500 bg-red-50 rounded-lg px-3 py-2">{error}</div>
        )}

        {/* 总览卡片：可点击进入版本详情 */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          {versions.map((v, i) => {
            const colors = VERSION_COLORS[v.id] || VERSION_COLORS.comfort
            return (
              <button
                key={i}
                onClick={() => openDetail(i)}
                className={`text-left bg-white rounded-xl border-2 ${colors.border} overflow-hidden shadow-sm hover:shadow-md transition`}
              >
                <div className="text-white text-sm font-bold px-4 py-2.5" style={{ backgroundColor: colors.bg }}>
                  {VERSION_LABELS[v.id] || v.label}
                  {v.id === 'comfort' && <span className="ml-2 bg-white text-blue-600 px-2 py-0.5 rounded text-xs">推荐</span>}
                </div>
                <div className="p-4">
                  <p className="text-xs text-gray-500 mb-3">{v.description}</p>
                  <div className="text-2xl font-bold mb-3" style={{ color: colors.text }}>
                    ¥{(v.budget?.total || 0).toLocaleString()}
                  </div>
                  <div className="text-xs text-gray-500 space-y-1">
                    <div className="flex justify-between"><span>✈️ 机票</span><span>¥{(v.budget?.flights || 0).toLocaleString()}</span></div>
                    <div className="flex justify-between"><span>🏨 酒店</span><span>¥{(v.budget?.hotels || 0).toLocaleString()}</span></div>
                    <div className="flex justify-between"><span>🎫 门票</span><span>¥{(v.budget?.attractions || 0).toLocaleString()}</span></div>
                    <div className="flex justify-between"><span>🍽️ 餐饮</span><span>¥{(v.budget?.meals || 0).toLocaleString()}</span></div>
                    <div className="flex justify-between"><span>🚇 交通</span><span>¥{(v.budget?.transport || 0).toLocaleString()}</span></div>
                  </div>
                  <div className="mt-3 text-xs font-medium" style={{ color: colors.text }}>
                    查看完整行程（{v.itinerary?.length || 0} 天）→
                  </div>
                </div>
              </button>
            )
          })}
        </div>

        {/* 对比表格 */}
        {versions.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden mb-8">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50">
                    <th className="text-left px-4 py-3 font-semibold text-gray-600 w-24">对比项</th>
                    {versions.map((v, i) => (
                      <th key={i} className="text-center px-4 py-3 font-semibold" style={{ color: VERSION_COLORS[v.id]?.text }}>
                        {VERSION_LABELS[v.id] || v.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {[
                    { label: '💰 总价', key: 'total' },
                    { label: '✈️ 机票', key: 'flights' },
                    { label: '🏨 酒店', key: 'hotels' },
                    { label: '🎫 门票', key: 'attractions' },
                    { label: '🍽️ 餐饮', key: 'meals' },
                    { label: '🚇 交通', key: 'transport' },
                  ].map((row) => (
                    <tr key={row.key}>
                      <td className="px-4 py-3 font-medium text-gray-600">{row.label}</td>
                      {versions.map((v, i) => (
                        <td key={i} className="text-center px-4 py-3 text-gray-700">
                          ¥{Number((v.budget as any)?.[row.key] || 0).toLocaleString()}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* 每日行程对比：列出全部天数 */}
        {dayCount > 0 && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-bold text-gray-800">📅 每日行程对比（共 {dayCount} 天）</h2>
              <button
                onClick={() => {
                  const next: Record<number, boolean> = {}
                  for (let i = 0; i < dayCount; i += 1) next[i] = !allCollapsed
                  setCollapsedDays(next)
                }}
                className="text-xs text-blue-600 hover:underline"
              >
                {allCollapsed ? '展开全部' : '收起全部'}
              </button>
            </div>

            {Array.from({ length: dayCount }, (_, dayIdx) => {
              const isCollapsed = !!collapsedDays[dayIdx]
              const dayLabel = versions[0].itinerary[dayIdx]?.date || `Day ${dayIdx + 1}`
              return (
                <div key={dayIdx} className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                  <button
                    className="w-full px-4 py-3 text-left font-semibold text-gray-700 bg-gray-50 hover:bg-gray-100 flex justify-between items-center"
                    onClick={() => setCollapsedDays((prev) => ({ ...prev, [dayIdx]: !prev[dayIdx] }))}
                  >
                    <span>
                      Day {dayIdx + 1}
                      <span className="ml-2 text-xs font-normal text-gray-400">{dayLabel}</span>
                    </span>
                    <span className="text-gray-400 text-xs">{isCollapsed ? '展开 ▼' : '收起 ▲'}</span>
                  </button>
                  {!isCollapsed && (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="bg-gray-50">
                            <th className="text-left px-4 py-2 font-medium text-gray-500 w-20">时间</th>
                            {versions.map((v, vi) => (
                              <th key={vi} className="text-left px-4 py-2 font-medium" style={{ color: VERSION_COLORS[v.id]?.text }}>
                                {VERSION_LABELS[v.id] || v.label}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                          {(versions[0].itinerary[dayIdx]?.nodes || []).map((node, nodeIdx) => (
                            <tr key={nodeIdx}>
                              <td className="px-4 py-2 text-gray-500 text-xs">{node.time}</td>
                              {versions.map((v, vi) => {
                                const vNode = v.itinerary[dayIdx]?.nodes?.[nodeIdx]
                                return (
                                  <td key={vi} className="px-4 py-2">
                                    {vNode ? (
                                      <div>
                                        <span className="text-sm font-medium">{vNode.title}</span>
                                        {vNode.type === 'attraction' && vNode.detail && (
                                          <div className="text-xs text-gray-400 mt-0.5">
                                            🎫 {(vNode.detail as any).ticketKnown === false
                                              ? '票价待查'
                                              : (vNode.detail as any).free
                                                ? '免费'
                                                : `¥${(vNode.detail as any).ticketPrice}`}
                                          </div>
                                        )}
                                      </div>
                                    ) : (
                                      <span className="text-gray-300">—</span>
                                    )}
                                  </td>
                                )
                              })}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
