import type { DayPlan, TimeNode, FlightDetail, TransitDetail, AttractionDetail, HotelInfo, MealDetail, FieldItem } from '../types'

const TYPE_ICONS: Record<string, string> = {
  flight: '✈️', transit: '🚇', attraction: '📍', meal: '🍽️', rest: '🏨', break: '☕',
}

const TYPE_COLORS: Record<string, string> = {
  flight: '#2563eb', transit: '#f59e0b', attraction: '#10b981', meal: '#ef4444',
  rest: '#8b5cf6', break: '#0ea5e9',
}

interface Props {
  day: DayPlan
  /** 点击任一地点（景点 / 餐饮 / 酒店等）时回调，用于把右侧地图切过去 */
  onNodeClick: (node: TimeNode) => void
}

/** 数据源自适应字段：外部接口返回什么就渲染什么 */
function FieldList({ fields }: { fields?: FieldItem[] }) {
  if (!fields || fields.length === 0) return null
  return (
    <div className="space-y-0.5">
      {fields
        .filter((f) => f && f.value)
        .map((f, i) => (
          <div key={i}>
            <span className="text-gray-400">{f.label}：</span>
            <span>{f.value}</span>
          </div>
        ))}
    </div>
  )
}

export default function ItineraryTimeline({ day, onNodeClick }: Props) {
  const careTips = day.careTips || []

  return (
    <div className="space-y-0">
      <div className="text-sm text-gray-400 mb-4">
        📅 {day.date} · {day.weather?.condition || '晴'} {day.weather?.temp || '25°C'}
      </div>

      {careTips.length > 0 && (
        <div className="mb-4 bg-sky-50 border-l-4 border-sky-400 rounded-r-lg p-3">
          <div className="text-xs font-semibold text-sky-700 mb-1">💗 同行关怀安排</div>
          <ul className="space-y-0.5">
            {careTips.map((tip, i) => (
              <li key={i} className="text-xs text-gray-600">· {tip}</li>
            ))}
          </ul>
        </div>
      )}

      {day.nodes.map((node, i) => (
        <div key={i} className="flex gap-3 pb-4">
          <div className="w-14 text-right text-sm font-bold text-blue-600 pt-0.5 flex-shrink-0">
            {node.time}
          </div>

          <div className="relative flex flex-col items-center">
            <div
              className="w-2.5 h-2.5 rounded-full mt-1 flex-shrink-0"
              style={{ backgroundColor: TYPE_COLORS[node.type] || '#999' }}
            />
            {i < day.nodes.length - 1 && (
              <div className="w-0.5 flex-1 bg-gray-200 mt-1" />
            )}
          </div>

          <div className="flex-1 pb-2">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-lg">{TYPE_ICONS[node.type] || '📍'}</span>
              <span
                className="font-semibold text-sm cursor-pointer hover:text-blue-600 transition"
                title="点击在地图上定位"
                onClick={() => onNodeClick(node)}
              >
                {node.title}
              </span>
              {node.category && (
                <span className="bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded text-xs">
                  {node.category}
                </span>
              )}
            </div>

            {node.type === 'flight' && node.detail && (() => {
              const d = node.detail as FlightDetail
              return (
                <div className="text-xs text-gray-500 space-y-0.5 ml-8">
                  <div>🛫 {d.flightNo} · {d.airline}</div>
                  <div>🛬 {d.departureTime} → {d.arrivalTime} · {d.duration}</div>
                  <div className="flex gap-3 mt-1">
                    <span className="text-orange-600 font-medium">¥{d.price}</span>
                    <span>{d.baggage}</span>
                    {d.seatsLeft > 0 && d.seatsLeft <= 5 && (
                      <span className="text-red-500">🔥 仅剩{d.seatsLeft}座</span>
                    )}
                  </div>
                  {d.isReference && (
                    <div className="text-amber-600">⚠️ {d.note || '参考航班，非实时数据'}</div>
                  )}
                </div>
              )
            })()}

            {node.type === 'transit' && node.detail && (() => {
              const d = node.detail as TransitDetail
              return (
                <div className="text-xs text-gray-500 ml-8 space-y-0.5">
                  <div>
                    <span>🕐 {d.duration}</span>
                    <span className="mx-2">|</span>
                    <span>💰 ¥{d.price}</span>
                  </div>
                  <FieldList fields={d.fields} />
                </div>
              )
            })()}

            {node.type === 'meal' && node.detail && (() => {
              const d = node.detail as MealDetail
              return (
                <div className="text-xs text-gray-500 ml-8 space-y-0.5">
                  <div>💰 人均 ¥{d.price}</div>
                  {d.address && <div>📍 {d.address}</div>}
                  <FieldList fields={d.fields} />
                </div>
              )
            })()}

            {node.type === 'attraction' && node.detail && (() => {
              const d = node.detail as AttractionDetail
              return (
                <div className="text-xs text-gray-500 space-y-0.5 ml-8">
                  <div>🕐 建议游玩 {d.suggestedDuration}</div>
                  <div>
                    🎫 {d.ticketKnown === false ? '票价待查' : d.free ? '免费' : `¥${d.ticketPrice}`}
                    {d.openingHours && (
                      <>
                        <span className="mx-2">|</span>
                        🕐 {d.openingHours}
                      </>
                    )}
                  </div>
                  {d.needBooking && (
                    <div className="text-orange-500">⚠️ 需要提前预约</div>
                  )}
                  {d.closingDay && (
                    <div className="text-red-400">📅 闭馆日：{d.closingDay}</div>
                  )}
                  <FieldList fields={d.fields} />
                  <span
                    className="text-blue-600 cursor-pointer underline text-xs inline-block"
                    onClick={() => onNodeClick(node)}
                  >
                    📷 查看详情与图片
                  </span>
                </div>
              )
            })()}

            {node.type === 'break' && node.detail && (() => {
              const d = node.detail as { duration?: string; tips?: string; fields?: FieldItem[] }
              return (
                <div className="text-xs text-gray-500 ml-8 space-y-0.5">
                  {d.duration && <div>🕐 {d.duration}</div>}
                  {d.tips && <div>💡 {d.tips}</div>}
                  <FieldList fields={d.fields} />
                </div>
              )
            })()}

            {node.type === 'rest' && node.detail && (() => {
              const d = node.detail as HotelInfo
              return (
                <div className="text-xs text-gray-500 ml-8 space-y-0.5">
                  {d.address && <div>📍 {d.address}</div>}
                  {d.pricePerNight ? <div>💰 ¥{d.pricePerNight}/晚</div> : null}
                  <FieldList fields={d.fields} />
                </div>
              )
            })()}
          </div>
        </div>
      ))}
    </div>
  )
}
