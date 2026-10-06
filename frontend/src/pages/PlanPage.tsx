import { useState, useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import PlanForm from '../components/PlanForm'
import PreferenceForm, { type PreferenceFormState } from '../components/PreferenceForm'
import { apiJson } from '../api/client'
import { stylesToTags } from '../constants/preferences'
import { budgetToOption } from '../constants/budget'
import { saveLastRequest } from '../utils/lastRequest'

interface Preference {
  departure_city: string
  destination: string
  days: number
  budget: number | null
  travelers: number
  preferences: string[]
  form_state: PreferenceFormState | null
  updated_at: string
}

// 预算档位与"数值→档位"的映射统一放在 constants/budget.ts，避免和表单里的定义走样

export default function PlanPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [step, setStep] = useState(1)
  const [basicInfo, setBasicInfo] = useState<any>(null)
  const [preference, setPreference] = useState<Preference | null>(null)
  const [preferenceLoaded, setPreferenceLoaded] = useState(false)

  const initialDestination = searchParams.get('destination') || ''

  // 读取偏好记忆用于表单回填
  useEffect(() => {
    apiJson<Preference | null>('/api/user/preferences')
      .then(setPreference)
      .catch(() => setPreference(null))
      .finally(() => setPreferenceLoaded(true))
  }, [])

  const handleBasicNext = (data: any) => {
    setBasicInfo(data)
    setStep(2)
  }

  const handlePreferenceSubmit = (prefs: PreferenceFormState) => {
    const fullRequest = { ...basicInfo, ...prefs }
    // 记住这次的请求，方案对比页从导航栏进入时也能拿到
    saveLastRequest(fullRequest)
    // 把本次偏好写入记忆，失败不阻塞主流程
    savePreferenceMemory(fullRequest).catch(() => {})
    navigate('/itinerary/new', { state: { request: fullRequest } })
  }

  const savePreferenceMemory = async (request: any) => {
    const days = request.departureDate && request.returnDate
      ? Math.ceil(
          (new Date(request.returnDate).getTime() - new Date(request.departureDate).getTime()) /
            (1000 * 60 * 60 * 24)
        ) + 1
      : 5
    const budget = parseInt(String(request.budget || '').replace(/[^0-9]/g, '').split('-')[0] || '0')

    await apiJson('/api/user/preferences', {
      method: 'PUT',
      body: JSON.stringify({
        departure_city: request.origin || '',
        destination: request.destination || '',
        days: days > 0 ? days : 5,
        budget: budget || null,
        travelers: (request.adults || 1) + (request.children || 0) + (request.seniors || 0),
        preferences: stylesToTags(request.styles || []),
        // 原始勾选状态，下次进偏好设置页原样回显。
        // 字段名要和 PreferenceForm 提交的一致（transport_pref / hotel_pref），否则存进去永远是空
        form_state: {
          styles: request.styles || [],
          transport_pref: request.transport_pref || '',
          hotel_pref: request.hotel_pref || [],
          pace: request.pace || '',
        },
      }),
    })
  }

  // 只回显用户上次在这里勾过的原始选择；没有记录就留空，让用户自己勾。
  // 不再按偏好标签反推——标签是有损的（一个标签对应多个风格），反推会凭空多出一堆勾选
  const initialForm: PreferenceFormState | null = preference?.form_state ?? null

  return (
    <div className="min-h-screen bg-gray-50 pb-24 md:pb-0">
      <div className="bg-white border-b border-gray-200 px-4 py-4">
        <div className="max-w-lg mx-auto">
          <div className="flex items-center justify-center gap-0 mb-3">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
              step >= 1 ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-400'
            }`}>1</div>
            <div className={`h-0.5 w-12 ${step >= 2 ? 'bg-blue-600' : 'bg-gray-200'}`} />
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
              step >= 2 ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-400'
            }`}>2</div>
            <div className={`h-0.5 w-12 bg-gray-200`} />
            <div className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold bg-gray-200 text-gray-400">3</div>
          </div>
          <div className="flex justify-center gap-16 text-xs text-gray-400">
            <span className={step >= 1 ? 'text-blue-600 font-semibold' : ''}>基本信息</span>
            <span className={step >= 2 ? 'text-blue-600 font-semibold' : ''}>偏好设置</span>
            <span>确认提交</span>
          </div>
        </div>
      </div>

      <div className="max-w-lg mx-auto px-4 py-8">
        {!preferenceLoaded && (
          <div className="text-center text-gray-400 text-sm py-10">正在读取你的偏好...</div>
        )}

        {preferenceLoaded && step === 1 && (
          <PlanForm
            initialDestination={initialDestination || preference?.destination || ''}
            initialValues={{
              origin: preference?.departure_city || undefined,
              budget: budgetToOption(preference?.budget ?? null),
            }}
            onNext={handleBasicNext}
          />
        )}

        {preferenceLoaded && step === 2 && (
          <PreferenceForm
            initialForm={initialForm}
            onBack={() => setStep(1)}
            onSubmit={handlePreferenceSubmit}
          />
        )}
      </div>
    </div>
  )
}
