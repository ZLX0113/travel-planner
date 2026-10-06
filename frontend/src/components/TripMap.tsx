import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet'
import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import type { DayPlan, TimeNode } from '../types'

// Fix Leaflet default icon issue
delete (L.Icon.Default.prototype as any)._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
})

// 少量兜底坐标（数据里没带经纬度时使用），正常情况都用节点自带的实时坐标
const FALLBACK_COORDS: Record<string, [number, number]> = {
  "天安门广场": [39.903182, 116.397755],
  "故宫博物院": [39.917839, 116.397029],
  "外滩": [31.239700, 121.490300],
  "西湖": [30.248600, 120.141800],
  "大熊猫繁育研究基地": [30.734200, 104.145700],
  "兵马俑": [34.384100, 109.278500],
}

// 国内目的地城市中心（地图初始视角）
const CITY_CENTERS: Record<string, [number, number]> = {
  "北京": [39.9042, 116.4074], "上海": [31.2304, 121.4737],
  "广州": [23.1291, 113.2644], "深圳": [22.5431, 114.0579],
  "成都": [30.5728, 104.0668], "重庆": [29.5630, 106.5516],
  "西安": [34.3416, 108.9398], "杭州": [30.2741, 120.1551],
  "南京": [32.0603, 118.7969], "苏州": [31.2989, 120.5853],
  "武汉": [30.5928, 114.3055], "长沙": [28.2282, 112.9388],
  "厦门": [24.4798, 118.0894], "青岛": [36.0671, 120.3826],
  "三亚": [18.2528, 109.5119], "海口": [20.0444, 110.1999],
  "桂林": [25.2736, 110.2900], "阳朔": [24.7785, 110.4966],
  "张家界": [29.1170, 110.4792], "丽江": [26.8721, 100.2299],
  "大理": [25.6065, 100.2676], "昆明": [24.8801, 102.8329],
  "贵阳": [26.6470, 106.6302], "哈尔滨": [45.8038, 126.5340],
  "沈阳": [41.8057, 123.4315], "大连": [38.9140, 121.6147],
  "济南": [36.6512, 117.1201],
  "天津": [39.0842, 117.2009], "郑州": [34.7466, 113.6254],
  "洛阳": [34.6197, 112.4540], "敦煌": [40.1421, 94.6618],
  "西宁": [36.6171, 101.7782], "银川": [38.4872, 106.2309],
  "乌鲁木齐": [43.8256, 87.6168], "拉萨": [29.6500, 91.1000],
  "黄山": [29.7147, 118.3376], "承德": [40.9515, 117.9634],
}

const DEFAULT_CENTER: [number, number] = [39.9042, 116.4074]  // 北京

/** 取节点坐标：优先用数据源返回的经纬度，没有再用兜底表 */
export function nodeCoord(node: TimeNode): [number, number] | null {
  const detail = (node.detail || {}) as Record<string, any>
  const lat = Number(detail.lat)
  const lon = Number(detail.lon)
  if (Number.isFinite(lat) && Number.isFinite(lon) && (lat !== 0 || lon !== 0)) {
    return [lat, lon]
  }
  return FALLBACK_COORDS[node.title] || null
}

/** 点击地点后地图要定位到的目标 */
export interface MapFocus {
  /** 用于触发切换的标识（切换同一个地点时也能重新定位） */
  id: string
  /** 地点名称，显示在地图标题栏 */
  name: string
  lat: number
  lon: number
}

interface TripMapProps {
  itinerary: DayPlan[]
  destination: string
  /** 点击景点 / 餐厅 / 酒店后把地图切到该位置 */
  focus?: MapFocus | null
}

function FocusOn({
  focus,
  markerRefs,
}: {
  focus?: MapFocus | null
  markerRefs: React.MutableRefObject<Record<string, L.Marker | null>>
}) {
  const map = useMap()

  useEffect(() => {
    if (!focus) return
    map.setView([focus.lat, focus.lon], 15)
    // 有对应标记时顺手把气泡打开，位置更直观
    const marker = Object.values(markerRefs.current).find((item) => {
      const latlng = item?.getLatLng?.()
      return (
        latlng &&
        Math.abs(latlng.lat - focus.lat) < 1e-6 &&
        Math.abs(latlng.lng - focus.lon) < 1e-6
      )
    })
    marker?.openPopup()
  }, [focus?.id, focus?.lat, focus?.lon, map, markerRefs])

  return null
}

