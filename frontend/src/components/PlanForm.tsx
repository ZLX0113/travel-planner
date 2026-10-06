import { useState } from 'react'
import CityCombobox from './CityCombobox'
import { DEFAULT_DEPARTURE } from '../constants/cities'
import { BUDGET_OPTIONS, CUSTOM_BUDGET, DEFAULT_BUDGET, MIN_BUDGET } from '../constants/budget'

interface PlanFormProps {
  initialDestination?: string
  /** 从用户偏好记忆中回填的出发地、预算档位 */
  initialValues?: { origin?: string; budget?: string }
  onNext: (data: any) => void
}

/** 转成 <input type="date"> 需要的本地日期（不能用 toISOString，会因时区差一天） */
function toDateInput(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

/** 日期字符串往后推 n 天 */
function addDays(dateStr: string, days: number): string {
  const date = new Date(`${dateStr}T00:00:00`)
  date.setDate(date.getDate() + days)
  return toDateInput(date)
}

export default function PlanForm({ initialDestination = '', initialValues, onNext }: PlanFormProps) {
  const [origin, setOrigin] = useState(initialValues?.origin || DEFAULT_DEPARTURE)
  const [destination, setDestination] = useState(initialDestination)
  const [departureDate, setDepartureDate] = useState('')
  const [returnDate, setReturnDate] = useState('')
  const [adults, setAdults] = useState(2)
  const [children, setChildren] = useState(0)
  const [seniors, setSeniors] = useState(0)
  const [specialNeeds, setSpecialNeeds] = useState<string[]>([])
  const [budget, setBudget] = useState(initialValues?.budget || DEFAULT_BUDGET)
  const [customBudget, setCustomBudget] = useState('')

  // 今天（本地日期），只取一次
  const [today] = useState(() => toDateInput(new Date()))
  /** 返程最早只能选出发的次日 */
  const minReturnDate = departureDate ? addDays(departureDate, 1) : today

  const SPECIAL_OPTIONS = [
    { value: 'infant', label: '👶 有婴幼儿（0-3岁）' },
    { value: 'child', label: '👧 有儿童（4-12岁）' },
    { value: 'senior', label: '👴 有老人（60+）' },
    { value: 'pregnant', label: '🤰 有孕妇' },
    { value: 'accessible', label: '♿ 无障碍需求' },
  ]

  const customBudgetValue = parseInt(customBudget, 10)

  // 日期和预算的校验：不合格时直接拦住提交并说明原因
  const errors: string[] = []
  if (departureDate && departureDate < today) errors.push('出发日期不能早于今天')
  if (departureDate && returnDate && returnDate <= departureDate) errors.push('返程日期要晚于出发日期')
  if (budget === CUSTOM_BUDGET) {
    if (!Number.isFinite(customBudgetValue)) {
      errors.push('请输入自定义预算')
    } else if (customBudgetValue < MIN_BUDGET) {
      errors.push(`预算不能低于 ${MIN_BUDGET} 元`)
    }
  }

  const canSubmit =
    Boolean(destination) && Boolean(departureDate) && Boolean(returnDate) && errors.length === 0

  const toggleSpecial = (value: string) => {
    setSpecialNeeds((prev) =>
      prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value]
    )
  }

  const handleDepartureChange = (value: string) => {
    setDepartureDate(value)
    // 出发日期往后挪时，早于它的返程日期自动顺延，避免出现无效区间
    if (value && (!returnDate || returnDate <= value)) {
      setReturnDate(addDays(value, 1))
    }
  }

  const handleSubmit = () => {
    onNext({
      origin, destination, departureDate, returnDate,
      adults, children, seniors, specialNeeds,
      // 自定义时传用户输入的数值，预设档位直接传档位文案（下游都只取其中的数字）
      budget: budget === CUSTOM_BUDGET ? String(customBudgetValue) : budget,
    })
  }

  return (
    <div className="max-w-lg mx-auto space-y-5">
      <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">基本信息</h3>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="text-xs font-semibold text-gray-500 mb-1 block">📍 出发地</label>
          <CityCombobox
            value={origin}
            onChange={setOrigin}
            scope="departure"
            placeholder="输入出发城市，如 北京"
          />
        </div>
        <div>
          <label className="text-xs font-semibold text-gray-500 mb-1 block">📍 目的地（仅国内）</label>
          <CityCombobox
            value={destination}
            onChange={setDestination}
            placeholder="输入任意国内地名，如 乌镇"
          />
          <p className="text-[11px] text-gray-400 mt-1">
            支持国内任意城市与小众目的地（区县、古镇、景区），境外暂不开放
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="text-xs font-semibold text-gray-500 mb-1 block">📅 出发日期</label>
          <input
            type="date" value={departureDate} min={today}
            onChange={(e) => handleDepartureChange(e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
          />
        </div>
        <div>
          <label className="text-xs font-semibold text-gray-500 mb-1 block">📅 返程日期</label>
          <input
            type="date" value={returnDate} min={minReturnDate}
            onChange={(e) => setReturnDate(e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
          />
          <p className="text-[11px] text-gray-400 mt-1">需晚于出发日期</p>
        </div>
      </div>

      <div>
        <label className="text-xs font-semibold text-gray-500 mb-2 block">👥 出行人数</label>
        <div className="flex gap-4">
          {[
            { label: '成人', value: adults, set: setAdults },
            { label: '儿童', value: children, set: setChildren },
            { label: '老人', value: seniors, set: setSeniors },
          ].map((item) => (
            <div key={item.label} className="flex items-center gap-2 bg-white border border-gray-200 rounded-lg px-3 py-2">
              <span className="text-xs text-gray-500">{item.label}</span>
              <span className="font-bold text-base">{item.value}</span>
              <button
                onClick={() => item.set(Math.max(0, item.value - 1))}
                className="text-blue-600 text-lg leading-none"
              >−</button>
              <button
                onClick={() => item.set(item.value + 1)}
                className="text-blue-600 text-lg leading-none"
              >+</button>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <label className="text-xs font-semibold text-gray-500 mb-2 block">⚠️ 特殊人群关怀（可选）</label>
        <div className="flex flex-wrap gap-3">
          {SPECIAL_OPTIONS.map((opt) => (
            <label key={opt.value} className="flex items-center gap-1.5 text-sm cursor-pointer">
              <input
                type="checkbox" checked={specialNeeds.includes(opt.value)}
                onChange={() => toggleSpecial(opt.value)}
                className="accent-blue-600"
              />
              {opt.label}
            </label>
          ))}
        </div>
      </div>

      <div>
        <label className="text-xs font-semibold text-gray-500 mb-2 block">💰 预算范围（每人）</label>
        <div className="flex gap-2 flex-wrap">
          {BUDGET_OPTIONS.map((opt) => (
            <button
              key={opt}
              onClick={() => setBudget(opt)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                budget === opt
                  ? 'bg-blue-50 text-blue-600 border-2 border-blue-600'
                  : 'bg-white border border-gray-200 text-gray-600 hover:border-gray-300'
              }`}
            >
              {opt}
            </button>
          ))}
        </div>
        {budget === CUSTOM_BUDGET && (
          <div className="mt-3 flex items-center gap-2">
            <span className="text-sm text-gray-500">¥</span>
            <input
              type="number"
              min={MIN_BUDGET}
              step={100}
              value={customBudget}
              onChange={(e) => setCustomBudget(e.target.value)}
              placeholder={`不低于 ${MIN_BUDGET}`}
              className="w-40 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
            />
            <span className="text-xs text-gray-400">元 / 每人，最低 {MIN_BUDGET} 元</span>
          </div>
        )}
      </div>

      {errors.length > 0 && (
        <div className="text-xs text-red-500 space-y-0.5">
          {errors.map((message, i) => (
            <div key={i}>· {message}</div>
          ))}
        </div>
      )}

      <button
        onClick={handleSubmit}
        disabled={!canSubmit}
        className="w-full bg-blue-600 text-white py-3 rounded-lg text-sm font-semibold hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition"
      >
        下一步：选择偏好 →
      </button>
    </div>
  )
}