import axios, { AxiosError, AxiosInstance } from 'axios'
import type { 
  Document, 
  DocumentListResponse, 
  TaskStatus, 
  Stats,
  LoginRequest,
  LoginResponse,
  ChatResponse,
  ThresholdResponse
} from '@/types'

// 创建 axios 实例
const api: AxiosInstance = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器 - 添加 token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器 - 处理错误
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Token 过期或无效，清除登录状态
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// 认证相关 API
export const authApi = {
  login: (data: LoginRequest) => 
    api.post<LoginResponse>('/auth/login', data),
  
  verify: () => 
    api.get<{ valid: boolean; username: string }>('/auth/verify')
}

// 文档相关 API
export const documentApi = {
  upload: (file: File, onProgress?: (progress: number) => void) => {
    const formData = new FormData()
    formData.append('file', file)
    
    return api.post('/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          onProgress(progress)
        }
      }
    })
  },
  
  getList: (params?: { page?: number; page_size?: number; status?: string }) =>
    api.get<DocumentListResponse>('/documents', { params }),
  
  getById: (docId: string) =>
    api.get<Document>(`/documents/${docId}`),
  
  getStatus: (docId: string) =>
    api.get<TaskStatus>(`/documents/${docId}/status`),
  
  delete: (docId: string) =>
    api.delete(`/documents/${docId}`)
}

// 统计相关 API
export const statsApi = {
  getStats: () =>
    api.get<Stats>('/stats'),
  
  getFormats: () =>
    api.get<{ supported_formats: string[]; max_file_size: number }>('/formats')
}

// 知识库对话 API
export const chatApi = {
  chat: (data: { question: string }) =>
    api.post<ChatResponse>('/chat', data),
  
  chatStream: (data: { question: string }, onMessage: (event: MessageEvent) => void) => {
    const token = localStorage.getItem('token')
    // 使用 GET 方式，通过 URL 参数传递 token 和问题
    const url = `/api/chat/stream?token=${token}&question=${encodeURIComponent(data.question)}`
    const eventSource = new EventSource(url)
    
    eventSource.onmessage = onMessage
    eventSource.onerror = (error: Event) => {
      console.error('SSE 连接错误:', error)
      eventSource.close()
    }
    
    return eventSource
  }
}

// 设置 API
export const settingsApi = {
  getThreshold: () =>
    api.get<ThresholdResponse>('/settings/threshold'),
  
  updateThreshold: (data: { threshold: number }) =>
    api.put<ThresholdResponse>('/settings/threshold', data)
}

export default api
