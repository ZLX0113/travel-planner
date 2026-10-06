import type { TimeNode, AttractionDetail } from '../types'

interface Props {
  node: TimeNode | null
  onClose: () => void
}

export default function AttractionModal({ node, onClose }: Props) {
  if (!node || !node.detail) return null

  const detail = node.detail as AttractionDetail

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-white rounded-2xl max-w-lg w-full max-h-[85vh] overflow-y-auto shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {detail.images && detail.images.length > 0 ? (
          <div className="h-48 bg-gray-100 rounded-t-2xl flex items-center justify-center">
            <img
              src={detail.images[0]}
              alt={detail.name}
              className="w-full h-full object-cover rounded-t-2xl"
              onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
            />
          </div>
        ) : (
          <div className="h-48 bg-gradient-to-br from-blue-100 to-cyan-100 rounded-t-2xl flex items-center justify-center">
            <span className="text-5xl">🏯</span>
          </div>
        )}

        <div className="p-5">
          <h2 className="text-lg font-bold text-gray-800 mb-2">{detail.name}</h2>

          <div className="flex flex-wrap gap-1.5 mb-4">
            {detail.tags?.map((tag, i) => (
              <span key={i} className="bg-blue-50 text-blue-600 px-2 py-0.5 rounded text-xs">{tag}</span>
            ))}
            <span className="bg-green-50 text-green-600 px-2 py-0.5 rounded text-xs">
              ⭐ {detail.rating} · {detail.reviewCount}条评价
            </span>
          </div>

          <div className="space-y-2 text-sm text-gray-600 mb-4">
            <div>🎫 <strong>门票：</strong>{detail.ticketKnown === false ? '实时票价待查' : detail.free ? '免费' : `¥${detail.ticketPrice}`}</div>
            {detail.openingHours && <div>🕐 <strong>开放时间：</strong>{detail.openingHours}</div>}
            {detail.closingDay && <div>📅 <strong>闭馆日：</strong>{detail.closingDay}</div>}
            <div>⚠️ <strong>预约：</strong>{detail.needBooking ? '需要提前预约' : '无需预约，直接入场'}</div>
            <div>🕐 <strong>建议游玩：</strong>{detail.suggestedDuration}</div>
          </div>

          {detail.fields && detail.fields.length > 0 && (
            <div className="mb-4 bg-gray-50 rounded-lg p-3">
              <div className="text-sm font-semibold text-gray-700 mb-2">ℹ️ 详细信息</div>
              <div className="space-y-1.5 text-xs text-gray-600">
                {detail.fields
                  .filter((f) => f && f.value)
                  .map((f, i) => (
                    <div key={i} className="flex gap-2">
                      <span className="text-gray-400 flex-shrink-0 w-20">{f.label}</span>
                      <span className="break-all">{f.value}</span>
                    </div>
                  ))}
              </div>
            </div>
          )}

          {detail.howToGet && detail.howToGet.length > 0 && (
            <div className="mb-4">
              <div className="text-sm font-semibold text-gray-700 mb-2">🚇 到达方式</div>
              <div className="space-y-1.5 text-xs text-gray-500">
                {detail.howToGet.map((t, i) => (
                  <div key={i}>{t.mode} {t.route} · {t.duration} · ¥{t.price}</div>
                ))}
              </div>
            </div>
          )}

          {detail.tips && (
            <div className="bg-amber-50 border-l-4 border-amber-400 p-3 rounded-r-lg text-xs text-gray-600">
              <div className="font-semibold text-amber-700 mb-1">💡 游玩提示</div>
              {detail.tips}
            </div>
          )}
        </div>

        <div className="border-t border-gray-100 p-3 text-center">
          <button onClick={onClose} className="text-gray-400 text-sm hover:text-gray-600 transition">关闭</button>
        </div>
      </div>
    </div>
  )
}