import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { documentApi, statsApi } from '@/api'
import type { Document, TaskStatus, Stats } from '@/types'

export const useDocumentStore = defineStore('document', () => {
  // State
  const documents = ref<Document[]>([])
  const total = ref(0)
  const stats = ref<Stats | null>(null)
  const loading = ref(false)
  const uploadProgress = ref<Record<string, number>>({})
  const taskStatuses = ref<Record<string, TaskStatus>>({})

  // Getters
  const completedDocs = computed(() => 
    documents.value.filter(d => d.status === 'completed')
  )
  
  const failedDocs = computed(() => 
    documents.value.filter(d => d.status === 'failed')
  )
  
  const processingDocs = computed(() => 
    documents.value.filter(d => d.status === 'processing' || d.status === 'pending')
  )

  // Actions
  const fetchDocuments = async (params?: { page?: number; page_size?: number; status?: string }) => {
    loading.value = true
    try {
      const response = await documentApi.getList(params)
      documents.value = response.data.documents
      total.value = response.data.total
    } finally {
      loading.value = false
    }
  }

  const fetchStats = async () => {
    try {
      const response = await statsApi.getStats()
      stats.value = response.data
    } catch (err) {
      console.error('获取统计信息失败:', err)
    }
  }

  const uploadDocument = async (file: File) => {
    const fileId = `${file.name}_${Date.now()}`
    uploadProgress.value[fileId] = 0
    
    try {
      const response = await documentApi.upload(file, (progress) => {
        uploadProgress.value[fileId] = progress
      })
      
      // 开始轮询任务状态
      const docId = response.data.doc_id
      pollTaskStatus(docId)
      
      return { success: true, docId }
    } catch (err: any) {
      return { 
        success: false, 
        error: err.response?.data?.detail || '上传失败' 
      }
    } finally {
      // 延迟清除进度
      setTimeout(() => {
        delete uploadProgress.value[fileId]
      }, 3000)
    }
  }

  const pollTaskStatus = async (docId: string) => {
    const poll = async () => {
      try {
        const response = await documentApi.getStatus(docId)
        const status = response.data
        taskStatuses.value[docId] = status
        
        // 如果还在处理中，继续轮询
        if (status.status === 'pending' || status.status === 'processing') {
          setTimeout(poll, 2000)
        } else {
          // 处理完成，刷新文档列表
          fetchDocuments()
          fetchStats()
        }
      } catch (err) {
        console.error('获取任务状态失败:', err)
      }
    }
    
    poll()
  }

  const deleteDocument = async (docId: string) => {
    try {
      await documentApi.delete(docId)
      // 从列表中移除
      documents.value = documents.value.filter(d => d.id !== docId)
      total.value--
      fetchStats()
      return { success: true }
    } catch (err: any) {
      return { 
        success: false, 
        error: err.response?.data?.detail || '删除失败' 
      }
    }
  }

  const getTaskStatus = (docId: string): TaskStatus | undefined => {
    return taskStatuses.value[docId]
  }

  return {
    documents,
    total,
    stats,
    loading,
    uploadProgress,
    taskStatuses,
    completedDocs,
    failedDocs,
    processingDocs,
    fetchDocuments,
    fetchStats,
    uploadDocument,
    deleteDocument,
    pollTaskStatus,
    getTaskStatus
  }
})