function FitBounds({ itinerary, destination }: { itinerary: DayPlan[]; destination: string }) {
  const map = useMap()

  useEffect(() => {
    const coords: [number, number][] = []
    itinerary.forEach((day) => {
      day.nodes.forEach((node) => {
        const coord = nodeCoord(node)
        if (coord) coords.push(coord)
      })
    })

    if (coords.length > 0) {
      const bounds = L.latLngBounds(coords.map((c) => L.latLng(c[0], c[1])))
      map.fitBounds(bounds, { padding: [40, 40] })
    } else {
      const center = CITY_CENTERS[destination] || DEFAULT_CENTER
      map.setView(center, 12)
    }
  }, [itinerary, destination, map])

  return null
}

function MapErrorHandler({ onError }: { onError: () => void }) {
  const map = useMap()

  useEffect(() => {
    const handleTileError = () => {
      onError()
    }
    map.on('tileerror', handleTileError)
    return () => {
      map.off('tileerror', handleTileError)
    }
  }, [map, onError])

  return null
}

export default function TripMap({ itinerary, destination, focus }: TripMapProps) {
  const center = CITY_CENTERS[destination] || DEFAULT_CENTER
  const [mapError, setMapError] = useState(false)
  const markerRefs = useRef<Record<string, L.Marker | null>>({})

  const markers: { name: string; coord: [number, number]; day: number; category: string }[] = []
  itinerary.forEach((day) => {
    day.nodes.forEach((node) => {
      const coord = nodeCoord(node)
      if (coord) {
        markers.push({ name: node.title, coord, day: day.day, category: node.category })
      }
    })
  })

  const polylines: [number, number][][] = []
  itinerary.forEach((day) => {
    const dayCoords: [number, number][] = []
    day.nodes.forEach((node) => {
      const coord = nodeCoord(node)
      if (coord) dayCoords.push(coord)
    })
    if (dayCoords.length > 1) polylines.push(dayCoords)
  })

  const dayColors = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899', '#06B6D4']

  return (
    <div className="my-3 rounded-xl overflow-hidden border border-gray-200">
      <div className="px-4 py-2 bg-gray-50 border-b border-gray-200 text-xs font-medium text-gray-500 flex items-center justify-between gap-2">
        <span>🗺️ 行程地图</span>
        {focus && <span className="text-blue-600 truncate">📍 {focus.name}</span>}
      </div>
      <div style={{ height: '320px', width: '100%' }}>
        {mapError ? (
          <div className="h-full flex flex-col items-center justify-center bg-gray-100 text-gray-400 gap-2">
            <span className="text-3xl">🗺️</span>
            <p className="text-sm">地图加载失败，请检查网络连接</p>
            <button
              onClick={() => setMapError(false)}
              className="text-xs text-blue-600 hover:underline mt-1"
            >
              点击重试
            </button>
          </div>
        ) : (
          <MapContainer
            center={center}
            zoom={12}
            style={{ height: '100%', width: '100%' }}
            scrollWheelZoom={false}
            zoomControl={true}
          >
            <TileLayer
              attribution='&copy; 高德地图'
              url="https://wprd0{s}.is.autonavi.com/appmaptile?x={x}&y={y}&z={z}&lang=zh_cn&size=1&scl=1&style=7"
              subdomains={['1', '2', '3', '4']}
            />
            <MapErrorHandler onError={() => setMapError(true)} />
            <FitBounds itinerary={itinerary} destination={destination} />
            <FocusOn focus={focus} markerRefs={markerRefs} />

            {markers.map((m, i) => {
              const key = `${m.name}@${m.coord[0]},${m.coord[1]}`
              return (
                <Marker
                  key={`${key}-${i}`}
                  position={m.coord}
                  ref={(instance) => {
                    markerRefs.current[key] = instance
                  }}
                >
                  <Popup>
                    <div className="text-sm">
                      <div className="font-medium">{m.name}</div>
                      <div className="text-xs text-gray-500">Day {m.day} · {m.category}</div>
                    </div>
                  </Popup>
                </Marker>
              )
            })}

            {polylines.map((line, i) => (
              <Polyline
                key={i}
                positions={line}
                color={dayColors[i % dayColors.length]}
                weight={3}
                opacity={0.7}
                dashArray="8 4"
              />
            ))}
          </MapContainer>
        )}
      </div>
    </div>
  )
}