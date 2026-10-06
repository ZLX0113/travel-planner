// 旅行请求（字段名与后端 form_state 保持一致）
export interface TravelRequest {
  origin: string
  destination: string
  departureDate: string
  returnDate: string
  adults: number
  children: number
  seniors: number
  specialNeeds: string[]
  budget: string
  styles: string[]
  transport_pref: string
  hotel_pref: string[]
  pace: string
}

// 数据源自适应字段：外部接口有什么就展示什么
export interface FieldItem {
  label: string
  value: string
}

// 通勤方案
export interface TransitOption {
  mode: string
  route: string
  duration: string
  price: number
}

// 通勤详情
export interface TransitDetail {
  mode: string
  route: string
  duration: string
  price: number
  alternatives?: TransitOption[]
  source?: string
  distanceKm?: number
  fields?: FieldItem[]
}

// 航班详情
export interface FlightDetail {
  flightNo: string
  airline: string
  departureTime: string
  arrivalTime: string
  duration: string
  price: number
  departureAirport: string
  arrivalAirport: string
  baggage: string
  seatsLeft: number
  source?: string
  isReference?: boolean
  note?: string
}

// 景点详情
export interface AttractionDetail {
  name: string
  images: string[]
  ticketPrice: number
  free: boolean
  ticketKnown?: boolean
  openingHours: string
  closingDay: string
  needBooking: boolean
  rating: number
  reviewCount: number
  suggestedDuration: string
  howToGet: TransitOption[]
  tips: string
  tags: string[]
  address?: string
  source?: string
  fields?: FieldItem[]
}

// 餐饮详情
export interface MealDetail {
  price: number
  notes?: string
  address?: string
  lat?: number
  lon?: number
  source?: string
  fields?: FieldItem[]
}

// 酒店信息
export interface HotelInfo {
  name: string
  images: string[]
  star: number
  address: string
  pricePerNight: number
  distanceToStation: string
  tags: string[]
  matchReason: string
  lat?: number
  lon?: number
  source?: string
  fields?: FieldItem[]
}

// 时间节点
export interface TimeNode {
  time: string
  type: 'flight' | 'transit' | 'attraction' | 'meal' | 'rest' | 'break'
  title: string
  category: string
  detail: FlightDetail | TransitDetail | AttractionDetail | HotelInfo | MealDetail | null
}

// 单日行程
export interface DayPlan {
  day: number
  date: string
  theme?: string
  notes?: string
  /** 同行关怀提示（有小孩 / 老人 / 孕妇 / 无障碍需求时生成） */
  careTips?: string[]
  weather: { condition: string; temp: string }
  nodes: TimeNode[]
  hotel: HotelInfo
}

// 预算
export interface BudgetBreakdown {
  flights: number
  hotels: number
  attractions: number
  meals: number
  transport: number
  insurance: number
  misc: number
  total: number
}

// 完整行程
export interface Itinerary {
  id: string
  version: string
  destination: string
  days: DayPlan[]
  totalBudget: BudgetBreakdown
  createdAt: string
}

// 消息（保留兼容）
export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  versions?: any[]
  itinerary?: any[]
  destination?: string
}