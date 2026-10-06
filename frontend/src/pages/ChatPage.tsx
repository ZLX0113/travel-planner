import { useState, useRef, useEffect } from 'react'
import html2pdf from 'html2pdf.js'
import ChatWindow from '../components/ChatWindow'
import ChatInput from '../components/ChatInput'
import { Message } from '../types'
import { apiFetch } from '../api/client'

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: '你好！我是旅行规划师 🌍\n\n我可以帮你：\n- 推荐旅行目的地\n- 规划每日行程\n- 估算旅行预算\n- 提供景点和美食攻略\n\n想去哪里玩？告诉我你的需求吧～',
    },
  ])
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null!)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async (content: string) => {
    if (!content.trim() || isLoading) return

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content,
    }
    setMessages((prev) => [...prev, userMsg])
    setIsLoading(true)

    const assistantMsg: Message = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: '',
    }
    setMessages((prev) => [...prev, assistantMsg])

    try {
      // 构建历史消息 (不含欢迎消息)
      const history = [...messages, userMsg]
        .filter((m) => m.id !== 'welcome')
        .map((m) => ({ role: m.role, content: m.content }))

      const response = await apiFetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: history, stream: true }),
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (reader) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6)
            try {
              const parsed = JSON.parse(data)
              if (parsed.done) {
                break
              }
              if (parsed.error) {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMsg.id
                      ? { ...m, content: `[错误] ${parsed.error}` }
                      : m
                  )
                )
                break
              }
              if (parsed.content) {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMsg.id
                      ? { ...m, content: m.content + parsed.content }
                      : m
                  )
                )
              }
            } catch {
              // 忽略解析失败的行
            }
          }
        }
      }
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsg.id
            ? { ...m, content: `[网络错误] ${err instanceof Error ? err.message : '请求失败，请检查后端是否启动'}` }
            : m
        )
      )
    } finally {
      setIsLoading(false)
    }
  }

  const handleQuickPlan = async () => {
    const planRequest = {
      destination: "成都",
      days: 5,
      budget: 10000,
      preferences: ["美食", "文化"],
      departure: "北京",
      travelers: 1,
    }

    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: `一键规划：${planRequest.destination} ${planRequest.days}天旅行，预算${planRequest.budget}元，偏好${planRequest.preferences.join("、")}`,
    }
    setMessages((prev) => [...prev, userMsg])
    setIsLoading(true)

    const assistantMsg: Message = {
      id: (Date.now() + 1).toString(),
      role: "assistant",
      content: "",
    }
    setMessages((prev) => [...prev, assistantMsg])

    let tripBudget: number | null = null
    let tripItinerary: any[] | null = null

    try {
      const response = await apiFetch("/api/trip/plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(planRequest),
      })

      if (!response.ok) throw new Error(`HTTP ${response.status}`)

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      let buffer = ""

      while (reader) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split("\n")
        buffer = lines.pop() || ""

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6)
            try {
              const parsed = JSON.parse(data)
              if (parsed.done) break
              if (parsed.status === "searching" || parsed.status === "searched" || parsed.status === "generating") {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMsg.id
                      ? { ...m, content: `🔄 ${parsed.message}` }
                      : m
                  )
                )
              } else if (parsed.status === "budget" && parsed.total) {
                tripBudget = parsed.total
              } else if (parsed.status === "itinerary" && parsed.data) {
                tripItinerary = parsed.data
              } else if (parsed.status === "done" && parsed.content) {
                const finalContent = tripBudget
                  ? `💰 **预算总计: ¥${tripBudget.toLocaleString()}**\n\n---\n\n${parsed.content}`
                  : parsed.content
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMsg.id
                      ? { ...m, content: finalContent, itinerary: tripItinerary ?? undefined, destination: planRequest.destination }
                      : m
                  )
                )
              } else if (parsed.status === "error") {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMsg.id
                      ? { ...m, content: `[错误] ${parsed.message}` }
                      : m
                  )
                )
              }
            } catch {}
          }
        }
      }
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsg.id
            ? { ...m, content: `[错误] ${err instanceof Error ? err.message : "请求失败"}` }
            : m
        )
      )
    } finally {
      setIsLoading(false)
    }
  }

  const handleVersions = async () => {
    const planRequest = {
      destination: "成都",
      days: 5,
      budget: 10000,
      preferences: ["美食", "文化"],
      departure: "北京",
      travelers: 1,
    }

    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: `生成多版本方案：${planRequest.destination} ${planRequest.days}天`,
    }
    setMessages((prev) => [...prev, userMsg])
    setIsLoading(true)

    const assistantMsg: Message = {
      id: (Date.now() + 1).toString(),
      role: "assistant",
      content: "正在生成多版本对比方案...",
    }
    setMessages((prev) => [...prev, assistantMsg])

    try {
      const response = await apiFetch("/api/trip/versions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(planRequest),
      })

      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const data = await response.json()

      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsg.id
            ? { ...m, content: "📊 已生成三个版本方案，请在下方切换查看：\n\n", versions: data.versions }
            : m
        )
      )
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsg.id
            ? { ...m, content: `[错误] ${err instanceof Error ? err.message : "请求失败"}` }
            : m
        )
      )
    } finally {
      setIsLoading(false)
    }
  }

  const handleExportPDF = () => {
    // Find the last assistant message with substantial content
    const lastAssistantMsg = [...messages].reverse().find(
      (m) => m.role === 'assistant' && m.content.length > 50
    )
    if (!lastAssistantMsg) return

    // Create a clean HTML element for PDF
    const element = document.createElement('div')
    element.innerHTML = `
      <div style="padding: 20px; font-family: 'Microsoft YaHei', sans-serif; max-width: 800px; margin: 0 auto;">
        <h1 style="color: #2563eb; border-bottom: 2px solid #2563eb; padding-bottom: 10px; margin-bottom: 20px;">
          ✈️ 旅行规划师 - 行程方案
        </h1>
        <div style="font-size: 14px; line-height: 1.8; color: #333;">
          ${lastAssistantMsg.content.replace(/\n/g, '<br>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')}
        </div>
        <div style="margin-top: 30px; padding-top: 15px; border-top: 1px solid #ddd; color: #999; font-size: 12px; text-align: center;">
          由旅行规划师生成 · ${new Date().toLocaleDateString('zh-CN')}
        </div>
      </div>
    `

    const opt = {
      margin: [10, 10, 10, 10] as [number, number, number, number],
      filename: `旅行行程_${new Date().toISOString().slice(0, 10)}.pdf`,
      image: { type: 'jpeg' as const, quality: 0.98 },
      html2canvas: { scale: 2, useCORS: true },
      jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' as const },
    }

    html2pdf().set(opt).from(element).save()
  }

  return (
    <div className="flex flex-col h-screen md:h-[calc(100vh-3.5rem)] max-w-3xl mx-auto pb-14 md:pb-0">
      {/* 顶部栏 */}
      <header className="flex items-center justify-center py-4 border-b border-gray-200 bg-white">
        <h1 className="text-xl font-bold text-gray-800">
          <span className="mr-2">✈️</span>
          旅行规划师
        </h1>
      </header>

      {/* 聊天区域 */}
      <ChatWindow
        messages={messages}
        isLoading={isLoading}
        messagesEndRef={messagesEndRef}
      />

      {/* 快速规划按钮 */}
      <div className="px-4 pb-2 flex gap-2 flex-wrap justify-center">
        <button
          onClick={handleQuickPlan}
          disabled={isLoading}
          className="px-3 py-1.5 bg-gradient-to-r from-blue-500 to-cyan-500 text-white rounded-full text-xs font-medium hover:from-blue-600 hover:to-cyan-600 disabled:opacity-40 transition-all"
        >
          ✈️ 成都5天·美食文化之旅
        </button>
        <button
          onClick={handleVersions}
          disabled={isLoading}
          className="px-3 py-1.5 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-full text-xs font-medium hover:from-purple-600 hover:to-pink-600 disabled:opacity-40 transition-all"
        >
          📊 多版本对比
        </button>
        <button
          onClick={() => handleSend("帮我把第三天的行程换成海边景点")}
          disabled={isLoading}
          className="px-3 py-1.5 bg-white text-gray-600 border border-gray-200 rounded-full text-xs font-medium hover:bg-gray-50 disabled:opacity-40 transition-all"
        >
          🔄 修改行程
        </button>
        <button
          onClick={() => handleSend("帮我规划一次西安的4天旅行，预算8000元，偏好历史古迹和美食")}
          disabled={isLoading}
          className="px-3 py-1.5 bg-white text-gray-600 border border-gray-200 rounded-full text-xs font-medium hover:bg-gray-50 disabled:opacity-40 transition-all"
        >
          🏯 西安4天·古迹美食
        </button>
        <button
          onClick={handleExportPDF}
          disabled={isLoading}
          className="px-3 py-1.5 bg-gradient-to-r from-green-500 to-emerald-500 text-white rounded-full text-xs font-medium hover:from-green-600 hover:to-emerald-600 disabled:opacity-40 transition-all"
        >
          📄 导出 PDF
        </button>
      </div>

      {/* 输入区域 */}
      <ChatInput onSend={handleSend} isLoading={isLoading} />
    </div>
  )
}