export interface Document {
  id: string
  file_name: string
  file_path: string
  file_size: number
  file_type: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  chunk_count: number
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface DocumentListResponse {
  total: number
  documents: Document[]
}

export interface TaskStatus {
  doc_id: string
  file_name: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress: number
  message: string
  chunk_count: number
  error_message: string | null
}

export interface Stats {
  total_chunks: number
  total_vectors: number
  total_documents: number
  collection_name: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_in: number
}

export interface ApiResponse<T = unknown> {
  status: string
  data?: T
  message?: string
}

export interface ChatSource {
  file_name: string
  relevance_score: number
  chunk_id: string
}

export interface ChatResponse {
  answer: string
  sources: ChatSource[]
  has_context: boolean
}

export interface ThresholdResponse {
  threshold: number
  source: string
}

// 流式聊天消息类型
export interface ChatStreamEvent {
  type: 'start' | 'step' | 'thinking' | 'answer' | 'sources' | 'error' | 'done'
  message?: string
  content?: string
  sources?: ChatSource[]
}
