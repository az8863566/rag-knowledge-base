import { defineStore } from 'pinia'
import { ref } from 'vue'
import { chatApi, settingsApi } from '@/api'
import type { ChatSource } from '@/types'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  thinking?: string
  sources?: ChatSource[]
  has_context?: boolean
  timestamp: string
  isStreaming?: boolean  // 标记消息是否正在流式输出
  threshold?: number     // 相似度阈值
  maxScore?: number      // 最高匹配分数
}

export const useChatStore = defineStore('chat', () => {
  // State
  const messages = ref<ChatMessage[]>([])
  const loading = ref(false)
  const error = ref('')
  const threshold = ref(0.75)
  const thresholdSource = ref('config')

  // Actions
  const sendMessage = async (question: string) => {
    // 添加用户消息
    messages.value.push({
      role: 'user',
      content: question,
      timestamp: new Date().toLocaleTimeString()
    })

    loading.value = true
    error.value = ''

    try {
      const response = await chatApi.chat({ question })
      const data = response.data

      // 添加助手消息
      messages.value.push({
        role: 'assistant',
        content: data.answer,
        sources: data.sources,
        has_context: data.has_context,
        timestamp: new Date().toLocaleTimeString()
      })
    } catch (err: any) {
      const errMsg = err.response?.data?.detail || 'AI 服务请求失败'
      error.value = errMsg
      messages.value.push({
        role: 'assistant',
        content: `请求失败: ${errMsg}`,
        timestamp: new Date().toLocaleTimeString()
      })
    } finally {
      loading.value = false
    }
  }

  const sendStreamMessage = async (question: string) => {
    // 添加用户消息
    messages.value.push({
      role: 'user',
      content: question,
      timestamp: new Date().toLocaleTimeString()
    })

    loading.value = true
    error.value = ''
    
    // 添加临时助手消息用于流式显示
    const assistantMessageIndex = messages.value.length
    messages.value.push({
      role: 'assistant',
      content: '',
      thinking: '',
      sources: [],
      has_context: false,
      isStreaming: true,
      timestamp: new Date().toLocaleTimeString()
    })

    let currentThinking = ''
    let currentAnswer = ''
    let currentSources: ChatSource[] = []
    let stepMessage = ''

    try {
      const eventSource = chatApi.chatStream(
        { question },
        (event: MessageEvent) => {
          try {
            const data = JSON.parse(event.data)
            
            switch (data.type) {
              case 'start':
                stepMessage = data.message || ''
                break
              
              case 'step':
                // 处理步骤更新 - 显示在 thinking 区域
                stepMessage = data.message || ''
                if (!currentThinking && !currentAnswer) {
                  messages.value[assistantMessageIndex].thinking = `⏳ ${stepMessage}`
                }
                break
              
              case 'thinking':
                // 流式思考内容更新
                currentThinking += data.content || ''
                messages.value[assistantMessageIndex].thinking = currentThinking
                break
              
              case 'answer':
                // 流式答案内容更新
                currentAnswer += data.content || ''
                messages.value[assistantMessageIndex].content = currentAnswer
                break
              
              case 'sources':
                // 源信息更新（包含所有来源、阈值和最高分）
                currentSources = data.sources || []
                messages.value[assistantMessageIndex].sources = currentSources
                messages.value[assistantMessageIndex].has_context = currentSources.some(
                  (s: ChatSource) => s.relevance_score >= (data.threshold || 0.75)
                )
                messages.value[assistantMessageIndex].threshold = data.threshold
                messages.value[assistantMessageIndex].maxScore = data.max_score
                break
              
              case 'error':
                // 错误处理
                error.value = data.message || '未知错误'
                messages.value[assistantMessageIndex].content = `❌ ${data.message}`
                messages.value[assistantMessageIndex].isStreaming = false
                eventSource.close()
                loading.value = false
                break
              
              case 'done':
                // 完成处理
                messages.value[assistantMessageIndex].isStreaming = false
                eventSource.close()
                loading.value = false
                break
            }
          } catch (parseError) {
            console.error('解析 SSE 数据失败:', parseError)
          }
        }
      )

      // 设置超时处理
      setTimeout(() => {
        if (eventSource.readyState !== EventSource.CLOSED) {
          eventSource.close()
          if (!currentAnswer) {
            messages.value[assistantMessageIndex].content = '⏰ 请求超时'
            messages.value[assistantMessageIndex].isStreaming = false
            error.value = '请求超时'
          }
          loading.value = false
        }
      }, 180000) // 3分钟超时

    } catch (err: any) {
      const errMsg = err.message || 'AI 服务请求失败'
      error.value = errMsg
      messages.value[assistantMessageIndex].content = `❌ 请求失败: ${errMsg}`
      messages.value[assistantMessageIndex].isStreaming = false
      loading.value = false
    }
  }

  const clearMessages = () => {
    messages.value = []
    error.value = ''
  }

  const fetchThreshold = async () => {
    try {
      const response = await settingsApi.getThreshold()
      threshold.value = response.data.threshold
      thresholdSource.value = response.data.source
    } catch (err) {
      console.error('获取阈值失败:', err)
    }
  }

  const updateThreshold = async (value: number) => {
    try {
      const response = await settingsApi.updateThreshold({ threshold: value })
      threshold.value = response.data.threshold
      thresholdSource.value = response.data.source
      return { success: true }
    } catch (err: any) {
      return {
        success: false,
        error: err.response?.data?.detail || '更新阈值失败'
      }
    }
  }

  return {
    messages,
    loading,
    error,
    threshold,
    thresholdSource,
    sendMessage,
    sendStreamMessage,
    clearMessages,
    fetchThreshold,
    updateThreshold
  }
})
