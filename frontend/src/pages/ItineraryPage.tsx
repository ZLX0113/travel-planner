import { useState, useEffect, useMemo, useRef } from 'react'
import { useLocation, useParams, useNavigate } from 'react-router-dom'
import html2pdf from 'html2pdf.js'
import TripMap, { nodeCoord, type MapFocus } from '../components/TripMap'
import ItineraryTimeline from '../components/ItineraryTimeline'
import AttractionModal from '../components/AttractionModal'
import HotelCard from '../components/HotelCard'
import { apiFetch, apiJson } from '../api/client'
import { stylesToTags } from '../constants/preferences'
import { saveLastRequest } from '../utils/lastRequest'
import type { Itinerary, DayPlan, TimeNode, BudgetBreakdown } from '../types'

export default function ItineraryPage() {
  const { id } = useParams<{ id: string }>()
  const location = useLocation()
  const navigate = useNavigate()
  const [itinerary, setItinerary] = useState<Itinerary | null>(null)
  const [currentDay, setCurrentDay] = useState(0)
  const [selectedNode, setSelectedNode] = useState<TimeNode | null>(null)
  // 点击地点后地图要定位到的位置
  const [mapFocus, setMapFocus] = useState<MapFocus | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const abortRef = useRef<AbortController | null>(null)
  const contentRef = useRef<HTMLDivElement>(null)

  // 保持引用稳定：否则每次渲染都生成新数组，地图的 fitBounds 会覆盖掉点击定位
  const activeDay = itinerary?.days?.[currentDay]
  const mapDayPlans = useMemo(() => (activeDay ? [activeDay] : []), [activeDay])

  /** 点击地点后把右侧地图切到该位置；景点同时打开详情弹窗 */
  const handleNodeClick = (node: TimeNode) => {
    const coord = nodeCoord(node)
    if (coord) {
      setMapFocus({
        id: `${node.title}@${node.time}`,
        name: node.title,
        lat: coord[0],
        lon: coord[1],
      })
    }
    if (node.type === 'attraction') {
      setSelectedNode(node)
    }
  }

  useEffect(() => {
    const request = location.state?.request
    if (id !== 'new' || !request) return

    // 记下来，方案对比页从导航栏进入时也能拿到这次请求
    saveLastRequest(request)

    let cancelled = false
    // 严格模式下会「挂载 → 卸载 → 再挂载」，用一个宏任务跳过那次假挂载，
    // 避免发出两次请求、第一次还被中止（控制台出现 ERR_ABORTED）
    const timer = setTimeout(() => {
      if (!cancelled) generateItinerary(request)
    }, 0)

    return () => {
      cancelled = true
      clearTimeout(timer)
      if (abortRef.current) {
        abortRef.current.abort()
      }
    }
  }, [id, location.state])

  const generateItinerary = async (request: any) => {
    setLoading(true)
    const destination = request.destination || ''
    const departure = request.origin || '北京'
    const days = Math.ceil(
      (new Date(request.returnDate).getTime() - new Date(request.departureDate).getTime()) /
      (1000 * 60 * 60 * 24)
    ) + 1
    const budget = parseInt(request.budget?.replace(/[^0-9]/g, '').split('-')[0] || '8000')
    const travelers = (request.adults || 1) + (request.children || 0) + (request.seniors || 0)
    const preferences = stylesToTags(request.styles || [])
    // 本次请求自己的 controller：判断中止必须用它，不能用 abortRef（重挂载后它已指向新请求）
    const controller = new AbortController()
    abortRef.current = controller

    try {
      const response = await apiFetch('/api/trip/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          destination,
          departure,
          days,
          budget,
          travelers,
          // 有小孩 / 老人 / 孕妇 / 无障碍需求时，后端会据此放缓行程节奏
          special_needs: request.specialNeeds || [],
          start_date: request.departureDate || undefined,
        }),
        signal: controller.signal,
      })

      // 后端会拒绝境外城市等非法目的地，这里把原因展示出来
      if (!response.ok) {
        let detail = `生成失败（HTTP ${response.status}）`
        try {
          const data = await response.json()
          if (data?.detail) detail = data.detail
        } catch {
          // 非 JSON 响应，用默认提示
        }
        throw new Error(detail)
      }

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let dayPlans: DayPlan[] = []
          let totalBudget: BudgetBreakdown = { flights: 0, hotels: 0, attractions: 0, meals: 0, transport: 0, insurance: 0, misc: 0, total: 0 }

      while (reader) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const event = JSON.parse(line.slice(6))

              if (event.status === 'itinerary' && event.data) {
                // data.data 是 DayPlan[] 数组
                dayPlans = event.data
                setItinerary({
                  id: 'new',
                  version: 'v1',
                  destination,
                  days: dayPlans,
                  totalBudget,
                  createdAt: new Date().toISOString(),
                })
              } else if (event.status === 'budget' && event.total) {
                totalBudget = event.breakdown
                setItinerary(prev => prev ? { ...prev, totalBudget } : null)
              }
            } catch {}
          }
        }
      }

      // 生成成功后写入历史行程（失败不影响页面展示）
      if (dayPlans.length > 0) {
        saveTripRecord({
          destination,
          departure,
          days,
          budget,
          travelers,
          preferences,
          dayPlans,
          totalBudget,
        })
      }
    } catch (err) {
      // 本次请求被主动中止（组件卸载、严格模式重挂载）不算失败
      if (!controller.signal.aborted) {
        console.error('生成行程失败:', err)
        setError(err instanceof Error ? err.message : '生成失败，请稍后重试')
      }
    } finally {
      setLoading(false)
    }
  }

  const saveTripRecord = async (params: {
    destination: string
    departure: string
    days: number
    budget: number
    travelers: number
    preferences: string[]
    dayPlans: DayPlan[]
    totalBudget: BudgetBreakdown
  }) => {
    try {
      await apiJson('/api/user/trips', {
        method: 'POST',
        body: JSON.stringify({
          destination: params.destination,
          departure_city: params.departure,
          days: params.dayPlans.length || params.days,
          budget: params.budget || null,
          travelers: params.travelers,
          preferences: params.preferences,
          summary: `${params.destination} ${params.dayPlans.length} 天行程，预算约 ¥${(params.totalBudget.total || 0).toLocaleString()}`,
          // 保存完整行程，历史详情页可直接还原
          content: JSON.stringify({
            type: 'plan',
            destination: params.destination,
            total: params.totalBudget.total || 0,
            budget: params.totalBudget,
            days: params.dayPlans,
          }),
        }),
      })
    } catch (err) {
      console.error('保存历史行程失败:', err)
    }
  }

  const handleExportPDF = () => {
    if (!contentRef.current) return
    const element = contentRef.current.cloneNode(true) as HTMLElement
    // 移除 sticky 元素避免 PDF 中重复
    element.querySelectorAll('.sticky').forEach(el => (el as HTMLElement).style.position = 'static')
    const opt = {
      margin: 10,
      filename: `${itinerary?.destination || '行程'}_${new Date().toISOString().slice(0, 10)}.pdf`,
      image: { type: 'jpeg' as const, quality: 0.98 },
      html2canvas: { scale: 2, useCORS: true },
      jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' as const },
    }
    html2pdf().set(opt).from(element).save()
  }

  const handleCompare = () => {
    const request = location.state?.request
    if (request) {
      navigate('/compare', { state: { request } })
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="text-4xl animate-bounce mb-4">✈️</div>
          <div className="text-gray-500">正在生成行程...</div>
        </div>
      </div>
    )
  }

  if (!itinerary) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50 pb-14 md:pb-0 gap-4 px-6">
        {error ? (
          <div className="max-w-md text-center">
            <div className="text-3xl mb-3">🚧</div>
            <p className="text-red-500 text-sm mb-2">{error}</p>
            <p className="text-xs text-gray-400 mb-4">目前仅支持国内目的地，境外城市暂不开放</p>
          </div>
        ) : (
          <p className="text-gray-400">未找到行程数据</p>
        )}
        <button onClick={() => navigate('/plan')} className="text-blue-600 hover:underline text-sm">前往规划行程</button>
      </div>
    )
  }

  if (!itinerary.days?.length) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50 pb-14 md:pb-0 gap-4">
        <p className="text-gray-400">行程数据为空</p>
        <button onClick={() => navigate('/plan')} className="text-blue-600 hover:underline text-sm">重新规划</button>
      </div>
    )
  }

  const currentDayPlan = itinerary.days[currentDay]

  return (
    <div className="min-h-screen bg-gray-50 pb-24 md:pb-0">
      {/* 桌面端顶部导航高 64px（h-16），这里跟着偏移，否则标题栏和按钮会被导航盖住 */}
      <div className="bg-white border-b border-gray-200 sticky top-0 md:top-16 z-10">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-base font-bold text-gray-800">🗺️ {itinerary.destination}</h1>
            <span className="text-orange-600 font-bold text-sm">💰 ¥{itinerary.totalBudget?.total?.toLocaleString()}</span>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleExportPDF}
              className="text-xs bg-gray-100 text-gray-600 px-3 py-1.5 rounded-lg hover:bg-gray-200 transition"
            >
              📄 导出 PDF
            </button>
            <button
              onClick={handleCompare}
              className="text-xs bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700 transition"
            >
              📊 多方案对比
            </button>
          </div>
        </div>

        <div className="max-w-6xl mx-auto px-4 pb-2 flex gap-1 overflow-x-auto">
          {itinerary.days.map((_, i) => (
            <button
              key={i}
              onClick={() => { setCurrentDay(i); setMapFocus(null) }}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium whitespace-nowrap transition ${
                currentDay === i ? 'bg-blue-600 text-white' : 'text-gray-500 hover:bg-gray-100'
              }`}
            >
              Day {i + 1}
            </button>
          ))}
        </div>
      </div>

      <div ref={contentRef} className="max-w-6xl mx-auto px-4 py-6">
        <div className="flex flex-col lg:flex-row gap-6">
          <div className="flex-1 min-w-0">
            <ItineraryTimeline day={currentDayPlan} onNodeClick={handleNodeClick} />
            {currentDayPlan.hotel && (
              <div className="mt-6">
                <div className="text-sm font-semibold text-gray-700 mb-3">🏨 今晚住宿</div>
                <HotelCard
                  hotel={currentDayPlan.hotel}
                  onClick={() => {
                    const { lat, lon, name } = currentDayPlan.hotel
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
                key={currentDay}
                itinerary={mapDayPlans}
                destination={itinerary.destination}
                focus={mapFocus}
              />
              {itinerary.totalBudget && (
                <div className="mt-4 bg-white rounded-xl border border-gray-200 p-4">
                  <div className="text-sm font-semibold text-gray-700 mb-2">💰 预算明细</div>
                  <div className="space-y-1.5 text-xs text-gray-500">
                    {itinerary.totalBudget.flights > 0 && (
                      <div className="flex justify-between"><span>✈️ 机票</span><span>¥{itinerary.totalBudget.flights.toLocaleString()}</span></div>
                    )}
                    {itinerary.totalBudget.hotels > 0 && (
                      <div className="flex justify-between"><span>🏨 酒店</span><span>¥{itinerary.totalBudget.hotels.toLocaleString()}</span></div>
                    )}
                    {itinerary.totalBudget.attractions > 0 && (
                      <div className="flex justify-between"><span>🎫 门票</span><span>¥{itinerary.totalBudget.attractions.toLocaleString()}</span></div>
                    )}
                    {itinerary.totalBudget.meals > 0 && (
                      <div className="flex justify-between"><span>🍽️ 餐饮</span><span>¥{itinerary.totalBudget.meals.toLocaleString()}</span></div>
                    )}
                    {itinerary.totalBudget.transport > 0 && (
                      <div className="flex justify-between"><span>🚇 交通</span><span>¥{itinerary.totalBudget.transport.toLocaleString()}</span></div>
                    )}
                    <div className="flex justify-between font-bold text-gray-800 pt-1.5 border-t border-gray-100">
                      <span>总计</span><span>¥{itinerary.totalBudget.total.toLocaleString()}</span>
                    </div>
                  </div>
                </div>
              )}
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