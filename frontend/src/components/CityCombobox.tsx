import { useEffect, useRef, useState } from 'react'
import { apiFetch } from '../api/client'
import { DEPARTURE_CITIES, DOMESTIC_CITIES } from '../constants/cities'

interface Suggestion {
  name: string
  district: string
  adcode: string
}

interface CityComboboxProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  /** 候选范围：目的地可选任意国内地名，出发地只给国内枢纽城市 */
  scope?: 'destination' | 'departure'
}

/**
 * 国内地名输入框：本地候选即时过滤 + 后端高德联想
 * 输入框接受任意国内地名（含区县、乡镇、景区），后端才是校验方。
 */
export default function CityCombobox({
  value,
  onChange,
  placeholder,
  scope = 'destination',
}: CityComboboxProps) {
  const [items, setItems] = useState<Suggestion[]>([])
  const [open, setOpen] = useState(false)
  const [highlight, setHighlight] = useState(-1)
  const boxRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const timerRef = useRef<number | null>(null)

  const localPool = scope === 'departure' ? DEPARTURE_CITIES : DOMESTIC_CITIES

  const clearTimer = () => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }

  // 点击组件外部时收起下拉
  useEffect(() => {
    const onDocMouseDown = (event: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onDocMouseDown)
    return () => document.removeEventListener('mousedown', onDocMouseDown)
  }, [])

  // 卸载时中止未完成的联想请求，避免控制台出现 ERR_ABORTED 之外的悬挂请求
  useEffect(
    () => () => {
      clearTimer()
      abortRef.current?.abort()
    },
    []
  )

  const localMatches = (keyword: string): Suggestion[] =>
    localPool
      .filter((city) => city.includes(keyword))
      .map((city) => ({ name: city, district: '', adcode: '' }))

  const handleInput = (text: string) => {
    onChange(text)
    setHighlight(-1)
    clearTimer()

    const keyword = text.trim()
    if (!keyword) {
      abortRef.current?.abort()
      setItems([])
      setOpen(false)
      return
    }

    const local = localMatches(keyword).slice(0, 8)
    setItems(local)
    setOpen(true)

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    timerRef.current = window.setTimeout(() => {
      apiFetch(`/api/cities/suggest?q=${encodeURIComponent(keyword)}`, {
        signal: controller.signal,
      })
        .then((res) => (res.ok ? res.json() : { items: [] }))
        .then((data) => {
          const seen = new Set<string>()
          const merged: Suggestion[] = []
          for (const item of [...((data?.items as Suggestion[]) || []), ...local]) {
            if (!item?.name || seen.has(item.name)) continue
            seen.add(item.name)
            merged.push(item)
          }
          setItems(merged.slice(0, 8))
        })
        .catch(() => {
          // 请求被中止或网络失败：保留本地候选
        })
    }, 250)
  }

  const select = (name: string) => {
    onChange(name)
    setItems([])
    setOpen(false)
    setHighlight(-1)
  }

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Escape') {
      setOpen(false)
      return
    }
    if (!open || items.length === 0) return

    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setHighlight((prev) => (prev + 1) % items.length)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setHighlight((prev) => (prev - 1 + items.length) % items.length)
    } else if (event.key === 'Enter') {
      event.preventDefault()
      select(items[highlight >= 0 ? highlight : 0].name)
    }
  }

  return (
    <div ref={boxRef} className="relative">
      <input
        type="text"
        value={value}
        onChange={(event) => handleInput(event.target.value)}
        onFocus={() => setOpen(items.length > 0)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        autoComplete="off"
        className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm bg-white focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
      />
      {open && items.length > 0 && (
        <ul className="absolute z-30 mt-1 w-full max-h-60 overflow-y-auto bg-white border border-gray-200 rounded-lg shadow-lg">
          {items.map((item, index) => (
            <li key={`${item.name}-${item.adcode}-${index}`}>
              <button
                type="button"
                onMouseEnter={() => setHighlight(index)}
                onClick={() => select(item.name)}
                className={`w-full flex items-center justify-between gap-2 px-3 py-2 text-left text-sm ${
                  highlight === index ? 'bg-blue-50 text-blue-700' : 'text-gray-700'
                }`}
              >
                <span className="truncate">{item.name}</span>
                {item.district && (
                  <span className="shrink-0 text-[11px] text-gray-400">{item.district}</span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
