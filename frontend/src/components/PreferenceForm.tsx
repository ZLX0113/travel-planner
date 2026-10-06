import { useState } from 'react'
import { STYLE_OPTIONS } from '../constants/preferences'

/** 偏好设置表单的原始选择，与后端 form_state 结构一致 */
export interface PreferenceFormState {
  styles: string[]
  transport_pref: string
  hotel_pref: string[]
  pace: string
}

interface PreferenceFormProps {
  onBack: () => void
  onSubmit: (prefs: PreferenceFormState) => void
  /** 用户上次保存过的选择，首次使用时为 undefined */
  initialForm?: PreferenceFormState | null
}

const TRANSPORT_OPTIONS = [
  { value: 'public', label: '🚇 公共交通' },
  { value: 'taxi', label: '🚕 打车为主' },
  { value: 'drive', label: '🚗 自驾' },
  { value: 'bike', label: '🚲 骑行' },
]

const HOTEL_OPTIONS = [
  { value: 'budget', label: '🏨 经济型' },
  { value: 'comfort', label: '🏢 舒适型' },
  { value: 'luxury', label: '🏰 豪华型' },
  { value: 'bnb', label: '🏡 民宿' },
  { value: 'parking', label: '🅿️ 需停车位' },
  { value: 'wifi', label: '📶 免费WiFi' },
  { value: 'breakfast', label: '🍳 含早餐' },
]

const PACE_OPTIONS = [
  { value: 'slow', label: '🐢 轻松漫游' },
  { value: 'moderate', label: '🚶 适中节奏' },
  { value: 'fast', label: '🏃 紧凑高效' },
]

export default function PreferenceForm({ onBack, onSubmit, initialForm }: PreferenceFormProps) {
  // 首次进入不预选任何项，由用户自己勾；有历史选择时按上次的还原
  const [styles, setStyles] = useState<string[]>(initialForm?.styles || [])
  const [transportPref, setTransportPref] = useState(initialForm?.transport_pref || '')
  const [hotelPref, setHotelPref] = useState<string[]>(initialForm?.hotel_pref || [])
  const [pace, setPace] = useState(initialForm?.pace || '')

  const toggleTag = (value: string, list: string[], setter: React.Dispatch<React.SetStateAction<string[]>>) => {
    setter(list.includes(value) ? list.filter((v) => v !== value) : [...list, value])
  }

  // 风格与节奏会直接影响行程生成，必须由用户明确选择
  const missing: string[] = []
  if (styles.length === 0) missing.push('旅行风格')
  if (!pace) missing.push('行程节奏')

  return (
    <div className="max-w-lg mx-auto space-y-6">
      <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">偏好设置</h3>

      <div>
        <label className="text-sm font-semibold text-gray-700 mb-3 block">
          🎯 旅行风格（多选）<span className="text-red-500">*</span>
        </label>
        <div className="flex flex-wrap gap-2">
          {STYLE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => toggleTag(opt.value, styles, setStyles)}
              className={`px-3 py-1.5 rounded-full text-sm transition ${
                styles.includes(opt.value)
                  ? 'bg-blue-50 text-blue-600 border-2 border-blue-600'
                  : 'bg-white border border-gray-200 text-gray-600 hover:border-gray-300'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="text-sm font-semibold text-gray-700 mb-3 block">🚗 交通偏好</label>
        <div className="flex gap-2 flex-wrap">
          {TRANSPORT_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setTransportPref(transportPref === opt.value ? '' : opt.value)}
              className={`px-4 py-2 rounded-full text-sm transition ${
                transportPref === opt.value
                  ? 'bg-blue-50 text-blue-600 border-2 border-blue-600'
                  : 'bg-white border border-gray-200 text-gray-600 hover:border-gray-300'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="text-sm font-semibold text-gray-700 mb-3 block">🏨 住宿偏好</label>
        <div className="flex flex-wrap gap-2">
          {HOTEL_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => toggleTag(opt.value, hotelPref, setHotelPref)}
              className={`px-3 py-1.5 rounded-full text-sm transition ${
                hotelPref.includes(opt.value)
                  ? 'bg-blue-50 text-blue-600 border-2 border-blue-600'
                  : 'bg-white border border-gray-200 text-gray-600 hover:border-gray-300'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="text-sm font-semibold text-gray-700 mb-3 block">
          ⏱️ 行程节奏<span className="text-red-500">*</span>
        </label>
        <div className="flex gap-3 flex-wrap">
          {PACE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setPace(pace === opt.value ? '' : opt.value)}
              className={`px-4 py-2 rounded-full text-sm transition ${
                pace === opt.value
                  ? 'bg-blue-50 text-blue-600 border-2 border-blue-600'
                  : 'bg-white border border-gray-200 text-gray-600 hover:border-gray-300'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex gap-3 pt-4">
        <button
          onClick={onBack}
          className="flex-1 bg-white border border-gray-200 text-gray-600 py-3 rounded-lg text-sm font-medium hover:bg-gray-50 transition"
        >
          ← 上一步
        </button>
        <button
          onClick={() => onSubmit({ styles, transport_pref: transportPref, hotel_pref: hotelPref, pace })}
          disabled={missing.length > 0}
          className="flex-[2] bg-blue-600 text-white py-3 rounded-lg text-sm font-semibold hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition"
        >
          {missing.length > 0 ? `请先选择${missing.join('、')}` : '🚀 生成行程方案'}
        </button>
      </div>
    </div>
  )
}
